from __future__ import annotations

import asyncio
import json

import pytest

from app.services.voice import wake_word
from app.storage import runtime_settings
from app.ui.panel import server


class FakeDetector:
    def __init__(self, running: bool) -> None:
        self._running = running

    def is_running(self) -> bool:
        return self._running


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime_settings, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(runtime_settings, "RUNTIME_SETTINGS_FILE", str(tmp_path / "runtime.json"))
    monkeypatch.setattr(wake_word, "VOSK_AVAILABLE", True)
    monkeypatch.setattr(wake_word, "PYAUDIO_AVAILABLE", True)
    monkeypatch.setattr(server, "_wake_word_enabled", True)
    monkeypatch.setattr(server, "_wake_word_detector", None)


def test_status_is_active_only_with_enabled_and_running_detector(monkeypatch):
    status = server._wake_word_status()
    assert status["available"] is True and status["enabled"] is True
    assert status["running"] is False and status["active"] is False

    monkeypatch.setattr(server, "_wake_word_detector", FakeDetector(running=True))
    status = server._wake_word_status()
    assert status["running"] is True and status["active"] is True
    assert status["phrase"] == "ei assistente"

    monkeypatch.setattr(server, "_wake_word_enabled", False)
    status = server._wake_word_status()
    assert status["running"] is True and status["active"] is False


def test_status_reports_unavailable_detector(monkeypatch):
    monkeypatch.setattr(wake_word, "PYAUDIO_AVAILABLE", False)
    monkeypatch.setattr(server, "_wake_word_detector", FakeDetector(running=False))
    status = server._wake_word_status()
    assert status["available"] is False and status["active"] is False


def test_broadcast_sends_event_with_profile_phrase(monkeypatch):
    runtime_settings.set_agent_profile({"name": "Nova", "style": "", "wake_phrase": ""})
    sent: list[str] = []

    class FakeSocket:
        async def send(self, message: str) -> None:
            sent.append(message)

    class BrokenSocket:
        async def send(self, message: str) -> None:
            raise ConnectionError("fechado")

    broken = BrokenSocket()
    monkeypatch.setattr(server, "_ws_clients", {FakeSocket(), broken})
    asyncio.run(server._broadcast_wake_word())

    assert [json.loads(message) for message in sent] == [{"type": "wake_word", "phrase": "ei nova"}]
    assert broken not in server._ws_clients
