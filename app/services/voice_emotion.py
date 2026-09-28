"""
Voice Emotion Analyzer — Análise Acústica de Estado Emocional do Usuário
Inspirado em `thymia_analyzer_python` do TEN-Framework.

Analisa frames de áudio PCM do microfone do usuário (entrada STT) e extrai:
- Energia RMS (volume / intensidade)
- Variação de pitch (frequência fundamental estimada via zero-crossing)
- Ritmo de fala (palavras por segundo)
- Taxa de pausas (silêncios detectados)

IMPORTANTE: Este módulo analisa APENAS a entrada de voz do usuário.
Não altera nem interfere no TTS Fish Audio do Jarvis em absoluto.
"""
from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Deque


class EmotionalState(str, Enum):
    CALM = "calm"
    EXCITED = "excited"
    STRESSED = "stressed"
    FATIGUED = "fatigued"
    FRUSTRATED = "frustrated"
    NEUTRAL = "neutral"

    @property
    def label_pt(self) -> str:
        return {
            "calm": "Calmo",
            "excited": "Animado",
            "stressed": "Estressado",
            "fatigued": "Cansado",
            "frustrated": "Frustrado",
            "neutral": "Neutro",
        }[self.value]

    @property
    def emoji(self) -> str:
        return {
            "calm": "😌",
            "excited": "🙌",
            "stressed": "😰",
            "fatigued": "😴",
            "frustrated": "😤",
            "neutral": "😐",
        }[self.value]


@dataclass
class EmotionReading:
    state: EmotionalState
    confidence: float
    rms_energy: float
    pitch_variance: float
    speech_rate: float       # palavras por segundo estimado
    pause_ratio: float       # 0.0..1.0 — fração do tempo em silêncio
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "state_label": self.state.label_pt,
            "emoji": self.state.emoji,
            "confidence": round(self.confidence, 3),
            "rms_energy": round(self.rms_energy, 4),
            "pitch_variance": round(self.pitch_variance, 4),
            "speech_rate": round(self.speech_rate, 2),
            "pause_ratio": round(self.pause_ratio, 3),
            "timestamp": self.timestamp,
        }

    def to_llm_context(self) -> str:
        """Retorna uma string de contexto para injetar no prompt do LLM."""
        return (
            f"[Estado emocional detectado na voz do usuário: "
            f"{self.state.emoji} {self.state.label_pt} "
            f"(confiança: {self.confidence:.0%})]"
        )


class VoiceEmotionAnalyzer:
    """
    Analisador acústico de estado emocional baseado em frames de áudio PCM.

    Uso:
        analyzer = VoiceEmotionAnalyzer()
        # Para cada frame de 16-bit PCM recebido do microfone:
        analyzer.feed_frame(pcm_bytes, sample_rate=16000)
        # Para obter a leitura atual:
        reading = analyzer.get_current_reading(words_spoken=10, duration_s=5.0)
    """

    SILENCE_RMS_THRESHOLD = 0.015    # Abaixo disto é considerado silêncio

    def __init__(self, window_seconds: float = 5.0) -> None:
        self._window_seconds = window_seconds
        self._rms_history: Deque[float] = deque()
        self._zcr_history: Deque[float] = deque()   # zero-crossing rate
        self._timestamps: Deque[float] = deque()
        self._silence_frames = 0
        self._total_frames = 0

    def feed_frame(self, pcm_bytes: bytes, sample_rate: int = 16000, channels: int = 1) -> None:
        """
        Alimenta um frame de áudio PCM 16-bit signed little-endian.
        pcm_bytes: bytes do frame de áudio.
        """
        import struct
        n_samples = len(pcm_bytes) // 2
        if n_samples == 0:
            return

        samples = struct.unpack(f"<{n_samples}h", pcm_bytes[:n_samples * 2])
        norm = [s / 32768.0 for s in samples]

        # RMS energy
        rms = math.sqrt(sum(s * s for s in norm) / len(norm))

        # Zero-crossing rate (proxy de variação de pitch/frequência)
        zc = sum(1 for i in range(1, len(norm)) if norm[i - 1] * norm[i] < 0)
        zcr = zc / len(norm)

        now = time.time()
        self._rms_history.append(rms)
        self._zcr_history.append(zcr)
        self._timestamps.append(now)
        self._total_frames += 1

        if rms < self.SILENCE_RMS_THRESHOLD:
            self._silence_frames += 1

        # Limpar frames fora da janela de análise
        cutoff = now - self._window_seconds
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()
            self._rms_history.popleft()
            self._zcr_history.popleft()

    def get_current_reading(self, words_spoken: int = 0, duration_s: float = 0.0) -> EmotionReading:
        """Calcula e retorna o estado emocional atual com base no histórico de frames."""
        if not self._rms_history:
            return EmotionReading(
                state=EmotionalState.NEUTRAL,
                confidence=0.5,
                rms_energy=0.0,
                pitch_variance=0.0,
                speech_rate=0.0,
                pause_ratio=0.0,
            )

        rms_vals = list(self._rms_history)
        zcr_vals = list(self._zcr_history)

        avg_rms = sum(rms_vals) / len(rms_vals)
        rms_std = math.sqrt(sum((r - avg_rms) ** 2 for r in rms_vals) / len(rms_vals))
        avg_zcr = sum(zcr_vals) / len(zcr_vals)
        zcr_std = math.sqrt(sum((z - avg_zcr) ** 2 for z in zcr_vals) / len(zcr_vals))

        pause_ratio = self._silence_frames / max(self._total_frames, 1)
        speech_rate = (words_spoken / duration_s) if duration_s > 0.5 else 0.0

        state, confidence = self._classify(avg_rms, rms_std, avg_zcr, zcr_std, pause_ratio, speech_rate)

        return EmotionReading(
            state=state,
            confidence=confidence,
            rms_energy=avg_rms,
            pitch_variance=zcr_std,
            speech_rate=speech_rate,
            pause_ratio=pause_ratio,
        )

    def reset(self) -> None:
        """Reseta o buffer de análise (ex: ao iniciar nova sessão de chamada)."""
        self._rms_history.clear()
        self._zcr_history.clear()
        self._timestamps.clear()
        self._silence_frames = 0
        self._total_frames = 0

    def _classify(
        self,
        avg_rms: float,
        rms_std: float,
        avg_zcr: float,
        zcr_std: float,
        pause_ratio: float,
        speech_rate: float,
    ) -> tuple[EmotionalState, float]:
        """Regras heurísticas de classificação emocional."""

        # Frustração: alta energia + alta variação + fala rápida + poucas pausas
        if avg_rms > 0.15 and rms_std > 0.06 and speech_rate > 3.0 and pause_ratio < 0.2:
            return EmotionalState.FRUSTRATED, 0.78

        # Stress: alta energia + alta variação de ZCR (voz trêmula/aguda)
        if avg_rms > 0.12 and zcr_std > 0.05:
            return EmotionalState.STRESSED, 0.75

        # Animado/Excitado: energia alta + variação alta + ritmo rápido
        if avg_rms > 0.10 and speech_rate > 2.5 and rms_std > 0.04:
            return EmotionalState.EXCITED, 0.72

        # Cansado/Fatigado: energia baixa + muitas pausas + fala lenta
        if avg_rms < 0.04 and pause_ratio > 0.45 and speech_rate < 1.0:
            return EmotionalState.FATIGUED, 0.70

        # Calmo: energia moderada + variação baixa + ritmo normal
        if avg_rms < 0.10 and rms_std < 0.03 and 1.0 <= speech_rate <= 2.5:
            return EmotionalState.CALM, 0.80

        return EmotionalState.NEUTRAL, 0.60
