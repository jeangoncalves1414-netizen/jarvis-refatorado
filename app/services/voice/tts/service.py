"""Interface de alto nível para Síntese de Voz (TTS) com suporte multi-provider."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .engine import TTSEngine
from .cleaner import strip_text_for_speech
from .cache import TTSCache
from .prefetch import split_text_for_tts
from .providers import EdgeTTSProvider, FishAudioProvider, GeminiTTSProvider, OxyyTTSProvider


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
        tts_provider: str = "fish",
        gemini_api_keys: list[str] | None = None,
        gemini_voice: str = "Charon",
        fish_api_key: str = "",
        fish_reference_id: str = FishAudioProvider.DEFAULT_REFERENCE_ID,
        fish_model: str = FishAudioProvider.DEFAULT_MODEL,
        fish_auto_emotions: bool = True,
        oxyy_api_keys: list[str] | None = None,
        oxyy_base_url: str = "https://api.oxyy.ai/v1",
        oxyy_model: str = "tts-1-hd",
        oxyy_voice: str = "alloy",
    ) -> None:
        self.voice = voice
        providers = _build_providers(
            tts_provider=tts_provider,
            gemini_api_keys=gemini_api_keys or [],
            gemini_voice=gemini_voice,
            edge_voice=voice,
            edge_rate=rate,
            fish_api_key=fish_api_key,
            fish_reference_id=fish_reference_id,
            fish_model=fish_model,
            fish_auto_emotions=fish_auto_emotions,
            oxyy_api_keys=oxyy_api_keys or [],
            oxyy_base_url=oxyy_base_url,
            oxyy_model=oxyy_model,
            oxyy_voice=oxyy_voice,
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

    def generate_stream(self, text: str):
        """Retorna chunks do Fish quando o provider estÃ¡ configurado."""
        clean_text = strip_text_for_speech(text)
        if not clean_text:
            return None
        for provider in self.engine._providers:
            if not provider.is_available():
                continue
            stream = getattr(provider, "generate_stream", None)
            if stream is None:
                continue
            try:
                return stream(clean_text)
            except Exception as exc:
                print(f"[TTSService] Streaming {getattr(provider, 'name', 'provider')} indisponível: {exc}")
        return None

    def stop(self) -> None:
        self.engine.stop()


def _build_providers(
    tts_provider: str,
    gemini_api_keys: list[str],
    gemini_voice: str,
    edge_voice: str,
    edge_rate: str,
    fish_api_key: str,
    fish_reference_id: str,
    fish_model: str,
    fish_auto_emotions: bool,
    oxyy_api_keys: list[str],
    oxyy_base_url: str,
    oxyy_model: str,
    oxyy_voice: str,
) -> list:
    """
    Constrói a lista de providers na ordem correta conforme configuração.
    - 'fish'    → Fish primeiro, Edge como fallback
    - 'gemini'  → Gemini primeiro, Edge como fallback
    - 'edge'    → Somente Edge TTS
    - 'auto'    → Gemini se houver chave, senão Edge
    """
    gemini = GeminiTTSProvider(api_keys=gemini_api_keys, voice=gemini_voice)
    edge = EdgeTTSProvider(voice=edge_voice, rate=edge_rate)
    fish = FishAudioProvider(
        api_key=fish_api_key,
        reference_id=fish_reference_id,
        model=fish_model,
        auto_emotions=fish_auto_emotions,
    )
    oxyy = OxyyTTSProvider(api_keys=oxyy_api_keys, base_url=oxyy_base_url, model=oxyy_model, voice=oxyy_voice)

    if tts_provider == "oxyy":
        return [oxyy, edge]
    if tts_provider == "fish":
        return [fish, edge]
    if tts_provider == "edge":
        return [edge]
    if tts_provider == "gemini":
        return [gemini, edge]
    # auto: prefer Fish when configured, then Gemini, then Edge.
    if fish.is_available():
        return [fish, edge]
    return [gemini, edge] if gemini.is_available() else [edge]
