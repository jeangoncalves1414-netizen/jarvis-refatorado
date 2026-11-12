"""Language learning API endpoints."""
from __future__ import annotations

import io
import wave
import json
import math
import urllib.parse
from typing import Any

from app.storage.tutor.fsrs import next_learning_due
from app.ui.panel.api.tutor import _orchestrator_for, undo_response


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


def _number(payload: dict[str, Any], key: str, default: float) -> float:
    """JSON number field (bool/str/NaN rejected with ValueError)."""
    value = payload.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(key)
    return value


def handle_language_post(path: str, body: bytes, handler: Any) -> tuple[int, dict[str, Any]] | None:
    if path == "/api/language/ipa":
        if len(body) > 1024 * 1024:
            return 413, {"error": "O áudio excedeu o limite."}
        try:
            with wave.open(io.BytesIO(body)) as audio:
                if (audio.getnchannels() != 1 or audio.getsampwidth() != 2 or
                        not 0 < audio.getnframes() <= 20 * audio.getframerate()):
                    raise ValueError
        except (wave.Error, EOFError, ValueError):
            return 400, {"error": "Grave novamente em WAV mono de até 20 segundos."}
        llm = getattr(_orchestrator_for(handler), "llm_service", None)
        key = llm._api_key_for("gemini") if llm else None
        if not key:
            return 503, {"error": "Configure a chave Gemini para transcrever em IPA."}
        try:
            from google import genai
            from google.genai import types
            with genai.Client(api_key=key, http_options=types.HttpOptions(timeout=45000)) as client:
                result = client.models.generate_content(
                    model=llm._effective_chat_model("gemini"),
                    contents=[types.Part.from_bytes(data=body, mime_type="audio/wav"),
                              "Transcreva somente os sons da fala audível em IPA entre colchetes. "
                              "Preserve desvios de pronúncia. Se não houver fala inteligível, responda SEM_FALA."],
                )
            ipa = (result.text or "").strip()
            if not ipa or ipa == "SEM_FALA":
                return 422, {"error": "Nenhuma fala inteligível. Grave novamente."}
            return 200, {"ipa": ipa}
        except Exception:
            return 502, {"error": "Gemini indisponível para transcrever este áudio."}

    language_paths = {
        "/api/language/vocabulary",
        "/api/language/vocabulary/review",
        "/api/language/vocabulary/undo",
        "/api/language/pronunciation",
        "/api/language/shadowing",
        "/api/language/conversation",
        "/api/language/level",
        "/api/language/settings",
    }
    path_parts = path.split("/")
    is_vocab_delete = (
        len(path_parts) == 6
        and path_parts[:4] == ["", "api", "language", "vocabulary"]
        and bool(path_parts[4])
        and path_parts[5] == "delete"
    )
    if path not in language_paths and not is_vocab_delete:
        return None

    store = _store(handler)
    if not store:
        return 503, {"ok": False, "error": "language_store_unavailable"}

    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    if is_vocab_delete:
        if not store.delete_vocabulary(urllib.parse.unquote(path_parts[4])):
            return 404, {"ok": False, "error": "card_not_found"}
        return 200, {"ok": True}

    if path == "/api/language/shadowing":
        try:
            score = _number(payload, "score", 0.0)
            speed = _number(payload, "speed", 1.0)
        except ValueError:
            return 400, {"ok": False, "error": "invalid_payload"}
        session_id = store.log_shadowing_session(str(payload.get("text", "")), score=score, speed=speed)
        return 200, {"ok": True, "id": session_id}

    if path == "/api/language/conversation":
        topic = str(payload.get("topic") or "").strip()
        if not topic:
            return 400, {"ok": False, "error": "topic_required"}
        new_vocab = payload.get("new_vocab") or []
        try:
            corrections = _number(payload, "corrections", 0)
            duration = _number(payload, "duration_minutes", 0)
            if not isinstance(new_vocab, list):
                raise ValueError("new_vocab")
        except ValueError:
            return 400, {"ok": False, "error": "invalid_payload"}
        session_id = store.log_conversation_session(
            topic=topic,
            corrections=int(corrections),
            new_vocab=[str(word) for word in new_vocab],
            duration_minutes=int(duration),
        )
        return 200, {"ok": True, "id": session_id}

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

