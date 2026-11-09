"""Loop agêntico: planeja, age, confere e continua sozinho (lote 6, evolução do ReAct).

Ciclo: o modelo planeja (uma chamada ``ask`` por rodada, em lote com ``ACOES:`` ou no
formato antigo ``FERRAMENTA:``/``ARGS:``), o ``ActionExecutor`` executa cada ação pelo
Kernel (risco, aprovação, Central, cancelamento), uma leitura por regra confere as
escritas (``verification.py``) e o modelo decide a próxima rodada até ``FINISH``.

Orçamento (AQ5): ``max_steps`` ações executadas e ``max_model_calls`` chamadas ao modelo;
ao esgotar, a resposta é montada por regra, sem chamar o modelo de novo.
Aprovação (C8): uma etapa que pede aprovação registra um ponto de retomada em
``app.core.loop_checkpoints``; quem aprovar retoma a sequência no mesmo pedido.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from app.agent.action_executor import ActionExecutor
from app.agent.tool_guardrails import ToolCallGuardrailController
from app.agent.tools.base import ToolResult
from app.agent.verification import plan_verification
from app.core import loop_checkpoints
from app.core.actions import TERMINAL_STATUSES
from app.core.runs import RunCancelled, check_run_cancelled, current_origin, current_run
from app.core.waits import current_wait_reporter

# Ferramentas do modo "Execução por etapas" quando o chamador não informa a lista do turno.
REACT_TOOLS = frozenset({"web_search", "timer", "wait", "calendar", "planning_workspace", "whiteboard_add_text", "whiteboard_clear"})
MAX_BATCH = 5
_HISTORY_STEPS = 6
_OBS_CHARS = 200
_CONVERSATION_MESSAGES = 4
_CONVERSATION_CHARS = 300
_DESCRIPTION_CHARS = 160
WAITING_TEXT = "A etapa {n} precisa da sua aprovação na Central: {preview} Assim que você aprovar, eu continuo sozinho."


@dataclass
class ReActStep:
    step_number: int
    thought: str
    action_type: str  # "tool" | "gui" | "finish"
    tool_name: str = ""
    tool_args: dict[str, Any] = field(default_factory=dict)
    observation: str = ""
    verification_passed: bool = True
    self_correction_note: str = ""
    elapsed_ms: int = 0
    action_status: str = ""
    action_id: str | None = None
    # Verificação de efeito (effect_checks): "confirmed" | "unconfirmed" | "" e a evidência lida.
    effect_status: str = ""
    evidence: str = ""


@dataclass
class ReActTrajectory:
    goal: str
    success: bool
    final_output: str
    steps: list[ReActStep] = field(default_factory=list)
    total_elapsed_sec: float = 0.0
    pending_action_id: str | None = None
    model_calls: int = 0
    max_steps: int = 0
    max_model_calls: int = 0
    # finish | limit_steps | limit_calls | waiting_approval | rejected | cancelled | invalid_plan
    stopped_reason: str = ""

    @property
    def action_steps(self) -> list[ReActStep]:
        return [step for step in self.steps if step.action_type == "tool"]


@dataclass
class _LoopState:
    goal: str
    context: dict[str, Any]
    executor: ActionExecutor
    allowed: frozenset[str]
    trajectory: ReActTrajectory
    verify: bool
    progress: Callable[[dict[str, Any]], None] | None
    save_reply: Callable[[str, ReActTrajectory], None] | None
    step_callback: Callable[[ReActStep], None] | None
    conversation: list[dict[str, Any]]
    origin: str
    start_time: float
    history: list[str] = field(default_factory=list)
    queue: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    results: dict[str, ToolResult] = field(default_factory=dict)
    paused_step: ReActStep | None = None


def _result_key(name: str, args: dict[str, Any] | None) -> str:
    try:
        return name + ":" + json.dumps(args or {}, sort_keys=True, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return name + ":" + repr(args)


def _short(text: Any, limit: int) -> str:
    value = " ".join(str(text or "").split())
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _compact_schema(parameters: Any) -> dict[str, str]:
    """Esquema reduzido: nome do parâmetro → tipo (com enum e campos de itens)."""
    props = parameters.get("properties") if isinstance(parameters, dict) else None
    if not isinstance(props, dict):
        return {}
    compact: dict[str, str] = {}
    for name, spec in props.items():
        if not isinstance(spec, dict):
            continue
        kind = str(spec.get("type") or "any")
        if isinstance(spec.get("enum"), list):
            kind += " (" + "|".join(str(item) for item in spec["enum"]) + ")"
        items = spec.get("items")
        if kind.startswith("array") and isinstance(items, dict):
            inner = items.get("properties")
            kind += "<{" + ",".join(inner) + "}>" if isinstance(inner, dict) else "<" + str(items.get("type") or "any") + ">"
        compact[name] = kind
    return compact


class ReActLoopEngine:
    """Motor do loop agêntico com verificação e retomada após aprovação."""

    def __init__(
        self,
        llm_service: Any = None,
        registry: Any = None,
        vision_service: Any = None,
        *,
        allowed_tools: frozenset[str] | None = None,
        budget: dict[str, int] | None = None,
        progress: Callable[[dict[str, Any]], None] | None = None,
        verify: bool = True,
    ) -> None:
        self.llm_service = llm_service
        self.registry = registry
        self.vision_service = vision_service
        self.allowed_tools = allowed_tools
        self.budget = dict(budget or {})
        self.progress = progress
        self.verify = verify

    # ------------------------------------------------------------------ entrada
    def run_loop(
        self,
        goal: str,
        max_steps: int | None = None,
        context: dict[str, Any] | None = None,
        step_callback: Callable[[ReActStep], None] | None = None,
        *,
        allowed_tools: frozenset[str] | None = None,
        max_model_calls: int | None = None,
        progress: Callable[[dict[str, Any]], None] | None = None,
        verify: bool | None = None,
        history: list[dict[str, Any]] | None = None,
        save_reply: Callable[[str, ReActTrajectory], None] | None = None,
    ) -> ReActTrajectory:
        """Executa o loop até FINISH, limite, cancelamento ou etapa aguardando aprovação."""
        start_time = time.time()
        context = context or {}
        trajectory = ReActTrajectory(goal=goal, success=False, final_output="")
        if not self.llm_service:
            trajectory.final_output = "ReAct indisponível: configure um provedor de IA. Nenhuma ferramenta foi executada."
            return trajectory
        max_steps = self.budget.get("max_steps", 8) if max_steps is None else max_steps
        max_model_calls = self.budget.get("max_model_calls", 10) if max_model_calls is None else max_model_calls
        if type(max_steps) is not int or not 1 <= max_steps <= 20:
            raise ValueError("O limite de etapas deve estar entre 1 e 20.")
        if type(max_model_calls) is not int or not 1 <= max_model_calls <= 30:
            raise ValueError("O limite de chamadas ao modelo deve estar entre 1 e 30.")
        trajectory.max_steps, trajectory.max_model_calls = max_steps, max_model_calls

        requested = allowed_tools if allowed_tools is not None else self.allowed_tools
        registered = frozenset(self.registry.tools) if self.registry else frozenset()
        allowed = frozenset(requested if requested is not None else REACT_TOOLS).intersection(registered)
        state_holder: dict[str, _LoopState] = {}

        def execute(name: str, args: dict, _user: str) -> ToolResult:
            if not self.registry:
                return ToolResult(False, "O registro de ferramentas não está disponível.")
            result = self.registry.execute_tool(name, args, context=context)
            state = state_holder.get("state")
            if state is not None and isinstance(result, ToolResult):
                state.results[_result_key(name, args)] = result
            return result

        executor = ActionExecutor(
            allowed, ToolCallGuardrailController(), execute,
            metadata_for=self.registry.get_tool_metadata if self.registry else None,
            source=f"react:{context.get('session_id') or 'default'}",
        )
        state = _LoopState(
            goal=goal, context=context, executor=executor, allowed=allowed, trajectory=trajectory,
            verify=self.verify if verify is None else bool(verify),
            progress=progress if progress is not None else self.progress,
            save_reply=save_reply, step_callback=step_callback,
            conversation=list(history or [])[-_CONVERSATION_MESSAGES:],
            origin=current_origin.get(), start_time=start_time,
        )
        state_holder["state"] = state
        self._drive(state)
        trajectory.total_elapsed_sec = round(time.time() - start_time, 2)
        return trajectory

    # ------------------------------------------------------------------ ciclo
    def _drive(self, state: _LoopState) -> None:
        """Roda até um motivo de parada; ``waiting_approval`` deixa um ponto de retomada."""
        t = state.trajectory
        while True:
            check_run_cancelled()
            if state.queue:
                if len(t.action_steps) >= t.max_steps:
                    return self._stop_by_limit(state, "limit_steps")
                name, args = state.queue.pop(0)
                if self._act(state, name, args):
                    return
                continue
            if len(t.action_steps) >= t.max_steps:
                return self._stop_by_limit(state, "limit_steps")
            if t.model_calls >= t.max_model_calls:
                return self._stop_by_limit(state, "limit_calls")
            self._emit(state, "planning", "Planejando a próxima etapa.")
            try:
                t.model_calls += 1
                decision, payload = self._plan_step(state)
            except RunCancelled:
                raise
            except Exception:
                t.stopped_reason = "invalid_plan"
                t.success = False
                t.final_output = "O planejamento ReAct falhou ou retornou uma ação inválida. Consulte as etapas na Central."
                self._emit(state, "done", "Planejamento inválido; nada mais foi executado.")
                return
            check_run_cancelled()
            if decision == "finish":
                return self._finish(state, payload)
            state.queue.extend(payload)

    def _act(self, state: _LoopState, name: str, args: dict[str, Any]) -> bool:
        """Executa uma ação; devolve ``True`` quando a sequência parou aguardando aprovação."""
        t = state.trajectory
        started = time.time()
        step = ReActStep(step_number=len(t.steps) + 1, thought="Executando ação planejada", action_type="tool", tool_name=name, tool_args=args)
        t.steps.append(step)
        self._emit(state, "acting", f"Executando {name}.")

        def report_wait(remaining: int, total: int) -> None:
            # Contador visível da espera (chat e Central); a fase "waiting" não fecha o contador.
            self._emit(state, "waiting", f"Aguardando {remaining} s de {total}.", extra={"wait_remaining": remaining, "wait_total": total})

        wait_token = current_wait_reporter.set(report_wait)
        try:
            observation = state.executor.execute(name, args, state.goal)
        except RunCancelled:
            raise
        except Exception:
            observation = "A ferramenta falhou; conclusão não confirmada. Consulte a Central."
        finally:
            current_wait_reporter.reset(wait_token)
        action = state.executor.last_action
        step.observation = observation
        step.action_id = action.id if action else None
        step.action_status = action.status if action else "blocked"
        step.elapsed_ms = int((time.time() - started) * 1000)
        check_run_cancelled()
        if action and action.status == "awaiting_confirmation":
            step.verification_passed = False
            return self._pause(state, step, action)
        self._after_action(state, step)
        return False

    def _after_action(self, state: _LoopState, step: ReActStep) -> None:
        success = step.action_status == "succeeded"
        passed, note = self._verify_and_correct(state.goal, step.tool_name, step.observation, success)
        step.verification_passed, step.self_correction_note = passed, note
        if success and state.verify:
            verified, verify_note = self._run_verification(state, step)
            if not verified:
                step.verification_passed = False
                step.self_correction_note = verify_note
        if success:
            result = state.results.get(_result_key(step.tool_name, step.tool_args))
            effect = (result.data or {}).get("effect") if result is not None and isinstance(result.data, dict) else None
            if isinstance(effect, dict) and effect.get("status") in {"confirmed", "unconfirmed"}:
                step.effect_status, step.evidence = effect["status"], str(effect.get("evidence") or "")
                if step.effect_status == "unconfirmed":
                    step.verification_passed = False
                    step.self_correction_note = f"Abri, mas não consegui confirmar: {step.evidence}."
        if state.step_callback:
            state.step_callback(step)
        summary = (
            f"Etapa {step.step_number}: {step.tool_name} {json.dumps(step.tool_args, ensure_ascii=False, default=str)[:160]} -> "
            f"{'SUCESSO' if step.verification_passed else 'FALHA'}. Obs: {_short(step.observation, _OBS_CHARS)}"
        )
        if step.self_correction_note:
            summary += f" | Nota: {step.self_correction_note}"
        state.history.append(summary)

    def _run_verification(self, state: _LoopState, step: ReActStep) -> tuple[bool, str]:
        """Relê o dado escrito pela ferramenta de leitura (observe) no mesmo pedido."""
        result = state.results.get(_result_key(step.tool_name, step.tool_args))
        plan = plan_verification(step.tool_name, step.tool_args, result)
        if plan is None or plan.tool not in state.allowed:
            return True, ""
        metadata = self.registry.get_tool_metadata(plan.tool) if self.registry else None
        if metadata is None or metadata.risk_for(plan.args) != "observe":
            return True, ""
        self._emit(state, "verifying", f"Conferindo {plan.label}.")
        try:
            state.executor.execute(plan.tool, plan.args, state.goal)
        except RunCancelled:
            raise
        except Exception:
            return False, "verificação: a leitura de conferência falhou."
        action = state.executor.last_action
        read = state.results.get(_result_key(plan.tool, plan.args))
        if not action or action.status != "succeeded" or read is None:
            return False, "verificação: a leitura de conferência não foi concluída."
        try:
            return plan.check(read)
        except Exception:
            return False, "verificação: não foi possível comparar a leitura."

    # ------------------------------------------------------------------ aprovação
    def _pause(self, state: _LoopState, step: ReActStep, action: Any) -> bool:
        t = state.trajectory
        store, run_id = state.executor.store, state.executor.run_id
        state.paused_step = step
        # Pendência antes do registro: quem retomar sempre encontra o pedido aberto.
        if run_id:
            store.set_resume_pending(run_id, True)
        loop_checkpoints.register(action.id, loop_checkpoints.LoopCheckpoint(
            action_id=action.id, run_id=run_id or "", session_id=state.context.get("session_id"),
            resume=lambda final_status: self._resume(state, action.id, final_status),
            abandon=lambda reason: self._abandon(state, action.id, reason),
        ))
        self._emit(state, "waiting_approval", f"Etapa {step.step_number} aguardando aprovação na Central.")
        current = store.get(action.id)
        # Aprovação que chegou durante o turno: continua aqui, uma vez só (``take`` é atômico).
        if current is not None and current.status in TERMINAL_STATUSES and loop_checkpoints.take(action.id) is not None:
            if run_id:
                store.set_resume_pending(run_id, False)
            self._absorb_paused(state, current)
            return False
        t.pending_action_id = action.id
        t.stopped_reason = "waiting_approval"
        t.success = False
        t.final_output = WAITING_TEXT.format(n=step.step_number, preview=_short(action.preview, 200))
        return True

    def _absorb_paused(self, state: _LoopState, action: Any) -> None:
        step = state.paused_step
        state.paused_step = None
        state.trajectory.pending_action_id = None
        if step is None:
            return
        step.action_status = getattr(action, "status", "") or "failed"
        if getattr(action, "result_summary", None):
            step.observation = action.result_summary
        self._after_action(state, step)

    def _with_run_context(self, state: _LoopState, body: Callable[[], None]) -> None:
        store, run_id = state.executor.store, state.executor.run_id
        run_token = current_run.set((store, run_id)) if run_id else None
        origin_token = current_origin.set(state.origin)
        # A retomada abre o próprio coletor de popups (lote 6); eles chegam pelo barramento.
        from app.core import ui_events
        popup_tokens = [
            (ui_events.current_popups, ui_events.current_popups.set([])),
            (ui_events.current_popup_session, ui_events.current_popup_session.set(state.context.get("session_id"))),
            (ui_events.current_popup_listener, ui_events.current_popup_listener.set(None)),
        ]
        try:
            body()
        finally:
            for var, token in reversed(popup_tokens):
                var.reset(token)
            current_origin.reset(origin_token)
            if run_token is not None:
                current_run.reset(run_token)

    def _resume(self, state: _LoopState, action_id: str, _final_status: str) -> None:
        """Continuação depois da aprovação, no mesmo pedido (chamada por quem aprovou)."""
        t = state.trajectory

        def body() -> None:
            t.stopped_reason, t.final_output = "", ""
            try:
                check_run_cancelled()
                self._emit(state, "resumed", "Aprovação recebida; continuando a sequência.")
                self._absorb_paused(state, state.executor.store.get(action_id))
                self._drive(state)
            except RunCancelled:
                t.stopped_reason, t.success = "cancelled", False
                t.final_output = "Pedido cancelado. Etapas já executadas não foram desfeitas."
            except Exception:
                t.stopped_reason, t.success = "invalid_plan", False
                t.final_output = "A continuação falhou depois da aprovação. Consulte as etapas na Central."
            if t.stopped_reason != "waiting_approval":
                self._complete_resume(state)

        self._with_run_context(state, body)

    def _abandon(self, state: _LoopState, action_id: str, reason: str) -> None:
        """Etapa recusada ou expirada: encerra sem nova chamada ao modelo."""
        t = state.trajectory

        def body() -> None:
            action = state.executor.store.get(action_id)
            step = state.paused_step
            state.paused_step = None
            if step is not None:
                step.action_status = getattr(action, "status", "") or "cancelled"
                step.observation = getattr(action, "result_summary", None) or step.observation
                step.verification_passed = False
            t.pending_action_id = None
            t.stopped_reason, t.success = "rejected", False
            t.final_output = self._rule_summary(state, reason)
            self._complete_resume(state)

        self._with_run_context(state, body)

    def _complete_resume(self, state: _LoopState) -> None:
        t = state.trajectory
        t.total_elapsed_sec = round(time.time() - state.start_time, 2)
        cancelled = t.stopped_reason == "cancelled"
        self._emit(state, "cancelled" if cancelled else "done", _short(t.final_output, 160))
        if state.save_reply and not cancelled:
            try:
                state.save_reply(t.final_output, t)
            except Exception:
                pass
        run_id = state.executor.run_id
        if run_id:
            try:
                state.executor.store.finish_resume(run_id, failed=not t.success and t.stopped_reason not in {"cancelled", "rejected"}, reply=t.final_output)
            except Exception:
                pass

    # ------------------------------------------------------------------ encerramento
    def _finish(self, state: _LoopState, text: str) -> None:
        t = state.trajectory
        t.steps.append(ReActStep(
            step_number=len(t.steps) + 1, thought="Planejamento encerrado", action_type="finish",
            tool_args={"response": text},
            observation="O modelo encerrou o planejamento. Os resultados das ferramentas estão na Central.",
        ))
        failed = self._unresolved_failure(state)
        t.success = failed is None
        t.stopped_reason = "finish"
        if failed:
            t.final_output = f"Execução encerrada com falha na etapa {failed.step_number}. {failed.observation}"
        elif any(s.action_status == "succeeded" and s.effect_status == "unconfirmed" for s in t.action_steps):
            # Sem evidência, o texto do modelo ("Pronto, tocando!") não vale: a resposta sai por regra.
            t.final_output = self._evidence_summary(state)
        else:
            unverified = [s for s in t.action_steps if s.action_status == "succeeded" and not s.verification_passed and s.self_correction_note]
            t.final_output = text
            if unverified:
                t.final_output += "\n\nAtenção: " + " ".join(f"etapa {s.step_number}: {s.self_correction_note}" for s in unverified)
            confirmed = [s for s in t.action_steps if s.action_status == "succeeded" and s.effect_status == "confirmed"]
            if confirmed:
                t.final_output += "\n\nConfirmado: " + "; ".join(f"etapa {s.step_number}: {s.evidence}" for s in confirmed) + "."
        if state.step_callback:
            state.step_callback(t.steps[-1])
        self._emit(state, "done", "Sequência concluída.")

    def _unresolved_failure(self, state: _LoopState) -> ReActStep | None:
        """Primeira etapa com falha que nenhuma etapa posterior corrigiu (mesma ferramenta e mesmo alvo).

        Vale o status da ação no Kernel. Sem alvo declarado, a ferramenta sozinha identifica a etapa.
        """
        steps = state.trajectory.action_steps

        def identity(step: ReActStep) -> tuple[str, str]:
            metadata = self.registry.get_tool_metadata(step.tool_name) if self.registry else None
            return step.tool_name, (metadata.target_for(step.tool_args).lower() if metadata else "")

        for index, step in enumerate(steps):
            if step.action_status == "succeeded":
                continue
            key = identity(step)
            if not any(later.action_status == "succeeded" and identity(later) == key for later in steps[index + 1:]):
                return step
        return None

    def _evidence_summary(self, state: _LoopState) -> str:
        """Resposta por regra quando algum efeito não foi confirmado: cada etapa com o que foi visto."""
        lines = []
        for step in state.trajectory.action_steps:
            if step.action_status != "succeeded":
                continue
            if step.effect_status == "confirmed":
                lines.append(f"Etapa {step.step_number} ({step.tool_name}): confirmado, {step.evidence}.")
            elif step.effect_status == "unconfirmed":
                lines.append(f"Etapa {step.step_number} ({step.tool_name}): abri, mas não consegui confirmar: {step.evidence}.")
            else:
                head = _short(step.observation, 120)
                lines.append(f"Etapa {step.step_number} ({step.tool_name}): {head}")
        return "Fiz as etapas, mas não consegui confirmar todas. Confira na tela:\n" + "\n".join(lines)

    def _stop_by_limit(self, state: _LoopState, reason: str) -> None:
        t = state.trajectory
        t.stopped_reason = reason
        t.success = all(s.action_status == "succeeded" for s in t.action_steps)
        tail = (f"Parei no limite de {t.max_steps} etapa(s)." if reason == "limit_steps"
                else f"Parei no limite de {t.max_model_calls} chamada(s) ao modelo.")
        t.final_output = self._rule_summary(state, tail)
        self._emit(state, "limit", tail)

    def _rule_summary(self, state: _LoopState, tail: str) -> str:
        """Resposta montada por regra (sem modelo) com o que foi feito."""
        t = state.trajectory
        steps = t.action_steps
        done = [s for s in steps if s.action_status == "succeeded"]
        total = len(steps) + len(state.queue)
        parts = "; ".join(f"{s.tool_name}: {_short(s.observation, 80)}" for s in done[:8])
        head = f"Fiz {len(done)} de {total} etapa(s)" + (f": {parts}" if parts else "") + "."
        return f"{head} {tail} Confira na Central."

    def _emit(self, state: _LoopState, phase: str, summary: str = "", *, extra: dict[str, Any] | None = None) -> None:
        if not state.progress:
            return
        t = state.trajectory
        try:
            state.progress({
                "phase": phase, "step": len(t.action_steps), "max_steps": t.max_steps,
                "model_calls": t.model_calls, "max_model_calls": t.max_model_calls, "summary": summary[:200],
                **(extra or {}),
            })
        except Exception:
            pass

    # ------------------------------------------------------------------ modelo
    def _gather_observation(self, context: dict[str, Any]) -> str:
        obs = ["Ambiente Desktop Windows Ativo."]
        if self.vision_service and context.get("capture_screen", False):
            try:
                res = self.vision_service.analyze("Descreva brevemente o estado atual da tela.")
                obs.append(f"Visão de Tela: {res.get('reply', '')[:200]}")
            except Exception as e:
                obs.append(f"Visão de Tela indisponível: {e}")
        if context.get("situational"):
            obs.append(str(context["situational"]))
        return "\n".join(obs)

    def _tool_lines(self, state: _LoopState) -> str:
        lines = []
        for name in sorted(state.allowed):
            tool = self.registry.tools.get(name) if self.registry else None
            description = _short(getattr(tool, "description", "") or "", _DESCRIPTION_CHARS)
            schema = _compact_schema(getattr(tool, "parameters", {}))
            lines.append(json.dumps({"nome": name, "descricao": description, "parametros": schema}, ensure_ascii=False))
        return "\n".join(lines) or "Nenhuma ferramenta disponível neste modo."

    @staticmethod
    def _wait_rules(state: _LoopState) -> str:
        if "wait" not in state.allowed:
            return ""
        return (
            'Para esperar entre ações use wait {"seconds": N} no mesmo lote, na ordem pedida (ex.: abrir, wait, abrir); '
            "timer só agenda um bipe e NÃO pausa. Espera maior que 1 hora ou pedido com horário/repetição: "
            "não use wait; crie uma rotina (ferramenta routine).\n"
        )

    def _build_prompt(self, state: _LoopState) -> str:
        t = state.trajectory
        history = "\n".join(state.history[-_HISTORY_STEPS:]) or "Nenhuma ação anterior."
        conversation = "\n".join(
            f"{'Usuária' if item.get('role') == 'user' else 'Assistente'}: {_short(item.get('content'), _CONVERSATION_CHARS)}"
            for item in state.conversation if isinstance(item, dict) and item.get("content")
        ) or "Sem mensagens anteriores."

        try:
            from app.agent.personas import get_persona, VALID_TONES
            p = get_persona()
            p_name = p.get("name", "Jarvis")
            p_tone = p.get("tone", "amigável")
            tone_desc = VALID_TONES.get(p_tone, "")
            persona_intro = f"Você é {p_name}, um assistente com tom {p_tone} ({tone_desc}) que executa pedidos com ferramentas controladas pela Central.\n"
            if p.get("custom_rules"):
                persona_intro += f"Regras da persona: {p['custom_rules']}\n"
        except Exception:
            persona_intro = "Você é um agente que executa pedidos com ferramentas controladas pela Central.\n"

        return (
            persona_intro +
            f"Objetivo: {state.goal}\n\n"
            f"Conversa recente:\n{conversation}\n\n"
            f"Etapas já feitas:\n{history}\n\n"
            f"Observação atual:\n{self._gather_observation(state.context)}\n\n"
            f"Ferramentas permitidas (nome, descrição, parâmetros):\n{self._tool_lines(state)}\n\n"
            f"Orçamento: {len(t.action_steps)} de {t.max_steps} etapas usadas; chamada {t.model_calls} de {t.max_model_calls} ao modelo.\n"
            "Regras: números e fatos só das observações; prefira operações em lote (create_many, add_many, check_many); "
            "não repita uma ação que já deu certo; termine com FINISH quando tudo estiver feito e verificado.\n"
            f"{self._wait_rules(state)}"
            "Só diga que abriu ou tocou algo se a observação disser 'Confirmado'; se disser 'não consegui confirmar', diga isso.\n\n"
            "Responda em UM destes formatos:\n"
            "FINISH: <resposta final em português para a usuária>\n"
            f'ACOES: [{{"ferramenta": "<nome>", "args": {{...}}}}]  (1 a {MAX_BATCH} ações, executadas em ordem)\n'
            "FERRAMENTA: <nome_da_tool>\nARGS: <objeto JSON>\n"
        )

    def _plan_step(self, state: _LoopState) -> tuple[str, Any]:
        """Lê o plano; argumentos malformados nunca viram execução."""
        raw = self.llm_service.ask(self._build_prompt(state))
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("Resposta de planejamento vazia.")
        return parse_plan(raw)

    def _verify_and_correct(self, goal: str, action_name: str, obs_result: str, action_success: bool) -> tuple[bool, str]:
        # Vale o status da ação no Kernel; o texto da observação nunca decide (um resumo pode citar "erro" sem ser falha).
        if not action_success:
            return False, f"Ação {action_name} falhou. Ajustando parâmetros ou alternando estratégia."
        return True, ""


def parse_plan(raw: str) -> tuple[str, Any]:
    """``("finish", texto)`` ou ``("actions", [(nome, args), ...])``; formato inválido levanta ``ValueError``."""
    cleaned = "\n".join(line for line in raw.strip().splitlines() if not line.strip().startswith("```"))
    lines = cleaned.strip().splitlines()
    finishes = [i for i, line in enumerate(lines) if line.startswith("FINISH:")]
    tools = [line.removeprefix("FERRAMENTA:").strip() for line in lines if line.startswith("FERRAMENTA:")]
    batches = [i for i, line in enumerate(lines) if line.startswith("ACOES:") or line.startswith("AÇÕES:")]
    if len(finishes) == 1 and not tools and not batches:
        final = "\n".join(lines[finishes[0]:]).removeprefix("FINISH:").strip()
        if final:
            return "finish", final
        raise ValueError("Resposta final vazia.")
    if batches:
        if len(batches) != 1 or finishes or tools:
            raise ValueError("Plano em lote inválido.")
        text = "\n".join(lines[batches[0]:]).split(":", 1)[1].strip()
        items, _end = json.JSONDecoder().raw_decode(text)
        if not isinstance(items, list) or not 1 <= len(items) <= MAX_BATCH:
            raise ValueError(f"O lote deve ter de 1 a {MAX_BATCH} ações.")
        actions = []
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("ferramenta"), str) or not item["ferramenta"].strip() or not isinstance(item.get("args"), dict):
                raise ValueError("Cada ação do lote precisa de 'ferramenta' e 'args' (objeto).")
            actions.append((item["ferramenta"].strip(), item["args"]))
        return "actions", actions
    if finishes or len(tools) != 1 or not tools[0] or sum(line.startswith("ARGS:") for line in lines) != 1:
        raise ValueError("Ação de planejamento inválida.")
    args = json.loads(cleaned.split("ARGS:", 1)[1].strip())
    if not isinstance(args, dict):
        raise ValueError("Os argumentos da ferramenta devem ser um objeto.")
    return "actions", [(tools[0], args)]
