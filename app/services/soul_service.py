"""
SOUL Service — inspirado no Brahma-AI
Carrega e injeta a personalidade e princípios comportamentais do Jarvis no prompt do agente.
"""
from __future__ import annotations

from pathlib import Path

SOUL_FILE = Path("docs/SOUL.md")


class SoulService:
    """Carregador de diretrizes comportamentais SOUL."""

    @staticmethod
    def get_soul_prompt() -> str:
        if SOUL_FILE.exists():
            try:
                return SOUL_FILE.read_text(encoding="utf-8").strip()
            except Exception:
                pass
        return "Você é o Jarvis — inteligência refinada, leal, ultrarrápida e direta ao ponto."
