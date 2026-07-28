"""Interface base para provedores de TTS."""
from __future__ import annotations

from abc import ABC, abstractmethod


class TTSProvider(ABC):
    """Contrato que todo provider de TTS deve implementar."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Nome do provider (ex: 'gemini', 'edge')."""

    @abstractmethod
    def generate(self, text: str) -> bytes | None:
        """
        Sintetiza *text* e retorna os bytes do áudio (MP3 ou WAV).
        Retorna None em caso de falha para que o orquestrador tente o próximo.
        """

    def is_available(self) -> bool:
        """Retorna True se o provider está configurado e pronto para uso."""
        return True
