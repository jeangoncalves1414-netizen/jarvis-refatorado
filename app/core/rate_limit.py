from __future__ import annotations

import threading
import time
from collections import deque


class RateLimiter:
    """Rate limiter com janela deslizante."""
    
    def __init__(self, max_per_minute: int = 10):
        self.max = max_per_minute
        self.window = 60.0
        self._timestamps: deque[float] = deque()
        self._lock = threading.Lock()
    
    def wait(self) -> None:
        """Aguarda slot disponível."""
        while True:
            wait = 0.0
            with self._lock:
                self._clean()
                if len(self._timestamps) < self.max:
                    self._timestamps.append(time.time())
                    return
                wait = self.window - (time.time() - self._timestamps[0])
            time.sleep(max(0.1, wait))
    
    def _clean(self) -> None:
        """Remove timestamps antigos."""
        cutoff = time.time() - self.window
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()
