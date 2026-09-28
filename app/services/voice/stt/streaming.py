"""Streaming STT Engine para baixa latência em tempo real.

Suporta streaming de áudio via Groq Whisper e Oxyy Whisper,
permitindo transcrição contínua enquanto o usuário fala.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, AsyncGenerator, Callable
from dataclasses import dataclass
from enum import Enum


class StreamingState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    FINISHED = "finished"


@dataclass
class StreamingResult:
    text: str
    is_final: bool
    confidence: float
    timestamp: float
    state: StreamingState


class StreamingSTTEngine:
    """Motor de STT streaming para baixa latência."""

    def __init__(
        self,
        groq_api_key: str = "",
        oxyy_api_keys: list[str] | None = None,
        oxyy_base_url: str = "https://api.oxyy.ai/v1",
        language: str = "pt-BR",
        provider: str = "groq",  # groq, oxyy
    ):
        self.groq_api_key = groq_api_key
        self.oxyy_api_keys = [str(k).strip() for k in (oxyy_api_keys or []) if str(k).strip()]
        self.oxyy_base_url = oxyy_base_url.rstrip("/")
        self.language = language
        self.provider = provider.lower()
        self._buffer: list[bytes] = []
        self._is_streaming = False
        self._last_result: StreamingResult | None = None

    async def stream_transcribe(
        self,
        audio_chunks: AsyncGenerator[bytes, None],
        on_partial: Callable[[StreamingResult], None] | None = None,
        on_final: Callable[[StreamingResult], None] | None = None,
    ) -> AsyncGenerator[StreamingResult, None]:
        """Transcreve áudio em streaming, gerando resultados parciais e finais."""
        self._is_streaming = True
        self._buffer = []

        try:
            if self.provider == "oxyy" and self.oxyy_api_keys:
                async for result in self._stream_oxyy(audio_chunks):
                    if on_partial and not result.is_final:
                        on_partial(result)
                    if on_final and result.is_final:
                        on_final(result)
                    yield result
            elif self.groq_api_key:
                async for result in self._stream_groq(audio_chunks):
                    if on_partial and not result.is_final:
                        on_partial(result)
                    if on_final and result.is_final:
                        on_final(result)
                    yield result
            else:
                # Fallback para processamento em batch se não houver provider de streaming
                async for result in self._stream_batch(audio_chunks):
                    if on_partial and not result.is_final:
                        on_partial(result)
                    if on_final and result.is_final:
                        on_final(result)
                    yield result
        finally:
            self._is_streaming = False

    async def _stream_groq(
        self, audio_chunks: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[StreamingResult, None]:
        """Streaming via Groq Whisper (simulado - Groq não tem streaming nativo)."""
        buffer = bytearray()
        chunk_count = 0
        last_emit_time = 0

        async for chunk in audio_chunks:
            buffer.extend(chunk)
            chunk_count += 1
            current_time = time.time()

            # Emitir resultado parcial a cada 10 chunks ou 500ms
            if chunk_count % 10 == 0 or (current_time - last_emit_time > 0.5):
                if len(buffer) > 16000:  # Mínimo de ~1 segundo de áudio
                    text = await self._transcribe_groq_batch(bytes(buffer))
                    if text:
                        yield StreamingResult(
                            text=text,
                            is_final=False,
                            confidence=0.8,
                            timestamp=current_time,
                            state=StreamingState.PROCESSING,
                        )
                        last_emit_time = current_time

        # Resultado final
        if len(buffer) > 16000:
            text = await self._transcribe_groq_batch(bytes(buffer))
            if text:
                yield StreamingResult(
                    text=text,
                    is_final=True,
                    confidence=0.9,
                    timestamp=time.time(),
                    state=StreamingState.FINISHED,
                )

    async def _stream_oxyy(
        self, audio_chunks: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[StreamingResult, None]:
        """Streaming via Oxyy (simulado - similar ao Groq)."""
        buffer = bytearray()
        chunk_count = 0
        last_emit_time = 0

        async for chunk in audio_chunks:
            buffer.extend(chunk)
            chunk_count += 1
            current_time = time.time()

            if chunk_count % 10 == 0 or (current_time - last_emit_time > 0.5):
                if len(buffer) > 16000:
                    text = await self._transcribe_oxyy_batch(bytes(buffer))
                    if text:
                        yield StreamingResult(
                            text=text,
                            is_final=False,
                            confidence=0.8,
                            timestamp=current_time,
                            state=StreamingState.PROCESSING,
                        )
                        last_emit_time = current_time

        if len(buffer) > 16000:
            text = await self._transcribe_oxyy_batch(bytes(buffer))
            if text:
                yield StreamingResult(
                    text=text,
                    is_final=True,
                    confidence=0.9,
                    timestamp=time.time(),
                    state=StreamingState.FINISHED,
                )

    async def _stream_batch(
        self, audio_chunks: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[StreamingResult, None]:
        """Fallback: processa chunks em batch."""
        buffer = bytearray()

        async for chunk in audio_chunks:
            buffer.extend(chunk)

        if len(buffer) > 16000:
            # Usar STT existente
            from .engine import STTEngine
            import tempfile
            import os

            stt = STTEngine(language=self.language, groq_api_key=self.groq_api_key)
            temp_file = os.path.join(tempfile.gettempdir(), f"stt_{time.time()}.webm")
            try:
                with open(temp_file, "wb") as f:
                    f.write(bytes(buffer))
                text, _ = stt.transcribe_file(temp_file)
                if text:
                    yield StreamingResult(
                        text=text,
                        is_final=True,
                        confidence=0.85,
                        timestamp=time.time(),
                        state=StreamingState.FINISHED,
                    )
            finally:
                if os.path.exists(temp_file):
                    os.remove(temp_file)

    async def _transcribe_groq_batch(self, audio_bytes: bytes) -> str | None:
        """Transcreve batch via Groq."""
        import tempfile
        import os
        from .engine import STTEngine

        temp_file = os.path.join(tempfile.gettempdir(), f"groq_{time.time()}.webm")
        try:
            with open(temp_file, "wb") as f:
                f.write(audio_bytes)
            stt = STTEngine(language=self.language, groq_api_key=self.groq_api_key)
            text, _ = stt.transcribe_file(temp_file)
            return text
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    async def _transcribe_oxyy_batch(self, audio_bytes: bytes) -> str | None:
        """Transcreve batch via Oxyy."""
        import tempfile
        import os
        from .engine import STTEngine

        temp_file = os.path.join(tempfile.gettempdir(), f"oxyy_{time.time()}.webm")
        try:
            with open(temp_file, "wb") as f:
                f.write(audio_bytes)
            stt = STTEngine(
                language=self.language,
                oxyy_api_keys=self.oxyy_api_keys,
                oxyy_base_url=self.oxyy_base_url,
                stt_provider="oxyy",
            )
            text, _ = stt.transcribe_file(temp_file)
            return text
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    def stop(self):
        """Para o streaming atual."""
        self._is_streaming = False
        self._buffer = []
