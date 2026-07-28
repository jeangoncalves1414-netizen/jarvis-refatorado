from __future__ import annotations

import json
from typing import Any

_fallback_pipeline: Any = None


def _get_pipeline(handler: Any) -> Any:
    global _fallback_pipeline
    pipeline = getattr(handler, "voice_pipeline", None)
    if pipeline is not None:
        return pipeline

    if _fallback_pipeline is None:
        try:
            from app.services.voice.pipeline import VoicePipeline
            settings = getattr(handler, "settings", None)
            _fallback_pipeline = VoicePipeline(settings=settings)
        except Exception as e:
            print(f"[Voice API] Erro ao inicializar VoicePipeline fallback: {e}")

    return _fallback_pipeline


def handle_voice_post(path: str, body: bytes, handler: Any) -> tuple[int, Any] | None:
    if path == "/api/voice/stt":
        pipeline = _get_pipeline(handler)
        if pipeline is None:
            return 503, {"ok": False, "error": "Serviço de voz indisponível."}

        if not body:
            return 200, {"ok": False, "error": "Áudio não enviado."}

        content_type = handler.headers.get("Content-Type", "")
        suffix = ".webm"
        if "wav" in content_type:
            suffix = ".wav"
        elif "mp3" in content_type:
            suffix = ".mp3"
        elif "ogg" in content_type:
            suffix = ".ogg"

        res = pipeline.transcribe_bytes(body, suffix=suffix)
        return 200, res

    if path == "/api/voice/tts":
        pipeline = _get_pipeline(handler)
        if pipeline is None:
            return 503, {"ok": False, "error": "Serviço de voz indisponível."}

        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except Exception:
            return 400, {"ok": False, "error": "JSON inválido."}

        text = payload.get("text", "").strip()
        if not text:
            return 400, {"ok": False, "error": "Texto não pode ser vazio."}

        audio_bytes = pipeline.synthesize_bytes(text)
        if audio_bytes is None:
            return 500, {"ok": False, "error": "Falha ao sintetizar o áudio."}

        return 200, audio_bytes

    return None
