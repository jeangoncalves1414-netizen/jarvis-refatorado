from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class LLMService:
    settings: Any

    def summarize(self, text: str) -> str:
        normalized = (text or "").strip()
        if not normalized:
            return "Nenhum texto fornecido para resumo."
        return f"[Resumo simulado] {normalized[:120]}"

    def detect_intent(self, text: str) -> str:
        normalized = (text or "").strip().lower()
        if "arquivo" in normalized or "pasta" in normalized:
            return "file"
        if "tarefa" in normalized or "meta" in normalized:
            return "productivity"
        if "voz" in normalized or "falar" in normalized:
            return "voice"
        return "general"
