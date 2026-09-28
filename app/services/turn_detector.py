"""
Turn Detector Engine — Detecção Inteligente de Turno de Conversa
Inspirado na extensão `ten_turn_detection` do TEN-Framework.

Analisa se a frase falada pelo usuário está completa (FINISHED),
incompleta (UNFINISHED) ou se houve uma pausa de hesitação (WAIT).
"""
from __future__ import annotations

import re
from enum import Enum
from dataclasses import dataclass, field
from typing import Any


class TurnDecision(str, Enum):
    FINISHED = "finished"
    UNFINISHED = "unfinished"
    WAIT = "wait"


@dataclass
class TurnEvaluation:
    decision: TurnDecision
    confidence: float
    reason: str
    cleaned_text: str = ""
    is_question: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "cleaned_text": self.cleaned_text,
            "is_question": self.is_question,
        }


class TurnDetectorEngine:
    """Classificador de integridade de turnos de conversa para assistentes de voz."""

    # Palavras de hesitação que indicam que o usuário ainda está pensando
    HESITATION_WORDS = {
        "é", "tipo", "hum", "hmmm", "ahn", "er", "éee", "ou seja",
        "sabe", "bom", "olha", "assim", "pera", "espera"
    }

    # Conjunções e conectivos que indicam frase incompleta no final
    INCOMPLETE_CONNECTIVES = {
        "e", "ou", "mas", "porque", "porém", "todavia", "contudo",
        "que", "se", "quando", "como", "onde", "para", "com", "de",
        "então", "pois", "já que", "afinal", "quanto", "enquanto"
    }

    # Expressões típicas de encerramento de frase
    COMPLETION_MARKERS = {
        "né", "entendeu", "certo", "tá", "obrigado", "valeu", "por favor",
        "ajuda", "faça isso", "pode ser", "só isso", "pronto", "beleza"
    }

    def evaluate(self, text: str, pause_duration_s: float = 0.0) -> TurnEvaluation:
        """
        Avalia o texto transcrito pelo VAD/STT e a duração da pausa.
        Retorna uma avaliação informando se a fala foi concluída.
        """
        raw = text.strip()
        if not raw:
            return TurnEvaluation(
                decision=TurnDecision.WAIT,
                confidence=0.9,
                reason="Texto vazio.",
                cleaned_text="",
            )

        cleaned = re.sub(r"[^\w\s\?!\.,]", "", raw).strip()
        words = [w.lower() for w in cleaned.split() if w]
        if not words:
            return TurnEvaluation(decision=TurnDecision.WAIT, confidence=0.8, reason="Nenhuma palavra válida.", cleaned_text=cleaned)

        last_word = words[-1]
        is_question = "?" in raw or words[0] in {"o que", "como", "qual", "quais", "quando", "onde", "por que", "quem"}

        # 1. Checa hesitação no final
        if last_word in self.HESITATION_WORDS and pause_duration_s < 2.0:
            return TurnEvaluation(
                decision=TurnDecision.WAIT,
                confidence=0.85,
                reason=f"Hesitação detectada no final: '{last_word}'.",
                cleaned_text=cleaned,
                is_question=is_question,
            )

        # 2. Checa conectivo no final (frase pendente)
        if last_word in self.INCOMPLETE_CONNECTIVES and pause_duration_s < 1.5:
            return TurnEvaluation(
                decision=TurnDecision.UNFINISHED,
                confidence=0.80,
                reason=f"Conectivo incompleto no final: '{last_word}'.",
                cleaned_text=cleaned,
                is_question=is_question,
            )

        # 3. Frase muito curta com conectivo inicial
        if len(words) <= 2 and words[0] in {"e", "mas", "se", "quando"} and pause_duration_s < 1.2:
            return TurnEvaluation(
                decision=TurnDecision.UNFINISHED,
                confidence=0.75,
                reason="Início de frase curto demais.",
                cleaned_text=cleaned,
                is_question=is_question,
            )

        # 4. Pausa longa é forte indicador de término
        if pause_duration_s >= 1.8:
            return TurnEvaluation(
                decision=TurnDecision.FINISHED,
                confidence=0.95,
                reason=f"Pausa longa de {pause_duration_s:.1f}s.",
                cleaned_text=cleaned,
                is_question=is_question,
            )

        # 5. Terminação forte ou pontuação
        if last_word in self.COMPLETION_MARKERS or raw.endswith((".", "!", "?")):
            return TurnEvaluation(
                decision=TurnDecision.FINISHED,
                confidence=0.90,
                reason="Marcador de conclusão ou pontuação presente.",
                cleaned_text=cleaned,
                is_question=is_question,
            )

        # 6. Default: se a frase tem mais de 3 palavras e pausa > 0.6s, considera FINISHED
        if len(words) >= 3 and pause_duration_s >= 0.6:
            return TurnEvaluation(
                decision=TurnDecision.FINISHED,
                confidence=0.85,
                reason="Tamanho de frase suficiente e pausa normal.",
                cleaned_text=cleaned,
                is_question=is_question,
            )

        return TurnEvaluation(
            decision=TurnDecision.UNFINISHED,
            confidence=0.60,
            reason="Aguardando mais contexto de fala.",
            cleaned_text=cleaned,
            is_question=is_question,
        )
