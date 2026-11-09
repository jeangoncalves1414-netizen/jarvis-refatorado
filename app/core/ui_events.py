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
