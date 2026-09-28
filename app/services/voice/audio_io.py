from __future__ import annotations

import os
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import time
import threading
from pathlib import Path
import pygame

class AudioIO:
    _lock = threading.Lock()
    _mixer_initialized = False

    @classmethod
    def _init_mixer(cls) -> None:
        with cls._lock:
            if not cls._mixer_initialized:
                try:
                    pygame.mixer.init()
                    cls._mixer_initialized = True
                except Exception as e:
                    print(f"[AudioIO] Erro ao inicializar pygame mixer: {e}")

    @classmethod
    def play_file(cls, path: str | Path, block: bool = True) -> None:
        """Toca um arquivo de áudio utilizando pygame mixer."""
        cls._init_mixer()
        if not cls._mixer_initialized:
            return

        try:
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.play()
            
            if block:
                while pygame.mixer.music.get_busy():
                    time.sleep(0.05)
        except Exception as e:
            print(f"[AudioIO] Erro ao reproduzir áudio: {e}")

    @classmethod
    def stop(cls) -> None:
        """Para qualquer reprodução de áudio em andamento."""
        if cls._mixer_initialized:
            try:
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
            except Exception as e:
                print(f"[AudioIO] Erro ao parar reprodução: {e}")

    @classmethod
    def listen_from_microphone(cls, timeout: float = 5.0, phrase_time_limit: float = 10.0) -> bytes | None:
        """
        Escuta o microfone usando SpeechRecognition e retorna os dados de áudio brutos.
        Retorna None se houver erro ou timeout.
        """
        try:
            import speech_recognition as sr
        except ImportError:
            print("[AudioIO] SpeechRecognition não está instalado. Não é possível escutar.")
            return None

        recognizer = sr.Recognizer()
        recognizer.energy_threshold = 1000
        recognizer.dynamic_energy_threshold = True

        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.8)
                print("[AudioIO] Escutando...")
                audio_data = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
                return audio_data.get_raw_data()
        except sr.WaitTimeoutError:
            print("[AudioIO] Timeout ao aguardar fala.")
            return None
        except Exception as e:
            print(f"[AudioIO] Erro na captura de áudio: {e}")
            return None
