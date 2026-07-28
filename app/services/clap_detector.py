from __future__ import annotations

from typing import Callable

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


class ClapDetector:
    """Detecção de palmas via áudio."""
    
    def __init__(self, threshold: float = 0.8, callback: Callable | None = None):
        if not NUMPY_AVAILABLE:
            raise RuntimeError("NumPy não disponível")
        self.threshold = threshold
        self.callback = callback
        self._listening = False
    
    def process_audio(self, audio_data: np.ndarray) -> bool:
        """Processa frame de áudio."""
        if not self._listening:
            return False
        
        energy = np.mean(np.abs(audio_data))
        
        if energy > self.threshold:
            if self.callback:
                self.callback()
            return True
        return False
    
    def start(self) -> None:
        """Inicia detecção."""
        self._listening = True
    
    def stop(self) -> None:
        """Para detecção."""
        self._listening = False
