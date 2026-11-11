"""Language learning API endpoints."""
from __future__ import annotations

import json
from typing import Any

from app.storage.tutor.fsrs import next_learning_due
from app.ui.panel.api.tutor import undo_response


def _store(handler: Any) -> Any | None:
    orch = getattr(handler, "orchestrator", None)
    if orch is None:
        orch = getattr(type(handler), "orchestrator", None)
    if orch is None:
        # Fallback: try module-level _orchestrator from server.py
        try:
            from app.ui.panel.server import _orchestrator
            orch = _orchestrator
        except ImportError:
            pass
    return getattr(orch, "language_store", None) if orch else None


def handle_language_get(parts: list[str], handler: Any) -> tuple[int, dict[str, Any]] | None:
    """Routes: /api/language, /api/language/dashboard, /api/language/vocabulary/due, etc."""
    if len(parts) < 2 or parts[1] != "language":
        return None

    store = _store(handler)
    if not store:
        return 200, {"progress": {}, "summary": ""}

    if len(parts) == 2:
        return 200, {"progress": store.get_progress(), "summary": store.get_summary_for_llm()}

    if len(parts) == 3 and parts[2] == "dashboard":
        return 200, store.get_dashboard()

    if len(parts) == 3 and parts[2] == "vocabulary":
        return 200, {"cards": store.get_vocabulary()}

    if len(parts) == 4 and parts[2] == "vocabulary" and parts[3] == "due":
        return 200, {
            "cards": store.get_due_vocabulary(),
            "next_due_at": next_learning_due(store.get_vocabulary()),
        }

    if len(parts) == 3 and parts[2] == "pronunciation":
        return 200, {"history": store.get_pronunciation_history()}

    return 404, {"error": "not_found"}


def handle_language_post(path: str, body: bytes, handler: Any) -> tuple[int, dict[str, Any]] | None:
    language_paths = {
        "/api/language/vocabulary",
        "/api/language/vocabulary/review",
        "/api/language/vocabulary/undo",
        "/api/language/pronunciation",
        "/api/language/level",
        "/api/language/settings",
    }
    if path not in language_paths:
        return None

    store = _store(handler)
    if not store:
        return 503, {"ok": False, "error": "language_store_unavailable"}

    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except Exception:
        payload = {}

    if path == "/api/language/vocabulary":
        card_id = store.add_vocabulary(
            word=str(payload.get("word", "")),
            translation=str(payload.get("translation", "")),
            example=str(payload.get("example", "")),
            phonetic=str(payload.get("phonetic", "")),
            category=str(payload.get("category", "general")),
            cefr=str(payload.get("cefr", "")),
        )
        return 200, {"ok": True, "id": card_id}

    if path == "/api/language/vocabulary/review":
        try:
            card = store.review_vocabulary(str(payload.get("card_id", "")), payload.get("grade"))
        except ValueError:
            return 400, {"ok": False, "error": "invalid_grade"}
        if not card:
            return 404, {"ok": False, "error": "card_not_found"}
        return 200, {"ok": True, "card": card}

    if path == "/api/language/vocabulary/undo":
        return undo_response(store.undo_last_review())

    if path == "/api/language/pronunciation":
        attempt_id = store.save_pronunciation_attempt(
            target=str(payload.get("target", "")),
            transcript=str(payload.get("transcript", "")),
            score=float(payload.get("score", 0)),
            confidence=float(payload.get("confidence", 0)),
            wrong_words=payload.get("wrong_words", []),
        )
        return 200, {"ok": True, "id": attempt_id}

    if path == "/api/language/level":
        store.set_cefr_level(str(payload.get("level", "A1")))
        return 200, {"ok": True}

    if path == "/api/language/settings":
        if payload.get("target_language"):
            store.set_target_language(str(payload["target_language"]))
        if payload.get("daily_goal"):
            store.set_daily_goal(int(payload["daily_goal"]))
        return 200, {"ok": True}

    return 404, {"error": "not_found"}

