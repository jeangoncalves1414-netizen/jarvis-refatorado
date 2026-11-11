"""Seções extras do system prompt de cada turno (chat, voz e loop agêntico).

Fase 1: contexto situacional. Fase 2: até 3 memórias com fonte ligadas ao pedido
(sobreposição de palavras, sem chamada ao modelo), ≤ 300 caracteres.
Nunca levanta exceção: sem dado, devolve vazio.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.agent import turn_meta

MEMORY_HEADER = "\n\n## Preferências salvas (com fonte)\n"
MEMORY_MAX_CHARS = 300


@dataclass
class TurnSections:
    text: str = ""
    situational: str = ""
    memories: str = ""


def _situational() -> str:
    try:
        from app.services.situational_context import get_situational_context

        block = get_situational_context().build()
    except Exception:
        return ""
    if not block.text:
        return ""
    if block.show_in_chat:
        turn_meta.record("situational_context", {"text": block.text, "sources": block.sources, "chars": block.chars})
    return "\n\n## Situação agora\n" + block.text


def _memories(text: str) -> str:
    try:
        from app.storage import memory_facts

        facts = memory_facts.relevant(text, limit=3)
    except Exception:
        return ""
    lines: list[str] = []
    used = 0
    for fact in facts:
        stamp = float((fact.get("source") or {}).get("created_at") or fact.get("updated_at") or 0)
        label = f" (memória de {datetime.fromtimestamp(stamp).strftime('%d/%m')})" if stamp else ""
        line = f"- {fact.get('text', '')}{label}"
        if used + len(line) + 1 > MEMORY_MAX_CHARS:
            break
        lines.append(line)
        used += len(line) + 1
    return MEMORY_HEADER + "\n".join(lines) if lines else ""


def build_turn_sections(text: str, origin: str | None = None) -> TurnSections:
    from app.agent.context_policy import is_chat_history_request
    if is_chat_history_request(text):
        return TurnSections(text="\n\nConsulte somente as mensagens deste chat para responder sobre esta conversa. "
                            "O histórico enviado pode ser parcial; se a mensagem solicitada não estiver nele, "
                            "informe essa limitação. Não use memórias nem consulte outros chats para preencher lacunas.")
    situational = _situational()
    memories = _memories(text)
    return TurnSections(text=situational + memories, situational=situational, memories=memories)
