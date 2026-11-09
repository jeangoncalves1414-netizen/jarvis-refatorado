"""Voice Call Session Engine (Inspirado no TEN-Framework RTC Engine).

Gerencia sessões de chamada por voz em tempo real (Full-Duplex RTC Call),
suportando VAD (Voice Activity Detection), interrupção imediata (Barge-In)
e controle de estados da ligação: IDLE -> CONNECTING -> LISTENING -> THINKING -> SPEAKING -> INTERRUPTED.
Inclui fillers de voz de baixa latência, suporte a modo silencioso, cancelamento ativo
e context stitching refinado pós-interrupção.
"""
from __future__ import annotations

import re
import time
import math
import random
import asyncio
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable

try:
    from app.services.turn_detector import TurnDetectorEngine, TurnDecision, TurnEvaluation
    TURN_DETECTOR_AVAILABLE = True
except ImportError:
    TURN_DETECTOR_AVAILABLE = False

try:
    from app.services.voice_emotion import VoiceEmotionAnalyzer, EmotionReading, EmotionalState
    VOICE_EMOTION_AVAILABLE = True
except ImportError:
    VOICE_EMOTION_AVAILABLE = False


SEARCH_FILLERS = [
    "Procurando na web...",
    "Deixa eu conferir as fontes...",
    "Dando uma olhada nos sites...",
]

THINKING_FILLERS = [
    "Só um momento...",
    "Hm, analisando aqui...",
    "Deixa eu pensar bem nisso...",
]

# Regex para comandos de cancelamento imediato por voz
CANCEL_COMMAND_REGEX = re.compile(
    r"^(?:jarvis[,.]?\s*)?(?:cancela(?:r)?(?:\s+(?:a\s+pesquisa|isso|agora|tudo))?|para(?:r)?(?:\s+(?:de\s+(?:pesquisar|buscar)|tudo|agora))?|deixa\s+pra\s+l[aá]|aborta(?:r)?)[.!]?$",
    re.IGNORECASE,
)

# Regex para ativar modo silencioso / sem narração
SILENCE_ENABLE_REGEX = re.compile(
    r"\b(?:n[aã]o\s+precisa\s+(?:narrar|falar(?:\s+nada)?(?:\s+enquanto\s+pesquisa)?)|pesquis(?:e|a)\s+em\s+sil[eê]ncio|pesquis(?:e|a)\s+sem\s+falar(?:\s+nada)?|modo\s+silencioso|ativ(?:e|ar)\s+(?:o\s+)?modo\s+silencioso|fiqu?e\s+em\s+sil[eê]ncio|sem\s+narrar)\b",
    re.IGNORECASE,
)

# Regex para desativar modo silencioso / voltar a narrar
SILENCE_DISABLE_REGEX = re.compile(
    r"\b(?:pode\s+(?:narrar|falar)|desativ(?:e|ar)\s+(?:o\s+)?modo\s+silencioso|sa(?:i|ia)\s+do\s+modo\s+silencioso|desativ(?:e|ar)\s+sil[eê]ncio)\b",
    re.IGNORECASE,
)


def is_cancel_command(text: str) -> bool:
    """Verifica se a fala do usuário é um comando de cancelamento ativo."""
    if not text:
        return False
    cleaned = text.strip()
    return bool(CANCEL_COMMAND_REGEX.match(cleaned))


def detect_silence_command(text: str) -> tuple[bool, bool]:
    """Detecta intenção de silêncio ou retorno de narração.

    Retorna (is_command, enable_silence).
    """
    if not text:
        return (False, False)
    # Verifica primeiro comandos explícitos de desativação (prevalecem sobre menções a "modo silencioso")
    if SILENCE_DISABLE_REGEX.search(text):
        return (True, False)
    if SILENCE_ENABLE_REGEX.search(text):
        return (True, True)
    return (False, False)


def build_context_stitching_prompt(interrupted_text: str, user_speech: str) -> str:
    """Mescla o trecho que o Jarvis estava dizendo antes do barge-in com a nova fala do usuário."""
    interrupted_clean = (interrupted_text or "").strip()
    user_clean = (user_speech or "").strip()
    return (
        f'[Contexto da Interrupção: Você estava dizendo: "{interrupted_clean}". '
        f'O usuário te interrompeu dizendo: "{user_clean}". '
        'Responda de forma ágil e coesa, incorporando a observação ao que já estava sendo discutido sem repetir tudo do zero.]'
    )


class CallState(str, Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"


@dataclass
class CallMetrics:
    total_duration_sec: float = 0.0
    user_speech_count: int = 0
    ai_speech_count: int = 0
    interruption_count: int = 0
    avg_latency_ms: float = 0.0


@dataclass
class CallSession:
    session_id: str
    created_at: float
    state: CallState = CallState.IDLE
    is_muted: bool = False
    silent_mode: bool = False
    metrics: CallMetrics = field(default_factory=CallMetrics)
    last_user_activity: float = field(default_factory=time.time)
    current_transcript: str = ""
    last_ai_reply: str = ""
    words_spoken: int = 0
    last_interrupted_text: str = ""
    last_filler: str = ""
    filler_index: int = 0
    last_emotion: dict = field(default_factory=dict)
    last_turn_eval: dict = field(default_factory=dict)


class VoiceCallEngine:
    """Motor de gerenciamento de chamadas por voz em tempo real (TEN-Framework RTC Architecture)."""

    def __init__(self, voice_pipeline: Any = None, llm_service: Any = None) -> None:
        self.voice_pipeline = voice_pipeline
        self.llm_service = llm_service
        self.active_sessions: dict[str, CallSession] = {}
        self.vad_threshold: float = 0.02  # Nível de energia RMS para VAD
        self._turn_detector = TurnDetectorEngine() if TURN_DETECTOR_AVAILABLE else None
        # One emotion analyzer per session (keyed by session_id)
        self._emotion_analyzers: dict[str, Any] = {}

    def start_call(self, session_id: str = "") -> CallSession:
        """Inicia uma nova sessão de chamada por voz."""
        if not session_id:
            session_id = f"call_{int(time.time())}"

        session = CallSession(
            session_id=session_id,
            created_at=time.time(),
            state=CallState.CONNECTING
        )
        self.active_sessions[session_id] = session
        session.state = CallState.LISTENING

        # Initialise per-session emotion analyzer
        if VOICE_EMOTION_AVAILABLE:
            self._emotion_analyzers[session_id] = VoiceEmotionAnalyzer(window_seconds=8.0)

        return session

    def process_audio_chunk(self, session_id: str, pcm_bytes: bytes) -> dict[str, Any]:
        """Processa um bloco de áudio PCM recebido do microfone do usuário e executa VAD."""
        session = self.active_sessions.get(session_id)
        if not session or session.state == CallState.IDLE:
            return {"ok": False, "error": "Sessão de chamada não encontrada ou inativa."}

        session.last_user_activity = time.time()

        # Calcula energia RMS do áudio
        rms = self._calculate_rms(pcm_bytes)
        is_speech = rms >= self.vad_threshold

        # Regra de Interrupção Imediata (Barge-In) inspirada no TEN-Framework:
        # Se a IA está no estado SPEAKING e o usuário começa a falar (is_speech=True),
        # a resposta da IA é cancelada imediatamente!
        was_interrupted = False
        if session.state == CallState.SPEAKING and is_speech:
            session.state = CallState.INTERRUPTED
            session.metrics.interruption_count += 1
            was_interrupted = True
            # Cancela a reprodução corrente
            session.state = CallState.LISTENING

        if is_speech and session.state != CallState.THINKING:
            session.state = CallState.LISTENING

        # Feed emotion analyzer with PCM frame
        if is_speech and session_id in self._emotion_analyzers:
            self._emotion_analyzers[session_id].feed_frame(pcm_bytes)

        return {
            "ok": True,
            "session_id": session_id,
            "state": session.state.value,
            "rms_energy": round(rms, 4),
            "is_speech": is_speech,
            "barge_in_triggered": was_interrupted
        }

    def interrupt_call(self, session_id: str, interrupted_text: str = "") -> dict[str, Any]:
        """Força a interrupção da fala da IA pelo usuário (barge-in manual)."""
        session = self.active_sessions.get(session_id)
        if not session:
            return {"ok": False, "error": "Sessão não encontrada."}

        session.state = CallState.INTERRUPTED
        session.metrics.interruption_count += 1
        if interrupted_text:
            session.last_interrupted_text = interrupted_text
        session.state = CallState.LISTENING
        return {
            "ok": True,
            "session_id": session_id,
            "state": session.state.value,
            "interrupted": True,
            "interrupted_text": session.last_interrupted_text,
        }

    def cancel_active_action(self, session_id: str) -> dict[str, Any]:
        """Cancela a ação em andamento (pesquisa, thinking, loop agêntico) e retorna confirmação por voz."""
        session = self.active_sessions.get(session_id)
        if not session:
            return {"ok": False, "error": "Sessão não encontrada."}

        session.state = CallState.LISTENING
        return {
            "ok": True,
            "session_id": session_id,
            "state": session.state.value,
            "cancelled": True,
            "confirmation": "Cancelado. O que você gostaria de fazer agora?",
        }

    def get_filler(self, category: str = "thinking", session_id: str = "", index: int | None = None) -> str:
        """Retorna um filler contextual em pt-BR de baixa latência.

        Se a sessão estiver em silent_mode, retorna string vazia.
        """
        session = self.active_sessions.get(session_id)
        if session and session.silent_mode:
            return ""

        cat = (category or "").lower().strip()
        if cat in ("search", "web", "pesquisa", "searching"):
            pool = SEARCH_FILLERS
        else:
            pool = THINKING_FILLERS

        if index is not None:
            chosen = pool[index % len(pool)]
        elif session:
            chosen = pool[session.filler_index % len(pool)]
            session.filler_index += 1
            session.last_filler = chosen
        else:
            chosen = random.choice(pool)

        return chosen

    def set_silent_mode(self, session_id: str, silent: bool = True) -> dict[str, Any]:
        """Define o modo silencioso (silence / progress narration off) para a sessão."""
        session = self.active_sessions.get(session_id)
        if not session:
            return {"ok": False, "error": "Sessão não encontrada."}
        session.silent_mode = bool(silent)
        return {"ok": True, "session_id": session_id, "silent_mode": session.silent_mode}

    def toggle_silent_mode(self, session_id: str) -> dict[str, Any]:
        """Alterna o modo silencioso na sessão."""
        session = self.active_sessions.get(session_id)
        if not session:
            return {"ok": False, "error": "Sessão não encontrada."}
        session.silent_mode = not session.silent_mode
        return {"ok": True, "session_id": session_id, "silent_mode": session.silent_mode}

    def is_silent_mode(self, session_id: str) -> bool:
        """Retorna se a sessão está com silent_mode ativo."""
        session = self.active_sessions.get(session_id)
        return bool(session and session.silent_mode)

    def build_context_stitching_prompt(self, interrupted_text: str, user_speech: str) -> str:
        """Gera o prompt com context stitching refinado pós-interrupção."""
        return build_context_stitching_prompt(interrupted_text, user_speech)

    def is_cancel_command(self, text: str) -> bool:
        """Verifica se o texto é um comando de cancelamento ativo por voz."""
        return is_cancel_command(text)

    def detect_silence_command(self, text: str) -> tuple[bool, bool]:
        """Detecta comandos de alternância de modo silencioso."""
        return detect_silence_command(text)

    def toggle_mute(self, session_id: str) -> dict[str, Any]:
        """Alterna o estado de Mute do microfone."""
        session = self.active_sessions.get(session_id)
        if not session:
            return {"ok": False, "error": "Sessão não encontrada."}

        session.is_muted = not session.is_muted
        return {"ok": True, "session_id": session_id, "is_muted": session.is_muted}

    def evaluate_turn(self, session_id: str, transcript: str, pause_s: float = 0.0) -> dict[str, Any]:
        """Avalia se o turno de fala do usuário está completo (FINISHED/UNFINISHED/WAIT)."""
        session = self.active_sessions.get(session_id)
        if not session:
            return {"ok": False, "error": "Sessão não encontrada."}

        if not self._turn_detector:
            return {"ok": True, "decision": "finished", "confidence": 1.0, "reason": "Turn detection indisponível (fallback)."}

        eval_result = self._turn_detector.evaluate(transcript, pause_duration_s=pause_s)
        session.last_turn_eval = eval_result.to_dict()
        session.current_transcript = transcript
        return {"ok": True, **eval_result.to_dict()}

    def get_emotion(self, session_id: str, words_spoken: int = 0) -> dict[str, Any]:
        """Retorna o estado emocional atual do usuário nesta sessão."""
        session = self.active_sessions.get(session_id)
        if not session:
            return {"ok": False, "error": "Sessão não encontrada."}

        analyzer = self._emotion_analyzers.get(session_id)
        if not analyzer:
            return {"ok": True, "state": "neutral", "state_label": "Neutro", "emoji": "😐", "confidence": 0.5}

        duration_s = time.time() - session.created_at
        reading = analyzer.get_current_reading(words_spoken=words_spoken, duration_s=duration_s)
        session.last_emotion = reading.to_dict()
        return {"ok": True, **reading.to_dict()}

    def end_call(self, session_id: str) -> dict[str, Any]:
        """Encerra a sessão de chamada por voz."""
        session = self.active_sessions.get(session_id)
        if not session:
            return {"ok": False, "error": "Sessão não encontrada."}

        duration = round(time.time() - session.created_at, 2)
        session.metrics.total_duration_sec = duration

        # Get final emotion reading before teardown
        final_emotion = {}
        analyzer = self._emotion_analyzers.pop(session_id, None)
        if analyzer and VOICE_EMOTION_AVAILABLE:
            reading = analyzer.get_current_reading(words_spoken=session.words_spoken, duration_s=duration)
            final_emotion = reading.to_dict()

        session.state = CallState.IDLE
        del self.active_sessions[session_id]

        return {
            "ok": True,
            "session_id": session_id,
            "duration_sec": duration,
            "final_emotion": final_emotion,
            "metrics": {
                "user_speech_count": session.metrics.user_speech_count,
                "ai_speech_count": session.metrics.ai_speech_count,
                "interruption_count": session.metrics.interruption_count
            }
        }

    def get_session_status(self, session_id: str) -> dict[str, Any]:
        """Retorna o status completo da chamada, incluindo modo silencioso, emoção e último turno."""
        session = self.active_sessions.get(session_id)
        if not session:
            return {"ok": False, "error": "Sessão inativa."}

        return {
            "ok": True,
            "session_id": session_id,
            "state": session.state.value,
            "is_muted": session.is_muted,
            "silent_mode": session.silent_mode,
            "last_interrupted_text": session.last_interrupted_text,
            "duration_sec": round(time.time() - session.created_at, 1),
            "last_emotion": session.last_emotion,
            "last_turn_eval": session.last_turn_eval,
            "metrics": {
                "user_speech_count": session.metrics.user_speech_count,
                "ai_speech_count": session.metrics.ai_speech_count,
                "interruption_count": session.metrics.interruption_count
            }
        }

    def _calculate_rms(self, pcm_bytes: bytes) -> float:
        """Calcula a energia média RMS do bloco de áudio PCM 16-bit."""
        if not pcm_bytes or len(pcm_bytes) < 2:
            return 0.0

        try:
            import struct
            count = len(pcm_bytes) // 2
            format_str = f"<{count}h"
            shorts = struct.unpack(format_str, pcm_bytes[:count * 2])
            sum_squares = sum(s * s for s in shorts)
            mean_square = sum_squares / count
            rms = math.sqrt(mean_square) / 32768.0
            return rms
        except Exception:
            return 0.0


# Instância global do motor de chamadas por voz
voice_call_engine = VoiceCallEngine()
