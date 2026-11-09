"""Espera real entre ações de um pedido (ferramenta ``wait`` e, depois, ``delay_before`` das rotinas).

Um laço único: dorme em fatias curtas, confere "Parar pedido" a cada fatia (``check_run_cancelled``)
e informa o tempo restante uma vez por segundo. Quem quer o contador (o loop agêntico) define
``current_wait_reporter``; sem ele, o restante vai para o progresso do Run (Central) e para o chat.
Relógio e sono são injetáveis (``_monotonic``, ``_sleep``) para testar sem esperar de verdade.
"""
from __future__ import annotations

import math
import time
from contextvars import ContextVar
from typing import Callable

from app.core.runs import check_run_cancelled, current_run

MAX_INLINE_WAIT = 3600
_SLICE = 0.5

# Recebe (restante, total) em segundos inteiros.
current_wait_reporter: ContextVar[Callable[[int, int], None] | None] = ContextVar("current_wait_reporter", default=None)

_monotonic: Callable[[], float] = time.monotonic
_sleep: Callable[[float], None] = time.sleep


def _default_report(remaining: int, total: int, label: str) -> None:
    """Sem reporter: contador no Run (Central) e no chat aberto da conversa."""
    context = current_run.get()
    if not context:
        return
    store, run_id = context
    summary = f"Aguardando {remaining} s de {total}" + (f" ({label})" if label else "") + "."
    event = {
        "phase": "waiting", "step": 0, "max_steps": 0, "model_calls": 0, "max_model_calls": 0,
        "wait_remaining": remaining, "wait_total": total, "summary": summary[:200],
    }
    try:
        store.update_run_progress(run_id, event)
    except Exception:
        pass
    try:
        from app.core import ui_events
        ui_events.publish({"type": "agent_progress", "session_id": ui_events.current_popup_session.get(), "run_id": run_id, **event})
    except Exception:
        pass


def wait_seconds(seconds: int, *, label: str = "") -> int:
    """Espera ``seconds`` segundos; levanta ``RunCancelled`` se o pedido for parado no meio."""
    total = int(seconds)
    if total < 0 or total > MAX_INLINE_WAIT:
        raise ValueError(f"A espera deve estar entre 0 e {MAX_INLINE_WAIT} segundos.")
    reporter = current_wait_reporter.get()
    start = _monotonic()
    last: int | None = None
    while True:
        check_run_cancelled()
        elapsed = _monotonic() - start
        remaining = max(0, math.ceil(round(total - elapsed, 3)))
        if remaining != last:
            last = remaining
            try:
                reporter(remaining, total) if reporter else _default_report(remaining, total, label)
            except Exception:
                pass
        if remaining <= 0:
            return total
        _sleep(min(_SLICE, total - elapsed))
