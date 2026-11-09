"""Seções extras do system prompt de cada turno (chat, voz e loop agêntico).

Fase 1: só o contexto situacional. Nunca levanta exceção: sem dado, devolve vazio.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.agent import turn_meta


@dataclass
class TurnSections:
    text: str = ""
    situational: str = ""
    memories: str = ""


def build_turn_sections(text: str, origin: str | None = None) -> TurnSections:
    try:
        from app.services.situational_context import get_situational_context

        block = get_situational_context().build()
    except Exception:
        return TurnSections()
    if not block.text:
        return TurnSections()
    situational = "\n\n## Situação agora\n" + block.text
    if block.show_in_chat:
        turn_meta.record("situational_context", {"text": block.text, "sources": block.sources, "chars": block.chars})
    return TurnSections(text=situational, situational=situational)
