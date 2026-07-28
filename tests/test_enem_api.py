import json
import threading
import urllib.error
import urllib.request
import uuid
from http.server import HTTPServer

import pytest

from app.agent.orchestrator import AgentOrchestrator
from app.config import Settings
from app.services.llm import LLMService
from app.storage.enem_store import EnemStore
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
def panel_enem_http(tmp_path, monkeypatch):
    sessions_file = tmp_path / "sessions.json"
    monkeypatch.setattr("app.storage.session_store.SESSIONS_FILE", str(sessions_file))
    monkeypatch.setattr("app.storage.session_store.DATA_DIR", str(tmp_path))

    enem_dir = tmp_path / f"enem-{uuid.uuid4().hex}"
    enem_store = EnemStore(storage_dir=str(enem_dir))
    tutor_store = TutorStore(storage_dir=str(tmp_path / f"tutor-{uuid.uuid4().hex}"))
    settings = Settings()
    settings.host = "127.0.0.1"
    settings.port = 0

    llm = LLMService(settings=settings)
    orchestrator = AgentOrchestrator(
        settings=settings,
        llm_service=llm,
        tutor_store=tutor_store,
        enem_store=enem_store,
    )
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

    yield base, enem_store

    server.shutdown()
    thread.join(timeout=2)
    PanelHandler.orchestrator = None


def test_enem_list_empty(panel_enem_http) -> None:
    base, _ = panel_enem_http
    status, body = _request("GET", f"{base}/api/enem/questions")
    assert status == 200
    data = json.loads(body)
    assert data["questions"] == []


def test_enem_save_and_list(panel_enem_http) -> None:
    base, store = panel_enem_http
    payload = json.dumps({
        "text": "Qual a capital do Brasil?",
        "subject": "ciencias_humanas",
        "year": 2022,
    }).encode("utf-8")

    status, body = _request("POST", f"{base}/api/enem/questions", payload)
    assert status == 200
    saved = json.loads(body)
    assert saved["ok"] is True
    assert saved["question"]["text"].startswith("Qual a capital")

    status, body = _request("GET", f"{base}/api/enem/questions")
    listed = json.loads(body)
    assert len(listed["questions"]) == 1
    assert listed["questions"][0]["subject"] == "ciencias_humanas"

    qid = saved["question"]["id"]
    assert store.get_question(qid) is not None


def test_enem_get_by_id(panel_enem_http) -> None:
    base, store = panel_enem_http
    question = store.save_question({"text": "2+2?", "subject": "matematica", "year": 2021})

    status, body = _request("GET", f"{base}/api/enem/questions/{question['id']}")
    assert status == 200
    data = json.loads(body)
    assert data["question"]["text"] == "2+2?"


def test_enem_get_not_found(panel_enem_http) -> None:
    base, _ = panel_enem_http
    status, _ = _request("GET", f"{base}/api/enem/questions/missing-id")
    assert status == 404


def test_enem_save_requires_text(panel_enem_http) -> None:
    base, _ = panel_enem_http
    payload = json.dumps({"subject": "matematica"}).encode("utf-8")
    status, body = _request("POST", f"{base}/api/enem/questions", payload)
    assert status == 400
    data = json.loads(body)
    assert data["ok"] is False
