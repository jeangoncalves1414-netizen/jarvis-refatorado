"""Metadados do turno (contexto usado, memórias citadas) num ContextVar.

Só o pedido de topo cria o coletor (`start`); uma chamada aninhada grava no do pedido
que a contém. `handle_request` copia `snapshot()` para `plan.context`.
"""
from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any

_current: ContextVar[dict[str, Any] | None] = ContextVar("jarvis_turn_meta", default=None)


def start() -> Token | None:
    """Cria o coletor do turno; devolve None quando já existe um (chamada aninhada)."""
    if _current.get() is not None:
        return None
    return _current.set({})


def reset(token: Token | None) -> None:
    if token is not None:
        _current.reset(token)


def record(key: str, value: Any) -> None:
    data = _current.get()
    if data is not None:
        data[key] = value


def append(key: str, item: Any, limit: int) -> None:
    data = _current.get()
    if data is None:
        return
    items = data.setdefault(key, [])
    if len(items) < limit:
        items.append(item)


def snapshot() -> dict[str, Any]:
    data = _current.get()
    return dict(data) if data else {}
