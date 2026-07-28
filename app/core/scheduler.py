from __future__ import annotations

import threading
import time
from typing import Callable


class Scheduler:
    """Scheduler simples baseado em intervalos."""
    
    def __init__(self):
        self._jobs: list[dict] = []
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
    
    def add_job(self, func: Callable, interval: float) -> None:
        """Adiciona job recorrente."""
        with self._lock:
            self._jobs.append({"func": func, "interval": interval, "last": 0})
    
    def start(self) -> None:
        """Inicia scheduler."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
    
    def stop(self) -> None:
        """Para scheduler."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
    
    def _loop(self) -> None:
        """Loop principal."""
        while self._running:
            now = time.time()
            with self._lock:
                for job in self._jobs:
                    if now - job["last"] >= job["interval"]:
                        try:
                            job["func"]()
                        except Exception:
                            pass
                        job["last"] = now
            time.sleep(1)
