from __future__ import annotations

import time
from threading import Thread


class Heartbeat:
    """Monitor de saúde do sistema."""
    
    def __init__(self, interval: float = 30.0):
        self.interval = interval
        self._last_beat = 0.0
        self._running = False
        self._thread = None
    
    def start(self) -> None:
        """Inicia heartbeat."""
        if self._running:
            return
        self._running = True
        self._thread = Thread(target=self._loop, daemon=True)
        self._thread.start()
    
    def stop(self) -> None:
        """Para heartbeat."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
    
    def _loop(self) -> None:
        """Loop de heartbeat."""
        while self._running:
            self._last_beat = time.time()
            time.sleep(self.interval)
    
    def is_alive(self) -> bool:
        """Verifica se sistema está vivo."""
        return (time.time() - self._last_beat) < (self.interval * 2)
