"""
Meeting Assistant Service (inspired by Brahma AI Lite meeting_assistant.py)
Records audio from active meetings and uses LLM to generate:
- Transcription summary
- Key topics discussed
- Action items / follow-ups

Uses built-in sounddevice (already in requirements) and Jarvis's own LLMService.
"""
from __future__ import annotations

import io
import json
import threading
import time
import wave
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

DATA_DIR = Path("data/meetings")
DATA_DIR.mkdir(parents=True, exist_ok=True)

try:
    import sounddevice as sd
    AUDIO_OK = True
except Exception:
    AUDIO_OK = False


class MeetingSession:
    """Gerencia a gravação de uma reunião e gera ata via LLM."""

    SAMPLE_RATE = 16000
    CHANNELS = 1

    def __init__(self, title: str = "", llm_service: Any = None) -> None:
        self.title = title or f"Reunião {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        self.llm = llm_service
        self._frames: list[bytes] = []
        self._recording = False
        self._thread: threading.Thread | None = None
        self._start_ts: float = 0.0
        self._end_ts: float = 0.0
        self._audio_file: Path | None = None

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self, on_started: Callable[[], None] | None = None) -> dict[str, Any]:
        if not AUDIO_OK:
            return {"ok": False, "error": "sounddevice não instalado. Execute: pip install sounddevice"}
        if self._recording:
            return {"ok": False, "error": "Gravação já em andamento."}

        self._frames.clear()
        self._recording = True
        self._start_ts = time.time()

        def _record() -> None:
            try:
                with sd.InputStream(
                    samplerate=self.SAMPLE_RATE,
                    channels=self.CHANNELS,
                    dtype="int16",
                    callback=self._audio_callback,
                ):
                    while self._recording:
                        sd.sleep(100)
            except Exception as exc:
                print(f"[MeetingAssistant] Erro na gravação: {exc}")
                self._recording = False

        self._thread = threading.Thread(target=_record, daemon=True)
        self._thread.start()

        if on_started:
            on_started()

        return {"ok": True, "started_at": datetime.now().isoformat(), "title": self.title}

    def _audio_callback(self, indata, frames, time_info, status) -> None:
        if self._recording:
            self._frames.append(bytes(indata))

    def stop(self) -> dict[str, Any]:
        if not self._recording:
            return {"ok": False, "error": "Nenhuma gravação ativa."}

        self._recording = False
        self._end_ts = time.time()
        duration_s = self._end_ts - self._start_ts

        if self._thread:
            self._thread.join(timeout=2)

        audio_data = b"".join(self._frames)
        if not audio_data:
            return {"ok": False, "error": "Nenhum áudio capturado."}

        # Salva arquivo WAV
        fname = f"meeting_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
        self._audio_file = DATA_DIR / fname
        with wave.open(str(self._audio_file), "wb") as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(2)  # int16 = 2 bytes
            wf.setframerate(self.SAMPLE_RATE)
            wf.writeframes(audio_data)

        return {
            "ok": True,
            "audio_file": str(self._audio_file),
            "duration_seconds": round(duration_s, 1),
            "title": self.title,
        }

    def generate_minutes(self, transcript_hint: str = "") -> dict[str, Any]:
        """Usa LLM para gerar ata completa da reunião."""
        if not self.llm:
            return {"ok": False, "error": "LLMService não configurado."}

        context = transcript_hint or (
            f"Reunião gravada: '{self.title}'. "
            f"Duração: {round(self._end_ts - self._start_ts, 0):.0f}s."
        )

        prompt = (
            f"Você é um assistente especializado em atas de reunião corporativa.\n"
            f"Contexto da reunião: {context}\n\n"
            f"Gere uma ata profissional com:\n"
            f"1. **Resumo Executivo** (2-3 frases)\n"
            f"2. **Principais Tópicos Discutidos** (lista)\n"
            f"3. **Decisões Tomadas** (lista)\n"
            f"4. **Action Items** (lista com responsáveis e prazo se mencionados)\n"
            f"5. **Próximos Passos**\n"
        )

        try:
            minutes = self.llm.ask(prompt)
            return {
                "ok": True,
                "title": self.title,
                "minutes": minutes,
                "generated_at": datetime.now().isoformat(),
                "audio_file": str(self._audio_file) if self._audio_file else None,
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


# Sessão global única (uma reunião por vez)
_active_session: MeetingSession | None = None


def start_meeting(title: str = "", llm_service: Any = None) -> dict[str, Any]:
    global _active_session
    if _active_session and _active_session.is_recording:
        return {"ok": False, "error": "Reunião em andamento. Pare a atual antes de iniciar uma nova."}
    _active_session = MeetingSession(title=title, llm_service=llm_service)
    return _active_session.start()


def stop_meeting() -> dict[str, Any]:
    global _active_session
    if not _active_session:
        return {"ok": False, "error": "Nenhuma reunião ativa."}
    return _active_session.stop()


def get_meeting_minutes(transcript_hint: str = "") -> dict[str, Any]:
    global _active_session
    if not _active_session:
        return {"ok": False, "error": "Nenhuma reunião finalizada para gerar ata."}
    return _active_session.generate_minutes(transcript_hint)


def get_meeting_status() -> dict[str, Any]:
    global _active_session
    if not _active_session:
        return {"active": False, "message": "Nenhuma reunião registrada."}
    return {
        "active": _active_session.is_recording,
        "title": _active_session.title,
        "audio_available": AUDIO_OK,
    }
