"""Study panel API: dashboard, stats, Pomodoro XP and language wiring endpoints."""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from datetime import date
from http.server import HTTPServer

import pytest

from app.agent.orchestrator import AgentOrchestrator
from app.config import Settings
from app.services.llm import LLMService
from app.storage.enem_store import EnemStore
from app.storage.language_store import LanguageStore
from app.storage.study_xp import StudyXP
from app.storage.tutor_store import TutorStore
from app.ui.panel.server import PanelHandler


def _request(method: str, url: str, payload: dict | None = None) -> tuple[int, dict]:
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


@pytest.fixture()
def study_http(tmp_path, monkeypatch):
    monkeypatch.setattr("app.storage.session_store.SESSIONS_FILE", str(tmp_path / "sessions.json"))
    monkeypatch.setattr("app.storage.session_store.DATA_DIR", str(tmp_path))

    xp = StudyXP(tmp_path / "study")
    tutor = TutorStore(storage_dir=str(tmp_path / "tutor"), xp=xp)
    language = LanguageStore(storage_dir=str(tmp_path / "language"), xp=xp)
    settings = Settings()
    settings.host = "127.0.0.1"
    settings.port = 0
    orchestrator = AgentOrchestrator(
        settings=settings,
        llm_service=LLMService(settings=settings),
        tutor_store=tutor,
        language_store=language,
        enem_store=EnemStore(storage_dir=str(tmp_path / "enem")),
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

    yield f"http://{host}:{port}", tutor, language

    server.shutdown()
    thread.join(timeout=2)
    PanelHandler.orchestrator = None


def _today_entry(rows: list[dict]) -> dict:
    assert rows[-1]["date"] == str(date.today())
    return rows[-1]


def test_dashboard_shape_and_due_counts(study_http) -> None:
    base, tutor, language = study_http
    tutor.add_flashcard("Q1", "A1")
    tutor.add_flashcard("Q2", "A2")
    language.add_vocabulary("sun", "sol")

    status, data = _request("GET", f"{base}/api/study/dashboard")
    assert status == 200
    assert set(data) == {"today", "due", "xp", "level", "badges"}
    assert data["today"] == str(date.today())
    assert data["due"] == {"flashcards": 2, "vocabulary": 1, "next_due_at": None}
    assert data["xp"]["total_xp"] == 0 and data["xp"]["daily_goal"] == 100
    assert data["level"]["level"] == 1
    assert {b["id"] for b in data["badges"]} >= {"first_review", "pomodoro_10", "vocab_50"}


def test_stats_after_reviews(study_http) -> None:
    base, tutor, language = study_http
    card_id = tutor.add_flashcard("Q", "A")
    vocab_id = language.add_vocabulary("moon", "lua")
    tutor.review_flashcard(card_id, 2)
    language.review_vocabulary(vocab_id, 3)

    status, data = _request("GET", f"{base}/api/study/stats")
    assert status == 200
    assert len(data["heatmap"]) == 371
    today = _today_entry(data["heatmap"])
    assert today["reviews"] == 2 and today["xp"] == 20
    assert len(data["daily_reviews"]) == 30
    assert _today_entry(data["daily_reviews"]) == {"date": str(date.today()), "tutor": 1, "language": 1}
    assert data["retention"] == {"rate": None, "correct": 0, "total": 0, "window_days": 30}
    assert data["totals"] == {"reviews": 2, "pomodoros": 0, "vocabulary": 1, "flashcards": 1}

    # A migrated legacy card is in 'review' state: its review counts for retention.
    tutor._data["flashcards"].append({
        "id": "fc-legacy", "front": "Legacy", "back": "Card",
        "ease": 2.5, "interval": 3, "reps": 2, "lapses": 0, "due": str(date.today()),
    })
    tutor.review_flashcard("fc-legacy", 2)

    status, data = _request("GET", f"{base}/api/study/stats")
    assert data["retention"]["rate"] == 1.0
    assert data["retention"]["total"] == 1
    states = data["states"]
    assert sum(states["tutor"].values()) == 2
    assert sum(states["language"].values()) == 1
    assert sum(states["total"].values()) == 3
    assert states["tutor"]["review"] == 1 and states["tutor"]["learning"] == 1
    assert states["language"]["review"] == 1

    status, dashboard = _request("GET", f"{base}/api/study/dashboard")
    assert dashboard["xp"]["total_xp"] == 30
    assert dashboard["xp"]["studied_today"] is True
    assert dashboard["xp"]["streak"] == 1
    assert next(b for b in dashboard["badges"] if b["id"] == "first_review")["earned"] is True


def test_pomodoro_awards_xp_and_validates(study_http) -> None:
    base, tutor, _ = study_http
    status, data = _request("POST", f"{base}/api/study/pomodoro", {"minutes": 25})
    assert status == 200
    assert data["ok"] is True
    assert data["xp"]["total_xp"] == 20
    assert data["xp"]["pomodoros"] == 1
    assert data["level"]["level"] == 1

    for payload in ({"minutes": 2}, {"minutes": 200}, {"minutes": "25"}, {"minutes": True}, {}):
        status, data = _request("POST", f"{base}/api/study/pomodoro", payload)
        assert status == 400
        assert data == {"ok": False, "error": "invalid_minutes"}
    assert tutor.xp.summary()["total_xp"] == 20


def test_vocabulary_delete(study_http) -> None:
    base, _, language = study_http
    card_id = language.add_vocabulary("tree", "árvore")
    status, data = _request("POST", f"{base}/api/language/vocabulary/{card_id}/delete", {})
    assert status == 200 and data == {"ok": True}
    assert language.get_vocabulary() == []
    assert language.get_progress()["stats"]["total_vocab"] == 0

    status, data = _request("POST", f"{base}/api/language/vocabulary/{card_id}/delete", {})
    assert status == 404
    assert data == {"ok": False, "error": "card_not_found"}


def test_shadowing_and_conversation(study_http) -> None:
    base, _, language = study_http
    status, data = _request("POST", f"{base}/api/language/shadowing", {"text": "Hello there", "score": 120, "speed": 0.75})
    assert status == 200 and data["id"].startswith("shd-")
    status, data = _request("POST", f"{base}/api/language/conversation", {
        "topic": "Viagem", "corrections": 3, "new_vocab": ["luggage"], "duration_minutes": 10,
    })
    assert status == 200 and data["id"].startswith("conv-")

    status, data = _request("POST", f"{base}/api/language/shadowing", {"text": "x", "score": "alto"})
    assert status == 400
    status, data = _request("POST", f"{base}/api/language/conversation", {"topic": "  "})
    assert status == 400
    status, data = _request("POST", f"{base}/api/language/conversation", {"topic": "T", "corrections": "muitas"})
    assert status == 400

    status, dashboard = _request("GET", f"{base}/api/language/dashboard")
    assert dashboard["stats"]["shadowing_sessions"] == 1
    assert dashboard["stats"]["conversation_sessions"] == 1
    assert dashboard["total_xp"] == 45

    progress = language.get_progress()
    shadow = progress["shadowing_history"][0]
    assert shadow["text"] == "Hello there" and shadow["score"] == 100.0 and shadow["speed"] == 0.75
    conversation = progress["conversation_history"][0]
    assert conversation["topic"] == "Viagem" and conversation["new_vocab"] == ["luggage"]


def test_study_categories_not_shadowed(study_http) -> None:
    base, _, _ = study_http
    status, data = _request("GET", f"{base}/api/study/categories")
    assert status == 200
    assert "categories" in data
