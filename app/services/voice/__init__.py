from __future__ import annotations

from .audio_io import AudioIO
from .stt import STTService, STTEngine, filter_stt_hallucinations
from .tts import TTSService, TTSEngine, strip_text_for_speech, TTSCache, split_text_for_tts

try:
    from .whisper_stt import WhisperSTT
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

try:
    from .wake_word import WakeWordDetector
    WAKE_WORD_AVAILABLE = True
except ImportError:
    WAKE_WORD_AVAILABLE = False

__all__ = [
    "AudioIO",
    "STTService",
    "STTEngine",
    "TTSService",
    "TTSEngine",
    "strip_text_for_speech",
    "TTSCache",
    "split_text_for_tts",
    "filter_stt_hallucinations",
]

if WHISPER_AVAILABLE:
    __all__.append("WhisperSTT")

if WAKE_WORD_AVAILABLE:
    __all__.append("WakeWordDetector")
