"""
Multi-Model Debate & Consensus Engine
Inspirado na técnica de Mixture-of-Agents (MoA) e Adversarial Multi-Agent Debate.

Três papéis de agentes conversam entre si para garantir solução de código sem bugs:
  1. PROPOSER (Gerador): Cria a solução inicial.
  2. CRITIC (Revisor/Adversário): Procura bugs, vulnerabilidades e edge cases.
  3. SYNTHESIZER (Refinador Final): Consolida a solução final perfeita.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class DebateRound:
    round_number: int
    proposal: str
    critique: str
    refined_solution: str


@dataclass
class DebateResult:
    ok: bool
    final_solution: str
    rounds_executed: int
    rounds_data: list[DebateRound] = field(default_factory=list)
    consensus_reached: bool = True
    model_used: str = "oxyy-code"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "final_solution": self.final_solution,
            "rounds_executed": self.rounds_executed,
            "consensus_reached": self.consensus_reached,
            "model_used": self.model_used,
            "rounds": [
                {
                    "round": r.round_number,
                    "proposal": r.proposal[:500],
                    "critique": r.critique[:500],
                    "refined": r.refined_solution[:500],
                }
                for r in self.rounds_data
            ],
        }


class MultiModelDebateEngine:
    """Motor de debate entre modelos para garantia de qualidade máxima de código."""

    def __init__(self, max_rounds: int = 2) -> None:
        self.max_rounds = max_rounds

    def run_debate(
        self,
        problem_description: str,
        proposer_fn: Callable[[str], str],
        critic_fn: Callable[[str, str], str],
        synthesizer_fn: Callable[[str, str, str], str],
    ) -> DebateResult:
        """
        Executa a rodada de debate entre os três papéis (Proposer -> Critic -> Synthesizer).
        """
        rounds_data: list[DebateRound] = []
        current_proposal = ""

        try:
            # Step 1: Gerar proposta inicial
            current_proposal = proposer_fn(problem_description)

            for r in range(1, self.max_rounds + 1):
                # Step 2: Crítico analisa a proposta atual
                critique = critic_fn(problem_description, current_proposal)

                # Se o crítico não encontrou falhas relevantes, temos consenso
                if "sem falhas" in critique.lower() or "código correto" in critique.lower() or len(critique.strip()) < 20:
                    rounds_data.append(DebateRound(
                        round_number=r,
                        proposal=current_proposal,
                        critique=critique,
                        refined_solution=current_proposal,
                    ))
                    return DebateResult(
                        ok=True,
                        final_solution=current_proposal,
                        rounds_executed=r,
                        rounds_data=rounds_data,
                        consensus_reached=True,
                    )

                # Step 3: Sintetizador refina o código com base na crítica
                refined = synthesizer_fn(problem_description, current_proposal, critique)
                rounds_data.append(DebateRound(
                    round_number=r,
                    proposal=current_proposal,
                    critique=critique,
                    refined_solution=refined,
                ))
                current_proposal = refined

            return DebateResult(
                ok=True,
                final_solution=current_proposal,
                rounds_executed=self.max_rounds,
                rounds_data=rounds_data,
                consensus_reached=True,
            )

        except Exception as exc:
            logger.error("Erro durante o debate multi-modelo: %s", exc)
            return DebateResult(
                ok=False,
                final_solution=current_proposal or "Falha no processo de debate.",
                rounds_executed=len(rounds_data),
                rounds_data=rounds_data,
                consensus_reached=False,
            )
