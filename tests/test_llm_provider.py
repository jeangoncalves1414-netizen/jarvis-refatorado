from __future__ import annotations

import json
import os
import tempfile

import pytest

from app.agent.tools.whiteboard_layout import board_bottom, estimate_text_height, resolve_y
from app.config import load_settings
from app.services.llm import LLMService
from app.storage import runtime_settings


@pytest.fixture
def isolated_runtime_settings(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "runtime_settings.json")
        monkeypatch.setattr(runtime_settings, "DATA_DIR", tmp)
        monkeypatch.setattr(runtime_settings, "RUNTIME_SETTINGS_FILE", path)
        yield path


def test_get_and_set_llm_provider(isolated_runtime_settings: str) -> None:
    assert runtime_settings.get_llm_provider("gemini") == "gemini"
    runtime_settings.set_llm_provider("groq")
    assert runtime_settings.get_llm_provider("gemini") == "groq"
    with open(isolated_runtime_settings, encoding="utf-8") as f:
        data = json.load(f)
    assert data["llm_provider"] == "groq"


def test_invalid_provider_raises(isolated_runtime_settings: str) -> None:
    with pytest.raises(ValueError):
        runtime_settings.set_llm_provider("openai")


def test_llm_service_active_provider(isolated_runtime_settings: str) -> None:
    settings = load_settings()
    llm = LLMService(settings=settings)
    runtime_settings.set_llm_provider("groq")
    assert llm.get_active_provider() == "groq"
    assert llm.get_active_provider("gemini") == "gemini"


def test_estimate_text_height_and_resolve_y() -> None:
    long_text = "A" * 200
    h = estimate_text_height(long_text, size=15)
    assert h > 40
    board = [{"type": "text", "content": long_text, "x": 40, "y": 80, "size": 15}]
    bottom = board_bottom(board)
    assert bottom > 120
    resolved = resolve_y(board, 100)
    assert resolved >= bottom + 24


def test_llm_settings_flags(isolated_runtime_settings: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")
    monkeypatch.setenv("GROQ_API_KEY", "")
    data = runtime_settings.get_llm_settings("gemini")
    assert data["llm_provider"] == "gemini"
    assert data["gemini_configured"] is True
    assert data["groq_configured"] is False
