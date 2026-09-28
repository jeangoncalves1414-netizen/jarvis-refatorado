"""Pacote de providers de TTS."""
from .base import TTSProvider
from .gemini_tts import GeminiTTSProvider
from .edge_tts_provider import EdgeTTSProvider
from .fish_audio import FishAudioProvider
from .oxyy_tts import OxyyTTSProvider

__all__ = ["TTSProvider", "GeminiTTSProvider", "EdgeTTSProvider", "FishAudioProvider", "OxyyTTSProvider"]
