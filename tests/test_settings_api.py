from __future__ import annotations

import json
import threading
from http.server import HTTPServer
from unittest.mock import MagicMock

import pytest

from app.config import Settings
from app.ui.panel.server import PanelHandler, PanelServer


@pytest.fixture
def settings_server(monkeypatch: pytest.MonkeyPatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr("app.storage.runtime_settings.DATA_DIR", str(data_dir))
    monkeypatch.setattr(
        "app.storage.runtime_settings.RUNTIME_SETTINGS_FILE",
        str(data_dir / "runtime_settings.json"),
    )
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")

    settings = Settings(
        host="127.0.0.1",
        port=0,
        gemini_api_key="test-gemini",
        groq_api_key="test-groq",
    )
    PanelHandler.orchestrator = MagicMock()
    PanelHandler.settings = settings
    server = HTTPServer(("127.0.0.1", 0), PanelHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    base = f"http://{host}:{port}"
    yield base
    server.shutdown()
    thread.join(timeout=2)


def test_settings_llm_get_and_post(settings_server: str) -> None:
    import urllib.request

    with urllib.request.urlopen(f"{settings_server}/api/settings/llm") as resp:
        data = json.loads(resp.read().decode("utf-8"))
    assert data["llm_provider"] in {"gemini", "groq"}
    assert data["gemini_configured"] is True
    assert data["groq_configured"] is True

    req = urllib.request.Request(
        f"{settings_server}/api/settings/llm",
        data=json.dumps({"llm_provider": "groq"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    assert data["ok"] is True
    assert data["llm_provider"] == "groq"

    with urllib.request.urlopen(f"{settings_server}/api/settings/llm") as resp:
        data = json.loads(resp.read().decode("utf-8"))
    assert data["llm_provider"] == "groq"
