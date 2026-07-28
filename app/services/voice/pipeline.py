from __future__ import annotations

import os
import tempfile
from typing import Any

from .stt import STTService
from .tts import TTSService


class VoicePipeline:
    def __init__(self, settings: Any) -> None:
        self.stt = STTService(
            language=getattr(settings, "stt_language", "pt-BR"),
            groq_api_key=getattr(settings, "groq_api_key", ""),
        )
        voice = getattr(settings, "tts_voice", "pt-BR-AntonioNeural") or "pt-BR-AntonioNeural"
        tts_provider = getattr(settings, "tts_provider", "gemini") or "gemini"
        gemini_keys = getattr(settings, "gemini_api_keys", []) or []
        gemini_voice = getattr(settings, "tts_gemini_voice", "Charon") or "Charon"

        self.tts = TTSService(
            voice=voice,
            tts_provider=tts_provider,
            gemini_api_keys=gemini_keys,
            gemini_voice=gemini_voice,
        )

    def transcribe_bytes(self, audio_bytes: bytes, suffix: str = ".webm") -> dict[str, Any]:
        if not audio_bytes:
            return {"text": "", "ok": False, "error": "Nenhum áudio recebido."}

        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"jarvis_upload_{os.urandom(4).hex()}{suffix}")
        try:
            with open(temp_path, "wb") as f:
                f.write(audio_bytes)
            text, error = self.stt.transcribe_file(temp_path)
            return {"text": text or "", "ok": bool(text), "error": error}
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass

    def synthesize_bytes(self, text: str) -> bytes | None:
        cleaned = (text or "").strip()
        if not cleaned:
            return None
        return self.tts.generate_bytes(cleaned)
