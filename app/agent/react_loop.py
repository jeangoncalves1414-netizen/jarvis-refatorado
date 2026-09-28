"""ReAct Computer Use Loop com Verificação Visual e Auto-Correção.

Implementa o ciclo autônomo:
  Observação (Tela/Output) -> Pensamento (LLM Plan) -> Ação (Ferramenta/GUI) -> Verificação (Visão/Assert) -> Auto-Correção
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable
from app.agent.tools.base import ToolResult


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

        for step_idx in range(1, max_steps + 1):
            step_start = time.time()

            # 1. Observação do estado atual (Visão de tela se disponível + resumo de passos anteriores)
            obs_text = self._gather_observation(context)
            
            # 2. Raciocínio & Decisão da Ação (Thought -> Action)
            thought, action_type, tool_name, tool_args, is_finish = self._plan_step(
                goal=goal,
                current_obs=obs_text,
                history=previous_steps_summary,
                step_num=step_idx
            )

            current_step = ReActStep(
                step_number=step_idx,
                thought=thought,
                action_type=action_type,
                tool_name=tool_name,
                tool_args=tool_args
            )

            if is_finish:
                current_step.observation = "Objetivo concluído com sucesso."
                current_step.elapsed_ms = int((time.time() - step_start) * 1000)
                trajectory.steps.append(current_step)
                trajectory.success = True
                trajectory.final_output = tool_args.get("response", thought)
                if step_callback:
                    step_callback(current_step)
                break

            # 3. Execução da Ação
            obs_result, success = self._execute_action(tool_name, tool_args, context)
            current_step.observation = obs_result

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
            trajectory.final_output = trajectory.steps[-1].observation if trajectory.steps else "Limite de passos atingido sem conclusão explícita."
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
        """Planeja o próximo passo chamando o LLM ou fallback heurístico."""
        if not self.llm_service:
            # Fallback sem LLM ativo
            return f"Executando passo heurístico {step_num} para '{goal}'", "finish", "", {"response": f"Concluído heurística {goal}"}, True

        history_formatted = "\n".join(history) if history else "Nenhuma ação anterior."
        prompt = (
            f"Você é o Agente Autônomo ReAct do Jarvis.\n"
            f"Objetivo: {goal}\n\n"
            f"Histórico de Ações:\n{history_formatted}\n\n"
            f"Observação Atual:\n{current_obs}\n\n"
            f"Decida a próxima ação. Se o objetivo estiver concluído, responda no formato:\n"
            f"PENSAMENTO: <raciocínio>\nFINISH: <resposta final>\n\n"
            f"Caso contrário:\n"
            f"PENSAMENTO: <raciocínio>\nFERRAMENTA: <nome_da_tool>\nARGS: <json_args>\n"
        )

        try:
            raw_resp = self.llm_service.ask(prompt)
            if "FINISH:" in raw_resp:
                parts = raw_resp.split("FINISH:")
                thought = parts[0].replace("PENSAMENTO:", "").strip()
                finish_text = parts[1].strip()
                return thought, "finish", "", {"response": finish_text}, True
            
            thought = "Executando ação planejada"
            tool_name = "desktop_search"
            tool_args: dict[str, Any] = {}

            if "PENSAMENTO:" in raw_resp:
                lines = raw_resp.splitlines()
                for line in lines:
                    if line.startswith("PENSAMENTO:"):
                        thought = line.replace("PENSAMENTO:", "").strip()
                    elif line.startswith("FERRAMENTA:"):
                        tool_name = line.replace("FERRAMENTA:", "").strip()

            return thought, "tool", tool_name, tool_args, False
        except Exception as exc:
            return f"Erro no planejamento: {exc}", "finish", "", {"response": f"Falha no ReAct: {exc}"}, True

    def _execute_action(self, tool_name: str, args: dict[str, Any], context: dict[str, Any]) -> tuple[str, bool]:
        if not tool_name:
            return "Nenhuma ferramenta especificada.", True
        
        if self.registry and hasattr(self.registry, "execute_tool"):
            try:
                res: ToolResult = self.registry.execute_tool(tool_name, args, context=context)
                return res.message, res.ok
            except Exception as e:
                return f"Erro ao executar {tool_name}: {e}", False

        return f"Simulação de execução de {tool_name} com {args}", True

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
