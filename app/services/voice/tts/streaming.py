"""Streaming TTS Engine para baixa latência em tempo real.

Suporta streaming de áudio via Fish Audio e Oxyy,
permitindo reprodução contínua enquanto o áudio é gerado.
"""
from __future__ import annotations

import asyncio
import time
from typing import AsyncGenerator, Callable
from dataclasses import dataclass
from enum import Enum


class StreamingTTSState(str, Enum):
    IDLE = "idle"
    GENERATING = "generating"
    STREAMING = "streaming"
    FINISHED = "finished"
    INTERRUPTED = "interrupted"


@dataclass
class StreamingTTSChunk:
    audio_bytes: bytes
    is_first: bool
    is_last: bool
    timestamp: float
    state: StreamingTTSState


class StreamingTTSEngine:
    """Motor de TTS streaming para baixa latência."""

    def __init__(
        self,
        fish_api_key: str = "",
        fish_reference_id: str = "78d40157e19a43ebb725f09fc6125585",
        fish_model: str = "s2.1-pro-free",
        oxyy_api_keys: list[str] | None = None,
        oxyy_base_url: str = "https://api.oxyy.ai/v1",
        oxyy_model: str = "tts-1-hd",
        oxyy_voice: str = "alloy",
        provider: str = "fish",  # fish, oxyy
    ):
        self.fish_api_key = fish_api_key
        self.fish_reference_id = fish_reference_id
        self.fish_model = fish_model
        self.oxyy_api_keys = [str(k).strip() for k in (oxyy_api_keys or []) if str(k).strip()]
        self.oxyy_base_url = oxyy_base_url.rstrip("/")
        self.oxyy_model = oxyy_model
        self.oxyy_voice = oxyy_voice
        self.provider = provider.lower()
        self._is_streaming = False
        self._should_stop = False

    async def stream_synthesize(
        self,
        text: str,
        on_chunk: Callable[[StreamingTTSChunk], None] | None = None,
        on_start: Callable[[], None] | None = None,
        on_complete: Callable[[], None] | None = None,
    ) -> AsyncGenerator[StreamingTTSChunk, None]:
        """Sintetiza texto em streaming, gerando chunks de áudio."""
        self._is_streaming = True
        self._should_stop = False

        if on_start:
            on_start()

        try:
            if self.provider == "oxyy" and self.oxyy_api_keys:
                async for chunk in self._stream_oxyy(text):
                    if self._should_stop:
                        yield StreamingTTSChunk(
                            audio_bytes=b"",
                            is_first=False,
                            is_last=True,
                            timestamp=time.time(),
                            state=StreamingTTSState.INTERRUPTED,
                        )
                        break
                    if on_chunk:
                        on_chunk(chunk)
                    yield chunk
            elif self.fish_api_key:
                async for chunk in self._stream_fish(text):
                    if self._should_stop:
                        yield StreamingTTSChunk(
                            audio_bytes=b"",
                            is_first=False,
                            is_last=True,
                            timestamp=time.time(),
                            state=StreamingTTSState.INTERRUPTED,
                        )
                        break
                    if on_chunk:
                        on_chunk(chunk)
                    yield chunk
            else:
                # Fallback para TTS batch se não houver provider de streaming
                async for chunk in self._stream_batch(text):
                    if self._should_stop:
                        yield StreamingTTSChunk(
                            audio_bytes=b"",
                            is_first=False,
                            is_last=True,
                            timestamp=time.time(),
                            state=StreamingTTSState.INTERRUPTED,
                        )
                        break
                    if on_chunk:
                        on_chunk(chunk)
                    yield chunk
        finally:
            self._is_streaming = False
            if on_complete:
                on_complete()

    async def _stream_fish(self, text: str) -> AsyncGenerator[StreamingTTSChunk, None]:
        """Streaming via Fish Audio."""
        from .providers.fish_audio import FishAudioProvider

        provider = FishAudioProvider(
            api_key=self.fish_api_key,
            reference_id=self.fish_reference_id,
            model=self.fish_model,
        )

        if not provider.is_available():
            raise ValueError("Fish Audio não configurado")

        stream = provider.generate_stream(text)
        if stream is None:
            raise ValueError("Fish Audio streaming falhou")

        chunk_count = 0
        for chunk in stream:
            if self._should_stop:
                break
            chunk_count += 1
            yield StreamingTTSChunk(
                audio_bytes=chunk,
                is_first=chunk_count == 1,
                is_last=False,
                timestamp=time.time(),
                state=StreamingTTSState.STREAMING,
            )

        # Chunk final vazio para sinalizar conclusão
        yield StreamingTTSChunk(
            audio_bytes=b"",
            is_first=False,
            is_last=True,
            timestamp=time.time(),
            state=StreamingTTSState.FINISHED,
        )

    async def _stream_oxyy(self, text: str) -> AsyncGenerator[StreamingTTSChunk, None]:
        """Streaming via Oxyy."""
        from .providers.oxyy_tts import OxyyTTSProvider

        provider = OxyyTTSProvider(
            api_keys=self.oxyy_api_keys,
            base_url=self.oxyy_base_url,
            model=self.oxyy_model,
            voice=self.oxyy_voice,
        )

        if not provider.is_available():
            raise ValueError("Oxyy não configurado")

        stream = provider.generate_stream(text)
        if stream is None:
            raise ValueError("Oxyy streaming falhou")

        chunk_count = 0
        for chunk in stream:
            if self._should_stop:
                break
            chunk_count += 1
            yield StreamingTTSChunk(
                audio_bytes=chunk,
                is_first=chunk_count == 1,
                is_last=False,
                timestamp=time.time(),
                state=StreamingTTSState.STREAMING,
            )

        yield StreamingTTSChunk(
            audio_bytes=b"",
            is_first=False,
            is_last=True,
            timestamp=time.time(),
            state=StreamingTTSState.FINISHED,
        )

    async def _stream_batch(self, text: str) -> AsyncGenerator[StreamingTTSChunk, None]:
        """Fallback: processa em batch."""
        from .service import TTSService
        from ..pipeline import VoicePipeline

        # Criar pipeline temporário
        class MockSettings:
            tts_provider = "edge"
            tts_voice = "pt-BR-AntonioNeural"

        pipeline = VoicePipeline(MockSettings())
        audio_bytes = pipeline.synthesize_bytes(text)

        if audio_bytes:
            chunk_size = 8192
            chunk_count = 0
            for i in range(0, len(audio_bytes), chunk_size):
                chunk = audio_bytes[i:i + chunk_size]
                chunk_count += 1
                yield StreamingTTSChunk(
                    audio_bytes=chunk,
                    is_first=chunk_count == 1,
                    is_last=False,
                    timestamp=time.time(),
                    state=StreamingTTSState.STREAMING,
                )

        yield StreamingTTSChunk(
            audio_bytes=b"",
            is_first=False,
            is_last=True,
            timestamp=time.time(),
            state=StreamingTTSState.FINISHED,
        )

    def stop(self):
        """Para o streaming atual."""
        self._should_stop = True
        self._is_streaming = False
