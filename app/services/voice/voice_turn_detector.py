"""
Smart Voice Turn-Taking Service (ChatGPT Live Style) — Detecção semântica e acústica de encerramento de fala.
Combina análise de completude gramatical de frases parciais em PT-BR e variações de pitch/prosódia
para disparar a resposta instantaneamente (sub-200ms) quando o usuário termina a frase,
ou estender o tempo de silêncio se a frase estiver hesitante/incompleta.
"""
from __future__ import annotations

import re
from typing import Any


# Conectivos e expressões de continuidade (frase incompleta / hesitação)
INCOMPLETE_INDICATORS = [
    r"\beu sou\b",
    r"\beu acho que\b",
    r"\bcomo que\b",
    r"\bonde fica o\b",
    r"\bme fala sobre\b$",
    r"\bpor causa de\b$",
    r"\bporque\b$",
    r"\bquando voce\b",
    r"\bsera que\b$",
    r"\bmas\b$",
    r"\bou seja\b$",
    r"\be tipo\b$",
    r"\beh\b$",
    r"\bhum\b$",
]

# Pontuações ou conectivos de conclusão clara de pensamento
COMPLETE_TERMINATORS = [
    ".", "!", "?", "por favor", "obrigado", "jarvis", "agora",
    "certo", "beleza", "entendeu", "voce consegue", "tudo bem"
]


class VoiceTurnDetectorService:
    """
    Detector Inteligente de Turno de Voz (Voice Turn-Taking).
    """

    @staticmethod
    def evaluate_turn(text: str, pitch_drop_detected: bool = False, silence_duration_ms: int = 400) -> dict[str, Any]:
        """
        Avalia se a fala atual do usuário representa um turno concluído ou se deve aguardar.

        Retorna:
            action: 'submit' (enviar imediatamente) ou 'wait' (aguardar continuação)
            confidence: float (0.0 a 1.0)
            reason: str
        """
        raw = text.strip().lower()
        if not raw:
            return {"action": "wait", "confidence": 1.0, "reason": "Sem texto transcrito."}

        # Check 1: Incompletude gramatical explícita
        for pattern in INCOMPLETE_INDICATORS:
            if re.search(pattern, raw):
                # Se for expressamente incompleta e o silêncio for curto (< 1800ms), aguarda
                if silence_duration_ms < 1800:
                    return {
                        "action": "wait",
                        "confidence": 0.9,
                        "reason": f"Frase incompleta/hesitante detectada ('{pattern}'). Aguardando continuação da fala.",
                    }

        # Check 2: Tom de encerramento acústico (Pitch Drop / Falling Intonation)
        if pitch_drop_detected and len(raw.split()) >= 2:
            return {
                "action": "submit",
                "confidence": 0.95,
                "reason": "Queda de tom acústico de encerramento detectada (Tom de Ponto Final). Disparo instantâneo.",
            }

        # Check 3: Terminadores de conclusão explicita
        words = raw.split()
        last_word = words[-1] if words else ""
        if any(raw.endswith(term) or last_word == term for term in COMPLETE_TERMINATORS):
            return {
                "action": "submit",
                "confidence": 0.9,
                "reason": "Terminador de conclusão gramatical detectado.",
            }

        # Check 4: Frase com verbo e predicado completos (comprimento suficiente)
        if len(words) >= 4 and silence_duration_ms >= 500:
            return {
                "action": "submit",
                "confidence": 0.85,
                "reason": "Frase longa concluída com silêncio suficiente.",
            }

        # Default fallback
        if silence_duration_ms >= 1200:
            return {
                "action": "submit",
                "confidence": 0.75,
                "reason": "Timeout de silêncio padrão atingido.",
            }

        return {
            "action": "wait",
            "confidence": 0.6,
            "reason": "Aguardando mais entrada ou pausa clara de silêncio.",
        }
