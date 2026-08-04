from __future__ import annotations

import json
import os
from typing import Any, List

DATA_DIR = os.path.join(os.getcwd(), "data")
SESSIONS_FILE = os.path.join(DATA_DIR, "sessions.json")

os.makedirs(DATA_DIR, exist_ok=True)


def _read() -> dict[str, Any]:
    if not os.path.exists(SESSIONS_FILE):
        return {"sessions": []}
    try:
        with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"sessions": []}


def _write(data: dict[str, Any]) -> None:
    with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _find_session(data: dict[str, Any], session_id: str) -> dict[str, Any] | None:
    for session in data.get("sessions", []):
        if session.get("id") == session_id:
            return session
    return None


def list_sessions(session_type: str | None = None) -> List[dict]:
    sessions = [s for s in _read().get("sessions", []) if not s.get("deleted_at")]
    if session_type:
        return [s for s in sessions if s.get("type", "chat") == session_type]
    return sessions


def list_trash(session_type: str | None = None) -> List[dict]:
    sessions = [s for s in _read().get("sessions", []) if s.get("deleted_at")]
    if session_type:
        sessions = [s for s in sessions if s.get("type", "chat") == session_type]
    return sessions


def trash_session(session_id: str) -> bool:
    import time
    data = _read()
    session = _find_session(data, session_id)
    if not session:
        return False
    session["deleted_at"] = time.time()
    session["updated_at"] = time.time()
    _write(data)
    return True


def restore_session(session_id: str) -> bool:
    data = _read()
    session = _find_session(data, session_id)
    if not session:
        return False
    session.pop("deleted_at", None)
    _write(data)
    return True


def purge_session(session_id: str) -> bool:
    return delete_session(session_id)


def list_categories() -> List[dict]:
    return list(_read().get("study_categories", []))


def add_category(category: dict) -> dict:
    import time
    data = _read()
    category.setdefault("created_at", time.time())
    data.setdefault("study_categories", []).append(category)
    _write(data)
    return category


def update_session(session_id: str, patch: dict) -> dict | None:
    import time
    data = _read()
    session = _find_session(data, session_id)
    if not session:
        return None
    allowed = {"title", "category_id", "category_color", "deleted_at"}
    for key, value in patch.items():
        if key in allowed:
            if value is None or value == "":
                session.pop(key, None)
            else:
                session[key] = value
    session["updated_at"] = time.time()
    _write(data)
    return dict(session)


def update_category(category_id: str, patch: dict) -> dict | None:
    data = _read()
    category = next((item for item in data.setdefault("study_categories", []) if item.get("id") == category_id), None)
    if not category:
        return None
    for key in ("name", "color"):
        if key in patch and patch[key]:
            category[key] = patch[key]
    _write(data)
    return dict(category)


def delete_category(category_id: str) -> bool:
    data = _read()
    categories = data.setdefault("study_categories", [])
    before = len(categories)
    data["study_categories"] = [item for item in categories if item.get("id") != category_id]
    if len(data["study_categories"]) == before:
        return False
    for session in data.get("sessions", []):
        if session.get("category_id") == category_id:
            session.pop("category_id", None)
    _write(data)
    return True


def add_session(session: dict) -> None:
    import time
    session["updated_at"] = time.time()
    data = _read()
    data.setdefault("sessions", []).append(session)
    _write(data)


def save_session_history(session_id: str, history: List[dict]) -> None:
    import time
    data = _read()
    session = _find_session(data, session_id)
    if session:
        session["history"] = history
        session["updated_at"] = time.time()
    else:
        data.setdefault("sessions", []).append({"id": session_id, "history": history, "updated_at": time.time()})
    _write(data)


def get_session(session_id: str) -> dict[str, Any] | None:
    session = _find_session(_read(), session_id)
    return dict(session) if session else None


def get_session_history(session_id: str) -> List[dict]:
    session = _find_session(_read(), session_id)
    raw_history = list(session.get("history", [])) if session else []
    sanitized: List[dict] = []
    try:
        from app.agent.tool_markers import parse_tool_markers
        for msg in raw_history:
            if isinstance(msg, dict):
                role = msg.get("role")
                content = msg.get("content") or msg.get("text") or ""
                if role == "assistant" and content and "[" in content and "]" in content:
                    clean_content, _ = parse_tool_markers(content)
                    new_msg = dict(msg)
                    new_msg["content"] = clean_content
                    sanitized.append(new_msg)
                else:
                    sanitized.append(msg)
            else:
                sanitized.append(msg)
        return sanitized
    except Exception:
        return raw_history


def get_whiteboard(session_id: str) -> List[dict]:
    session = _find_session(_read(), session_id)
    return list(session.get("whiteboard", [])) if session else []


def save_whiteboard(session_id: str, elements: List[dict]) -> None:
    data = _read()
    session = _find_session(data, session_id)
    if not session:
        session = {"id": session_id, "title": "Sessão", "history": [], "whiteboard": []}
        data.setdefault("sessions", []).append(session)
    session["whiteboard"] = elements
    _write(data)


def append_whiteboard_element(session_id: str, element: dict) -> None:
    board = get_whiteboard(session_id)
    board.append(element)
    save_whiteboard(session_id, board)


def delete_session(session_id: str) -> bool:
    data = _read()
    sessions = data.get("sessions", [])
    original_length = len(sessions)
    data["sessions"] = [s for s in sessions if s.get("id") != session_id]
    if len(data["sessions"]) < original_length:
        _write(data)
        return True
    return False
