"""Pacote de providers de TTS."""
from .base import TTSProvider
from .gemini_tts import GeminiTTSProvider
from .edge_tts_provider import EdgeTTSProvider

__all__ = ["TTSProvider", "GeminiTTSProvider", "EdgeTTSProvider"]
