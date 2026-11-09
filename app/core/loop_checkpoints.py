"""Pontos de retomada do loop agêntico, só em memória (como o broker de aprovação).

Quando uma etapa do loop pede aprovação, o motor registra aqui como continuar. Quem
aprova (ou o próprio turno, se a aprovação chegar antes de ele terminar) chama ``take``:
a operação é atômica, então só um dos dois retoma. Nada vai ao disco; reiniciar o
backend perde o ponto de retomada e o pedido vira ``interrupted`` pela recuperação.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class LoopCheckpoint:
    action_id: str
    run_id: str
    session_id: str | None
    resume: Callable[[str], Any]
    abandon: Callable[[str], Any]
    created_at: float = field(default_factory=time.monotonic)


class LoopCheckpointRegistry:
    def __init__(self, ttl_seconds: int = 600) -> None:
        self.ttl_seconds = ttl_seconds
        self._items: dict[str, tuple[float, LoopCheckpoint]] = {}
        self._lock = threading.Lock()

    def _prune(self, now: float) -> None:
        self._items = {key: item for key, item in self._items.items() if item[0] >= now}

    def register(self, action_id: str, checkpoint: LoopCheckpoint) -> None:
        with self._lock:
            now = time.monotonic()
            self._prune(now)
            self._items[action_id] = (now + self.ttl_seconds, checkpoint)

    def take(self, action_id: str) -> LoopCheckpoint | None:
        with self._lock:
            item = self._items.pop(action_id, None)
        if item is None or item[0] < time.monotonic():
            return None
        return item[1]

    def discard_for_run(self, run_id: str) -> None:
        with self._lock:
            self._items = {key: item for key, item in self._items.items() if item[1].run_id != run_id}

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


loop_checkpoints = LoopCheckpointRegistry()


def register(action_id: str, checkpoint: LoopCheckpoint) -> None:
    loop_checkpoints.register(action_id, checkpoint)


def take(action_id: str) -> LoopCheckpoint | None:
    return loop_checkpoints.take(action_id)


def discard_for_run(run_id: str) -> None:
    loop_checkpoints.discard_for_run(run_id)


def resume_runner(checkpoint: LoopCheckpoint, final_status: str) -> None:
    """Retoma em segundo plano para a aprovação responder logo. Testes trocam por execução síncrona."""
    threading.Thread(target=checkpoint.resume, args=(final_status,), daemon=True, name="agent-loop-resume").start()
