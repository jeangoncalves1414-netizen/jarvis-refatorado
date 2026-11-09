"""
Real-Time WebSocket Audio Stream Pipeline (Full-Duplex RTC)
Inspirado na arquitetura Realtime Engine do TEN-Framework & Gemini Live.

Substitui a troca tradicional de arquivos por um canal contínuo de áudio em tempo real:
  - Recepção contínua de pacotes PCM de 16-bit 16kHz
  - VAD e detecção de hesitação em tempo real
  - Feed instantâneo para o VoiceEmotionAnalyzer e TurnDetectorEngine
  - Emissão de eventos de Barge-In e áudio de resposta
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from app.services.turn_detector import TurnDetectorEngine, TurnDecision
from app.services.voice_emotion import VoiceEmotionAnalyzer
from app.services.voice_call import VoiceCallEngine, voice_call_engine

logger = logging.getLogger(__name__)


@dataclass
class StreamFrame:
    session_id: str
    pcm_bytes: bytes
    timestamp: float = field(default_factory=time.time)
    sequence: int = 0


class RealTimeStreamManager:
    """Gerenciador de sessões de áudio em tempo real por WebSockets."""

    def __init__(self) -> None:
        self.call_engine = voice_call_engine
        self._active_connections: dict[str, Any] = {}
        self._frame_counters: dict[str, int] = {}

    def register_session(self, session_id: str, websocket: Any) -> None:
        self._active_connections[session_id] = websocket
        self._frame_counters[session_id] = 0
        if session_id not in self.call_engine.active_sessions:
            self.call_engine.start_call(session_id)
        logger.info("RealTimeStreamManager: Sessão WebSocket registrada: %s", session_id)

    def unregister_session(self, session_id: str) -> None:
        self._active_connections.pop(session_id, None)
        self._frame_counters.pop(session_id, None)
        if session_id in self.call_engine.active_sessions:
            self.call_engine.end_call(session_id)
        logger.info("RealTimeStreamManager: Sessão WebSocket encerrada: %s", session_id)

    async def process_incoming_frame(self, session_id: str, raw_data: bytes | str) -> dict[str, Any]:
        """
        Processa um pacote recebido via WebSocket.
        Pode ser um frame binário PCM 16-bit ou mensagem de controle JSON.
        """
        if isinstance(raw_data, str):
            try:
                ctrl = json.loads(raw_data)
                cmd = ctrl.get("command", "")
                if cmd == "barge_in":
                    return self.call_engine.interrupt_call(
                        session_id,
                        interrupted_text=ctrl.get("interrupted_text", "")
                    )
                elif cmd == "cancel":
                    return self.call_engine.cancel_active_action(session_id)
                elif cmd == "toggle_mute":
                    return self.call_engine.toggle_mute(session_id)
                elif cmd == "toggle_silent_mode":
                    return self.call_engine.toggle_silent_mode(session_id)
                elif cmd == "set_silent_mode":
                    return self.call_engine.set_silent_mode(session_id, silent=bool(ctrl.get("silent", True)))
                elif cmd == "get_filler":
                    cat = ctrl.get("category", "thinking")
                    filler = self.call_engine.get_filler(cat, session_id=session_id)
                    return {"ok": True, "filler": filler, "silent_mode": self.call_engine.is_silent_mode(session_id)}
                elif cmd == "evaluate_turn":
                    return self.call_engine.evaluate_turn(
                        session_id,
                        ctrl.get("transcript", ""),
                        pause_s=float(ctrl.get("pause_s", 0.0))
                    )
            except Exception as e:
                return {"ok": False, "error": str(e)}

        # Pacote binário PCM
        seq = self._frame_counters.get(session_id, 0) + 1
        self._frame_counters[session_id] = seq

        # Processa chunk via VoiceCallEngine (VAD + Emotion Feed)
        res = self.call_engine.process_audio_chunk(session_id, raw_data)

        # Se o barge-in foi disparado, notifica o cliente imediatamente
        if res.get("barge_in_triggered"):
            ws = self._active_connections.get(session_id)
            if ws:
                try:
                    await ws.send_text(json.dumps({
                        "event": "barge_in",
                        "session_id": session_id,
                        "message": "IA interrompida pelo usuário."
                    }))
                except Exception:
                    pass

        return res

    def get_session_telemetry(self, session_id: str) -> dict[str, Any]:
        """Retorna telemetria completa da sessão de áudio em tempo real."""
        status = self.call_engine.get_session_status(session_id)
        emotion = self.call_engine.get_emotion(session_id)
        status["emotion"] = emotion
        status["frames_received"] = self._frame_counters.get(session_id, 0)
        return status


# Instância global do gerenciador de streaming em tempo real
realtime_stream_manager = RealTimeStreamManager()
