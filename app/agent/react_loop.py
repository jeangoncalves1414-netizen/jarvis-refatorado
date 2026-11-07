"""ReAct Computer Use Loop com Verificação Visual e Auto-Correção.

Implementa o ciclo autônomo:
  Observação (Tela/Output) -> Pensamento (LLM Plan) -> Ação (Ferramenta/GUI) -> Verificação (Visão/Assert) -> Auto-Correção
"""
from __future__ import annotations

import time
import json
from dataclasses import dataclass, field
from typing import Any, Callable
from app.agent.tools.base import ToolResult
from app.agent.action_executor import ActionExecutor
from app.agent.tool_guardrails import ToolCallGuardrailController
from app.core.runs import RunCancelled, check_run_cancelled

# These tools can be addressed explicitly by the step planner.
REACT_TOOLS = frozenset({"web_search", "timer", "calendar", "planning_workspace", "whiteboard_add_text", "whiteboard_clear"})


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


@dataclass
class ReActTrajectory:
    goal: str
    success: bool
    final_output: str
    steps: list[ReActStep] = field(default_factory=list)
    total_elapsed_sec: float = 0.0
    pending_action_id: str | None = None


class ReActLoopEngine:
    """Motor de execução ReAct autônomo com auto-correção."""

    def __init__(self, llm_service: Any = None, registry: Any = None, vision_service: Any = None) -> None:
        self.llm_service = llm_service
        self.registry = registry
        self.vision_service = vision_service

    def run_loop(
        self,
        goal: str,
        max_steps: int = 8,
        context: dict[str, Any] | None = None,
        step_callback: Callable[[ReActStep], None] | None = None
    ) -> ReActTrajectory:
        """Executa um loop ReAct completo para atingir um objetivo complexo."""
        start_time = time.time()
        context = context or {}
        trajectory = ReActTrajectory(goal=goal, success=False, final_output="")
        previous_steps_summary: list[str] = []
        if not self.llm_service:
            trajectory.final_output = "ReAct indisponível: configure um provedor de IA. Nenhuma ferramenta foi executada."
            return trajectory
        if type(max_steps) is not int or not 1 <= max_steps <= 20:
            raise ValueError("O limite de etapas deve estar entre 1 e 20.")

        def execute(name: str, args: dict, _user: str) -> ToolResult:
            if not self.registry:
                return ToolResult(False, "O registro de ferramentas não está disponível.")
            return self.registry.execute_tool(name, args, context=context)

        executor = ActionExecutor(
            REACT_TOOLS.intersection(self.registry.tools) if self.registry else frozenset(),
            ToolCallGuardrailController(), execute,
            metadata_for=self.registry.get_tool_metadata if self.registry else None,
            source=f"react:{context.get('session_id') or 'default'}",
        )

        for step_idx in range(1, max_steps + 1):
            check_run_cancelled()
            step_start = time.time()

            # 1. Observação do estado atual (Visão de tela se disponível + resumo de passos anteriores)
            obs_text = self._gather_observation(context)
            
            # 2. Raciocínio & Decisão da Ação (Thought -> Action)
            check_run_cancelled()
            try:
                thought, action_type, tool_name, tool_args, is_finish = self._plan_step(
                    goal=goal, current_obs=obs_text, history=previous_steps_summary, step_num=step_idx,
                )
            except RunCancelled:
                raise
            except Exception:
                trajectory.final_output = "O planejamento ReAct falhou ou retornou uma ação inválida. Consulte as etapas na Central."
                break
            check_run_cancelled()

            current_step = ReActStep(
                step_number=step_idx,
                thought=thought,
                action_type=action_type,
                tool_name=tool_name,
                tool_args=tool_args
            )

            if is_finish:
                current_step.observation = "O modelo encerrou o planejamento. Os resultados das ferramentas estão na Central."
                current_step.elapsed_ms = int((time.time() - step_start) * 1000)
                trajectory.steps.append(current_step)
                failed_step = next((s for s in trajectory.steps if not s.verification_passed), None)
                trajectory.success = failed_step is None
                trajectory.final_output = (
                    f"Execução encerrada com falha na etapa {failed_step.step_number}. {failed_step.observation}"
                    if failed_step else tool_args.get("response", thought)
                )
                if step_callback:
                    step_callback(current_step)
                break

            # 3. Execução da Ação
            try:
                obs_result = executor.execute(tool_name, tool_args, goal)
            except RunCancelled:
                raise
            except Exception:
                obs_result = "A ferramenta falhou; conclusão não confirmada. Consulte a Central."
            action = executor.last_action
            success = bool(action and action.status == "succeeded")
            current_step.observation = obs_result
            check_run_cancelled()

            if action and action.status == "awaiting_confirmation":
                current_step.verification_passed = False
                current_step.elapsed_ms = int((time.time() - step_start) * 1000)
                trajectory.steps.append(current_step)
                trajectory.pending_action_id = action.id
                trajectory.final_output = f"{obs_result} O planejamento parou nesta etapa. Confira o resultado em Ver execução e envie um novo pedido para planejar outras etapas."
                if step_callback:
                    step_callback(current_step)
                break

            # 4. Verificação & Auto-Correção
            verif_passed, correction_note = self._verify_and_correct(
                goal=goal,
                action_name=tool_name,
                obs_result=obs_result,
                action_success=success
            )

            current_step.verification_passed = verif_passed
            current_step.self_correction_note = correction_note
            current_step.elapsed_ms = int((time.time() - step_start) * 1000)

            trajectory.steps.append(current_step)
            if step_callback:
                step_callback(current_step)

            # Grava no histórico para a próxima iteração
            step_summary = (
                f"Passo {step_idx}: Ação '{tool_name}' -> "
                f"Resultado: {'SUCESSO' if verif_passed else 'FALHA'}. "
                f"Obs: {(obs_result or '')[:150]}"
            )
            if correction_note:
                step_summary += f" | Auto-correção: {correction_note}"
            previous_steps_summary.append(step_summary)

        trajectory.total_elapsed_sec = round(time.time() - start_time, 2)
        if not trajectory.final_output:
            trajectory.final_output = "Limite de etapas atingido. Confira os resultados parciais na Central."
        return trajectory

    def _gather_observation(self, context: dict[str, Any]) -> str:
        obs = ["Ambiente Desktop Windows Ativo."]
        if self.vision_service and context.get("capture_screen", False):
            try:
                res = self.vision_service.analyze("Descreva brevemente o estado atual da tela.")
                obs.append(f"Visão de Tela: {res.get('reply', '')[:200]}")
            except Exception as e:
                obs.append(f"Visão de Tela indisponível: {e}")
        return "\n".join(obs)

    def _plan_step(
        self,
        goal: str,
        current_obs: str,
        history: list[str],
        step_num: int
    ) -> tuple[str, str, str, dict[str, Any], bool]:
        """Parse an explicit plan; malformed arguments never become an execution."""
        history_formatted = "\n".join(history) if history else "Nenhuma ação anterior."
        available = sorted(REACT_TOOLS.intersection(self.registry.tools)) if self.registry else []
        descriptions = [{"name": name, "parameters": getattr(self.registry.tools[name], "parameters", {})} for name in available]
        prompt = (
            f"Você é um agente de execução com ferramentas controladas pela Central.\n"
            f"Objetivo: {goal}\n\n"
            f"Histórico de Ações:\n{history_formatted}\n\n"
            f"Observação Atual:\n{current_obs}\n\n"
            f"Ferramentas disponíveis e parâmetros: {json.dumps(descriptions, ensure_ascii=False)}\n"
            f"Decida a próxima ação. Se o objetivo estiver concluído, responda no formato:\n"
            f"FINISH: <resposta final>\n\n"
            f"Caso contrário:\n"
            f"FERRAMENTA: <nome_da_tool>\nARGS: <objeto JSON>\n"
        )

        raw_resp = self.llm_service.ask(prompt)
        if not isinstance(raw_resp, str) or not raw_resp.strip():
            raise ValueError("Resposta de planejamento vazia.")
        lines = raw_resp.strip().splitlines()
        finishes = [i for i, line in enumerate(lines) if line.startswith("FINISH:")]
        tools = [line.removeprefix("FERRAMENTA:").strip() for line in lines if line.startswith("FERRAMENTA:")]
        if len(finishes) == 1 and not tools:
            final = "\n".join(lines[finishes[0]:]).removeprefix("FINISH:").strip()
            if final:
                return "Planejamento encerrado", "finish", "", {"response": final}, True
        if finishes or len(tools) != 1 or not tools[0] or sum(line.startswith("ARGS:") for line in lines) != 1:
            raise ValueError("Ação de planejamento inválida.")
        args_text = raw_resp.split("ARGS:", 1)[1].strip()
        args = json.loads(args_text)
        if not isinstance(args, dict):
            raise ValueError("Os argumentos da ferramenta devem ser um objeto.")
        return "Executando ação planejada", "tool", tools[0], args, False

    def _verify_and_correct(
        self,
        goal: str,
        action_name: str,
        obs_result: str,
        action_success: bool
    ) -> tuple[bool, str]:
        if not action_success or "erro" in obs_result.lower() or "falha" in obs_result.lower():
            note = f"Ação {action_name} falhou. Ajustando parâmetros ou alternando estratégia."
            return False, note
        return True, ""
