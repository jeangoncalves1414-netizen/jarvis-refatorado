from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    logger.info("Whisper não disponível localmente. STT em nuvem/navegador será utilizado.")


class WhisperSTT:
    """Speech-to-Text usando Whisper local (offline)."""
    
    def __init__(self, model_size: str = "base", device: str = "cpu"):
        if not WHISPER_AVAILABLE:
            raise RuntimeError("Whisper não instalado. Instale com: pip install openai-whisper")
        
        self.model_size = model_size
        self.device = device
        self._model = None
    
    def _load_model(self):
        if self._model is None:
            try:
                self._model = whisper.load_model(self.model_size, device=self.device)
                logger.info(f"Whisper {self.model_size} carregado no dispositivo {self.device}")
            except Exception as e:
                logger.error(f"Falha ao carregar Whisper: {e}")
                raise
    
    def transcribe_file(self, audio_path: str | Path, language: str = "pt") -> Optional[str]:
        """Transcreve arquivo de áudio para texto."""
        if not WHISPER_AVAILABLE:
            return None
        
        try:
            self._load_model()
            result = self._model.transcribe(str(audio_path), language=language)
            return result["text"].strip()
        except Exception as e:
            logger.error(f"Falha ao transcrever áudio: {e}")
            return None
    
    def transcribe_bytes(self, audio_bytes: bytes, language: str = "pt") -> Optional[str]:
        """Transcreve bytes de áudio para texto."""
        if not WHISPER_AVAILABLE:
            return None
        
        import tempfile
        import os
        
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_bytes)
                temp_path = f.name
            
            try:
                return self.transcribe_file(temp_path, language)
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
        except Exception as e:
            logger.error(f"Falha ao transcrever bytes: {e}")
            return None
    
    def is_available(self) -> bool:
        return WHISPER_AVAILABLE
