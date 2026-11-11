"""Barramento de eventos para a interface (chat por WebSocket).

O agente publica eventos pequenos (progresso do loop, resposta retomada e, nas próximas
fases, popups). O servidor WebSocket assina e repassa a todos os clientes conectados.
Publicar nunca levanta: um assinante com defeito não derruba o pedido.
"""
from __future__ import annotations

import threading
from contextvars import ContextVar
from typing import Any, Callable

Subscriber = Callable[[dict[str, Any]], None]

_subscribers: list[Subscriber] = []
_lock = threading.Lock()

# Coletor de popups do turno (Fase 3): aberto por handle_request e pela retomada do loop.
# None = fora de um turno de conversa (rotas de janela): nenhum popup é emitido.
current_popups: ContextVar[list[dict[str, Any]] | None] = ContextVar("current_popups", default=None)
# Conversa do turno (vai no envelope do evento) e quem quer o popup assim que ele nasce (SSE).
current_popup_session: ContextVar[str | None] = ContextVar("current_popup_session", default=None)
current_popup_listener: ContextVar[Callable[[dict[str, Any]], None] | None] = ContextVar("current_popup_listener", default=None)


def subscribe(fn: Subscriber) -> Callable[[], None]:
    with _lock:
        _subscribers.append(fn)

    def unsubscribe() -> None:
        with _lock:
            if fn in _subscribers:
                _subscribers.remove(fn)

    return unsubscribe


def publish(event: dict[str, Any]) -> None:
    if not isinstance(event, dict):
        return
    with _lock:
        targets = list(_subscribers)
    for fn in targets:
        try:
            fn(dict(event))
        except Exception:
            pass


def publish_personal_change(tool: str, args: dict[str, Any]) -> None:
    """Invalida as leituras abertas, inclusive quando a usuária desativa os popups."""
    action = str(args.get("action") or "").strip().lower()
    if tool == "personal_records":
        publish({"type": "personal_data_changed", "area": "habits"})
        publish({"type": "personal_data_changed", "area": "finance"})
        publish({"type": "personal_data_changed", "area": "notes"})
        return
    if tool == "finance_tool" and action in {"add", "create", "add_many", "update", "delete"}:
        area = "finance"
    elif tool == "habit_tool" and action in {"create", "create_many", "update", "check", "done", "complete", "check_many", "auto_check", "uncheck", "undo", "delete"}:
        area = "habits"
    elif tool == "lifeos_tool" and action in {"add_water", "set_water"}:
        area = "water"
    elif tool == "lifeos_tool" and action in {"check_habit", "check", "uncheck_habit", "uncheck", "log_workout"}:
        area = "habits"
    elif tool in {"vault_save_note", "vault_daily_log"}:
        area = "notes"
    elif tool in {'task_tool', 'checklist_tool'} and action not in {'list', 'summary', 'get'}:
        area = 'personal'
    else:
        return
    publish({"type": "personal_data_changed", "area": area})
