from __future__ import annotations

import os
import tempfile
from typing import Any

from .stt import STTService
from .tts import TTSService


class VoicePipeline:
    def __init__(self, settings: Any) -> None:
        groq_keys = getattr(settings, "groq_api_keys", []) or []
        groq_key = getattr(settings, "groq_api_key", "") or (groq_keys[0] if groq_keys else "")
        self.stt = STTService(
            language=getattr(settings, "stt_language", "pt-BR"),
            groq_api_key=groq_keys or groq_key,
            stt_provider=getattr(settings, "stt_provider", "groq"),
            oxyy_api_keys=getattr(settings, "oxyy_api_keys", []) or [],
            oxyy_base_url=getattr(settings, "oxyy_base_url", "https://api.oxyy.ai/v1"),
            oxyy_model=getattr(settings, "oxyy_stt_model", "whisper-1"),
        )
        voice = getattr(settings, "tts_voice", "pt-BR-AntonioNeural") or "pt-BR-AntonioNeural"
        tts_provider = getattr(settings, "tts_provider", "fish") or "fish"
        gemini_keys = getattr(settings, "gemini_api_keys", []) or []
        gemini_voice = getattr(settings, "tts_gemini_voice", "Charon") or "Charon"
        fish_key = getattr(settings, "fish_api_key", "") or ""
        fish_reference_id = getattr(settings, "fish_reference_id", "") or "78d40157e19a43ebb725f09fc6125585"
        fish_model = getattr(settings, "fish_tts_model", "s2.1-pro-free") or "s2.1-pro-free"
        fish_auto_emotions = bool(getattr(settings, "fish_auto_emotions", True))
        oxyy_keys = getattr(settings, "oxyy_api_keys", []) or []
        oxyy_base_url = getattr(settings, "oxyy_base_url", "https://api.oxyy.ai/v1")
        oxyy_tts_model = getattr(settings, "oxyy_tts_model", "tts-1-hd")
        oxyy_tts_voice = getattr(settings, "oxyy_tts_voice", "alloy")

        self.tts = TTSService(
            voice=voice,
            tts_provider=tts_provider,
            gemini_api_keys=gemini_keys,
            gemini_voice=gemini_voice,
            fish_api_key=fish_key,
            fish_reference_id=fish_reference_id,
            fish_model=fish_model,
            fish_auto_emotions=fish_auto_emotions,
            oxyy_api_keys=oxyy_keys,
            oxyy_base_url=oxyy_base_url,
            oxyy_model=oxyy_tts_model,
            oxyy_voice=oxyy_tts_voice,
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
            return {
                "text": text or "", "ok": bool(text), "error": error,
                "attempts": list(getattr(self.stt, "last_attempts", [])),
            }
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

    def synthesize_stream(self, text: str):
        cleaned = (text or "").strip()
        if not cleaned:
            return None
        return self.tts.generate_stream(cleaned)
