import json
import os
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.core import diagnostics
from app.ui.panel.api import voice as voice_api


def test_diagnostics_writes_safe_private_metadata(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(diagnostics, "_DIRECTORY", tmp_path / "diagnostics")

    diagnostics.record(
        "voice.browser",
        "stt_failed",
        "ERROR",
        error="provider_error",
        api_key="must-not-be-written",
        transcript="fala particular",
        bytes=1200,
    )

    files = list((tmp_path / "diagnostics").glob("*.jsonl"))
    assert len(files) == 1
    entry = json.loads(files[0].read_text(encoding="utf-8"))
    assert entry["component"] == "voice.browser"
    assert entry["level"] == "ERROR"
    assert entry["context"] == {"error": "provider_error", "bytes": 1200}


def test_diagnostics_removes_expired_files(tmp_path, monkeypatch) -> None:
    directory = tmp_path / "diagnostics"
    directory.mkdir()
    old = directory / "jarvis-2000-01-01.jsonl"
    old.write_text("old\n", encoding="utf-8")
    expired = time.time() - (30 * 24 * 60 * 60)
    os.utime(old, (expired, expired))
    monkeypatch.setattr(diagnostics, "_DIRECTORY", directory)

    diagnostics.record("voice.api", "stt_result")

    assert not old.exists()


def test_stt_diagnostic_keeps_voice_turn_correlation(monkeypatch) -> None:
    recorded: list[tuple] = []
    monkeypatch.setattr(voice_api, "diagnostic_record", lambda *args, **kwargs: recorded.append((args, kwargs)))
    pipeline = MagicMock()
    pipeline.transcribe_bytes.return_value = {"ok": True, "text": "ok", "error": None}
    handler = SimpleNamespace(
        voice_pipeline=pipeline,
        headers={"Content-Type": "audio/webm", "X-Jarvis-Turn-ID": "turn-123", "X-Jarvis-Session-ID": "session-456"},
    )

    status, payload = voice_api.handle_voice_post("/api/voice/stt", b"audio", handler)

    assert status == 200 and payload["ok"] is True
    assert recorded[-1][0][:3] == ("voice.api", "stt_result", "INFO")
    assert recorded[-1][1]["turn_id"] == "turn-123"
    assert recorded[-1][1]["session_id"] == "session-456"
