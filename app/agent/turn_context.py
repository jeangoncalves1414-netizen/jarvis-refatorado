"""Seções extras do system prompt de cada turno (chat, voz e loop agêntico).

Fase 1: contexto situacional. Fase 2: até 3 memórias com fonte ligadas ao pedido
(sobreposição de palavras, sem chamada ao modelo), ≤ 300 caracteres. Perfil essencial
(fatos fixados, importantes ou de nome/cidade, ≤ 500 caracteres) em todo turno comum.
Nunca levanta exceção: sem dado, devolve vazio; falha de uma fonte vira etapa na Central.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.agent import turn_meta

MEMORY_HEADER = "\n\n## Preferências salvas (com fonte)\n"
MEMORY_MAX_CHARS = 300
PROFILE_HEADER = "\n\n## Perfil essencial do usuário\n"
PROFILE_MAX_CHARS = 500


@dataclass
class TurnSections:
    text: str = ""
    situational: str = ""
    memories: str = ""
    profile: str = ""


def _source_failed(source: str, exc: Exception) -> None:
    try:
        from app.agent.run_tracking import record_run_step

        record_run_step(f"Contexto do turno: {source} indisponível ({type(exc).__name__}).", kind="failure")
    except Exception:
        pass


def _situational() -> str:
    try:
        from app.services.situational_context import get_situational_context

        block = get_situational_context().build()
    except Exception as exc:
        _source_failed("situação agora", exc)
        return ""
    if not block.text:
        return ""
    if block.show_in_chat:
        turn_meta.record("situational_context", {"text": block.text, "sources": block.sources, "chars": block.chars})
    return "\n\n## Situação agora\n" + block.text


def _profile_facts() -> list[dict]:
    try:
        from app.storage import memory_facts

        return memory_facts.essential(PROFILE_MAX_CHARS)
    except Exception as exc:
        _source_failed("perfil essencial", exc)
        return []


def _profile(facts: list[dict]) -> str:
    lines = [f"- {fact.get('text', '')}" for fact in facts if fact.get("text")]
    return PROFILE_HEADER + "\n".join(lines) if lines else ""


def _memories(text: str, skip_ids: frozenset[str] = frozenset()) -> str:
    try:
        from app.storage import memory_facts

        facts = memory_facts.relevant(text, limit=3 + len(skip_ids))
    except Exception as exc:
        _source_failed("memórias com fonte", exc)
        return ""
    lines: list[str] = []
    used = 0
    for fact in [fact for fact in facts if fact.get("id") not in skip_ids][:3]:
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
    essential = _profile_facts()
    profile = _profile(essential)
    memories = _memories(text, frozenset(str(fact.get("id")) for fact in essential))
    return TurnSections(text=situational + profile + memories, situational=situational,
                        memories=memories, profile=profile)
