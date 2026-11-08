"""Pipeline de streaming de voz em tempo real para baixa latência.

Implementa arquitetura similar ao TEN Framework:
- STT streaming enquanto usuário fala
- LLM processamento paralelo
- TTS streaming enquanto resposta é gerada
- Reprodução imediata de chunks de áudio
"""
from __future__ import annotations

import asyncio
import time
from typing import AsyncGenerator, Callable, Any
from dataclasses import dataclass
from enum import Enum

from .stt.streaming import StreamingSTTEngine, StreamingResult, StreamingState
from .tts.streaming import StreamingTTSEngine, StreamingTTSChunk, StreamingTTSState


class PipelineState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"


@dataclass
class PipelineEvent:
    event_type: str  # "transcript", "audio_chunk", "state_change", "error"
    data: Any
    timestamp: float


class RealtimeVoicePipeline:
    """Pipeline de voz em tempo real com baixa latência."""

    def __init__(
        self,
        stt_engine: StreamingSTTEngine,
        tts_engine: StreamingTTSEngine,
        llm_service: Any = None,
        on_event: Callable[[PipelineEvent], None] | None = None,
    ):
        self.stt_engine = stt_engine
        self.tts_engine = tts_engine
        self.llm_service = llm_service
        self.on_event = on_event
        self._state = PipelineState.IDLE
        self._is_running = False
        self._should_stop = False
        self._current_transcript = ""
        self._audio_queue: asyncio.Queue[bytes] = asyncio.Queue()

    async def start_session(
        self,
        audio_stream: AsyncGenerator[bytes, None],
    ) -> AsyncGenerator[PipelineEvent, None]:
        """Inicia sessão de voz em tempo real."""
        self._is_running = True
        self._should_stop = False
        self._state = PipelineState.LISTENING
        self._current_transcript = ""

        yield PipelineEvent(
            event_type="state_change",
            data={"state": self._state.value},
            timestamp=time.time(),
        )

        try:
            # Pipeline de STT streaming
            stt_task = asyncio.create_task(self._stt_loop(audio_stream))

            # Processar resultados do STT
            async for result in self._process_stt_results(stt_task):
                yield result

        finally:
            self._is_running = False
            self._state = PipelineState.IDLE

    async def _stt_loop(
        self, audio_stream: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[StreamingResult, None]:
        """Loop de STT streaming."""
        async for result in self.stt_engine.stream_transcribe(
            audio_stream,
            on_partial=self._on_partial_transcript,
            on_final=self._on_final_transcript,
        ):
            yield result

    async def _process_stt_results(
        self, stt_task: asyncio.Task
    ) -> AsyncGenerator[PipelineEvent, None]:
        """Processa resultados do STT e aciona LLM + TTS."""
        async for result in stt_task:
            if result.is_final:
                self._state = PipelineState.THINKING
                yield PipelineEvent(
                    event_type="state_change",
                    data={"state": self._state.value},
                    timestamp=time.time(),
                )

                # Processar com LLM
                if self.llm_service:
                    llm_response = await self._process_llm(result.text)
                    if llm_response:
                        # Gerar TTS em streaming
                        async for tts_event in self._tts_stream(llm_response):
                            yield tts_event

                self._state = PipelineState.LISTENING
                yield PipelineEvent(
                    event_type="state_change",
                    data={"state": self._state.value},
                    timestamp=time.time(),
                )

    async def _process_llm(self, text: str) -> str | None:
        """Processa texto com LLM."""
        try:
            # Aqui você pode integrar com o LLM service existente
            # Por enquanto, retorna um echo para teste
            if hasattr(self.llm_service, 'handle_request'):
                plan = self.llm_service.handle_request(text, origin="voice")
                return getattr(plan, 'summary', str(plan))
            return f"Você disse: {text}"
        except Exception as e:
            print(f"[Pipeline] Erro no LLM: {e}")
            return None

    async def _tts_stream(self, text: str) -> AsyncGenerator[PipelineEvent, None]:
        """Gera TTS em streaming."""
        self._state = PipelineState.SPEAKING
        yield PipelineEvent(
            event_type="state_change",
            data={"state": self._state.value},
            timestamp=time.time(),
        )

        async for chunk in self.tts_engine.stream_synthesize(
            text,
            on_chunk=self._on_audio_chunk,
            on_start=self._on_tts_start,
            on_complete=self._on_tts_complete,
        ):
            if chunk.state == StreamingTTSState.INTERRUPTED:
                self._state = PipelineState.INTERRUPTED
                yield PipelineEvent(
                    event_type="state_change",
                    data={"state": self._state.value},
                    timestamp=time.time(),
                )
                break

            if chunk.audio_bytes:
                yield PipelineEvent(
                    event_type="audio_chunk",
                    data={"audio": chunk.audio_bytes, "is_first": chunk.is_first, "is_last": chunk.is_last},
                    timestamp=chunk.timestamp,
                )

    def _on_partial_transcript(self, result: StreamingResult):
        """Callback para transcript parcial."""
        self._current_transcript = result.text
        if self.on_event:
            self.on_event(
                PipelineEvent(
                    event_type="transcript",
                    data={"text": result.text, "is_final": result.is_final},
                    timestamp=result.timestamp,
                )
            )

    def _on_final_transcript(self, result: StreamingResult):
        """Callback para transcript final."""
        self._current_transcript = result.text
        if self.on_event:
            self.on_event(
                PipelineEvent(
                    event_type="transcript",
                    data={"text": result.text, "is_final": result.is_final},
                    timestamp=result.timestamp,
                )
            )

    def _on_audio_chunk(self, chunk: StreamingTTSChunk):
        """Callback para chunk de áudio."""
        if self.on_event:
            self.on_event(
                PipelineEvent(
                    event_type="audio_chunk",
                    data={"audio": chunk.audio_bytes, "is_first": chunk.is_first, "is_last": chunk.is_last},
                    timestamp=chunk.timestamp,
                )
            )

    def _on_tts_start(self):
        """Callback quando TTS começa."""
        if self.on_event:
            self.on_event(
                PipelineEvent(
                    event_type="state_change",
                    data={"state": "speaking"},
                    timestamp=time.time(),
                )
            )

    def _on_tts_complete(self):
        """Callback quando TTS termina."""
        if self.on_event:
            self.on_event(
                PipelineEvent(
                    event_type="state_change",
                    data={"state": "listening"},
                    timestamp=time.time(),
                )
            )

    def interrupt(self):
        """Interrompe a fala atual."""
        self._should_stop = True
        self.tts_engine.stop()
        self._state = PipelineState.INTERRUPTED

    def stop(self):
        """Para o pipeline."""
        self._should_stop = True
        self._is_running = False
        self.tts_engine.stop()

    @property
    def state(self) -> PipelineState:
        return self._state

    @property
    def current_transcript(self) -> str:
        return self._current_transcript
