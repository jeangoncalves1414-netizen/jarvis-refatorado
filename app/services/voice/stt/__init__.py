from __future__ import annotations

from .engine import STTEngine
from .filter import filter_stt_hallucinations, HARD_HALLUCINATIONS, SOFT_HALLUCINATIONS

STTService = STTEngine

__all__ = [
    "STTService",
    "STTEngine",
    "filter_stt_hallucinations",
    "HARD_HALLUCINATIONS",
    "SOFT_HALLUCINATIONS",
]
