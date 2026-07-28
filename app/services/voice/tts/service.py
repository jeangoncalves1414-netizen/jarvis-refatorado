"""Interface de alto nível para Síntese de Voz (TTS) com suporte multi-provider."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .engine import TTSEngine
from .cleaner import strip_text_for_speech
from .cache import TTSCache
from .prefetch import split_text_for_tts
from .providers import GeminiTTSProvider, EdgeTTSProvider


class TTSService:
    """
    Interface de alto nível para Síntese de Voz (TTS) com suporte multi-provider.
    Ordem padrão: GeminiTTS (Charon) → EdgeTTS (SSML) → pyttsx3 local.
    """

    def __init__(
        self,
        voice: str = "pt-BR-AntonioNeural",
        rate: str = "-5%",
        volume: str = "+0%",
        local_fallback: bool = True,
        cache_dir: str | Path = "data/tts_cache",
        # Provider settings
        tts_provider: str = "gemini",
        gemini_api_keys: list[str] | None = None,
        gemini_voice: str = "Charon",
    ) -> None:
        self.voice = voice
        providers = _build_providers(
            tts_provider=tts_provider,
            gemini_api_keys=gemini_api_keys or [],
            gemini_voice=gemini_voice,
            edge_voice=voice,
            edge_rate=rate,
        )
        self.engine = TTSEngine(
            providers=providers,
            voice=voice,
            rate=rate,
            volume=volume,
            local_fallback=local_fallback,
            cache_dir=cache_dir,
        )

    def speak(
        self,
        text: str,
        block: bool = True,
        on_start: Callable[[], None] | None = None,
        on_complete: Callable[[], None] | None = None,
    ) -> str | None:
        """Sintetiza e reproduz o áudio do texto fornecido."""
        return self.engine.speak(text, block=block, on_start=on_start, on_complete=on_complete)

    def generate_bytes(self, text: str) -> bytes | None:
        """Gera o áudio e retorna os bytes (sem reproduzir)."""
        audio, _ = self.engine._generate_with_fallback(strip_text_for_speech(text))
        return audio

    def stop(self) -> None:
        self.engine.stop()


def _build_providers(
    tts_provider: str,
    gemini_api_keys: list[str],
    gemini_voice: str,
    edge_voice: str,
    edge_rate: str,
) -> list:
    """
    Constrói a lista de providers na ordem correta conforme configuração.
    - 'gemini'  → Gemini primeiro, Edge como fallback
    - 'edge'    → Somente Edge TTS
    - 'auto'    → Gemini se houver chave, senão Edge
    """
    gemini = GeminiTTSProvider(api_keys=gemini_api_keys, voice=gemini_voice)
    edge = EdgeTTSProvider(voice=edge_voice, rate=edge_rate)

    if tts_provider == "edge":
        return [edge]
    if tts_provider == "gemini":
        return [gemini, edge]
    # auto
    return [gemini, edge] if gemini.is_available() else [edge]
