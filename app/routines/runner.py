"""Executa uma rotina: um Run de origem ``routine`` na Central e cada etapa pelo Action Kernel.

Risco, aprovações, regras de auto-aprovação e Modo liberado valem como em qualquer pedido, porque
cada etapa é um ``ActionExecutor.execute``. Etapa que pede aprovação PAUSA a rotina com o mesmo
ponto de retomada do loop agêntico (``app.core.loop_checkpoints``): aprovar continua da etapa
seguinte; recusar ou deixar expirar encerra a rotina como falha, qualquer que seja o ``on_failure``.

A espera ``delay_before`` usa o laço único de ``app.core.waits`` (cancela com "Parar pedido").
``spawn`` roda a execução em segundo plano; os testes trocam por execução síncrona.
"""
from __future__ import annotations

import contextvars
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from typing import Any, Callable

from app.agent.action_executor import ActionExecutor
from app.agent.tool_guardrails import ToolCallGuardrailController
from app.agent.tools.base import ToolResult
from app.core import loop_checkpoints, ui_events, waits
from app.core.actions import TERMINAL_STATUSES
from app.core.runs import RUN_TERMINAL, RunCancelled, check_run_cancelled, current_run
from app.routines.models import operation_spec, step_arguments
from app.storage import action_store as action_store_module
from app.storage import routine_store as routine_store_module

TRIGGER_LABELS = {
    "manual": "executar agora", "schedule": "horário", "catch_up": "recuperação após o PC ligar",
    "voice": "frase de voz", "command": "comando", "agent": "pedido ao agente",
}
STATUS_LABELS = {
    "succeeded": "concluída", "failed": "com falha", "cancelled": "cancelada", "paused": "aguardando aprovação",
    "skipped": "pulada", "missed": "perdida", "interrupted": "interrompida", "running": "em execução",
}
RETRY_PAUSE_SECONDS = 2
APPROVAL_MINUTES = 10


class RoutineBusy(RuntimeError):
    """A rotina já está em execução."""


def _short(text: Any, limit: int = 90) -> str:
    value = " ".join(str(text or "").split())
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _thread_spawn(fn: Callable[[], None]) -> None:
    threading.Thread(target=fn, daemon=True, name="routine-run").start()


@dataclass
class _Execution:
    routine: dict[str, Any]
    entry_id: str
    run_id: str
    store: Any
    trigger_kind: str
    guardrails: ToolCallGuardrailController = field(default_factory=lambda: ToolCallGuardrailController(exact_repeat_limit=6))
    index: int = 0
    attempt: int = 0
    paused_action: str | None = None
    turn_closed: bool = False
    failures: int = 0
    lines: list[str] = field(default_factory=list)
    finished: bool = False

    @property
    def name(self) -> str:
        return str(self.routine.get("name") or "")

    @property
    def steps(self) -> list[dict[str, Any]]:
        return list(self.routine.get("steps") or [])


class RoutineRunner:
    def __init__(self, registry: Any = None, spawn: Callable[[Callable[[], None]], None] | None = None) -> None:
        self.registry = registry
        self.spawn = spawn or _thread_spawn
        self._active: dict[str, _Execution] = {}
        self._lock = threading.Lock()

    # ── dependências resolvidas na hora (os testes trocam os módulos) ──────────
    def _registry(self) -> Any:
        if self.registry is not None:
            return self.registry
        from app.agent.tools.registry import registry
        return registry

    @staticmethod
    def _routines() -> Any:
        return routine_store_module.routine_store

    def is_running(self, routine_id: str) -> bool:
        with self._lock:
            return routine_id in self._active

    def active(self) -> list[_Execution]:
        with self._lock:
            return list(self._active.values())

    # ── início ─────────────────────────────────────────────────────────────────
    def start(self, routine: dict[str, Any], trigger_kind: str, scheduled_for: float | None = None) -> str | None:
        """Cria o Run e começa em segundo plano; devolve o id do Run (None se já estava rodando)."""
        routine_id = routine["id"]
        rstore = self._routines()
        with self._lock:
            if routine_id in self._active:
                rstore.add_run(routine_id, trigger_kind, status="skipped", scheduled_for=scheduled_for,
                               summary="Ainda em execução; este disparo foi ignorado.")
                return None
            store = action_store_module.action_store
            run = store.create_run(session_id=f"routine:{routine_id}", mode="routine", source=f"routine:{routine_id}", origin="routine")
            entry = rstore.add_run(routine_id, trigger_kind, run_id=run.id, scheduled_for=scheduled_for, summary="Em execução.")
            execution = _Execution(routine=routine, entry_id=entry["id"], run_id=run.id, store=store, trigger_kind=trigger_kind)
            self._active[routine_id] = execution
        rstore.set_last(routine_id, last_run_at=time.time(), last_status="running", last_run_id=run.id, last_summary="Em execução.")
        label = TRIGGER_LABELS.get(trigger_kind, trigger_kind)
        self._event(execution, f'Rotina "{execution.name}" iniciada (gatilho: {label}).')
        self._publish(execution, "start", "running")
        self.spawn(lambda: self._in_context(execution, lambda: self._advance(execution)))
        return run.id

    # ── execução ───────────────────────────────────────────────────────────────
    def _in_context(self, execution: _Execution, body: Callable[[], None]) -> None:
        token = current_run.set((execution.store, execution.run_id))
        popups_token = ui_events.current_popups.set(None)
        try:
            body()
        except RunCancelled:
            self._finish(execution, "cancelled", f'Rotina "{execution.name}" cancelada. Etapas já executadas não foram desfeitas.')
        except Exception:
            self._finish(execution, "failed", f'Rotina "{execution.name}" falhou por um erro interno. Consulte as etapas na Central.')
        finally:
            ui_events.current_popups.reset(popups_token)
            current_run.reset(token)

    def _advance(self, execution: _Execution) -> None:
        steps = execution.steps
        while execution.index < len(steps):
            step = steps[execution.index]
            check_run_cancelled()
            delay = RETRY_PAUSE_SECONDS if execution.attempt > 0 else int(step.get("delay_before") or 0)
            if delay:
                self._wait(execution, delay)
            action, message = self._execute_step(execution, step)
            if action is not None and action.status == "awaiting_confirmation":
                if self._pause(execution, action):
                    return
                action = execution.store.get(action.id) or action
            status = action.status if action is not None else "failed"
            if not self._settle(execution, step, status, message or (getattr(action, "result_summary", "") or "")):
                return
        self._complete(execution)

    def _wait(self, execution: _Execution, seconds: int) -> None:
        total_steps = len(execution.steps)

        def report(remaining: int, total: int) -> None:
            event = {"phase": "waiting", "step": execution.index + 1, "max_steps": total_steps,
                     "wait_remaining": remaining, "wait_total": total}
            try:
                execution.store.update_run_progress(execution.run_id, event)
            except Exception:
                pass
            ui_events.publish({"type": "routine_progress", "routine_id": execution.routine["id"], "run_id": execution.run_id, **event})

        token = waits.current_wait_reporter.set(report)
        try:
            waits.wait_seconds(seconds, label=f"rotina {execution.name}")
        finally:
            waits.current_wait_reporter.reset(token)

    def _execute_step(self, execution: _Execution, step: dict[str, Any]) -> tuple[Any, str]:
        registry = self._registry()
        tool_name = step["tool"]
        tool = registry.get_tool(tool_name)
        argument = operation_spec(tool, registry.get_tool_metadata(tool_name))[0] if tool is not None else None
        args = step_arguments(step, argument)
        timeout = step.get("timeout")

        def legacy(name: str, call_args: dict, _user: str) -> ToolResult:
            return self._call(registry, name, call_args, timeout)

        executor = ActionExecutor(
            frozenset({tool_name}), execution.guardrails, legacy,
            metadata_for=registry.get_tool_metadata, store=execution.store, source=f"routine:{execution.routine['id']}",
        )
        message = executor.execute(tool_name, args, f"Rotina {execution.name}, etapa {execution.index + 1}")
        return executor.last_action, message

    @staticmethod
    def _call(registry: Any, name: str, args: dict, timeout: int | None) -> ToolResult:
        if not timeout:
            return registry.execute_tool(name, args, context=None)
        # A thread da ferramenta não é morta ao estourar o tempo (limite aceito e registrado).
        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="routine-step")
        future = pool.submit(contextvars.copy_context().run, registry.execute_tool, name, args, None)
        try:
            return future.result(timeout=timeout)
        except FutureTimeout:
            return ToolResult(False, f"Tempo esgotado ({timeout} s); a ferramenta pode continuar rodando.")
        finally:
            pool.shutdown(wait=False)

    def _settle(self, execution: _Execution, step: dict[str, Any], status: str, message: str) -> bool:
        """Aplica o resultado da etapa; False quando a rotina foi encerrada aqui."""
        number, label = execution.index + 1, step.get("label") or step["tool"]
        if status == "succeeded":
            execution.lines.append(f"{number}. {label}: {_short(message)}")
            execution.index, execution.attempt = execution.index + 1, 0
            return True
        if step.get("on_failure") == "retry" and execution.attempt < int(step.get("retries") or 0):
            execution.attempt += 1
            self._event(execution, f"Etapa {number} falhou; tentando de novo ({execution.attempt}/{step.get('retries')}).")
            return True
        execution.failures += 1
        execution.lines.append(f"{number}. {label}: falhou ({_short(message)})")
        if step.get("on_failure") == "continue":
            self._event(execution, f"Etapa {number} falhou; a rotina continua (se falhar: continuar).")
            execution.index, execution.attempt = execution.index + 1, 0
            return True
        self._finish(execution, "failed", f'Rotina "{execution.name}" parou na etapa {number} ({label}).')
        return False

    def _complete(self, execution: _Execution) -> None:
        total = len(execution.steps)
        if execution.failures:
            headline = f'Rotina "{execution.name}" concluída com {execution.failures} etapa(s) com falha de {total}.'
        else:
            headline = f'Rotina "{execution.name}" concluída: {total} etapa(s).'
        self._finish(execution, "succeeded", headline)

    # ── aprovação ──────────────────────────────────────────────────────────────
    def _pause(self, execution: _Execution, action: Any) -> bool:
        """Registra o ponto de retomada; False se a aprovação já chegou (continua aqui mesmo)."""
        store, run_id = execution.store, execution.run_id
        number, step = execution.index + 1, execution.steps[execution.index]
        execution.paused_action = action.id
        # Pendência antes do registro: quem retomar sempre encontra o pedido aberto. A pendência só
        # é limpa no fim (finish_resume), porque a rotina continua depois da aprovação.
        store.set_resume_pending(run_id, True)
        if not execution.turn_closed:
            execution.turn_closed = True
            store.finish_run(run_id, failed=False)
        loop_checkpoints.register(action.id, loop_checkpoints.LoopCheckpoint(
            action_id=action.id, run_id=run_id, session_id=None,
            resume=lambda final_status: self._resume(execution, action.id, final_status),
            abandon=lambda reason: self._abandon(execution, action.id, reason),
        ))
        current = store.get(action.id)
        if current is not None and current.status in TERMINAL_STATUSES and loop_checkpoints.take(action.id) is not None:
            execution.paused_action = None
            return False
        summary = f"Etapa {number} ({step.get('label') or step['tool']}) aguarda aprovação na Central (até {APPROVAL_MINUTES} min)."
        rstore = self._routines()
        rstore.update_run(execution.entry_id, status="paused", step_index=execution.index, summary=summary)
        rstore.set_last(execution.routine["id"], last_status="paused", last_summary=summary)
        self._event(execution, summary)
        self._popup(execution, "Rotina aguardando aprovação", [
            f'Rotina "{_short(execution.name, 100)}"', _short(f"Etapa {number}: {step.get('label') or step['tool']}", 120),
            f"Aprove na Central em até {APPROVAL_MINUTES} min; depois disso a rotina é encerrada.",
        ])
        self._publish(execution, "paused", "paused")
        return True

    def _resume(self, execution: _Execution, action_id: str, _final_status: str) -> None:
        def body() -> None:
            action = execution.store.get(action_id)
            execution.paused_action = None
            self._routines().update_run(execution.entry_id, status="running", summary="Aprovação recebida; em execução.")
            self._routines().set_last(execution.routine["id"], last_status="running", last_summary="Em execução.")
            self._event(execution, "Aprovação recebida; a rotina continua.")
            self._publish(execution, "resumed", "running")
            step = execution.steps[execution.index]
            status = getattr(action, "status", None) or "failed"
            if self._settle(execution, step, status, getattr(action, "result_summary", "") or ""):
                self._advance(execution)

        self._in_context(execution, body)

    def _abandon(self, execution: _Execution, action_id: str, _reason: str) -> None:
        def body() -> None:
            action = execution.store.get(action_id)
            self._fail_unapproved(execution, getattr(action, "status", "") or "cancelled")

        self._in_context(execution, body)

    def _fail_unapproved(self, execution: _Execution, status: str) -> None:
        number = execution.index + 1
        execution.paused_action = None
        if status == "expired":
            text = f"Etapa {number} não foi aprovada a tempo (expirou)."
        else:
            text = f"Etapa {number} foi recusada na Central."
        execution.lines.append(text)
        self._finish(execution, "failed", f'Rotina "{execution.name}" encerrada: {text}')

    def reconcile(self) -> int:
        """Execuções pausadas cujo pedido foi cancelado ou cuja aprovação expirou sem retomada."""
        closed = 0
        for execution in self.active():
            if not execution.paused_action or execution.finished:
                continue
            action = execution.store.get(execution.paused_action)
            detail = execution.store.run_details(execution.run_id) or {}
            run = detail.get("run") or {}
            if action is not None and action.status == "expired":
                self._in_context(execution, lambda e=execution: self._fail_unapproved(e, "expired"))
            elif run.get("cancel_requested") or run.get("status") in RUN_TERMINAL:
                self._in_context(execution, lambda e=execution: self._finish(e, "cancelled", f'Rotina "{e.name}" cancelada enquanto aguardava aprovação.'))
            else:
                continue
            closed += 1
        return closed

    # ── encerramento ───────────────────────────────────────────────────────────
    def _finish(self, execution: _Execution, status: str, headline: str) -> None:
        if execution.finished:
            return
        execution.finished = True
        details = " ".join(execution.lines)
        summary = f"{headline} {details}".strip()[:500]
        failed = status == "failed"
        store = execution.store
        try:
            if execution.turn_closed:
                store.finish_resume(execution.run_id, failed=failed, reply=summary)
            else:
                store.finish_run(execution.run_id, failed=failed, reply=summary)
        except Exception:
            pass
        rstore = self._routines()
        try:
            rstore.update_run(execution.entry_id, status=status, finished_at=time.time(), step_index=execution.index, summary=summary)
            rstore.set_last(execution.routine["id"], last_status=status, last_summary=summary, last_run_id=execution.run_id)
        finally:
            with self._lock:
                if self._active.get(execution.routine["id"]) is execution:
                    self._active.pop(execution.routine["id"], None)
        self._event(execution, f"Rotina {STATUS_LABELS.get(status, status)}.")
        self._publish(execution, "end", status, summary)

    # ── avisos ─────────────────────────────────────────────────────────────────
    @staticmethod
    def _event(execution: _Execution, summary: str) -> None:
        try:
            execution.store.add_run_event(execution.run_id, "routine", summary)
        except Exception:
            pass

    @staticmethod
    def _publish(execution: _Execution, phase: str, status: str, summary: str = "") -> None:
        ui_events.publish({
            "type": "routine_run", "phase": phase, "status": status, "routine_id": execution.routine["id"],
            "run_id": execution.run_id, "name": execution.name, "summary": summary,
        })

    @staticmethod
    def _popup(execution: _Execution, title: str, lines: list[str]) -> None:
        try:
            from app.agent import popups
            from app.storage.runtime_settings import get_popup_settings

            if not get_popup_settings()["enabled"]:
                return
            popup = popups.build_popup("info", {"title": title, "lines": lines, "tone": "warn"}, origin="command", run_id=execution.run_id)
            popups.emit(popup, run_id=execution.run_id)
        except Exception:
            pass
