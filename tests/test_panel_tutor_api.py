import json
import threading
import urllib.error
import urllib.request
import uuid
from http.server import HTTPServer
from unittest.mock import MagicMock

import pytest

from app.agent.orchestrator import AgentOrchestrator
from app.config import Settings
from app.services.llm import LLMService
from app.storage.tutor_store import TutorStore
from app.ui.panel.server import PanelHandler


def _request(method: str, url: str, data: bytes | None = None, content_type: str = "application/json") -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


@pytest.fixture()
def panel_http(tmp_path, monkeypatch):
    sessions_file = tmp_path / "sessions.json"
    monkeypatch.setattr("app.storage.session_store.SESSIONS_FILE", str(sessions_file))
    monkeypatch.setattr("app.storage.session_store.DATA_DIR", str(tmp_path))

    tutor_store = TutorStore(storage_dir=str(tmp_path / f"tutor-{uuid.uuid4().hex}"))
    settings = Settings()
    settings.host = "127.0.0.1"
    settings.port = 0

    llm = LLMService(settings=settings)
    orchestrator = AgentOrchestrator(settings=settings, llm_service=llm, tutor_store=tutor_store)
    PanelHandler.orchestrator = orchestrator
    PanelHandler.settings = settings
    PanelHandler.voice_pipeline = None

    class _TestPanelHandler(PanelHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.orchestrator = orchestrator
            self.settings = settings

    server = HTTPServer(("127.0.0.1", 0), _TestPanelHandler)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://{host}:{port}"

    yield base, tutor_store, sessions_file

    server.shutdown()
    thread.join(timeout=2)
    PanelHandler.orchestrator = None


def test_tutor_dashboard_api(panel_http) -> None:
    base, store, _ = panel_http
    store.add_flashcard("Pergunta", "Resposta")
    status, body = _request("GET", f"{base}/api/tutor/dashboard")
    assert status == 200
    data = json.loads(body)
    assert data["due_flashcards"] == 1


def test_tutor_progress_api(panel_http) -> None:
    base, store, _ = panel_http
    store.add_flashcard("Q1", "A1")
    store.add_weak_spot("logaritmos")
    status, body = _request("GET", f"{base}/api/tutor/progress")
    assert status == 200
    data = json.loads(body)
    assert data["due_flashcards"] == 1
    assert "logaritmos" in data["weak_spots"]
    assert "progress" in data
    assert "summary" in data


def test_tutor_flashcards_due_api(panel_http) -> None:
    base, store, _ = panel_http
    store.add_flashcard("Due card", "Answer")
    status, body = _request("GET", f"{base}/api/tutor/flashcards/due")
    assert status == 200
    data = json.loads(body)
    assert len(data["cards"]) == 1


def test_whiteboard_roundtrip(panel_http) -> None:
    base, _, _ = panel_http
    sid = "test-session-1"
    board = [{"type": "text", "content": "Olá", "x": 10, "y": 20}]
    status, _ = _request(
        "POST",
        f"{base}/api/sessions/{sid}/whiteboard",
        json.dumps({"whiteboard": board}).encode(),
    )
    assert status == 200
    status, body = _request("GET", f"{base}/api/sessions/{sid}/whiteboard")
    assert status == 200
    data = json.loads(body)
    assert data["whiteboard"][0]["content"] == "Olá"


def test_flashcard_review_api(panel_http) -> None:
    base, store, _ = panel_http
    card_id = store.add_flashcard("Q", "A")
    status, body = _request(
        "POST",
        f"{base}/api/tutor/flashcards/review",
        json.dumps({"card_id": card_id, "grade": 2}).encode(),
    )
    assert status == 200
    data = json.loads(body)
    assert data["ok"] is True
    assert data["card"]["reps"] == 1


def test_voice_stt_empty_returns_ok_false(panel_http) -> None:
    base, _, _ = panel_http
    PanelHandler.voice_pipeline = MagicMock()
    status, body = _request("POST", f"{base}/api/voice/stt", b"", content_type="audio/webm")
    assert status == 200
    data = json.loads(body)
    assert data["ok"] is False
    assert data.get("error")
