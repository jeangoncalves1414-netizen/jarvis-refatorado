"""Memória que preenche parâmetros (fase contexto 2): regras por ferramenta, sem chamada ao modelo.

Chamado pelo ``ActionExecutor.execute`` antes da proposta, então chat nativo, marcador e loop
recebem o mesmo preenchimento, e o digest da aprovação já usa os argumentos preenchidos.
Nunca sobrescreve um valor informado; erro interno devolve os argumentos sem mudança.
Quando uma memória preenche (``preenchido``) ou aparece no argumento enviado (``citado``),
a citação vai para ``turn_meta`` (``memory_used``, no máximo 3, sem repetir ``id``).
"""
from __future__ import annotations

import re
from collections.abc import Callable
from copy import deepcopy
from datetime import datetime
from typing import Any

from app.agent import turn_meta

MAX_CITATIONS = 3
_TOOLS = frozenset({"spotify", "realtime", "places_search", "open_windows_app"})
_PLAY_REQUEST = re.compile(r"\b(?:toca|tocar|toque|coloca|colocar|coloque|bota|botar|poe|por)\b.*\bmusica|\bplaylist")
_PERIOD = {"manhã": "manha", "tarde": "tarde", "noite": "noite"}


def _now() -> datetime:
    from app.services.situational_context import local_now
    return local_now()


# Relógio injetável nos testes.
clock: Callable[[], datetime] = _now


def _norm(text: Any) -> str:
    from app.services.memory_slots import normalize_aligned
    return " ".join(normalize_aligned(str(text or "")).split())


def _blank(value: Any) -> bool:
    return not isinstance(value, str) or not value.strip()


def _latest(facts: list[dict[str, Any]], slot: str) -> dict[str, Any] | None:
    matching = [fact for fact in facts if fact.get("slot") == slot and fact.get("value")]
    return max(matching, key=lambda fact: float(fact.get("updated_at") or 0), default=None)


def _music_fact(facts: list[dict[str, Any]]) -> dict[str, Any] | None:
    from app.services.situational_context import period_of
    period = _PERIOD.get(period_of(clock().hour))
    music = [fact for fact in facts if fact.get("slot") == "music" and fact.get("value")]
    timed = [fact for fact in music if fact.get("when") == period]
    untimed = [fact for fact in music if not fact.get("when")]
    return _latest(timed or untimed, "music")


def citation(fact: dict[str, Any], tool: str, param: str, value: str, how: str) -> dict[str, Any]:
    source = fact.get("source") or {}
    stamp = float(source.get("created_at") or fact.get("updated_at") or 0)
    when = datetime.fromtimestamp(stamp) if stamp else clock()
    return {
        "id": fact.get("id", ""), "text": fact.get("text", ""), "date": when.strftime("%Y-%m-%d"),
        "label": f"memória de {when.strftime('%d/%m')}", "origin": source.get("origin") or "chat",
        "session_id": source.get("session_id") or "",
        "applied_to": {"tool": tool, "param": param, "value": str(value)[:80]}, "how": how,
    }


def _cite(fact: dict[str, Any], tool: str, param: str, value: str, how: str) -> None:
    used = turn_meta.snapshot().get("memory_used") or []
    if any(item.get("id") == fact.get("id") for item in used):
        return
    turn_meta.append("memory_used", citation(fact, tool, param, value, how), limit=MAX_CITATIONS)


def _fill(name: str, args: dict[str, Any], user_text: str, facts: list[dict[str, Any]]) -> list[tuple[dict, str, str]]:
    filled: list[tuple[dict, str, str]] = []

    def put(fact: dict[str, Any] | None, param: str) -> None:
        if fact is not None:
            args[param] = fact["value"]
            filled.append((fact, param, fact["value"]))

    if name == "spotify" and _blank(args.get("query")):
        action = args.get("action")
        if action == "search_play" or (action in {"play_pause", "open"} and _PLAY_REQUEST.search(_norm(user_text))):
            fact = _music_fact(facts)
            if fact is not None:
                args["action"] = "search_play"
                put(fact, "query")
    elif name == "realtime" and args.get("action") == "get_weather" and _blank(args.get("city")):
        put(_latest(facts, "city"), "city")
    elif name == "places_search" and _blank(args.get("near")):
        put(_latest(facts, "city"), "near")
    elif name == "open_windows_app" and args.get("action", "open") == "open":
        category = _norm(args.get("app_name"))
        if category in {"navegador", "editor", "player"}:
            put(_latest(facts, f"app.{category}"), "app_name")
    return filled


def _tool_slots(name: str) -> tuple[str, ...]:
    if name == "spotify":
        return ("music",)
    if name in {"realtime", "places_search"}:
        return ("city",)
    return ("app.navegador", "app.editor", "app.player")


def apply_memory_params(name: str, args: dict[str, Any] | None, user_text: str | None = None) -> dict[str, Any]:
    original = args or {}
    if name not in _TOOLS:
        return original
    try:
        from app.storage import memory_facts
        facts = memory_facts.list_facts()
        if not facts:
            return original
        result = deepcopy(original)
        filled = _fill(name, result, user_text or "", facts)
        for fact, param, value in filled:
            _cite(fact, name, param, value, "preenchido")
        filled_ids = {fact.get("id") for fact, _param, _value in filled}
        slots = _tool_slots(name)
        for fact in facts:
            if fact.get("slot") not in slots or not fact.get("value") or fact.get("id") in filled_ids:
                continue
            needle = _norm(fact["value"])
            for param, value in result.items():
                if isinstance(value, str) and needle and needle in _norm(value):
                    _cite(fact, name, param, value, "citado")
                    break
        return result
    except Exception:
        return original
