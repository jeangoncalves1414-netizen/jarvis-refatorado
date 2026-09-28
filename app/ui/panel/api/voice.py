from __future__ import annotations

import json
from typing import Any

from app.core.diagnostics import record as diagnostic_record

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
    if path == "/api/voice/identity/model":
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except Exception:
            return 400, {"ok": False, "error": "JSON inválido."}
        from app.services.identity import IdentityService

        if payload.get("action") == "status":
            return 200, {"ok": True, **IdentityService.voice_model_status()}
        if payload.get("action") == "install":
            result = IdentityService.install_voice_model()
            diagnostic_record("voice.identity", "model_installed" if result.get("ok") else "model_install_failed", "INFO" if result.get("ok") else "ERROR")
            return (200 if result.get("ok") else 500), result
        return 400, {"ok": False, "error": "Ação de modelo inválida."}

    if path == "/api/diagnostics/event":
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
            component = str(payload.get("component", "browser"))
            event = str(payload.get("event", "unknown"))
            level = str(payload.get("level", "INFO"))
            context = payload.get("context", {})
            diagnostic_record(component, event, level, **(context if isinstance(context, dict) else {}))
            return 200, {"ok": True}
        except Exception:
            return 400, {"ok": False, "error": "Evento de diagnóstico inválido."}

    if path == "/api/voice/stt":
        request_context = {
            "turn_id": handler.headers.get("X-Jarvis-Turn-ID", "")[:80] or None,
            "session_id": handler.headers.get("X-Jarvis-Session-ID", "")[:80] or None,
        }
        pipeline = _get_pipeline(handler)
        if pipeline is None:
            diagnostic_record("voice.api", "stt_pipeline_unavailable", "ERROR", **request_context)
            return 503, {"ok": False, "error": "Serviço de voz indisponível."}

        if not body:
            diagnostic_record("voice.api", "stt_empty_audio", "WARN", **request_context)
            return 200, {"ok": False, "error": "Áudio não enviado."}

        content_type = handler.headers.get("Content-Type", "")
        suffix = ".webm"
        if "wav" in content_type:
            suffix = ".wav"
        elif "mp3" in content_type:
            suffix = ".mp3"
        elif "ogg" in content_type:
            suffix = ".ogg"

        try:
            res = pipeline.transcribe_bytes(body, suffix=suffix)
        except Exception as exc:
            diagnostic_record("voice.api", "stt_unhandled_exception", "ERROR", error=type(exc).__name__, suffix=suffix, bytes=len(body), **request_context)
            return 500, {"ok": False, "error": "Falha interna ao transcrever o áudio."}
        if res.get("ok"):
            from app.services.identity import IdentityService
            speaker = IdentityService.identify_audio_bytes(body, content_type)
            res["speaker"] = speaker
            diagnostic_record("voice.identity", "turn_identified" if speaker.get("matched") else "turn_unknown", "INFO", confidence=speaker.get("confidence"), **request_context)
        diagnostic_record(
            "voice.api",
            "stt_result" if res.get("ok") else "stt_failed",
            "INFO" if res.get("ok") else "WARN",
            suffix=suffix,
            bytes=len(body),
            error=res.get("error") if not res.get("ok") else None,
            attempts=res.get("attempts", []),
            **request_context,
        )
        return 200, res

    if path == "/api/voice/tts":
        pipeline = _get_pipeline(handler)
        if pipeline is None:
            diagnostic_record("voice.api", "tts_pipeline_unavailable", "ERROR")
            return 503, {"ok": False, "error": "Serviço de voz indisponível."}

        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except Exception:
            return 400, {"ok": False, "error": "JSON inválido."}

        text = payload.get("text", "").strip()
        if not text:
            diagnostic_record("voice.api", "tts_empty_text", "WARN")
            return 400, {"ok": False, "error": "Texto não pode ser vazio."}

        audio_bytes = pipeline.synthesize_bytes(text)
        if audio_bytes is None:
            diagnostic_record("voice.api", "tts_failed", "ERROR", characters=len(text))
            return 500, {"ok": False, "error": "Falha ao sintetizar o áudio."}

        return 200, audio_bytes

    return None


def handle_voice_stream(path: str, body: bytes, handler: Any):
    """Entrega o streaming do provider TTS ativo sem expor chaves ao navegador."""
    if path != "/api/voice/tts/stream":
        return None
    pipeline = _get_pipeline(handler)
    if pipeline is None:
        return None
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except Exception:
        return None
    text = str(payload.get("text", "")).strip()
    if not text:
        return None
    return pipeline.synthesize_stream(text)


def handle_voice_realtime_stream(path: str, body: bytes, handler: Any):
    """Endpoint para streaming de voz em tempo real (STT + LLM + TTS)."""
    if path != "/api/voice/realtime/stream":
        return None

    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except Exception:
        return None

    action = payload.get("action")
    session_id = payload.get("session_id")

    if action == "start":
        # Iniciar sessão de streaming
        from app.services.voice.streaming_pipeline import RealtimeVoicePipeline
        from app.services.voice.stt.streaming import StreamingSTTEngine
        from app.services.voice.tts.streaming import StreamingTTSEngine

        settings = getattr(handler, "settings", None)
        stt = StreamingSTTEngine(
            groq_api_key=getattr(settings, "groq_api_key", ""),
            oxyy_api_keys=getattr(settings, "oxyy_api_keys", []),
            language=getattr(settings, "stt_language", "pt-BR"),
            provider=getattr(settings, "stt_provider", "groq"),
        )
        tts = StreamingTTSEngine(
            fish_api_key=getattr(settings, "fish_api_key", ""),
            fish_reference_id=getattr(settings, "fish_reference_id", ""),
            fish_model=getattr(settings, "fish_tts_model", "s2.1-pro-free"),
            oxyy_api_keys=getattr(settings, "oxyy_api_keys", []),
            oxyy_base_url=getattr(settings, "oxyy_base_url", "https://api.oxyy.ai/v1"),
            oxyy_model=getattr(settings, "oxyy_tts_model", "tts-1-hd"),
            oxyy_voice=getattr(settings, "oxyy_tts_voice", "alloy"),
            provider=getattr(settings, "tts_provider", "fish"),
        )

        pipeline = RealtimeVoicePipeline(
            stt_engine=stt,
            tts_engine=tts,
            llm_service=getattr(handler, "orchestrator", None),
        )

        # Armazenar pipeline na sessão (simplificado - em produção usar cache/dict)
        if not hasattr(handler, "_realtime_sessions"):
            handler._realtime_sessions = {}
        handler._realtime_sessions[session_id] = pipeline

        return 200, {"ok": True, "session_id": session_id, "state": pipeline.state.value}

    if action == "stop":
        # Parar sessão
        if hasattr(handler, "_realtime_sessions") and session_id in handler._realtime_sessions:
            pipeline = handler._realtime_sessions.pop(session_id)
            pipeline.stop()
            return 200, {"ok": True, "state": "idle"}

    if action == "interrupt":
        # Interromper fala atual
        if hasattr(handler, "_realtime_sessions") and session_id in handler._realtime_sessions:
            pipeline = handler._realtime_sessions[session_id]
            pipeline.interrupt()
            return 200, {"ok": True, "state": pipeline.state.value}

    if action == "status":
        # Status da sessão
        if hasattr(handler, "_realtime_sessions") and session_id in handler._realtime_sessions:
            pipeline = handler._realtime_sessions[session_id]
            return 200, {
                "ok": True,
                "state": pipeline.state.value,
                "transcript": pipeline.current_transcript,
            }

    return None
