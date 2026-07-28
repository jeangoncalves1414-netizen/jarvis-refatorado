from __future__ import annotations

from .stt.engine import STTEngine
from .stt.filter import filter_stt_hallucinations, HARD_HALLUCINATIONS, SOFT_HALLUCINATIONS


class STTSericeFacade(STTEngine):
    """
    Interface de alto nível para Reconhecimento de Fala (STT).
    Mantém compatibilidade de chamadas legadas com STTService.
    """
    pass


# Alias para manter compatibilidade exata com importações legadas
STTService = STTSericeFacade

__all__ = [
    "STTService",
    "STTEngine",
    "filter_stt_hallucinations",
    "HARD_HALLUCINATIONS",
    "SOFT_HALLUCINATIONS",
]
