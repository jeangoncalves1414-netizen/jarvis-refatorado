from __future__ import annotations

import json
from typing import Any


def _store(handler: Any) -> Any | None:
    orch = getattr(handler, "orchestrator", None)
    if orch is None:
        orch = getattr(type(handler), "orchestrator", None)
    if orch is None:
        try:
            from app.ui.panel.server import _orchestrator
            orch = _orchestrator
        except ImportError:
            pass
    return getattr(orch, "tutor_store", None) if orch else None


def handle_tutor_get(parts: list[str], handler: Any) -> tuple[int, dict[str, Any]] | None:
    """Routes: /api/tutor, /api/tutor/dashboard, /api/tutor/flashcards/due, etc."""
    if len(parts) < 2 or parts[1] != "tutor":
        return None

    store = _store(handler)
    if not store:
        return 200, {"progress": {}, "summary": ""}

    if len(parts) == 2:
        return 200, {"progress": store.get_progress(), "summary": store.get_summary_for_llm()}

    if len(parts) == 3 and parts[2] == "dashboard":
        return 200, store.get_dashboard()

    if len(parts) == 3 and parts[2] == "progress":
        dashboard = store.get_dashboard()
        progress = dashboard.get("progress", {})
        return 200, {
            "progress": progress,
            "due_flashcards": dashboard.get("due_flashcards", 0),
            "weak_spots": dashboard.get("weak_spots", progress.get("weak_spots", [])),
            "summary": store.get_summary_for_llm(),
        }

    if len(parts) == 4 and parts[2] == "flashcards" and parts[3] == "due":
        return 200, {"cards": store.get_due_flashcards()}

    if len(parts) == 3 and parts[2] == "flashcards":
        return 200, {"cards": store.get_flashcards()}

    if len(parts) == 3 and parts[2] == "feynman":
        return 200, {"attempts": store.get_feynman_attempts()}

    if len(parts) == 3 and parts[2] == "assessments":
        return 200, {"assessments": store.get_assessments()}

    return 404, {"error": "not_found"}


def handle_tutor_post(path: str, body: bytes, handler: Any) -> tuple[int, dict[str, Any]] | None:
    tutor_paths = {
        "/api/tutor/flashcards/review",
        "/api/tutor/feynman",
        "/api/tutor/assessments",
    }
    if path not in tutor_paths:
        return None

    store = _store(handler)
    if not store:
        return 503, {"ok": False, "error": "tutor_store_unavailable"}

    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except Exception:
        payload = {}

    if path == "/api/tutor/flashcards/review":
        card = store.review_flashcard(str(payload.get("card_id", "")), int(payload.get("grade", 2)))
        if not card:
            return 404, {"ok": False, "error": "card_not_found"}
        return 200, {"ok": True, "card": card}

    if path == "/api/tutor/feynman":
        attempt_id = store.add_feynman_attempt(
            topic=str(payload.get("topic", "")),
            explanation=str(payload.get("explanation", "")),
            grade=payload.get("grade"),
            feedback=str(payload.get("feedback", "")),
        )
        return 200, {"ok": True, "id": attempt_id}

    if path == "/api/tutor/assessments":
        assessment_id = store.add_assessment(
            stage_id=str(payload.get("stage_id", store.get_progress().get("current_stage", ""))),
            correct=int(payload.get("correct", 0)),
            total=int(payload.get("total", 0)),
            weak_topics=payload.get("weak_topics"),
        )
        return 200, {"ok": True, "id": assessment_id}

    return 404, {"error": "not_found"}
