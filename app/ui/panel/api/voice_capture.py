"""Endpoints locais da captura de microfone no backend (ligação por voz no PC)."""
from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import parse_qs, urlsplit

from app.core.diagnostics import record as diagnostic_record
from app.services.voice import mic_capture
from app.ui.panel.api.voice import _get_pipeline

_LOOPBACK = {"127.0.0.1", "::1", "::ffff:127.0.0.1"}
_FORBIDDEN = (403, {"ok": False, "error": "A captura de microfone do PC só aceita pedidos locais."})


def _is_local(handler: Any) -> bool:
    client = handler.client_address[0] if getattr(handler, "client_address", None) else ""
    return client in _LOOPBACK


def _transcriber(handler: Any):
    def transcribe(wav: bytes) -> dict[str, Any]:
        pipeline = _get_pipeline(handler)
        if pipeline is None:
            return {"ok": False, "error": "Serviço de voz indisponível."}
        return pipeline.transcribe_bytes(wav, suffix=".wav")
    return transcribe


def capture_component_status() -> dict[str, str]:
    """Estado para a tela de Integrações: 'desligado, motivo' quando o PC não pode capturar."""
    from app.storage.runtime_settings import get_mic_settings
    ok, reason = mic_capture.availability()
    engine = get_mic_settings()["engine"]
    if not ok:
        return {"status": "off", "reason": f"Desligado: {reason}"}
    if engine == "browser":
        return {"status": "off", "reason": "Desligado: motor de detecção definido como Navegador nas Configurações."}
    if mic_capture.capture.active:
        return {"status": "healthy", "reason": "Ouvindo pelo microfone do PC (SpeechRecognition)."}
    return {"status": "healthy", "reason": "Pronto: a ligação por voz no PC usa SpeechRecognition + PyAudio."}


def _query(handler: Any) -> dict[str, list[str]]:
    return parse_qs(urlsplit(handler.path).query)


def handle_capture_get(parts: list[str], handler: Any) -> tuple[int, dict[str, Any]] | None:
    if parts[:3] != ["api", "voice", "capture"] or len(parts) != 4:
        return None
    if not _is_local(handler):
        return _FORBIDDEN
    action = parts[3]
    if action == "status":
        ok, reason = mic_capture.availability()
        from app.storage.runtime_settings import get_mic_settings
        return 200, {"ok": True, "available": ok, "reason": reason, "engine": get_mic_settings()["engine"], **mic_capture.capture.status()}
    if action == "devices":
        ok, reason = mic_capture.availability()
        if not ok:
            return 200, {"ok": True, "available": False, "reason": reason, "devices": [], "default_index": None}
        try:
            return 200, {"ok": True, "available": True, "reason": "", **mic_capture.list_devices()}
        except Exception as exc:  # noqa: BLE001
            return 200, {"ok": True, "available": False, "reason": f"Não foi possível listar os microfones: {exc}", "devices": [], "default_index": None}
    if action == "events":
        query = _query(handler)
        try:
            after = int(query.get("after", ["0"])[0])
            wait = float(query.get("wait", ["0"])[0])
        except ValueError:
            return 400, {"ok": False, "error": "Parâmetros inválidos."}
        return 200, {"ok": True, **mic_capture.capture.events(after, wait)}
    return None


def _start_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    from app.storage.runtime_settings import get_mic_settings
    saved = get_mic_settings()
    return {
        "sensitivity": float(payload.get("sensitivity", saved["sensitivity"])),
        "silence_ms": float(payload.get("silence_ms", saved["silence_ms"])),
        "gain": float(payload.get("gain", saved["gain"])),
        "device_name": str(payload.get("device_name", saved["device_name"]) or ""),
    }


def _run_test(handler: Any, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    capture = mic_capture.capture
    if capture.active:
        return 409, {"ok": False, "error": "O microfone do PC está em uso (ligação por voz ativa). Encerre a ligação para testar."}
    started = capture.start(**_start_kwargs(payload), transcribe=_transcriber(handler))
    if not started.get("ok"):
        return 200, {"ok": False, "error": started.get("error", "Não foi possível abrir o microfone.")}
    after = int(started.get("seq", 0))
    deadline = time.monotonic() + 15.0
    result: dict[str, Any] = {"ok": False, "error": "Nenhuma fala detectada em 15 s.", "threshold": started.get("threshold"), "base_threshold": started.get("base_threshold"), "peak": 0}
    try:
        while time.monotonic() < deadline:
            data = capture.events(after, 0.5)
            for event in data["events"]:
                after = max(after, event["seq"])
                if event["type"] == "calibrated":
                    result["threshold"] = event["threshold"]
                elif event["type"] == "level":
                    result["peak"] = max(result["peak"], event["level"])
                    result["threshold"] = event["threshold"]
                elif event["type"] == "transcript":
                    result.update(ok=True, error="", text=event["text"], stt_ms=event["stt_ms"])
                    return 200, result
                elif event["type"] == "empty":
                    result.update(error=event.get("error") or "A fala não pôde ser transcrita.", stt_ms=event.get("stt_ms"))
                    return 200, result
                elif event["type"] == "error":
                    result["error"] = event.get("message", "Falha no microfone.")
                    return 200, result
            if not data["active"] and not data["events"]:
                break
        return 200, result
    finally:
        capture.stop()


def handle_capture_post(path: str, body: bytes, handler: Any) -> tuple[int, dict[str, Any]] | None:
    if not path.startswith("/api/voice/capture/"):
        return None
    if not _is_local(handler):
        return _FORBIDDEN
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except Exception:
        return 400, {"ok": False, "error": "JSON inválido."}
    if not isinstance(payload, dict):
        return 400, {"ok": False, "error": "JSON inválido."}
    capture = mic_capture.capture
    action = path.rsplit("/", 1)[-1]
    if action == "start":
        try:
            kwargs = _start_kwargs(payload)
        except (TypeError, ValueError):
            return 400, {"ok": False, "error": "Parâmetros inválidos."}
        result = capture.start(**kwargs, transcribe=_transcriber(handler), semantic_turns=payload.get("semantic_turns") is True)
        diagnostic_record("voice.capture", "start" if result.get("ok") else "start_failed", "INFO" if result.get("ok") else "WARN", error=result.get("error"))
        return 200, result
    if action == "stop":
        capture.stop()
        diagnostic_record("voice.capture", "stop", "INFO")
        return 200, {"ok": True}
    if action == "playback":
        capture.set_playback(bool(payload.get("active")))
        return 200, {"ok": True}
    if action == "test":
        try:
            return _run_test(handler, payload)
        except (TypeError, ValueError):
            return 400, {"ok": False, "error": "Parâmetros inválidos."}
    return None
