"""
wake_word.py — Fase 6
Detecção de wake word "Ei Jarvis" / "Jarvis" usando Vosk (PT-BR, 100% local, sem API key).

Fluxo:
  1. Thread daemon em background captura áudio do microfone
  2. Vosk processa frames em tempo real (reconhecimento de fala local)
  3. Quando a transcrição contém "jarvis", o callback é disparado
  4. O callback sinaliza o frontend via WebSocket para abrir o microfone
  5. Toggle On/Off via settings
"""
from __future__ import annotations

import json
import logging
import os
import queue
import threading
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# ── Dependências opcionais ────────────────────────────────────────────────────

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    logger.warning("PyAudio não disponível. Wake word detection será desabilitado.")

try:
    import vosk
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False
    logger.warning("Vosk não disponível. Wake word detection será desabilitado.")

# Caminho do modelo Vosk PT-BR (baixado automaticamente se ausente)
_MODEL_DIR = Path("data/vosk_model_ptbr")
_MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip"

WAKE_WORDS = {"jarvis", "ei jarvis", "jarvis!", "jarvis,", "hey jarvis"}


def _download_model() -> bool:
    """Baixa e descompacta o modelo Vosk PT-BR se não estiver presente."""
    if _MODEL_DIR.exists() and any(_MODEL_DIR.iterdir()):
        return True
    try:
        import urllib.request, zipfile, tempfile
        logger.info(f"Baixando modelo Vosk PT-BR de {_MODEL_URL} …")
        _MODEL_DIR.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            urllib.request.urlretrieve(_MODEL_URL, tmp.name)
            tmp_path = tmp.name
        with zipfile.ZipFile(tmp_path, "r") as zf:
            # O zip tem uma pasta raiz (vosk-model-small-pt-0.3/)
            top = zf.namelist()[0].split("/")[0]
            zf.extractall(_MODEL_DIR.parent)
            extracted = _MODEL_DIR.parent / top
            extracted.rename(_MODEL_DIR)
        os.unlink(tmp_path)
        logger.info("Modelo Vosk PT-BR instalado com sucesso.")
        return True
    except Exception as e:
        logger.error(f"Falha ao baixar modelo Vosk: {e}")
        return False


class WakeWordDetector:
    """
    Detector de wake word usando Vosk (reconhecimento de fala local, PT-BR).
    Detecção em tempo real, sem internet, sem API key.
    """

    def __init__(
        self,
        wake_words: set[str] | None = None,
        sample_rate: int = 16000,
        on_wake: Callable[[], None] | None = None,
    ):
        self.wake_words = wake_words or WAKE_WORDS
        self.sample_rate = sample_rate
        self._on_wake = on_wake
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._model: Optional[vosk.Model] = None if VOSK_AVAILABLE else None
        self._enabled = True

    def _load_model(self) -> bool:
        if not VOSK_AVAILABLE or not PYAUDIO_AVAILABLE:
            return False
        if self._model:
            return True
        if not _MODEL_DIR.exists() or not any(_MODEL_DIR.iterdir()):
            logger.info("Modelo Vosk não encontrado — baixando em background…")
            if not _download_model():
                return False
        try:
            vosk.SetLogLevel(-1)  # silencia logs do Kaldi
            self._model = vosk.Model(str(_MODEL_DIR))
            logger.info("Modelo Vosk PT-BR carregado para wake word detection.")
            return True
        except Exception as e:
            logger.error(f"Falha ao carregar modelo Vosk: {e}")
            return False

    def _matches_wake_word(self, text: str) -> bool:
        text_lower = text.lower().strip()
        for ww in self.wake_words:
            if ww in text_lower:
                return True
        return False

    def _listen_loop(self) -> None:
        if not self._load_model():
            logger.warning("Wake word: modelo não disponível — encerrando thread.")
            return

        recognizer = vosk.KaldiRecognizer(self._model, self.sample_rate)
        recognizer.SetWords(False)

        pa = pyaudio.PyAudio()
        chunk = 4096
        stream = None
        try:
            stream = pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=chunk,
            )
            logger.info(f"🎤 Wake word ativo — ouvindo por: {self.wake_words}")

            while self._running:
                if not self._enabled:
                    import time; time.sleep(0.2)
                    continue
                try:
                    data = stream.read(chunk, exception_on_overflow=False)
                except Exception:
                    continue

                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "")
                    if text and self._matches_wake_word(text):
                        logger.info(f"🔔 Wake word detectada: '{text}'")
                        if self._on_wake:
                            try:
                                self._on_wake()
                            except Exception as e:
                                logger.error(f"Erro no callback de wake word: {e}")
                else:
                    partial = json.loads(recognizer.PartialResult())
                    ptext = partial.get("partial", "")
                    if ptext and self._matches_wake_word(ptext):
                        logger.info(f"🔔 Wake word (parcial) detectada: '{ptext}'")
                        recognizer.Reset()
                        if self._on_wake:
                            try:
                                self._on_wake()
                            except Exception as e:
                                logger.error(f"Erro no callback de wake word: {e}")
        finally:
            if stream:
                stream.stop_stream()
                stream.close()
            pa.terminate()
            logger.info("Wake word thread encerrada.")

    # ── API pública ───────────────────────────────────────────────────────────

    def start(self, on_wake: Callable[[], None] | None = None) -> None:
        """Inicia detecção em thread daemon."""
        if self._running:
            return
        if on_wake:
            self._on_wake = on_wake
        if not VOSK_AVAILABLE or not PYAUDIO_AVAILABLE:
            logger.warning("Wake word desativado — instale: pip install vosk pyaudio")
            return
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True, name="wake-word")
        self._thread.start()

    def stop(self) -> None:
        """Para o listener."""
        self._running = False

    def set_enabled(self, enabled: bool) -> None:
        """Pausa/retoma o listener sem matar a thread."""
        self._enabled = enabled
        logger.info(f"Wake word {'ativado' if enabled else 'pausado'}.")

    def is_available(self) -> bool:
        return VOSK_AVAILABLE and PYAUDIO_AVAILABLE

    def is_running(self) -> bool:
        return self._running and bool(self._thread and self._thread.is_alive())
