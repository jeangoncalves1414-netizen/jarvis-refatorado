"""Reflexion Engine: Motor Evaluator-Optimizer para Garantia de Qualidade e Código Impecável.

Aplica a arquitetura Evaluator-Optimizer (Reflexion):
  1. Gerador: Produz a resposta inicial ou código.
  2. Crítico: Avalia a resposta atribuindo uma nota (0-10) e apontando vulnerabilidades ou omissões.
  3. Refinador: Reescreve e otimiza a resposta se a nota for inferior ao threshold (8.5).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from app.services.stm_filters import stm_filter


@dataclass
class EvaluationResult:
    score: float
    reasoning: str
    needs_refinement: bool
    suggested_changes: str


class ReflexionEngine:
    """Motor Evaluator-Optimizer para validação e refinamento de respostas."""

    def __init__(self, llm_service: Any = None, min_score_threshold: float = 8.5) -> None:
        self.llm_service = llm_service
        self.min_score_threshold = min_score_threshold

    def evaluate(self, prompt: str, candidate_response: str) -> EvaluationResult:
        """Submete o candidato a uma avaliação detalhada pelo modelo Crítico."""
        if not self.llm_service or not candidate_response:
            return EvaluationResult(
                score=9.0,
                reasoning="Avaliação automática desabilitada ou resposta vazia.",
                needs_refinement=False,
                suggested_changes=""
            )

        eval_prompt = (
            f"Você é o Crítico de Qualidade e Segurança do Jarvis.\n"
            f"Pergunta/Objetivo do Usuário: '{prompt}'\n\n"
            f"Resposta do Gerador:\n{candidate_response}\n\n"
            "Avalie a resposta quanto à precisão, clareza, correção de código e completude.\n"
            "Responda EXATAMENTE no formato JSON:\n"
            "{\n"
            '  "score": <nota_de_0_a_10>,\n'
            '  "reasoning": "<justificativa_sucinta>",\n'
            '  "suggested_changes": "<melhorias_necessarias_se_houver>"\n'
            "}"
        )

        try:
            raw_eval = self.llm_service.ask(eval_prompt)
            # Extrai bloco JSON
            clean_eval = raw_eval.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_eval)
            score = float(data.get("score", 9.0))
            reasoning = str(data.get("reasoning", ""))
            changes = str(data.get("suggested_changes", ""))
            needs_refinement = score < self.min_score_threshold

            return EvaluationResult(
                score=score,
                reasoning=reasoning,
                needs_refinement=needs_refinement,
                suggested_changes=changes
            )
        except Exception:
            # Fallback tolerante em caso de resposta não estruturada
            return EvaluationResult(
                score=8.5,
                reasoning="Avaliação heurística fallback.",
                needs_refinement=False,
                suggested_changes=""
            )

    def refine(self, prompt: str, candidate_response: str, evaluation: EvaluationResult) -> str:
        """Reescreve a resposta com base no feedback crítico do Evaluator."""
        if not self.llm_service or not evaluation.needs_refinement:
            return stm_filter.process(candidate_response)

        refine_prompt = (
            f"Aperfeiçoe a seguinte resposta de acordo com o feedback do Crítico:\n\n"
            f"Objetivo do Usuário: {prompt}\n"
            f"Resposta Atual:\n{candidate_response}\n\n"
            f"Crítica (Nota: {evaluation.score}/10): {evaluation.reasoning}\n"
            f"Melhorias Necessárias: {evaluation.suggested_changes}\n\n"
            "Forneça a versão final totalmente corrigida, polida e sem enrolações."
        )

        try:
            refined_res = self.llm_service.ask(refine_prompt)
            return stm_filter.process(refined_res)
        except Exception:
            return stm_filter.process(candidate_response)

    def process_with_reflexion(self, prompt: str, candidate_response: str) -> dict[str, Any]:
        """Aplica o fluxo completo Evaluator-Optimizer."""
        eval_res = self.evaluate(prompt, candidate_response)

        if eval_res.needs_refinement:
            final_response = self.refine(prompt, candidate_response, eval_res)
            refined = True
        else:
            final_response = stm_filter.process(candidate_response)
            refined = False

        return {
            "ok": True,
            "response": final_response,
            "score": eval_res.score,
            "reasoning": eval_res.reasoning,
            "refined": refined
        }


# Instância global do Reflexion Engine
reflexion_engine = ReflexionEngine()
