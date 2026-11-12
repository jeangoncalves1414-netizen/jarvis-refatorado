from __future__ import annotations

import json
from typing import Any

from app.storage.tutor.fsrs import next_learning_due


def undo_response(result: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if result.get("ok"):
        return 200, result
    return (404 if result.get("error") == "nothing_to_undo" else 409), result


def _orchestrator_for(handler: Any) -> Any | None:
    orch = getattr(handler, "orchestrator", None)
    if orch is None:
        orch = getattr(type(handler), "orchestrator", None)
    if orch is None:
        try:
            from app.ui.panel.server import _orchestrator
            orch = _orchestrator
        except ImportError:
            pass
    return orch


def handle_tutor_get(parts: list[str], handler: Any) -> tuple[int, dict[str, Any]] | None:
    """Routes: /api/tutor, /api/tutor/dashboard, /api/tutor/flashcards/due, etc."""
    if len(parts) < 2 or parts[1] != "tutor":
        return None

    store = getattr(_orchestrator_for(handler), "tutor_store", None)
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
        return 200, {
            "cards": store.get_due_flashcards(),
            "next_due_at": next_learning_due(store.get_flashcards()),
        }

    if len(parts) == 3 and parts[2] == "flashcards":
        return 200, {"cards": store.get_flashcards()}

    if len(parts) == 3 and parts[2] == "feynman":
        return 200, {"attempts": store.get_feynman_attempts()}

    if len(parts) == 3 and parts[2] == "assessments":
        return 200, {"assessments": store.get_assessments()}

    return 404, {"error": "not_found"}


def handle_tutor_post(path: str, body: bytes, handler: Any) -> tuple[int, dict[str, Any]] | None:
    tutor_paths = {
        "/api/tutor/flashcards",
        "/api/tutor/flashcards/suggest",
        "/api/tutor/flashcards/review",
        "/api/tutor/flashcards/undo",
        "/api/tutor/feynman",
        "/api/tutor/assessments",
    }
    if path not in tutor_paths:
        return None

    store = getattr(_orchestrator_for(handler), "tutor_store", None)
    if not store:
        return 503, {"ok": False, "error": "tutor_store_unavailable"}

    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except Exception:
        payload = {}

    if not isinstance(payload, dict):
        return 400, {"error": "Esperado objeto JSON."}
    if path == "/api/tutor/flashcards":
        try:
            return 201, {"ids": store.create_note(payload)}
        except ValueError as exc:
            return 400, {"error": str(exc)}
    if path == "/api/tutor/flashcards/suggest":
        from app.storage.session_store import get_session, get_session_history
        session_id = str(payload.get("session_id", ""))
        if (get_session(session_id) or {}).get("type") != "tutor":
            return 404, {"error": "Sessão de estudos não encontrada."}
        history = [str(row.get("content", ""))[:1200] for row in get_session_history(session_id)[-12:]
                   if row.get("role") in ("user", "assistant") and not row.get("failed")]
        if not any(history):
            return 400, {"error": "Converse com o tutor antes de gerar cartões."}
        result = _orchestrator_for(handler).llm_service.ask(
            json.dumps(history, ensure_ascii=False),
            system_instruction='Com base na aula fornecida, sugira até cinco cartões. Responda apenas com um array JSON de objetos com strings front e back.',
        )
        try:
            rows = json.loads(result.strip().removeprefix("```json").removeprefix("```").removesuffix("```"))
            cards = [row for row in rows if isinstance(row, dict) and
                     all(isinstance(row.get(k), str) and 0 < len(row[k].strip()) <= 4000 for k in ("front", "back"))]
            if not cards:
                raise ValueError
        except (ValueError, TypeError):
            return 502, {"error": "O tutor não conseguiu gerar cartões. Tente novamente."}
        return 200, {"cards": cards[:5]}

    if path == "/api/tutor/flashcards/review":
        try:
            card = store.review_flashcard(str(payload.get("card_id", "")), payload.get("grade"))
        except ValueError:
            return 400, {"ok": False, "error": "invalid_grade"}
        if not card:
            return 404, {"ok": False, "error": "card_not_found"}
        return 200, {"ok": True, "card": card}

    if path == "/api/tutor/flashcards/undo":
        return undo_response(store.undo_last_review())

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
