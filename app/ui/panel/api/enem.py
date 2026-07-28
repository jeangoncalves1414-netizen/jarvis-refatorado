from __future__ import annotations

import json
from typing import Any


def _store(handler: Any) -> Any | None:
    orch = getattr(handler, "orchestrator", None)
    if orch is None:
        orch = getattr(type(handler), "orchestrator", None)
    return getattr(orch, "enem_store", None) if orch else None


def handle_enem_get(parts: list[str], handler: Any) -> tuple[int, dict[str, Any]] | None:
    """Routes: /api/enem/questions, /api/enem/questions/{id}."""
    if len(parts) < 2 or parts[1] != "enem":
        return None

    store = _store(handler)
    if not store:
        return 503, {"ok": False, "error": "enem_store_unavailable"}

    if len(parts) == 3 and parts[2] == "questions":
        return 200, {"questions": store.list_questions()}

    if len(parts) == 4 and parts[2] == "questions":
        question = store.get_question(parts[3])
        if not question:
            return 404, {"ok": False, "error": "question_not_found"}
        return 200, {"question": question}

    return 404, {"error": "not_found"}


def handle_enem_post(path: str, body: bytes, handler: Any) -> tuple[int, dict[str, Any]] | None:
    if path != "/api/enem/questions":
        return None

    store = _store(handler)
    if not store:
        return 503, {"ok": False, "error": "enem_store_unavailable"}

    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except Exception:
        payload = {}

    text = str(payload.get("text", "")).strip()
    if not text:
        return 400, {"ok": False, "error": "text_required"}

    question = store.save_question({
        "text": text,
        "subject": payload.get("subject", payload.get("area", "")),
        "year": payload.get("year"),
        "image_base64": payload.get("image_base64"),
        "source": payload.get("source", "paste"),
    })
    return 200, {"ok": True, "question": question}
