from __future__ import annotations

import json
import os
import threading
from typing import Any, List

DATA_DIR = os.path.join(os.getcwd(), "data")
SESSIONS_FILE = os.path.join(DATA_DIR, "sessions.json")
_history_lock = threading.RLock()

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
    tmp = f"{SESSIONS_FILE}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SESSIONS_FILE)


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


def change_chat_trash(ids: list[str], restore: bool = False) -> list[str]:
    import time
    if not isinstance(ids, list) or not ids or not all(isinstance(i, str) and i for i in ids):
        raise ValueError("Seleção de conversas inválida.")
    requested = set(ids)
    with _history_lock:
        data = _read()
        changed = []
        now = time.time()
        for row in data.get("sessions", []):
            if row.get("id") not in requested or (row.get("type") or "chat") != "chat":
                continue
            if bool(row.get("deleted_at")) != restore:
                continue
            if restore:
                row.pop("deleted_at")
            else:
                row["deleted_at"] = now
            row["updated_at"] = now
            changed.append(row["id"])
        if changed:
            _write(data)
        return changed


def trash_session(session_id: str) -> bool:
    with _history_lock:
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
    with _history_lock:
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
    with _history_lock:
        import time
        data = _read()
        category.setdefault("created_at", time.time())
        data.setdefault("study_categories", []).append(category)
        _write(data)
        return category


def update_session(session_id: str, patch: dict) -> dict | None:
    with _history_lock:
        return _update_session(session_id, patch)


def _update_session(session_id: str, patch: dict) -> dict | None:
    with _history_lock:
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


def set_generated_title(session_id: str, title: str) -> dict | None:
    with _history_lock:
        session = get_session(session_id)
        if not session or session.get('deleted_at'):
            return None
        if session.get('title') not in (None, '', 'Nova conversa', 'Nova sessão', 'Sessão'):
            return session
        return _update_session(session_id, {'title': title})


def update_category(category_id: str, patch: dict) -> dict | None:
    with _history_lock:
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
    with _history_lock:
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
    with _history_lock:
        import time
        session["updated_at"] = time.time()
        data = _read()
        data.setdefault("sessions", []).append(session)
        _write(data)


def save_session_history(session_id: str, history: List[dict]) -> None:
    with _history_lock:
        current = get_session_history(session_id)
        # Clientes antigos enviam cópias inteiras, às vezes atrasadas. Uma cópia
        # não pode apagar nem substituir turnos que o servidor já confirmou.
        if any(row.get("run_id") for row in current):
            def same(left, right):
                if left.get("role") != right.get("role"):
                    return False
                if left.get("run_id") and right.get("run_id"):
                    return left["run_id"] == right["run_id"]
                return (left.get("content") or left.get("text")) == (right.get("content") or right.get("text"))
            if not all(same(a, b) for a, b in zip(current, history)):
                return
            history = [*current, *history[len(current):]]
        _save_history(session_id, history)


def save_turn(session_id: str, run_id: str, text: str, reply: str, *, timestamp: float, failed: bool = False,
              context_usage: list[dict] | None = None) -> None:
    """Persiste um turno completo uma única vez, inclusive falhas e cancelamentos."""
    import time
    with _history_lock:
        history = get_session_history(session_id)
        matches = [i for i, row in enumerate(history) if row.get("run_id") == run_id and row.get("role") == "assistant"]
        if matches:
            index = matches[-1]
            history[index]["content"] = reply
            history[index]["failed"] = failed
            if index and history[index - 1].get("role") == "user":
                history[index - 1].setdefault("run_id", run_id)
        else:
            user = {"role": "user", "content": text, "run_id": run_id, "timestamp": timestamp}
            # Compatibilidade com clientes que salvaram a pergunta antes da resposta.
            if history and history[-1].get("role") == "user" and history[-1].get("content") == text and not history[-1].get("run_id"):
                history[-1].update(user)
            else:
                history.append(user)
            history.append({"role": "assistant", "content": reply, "run_id": run_id,
                            "timestamp": time.time() * 1000, "failed": failed})
        if context_usage:
            assistant = next(row for row in reversed(history) if row.get('run_id') == run_id and row.get('role') == 'assistant')
            assistant.setdefault('meta', {})['context_usage'] = context_usage[:32]
        _save_history(session_id, history)


def _save_history(session_id: str, history: List[dict]) -> None:
    with _history_lock:
        import time
        data = _read()
        session = _find_session(data, session_id)
        if session:
            session["history"] = history
            session["updated_at"] = time.time()
        else:
            data.setdefault("sessions", []).append({"id": session_id, "history": history, "updated_at": time.time()})
        _write(data)


def truncate_session_history(session_id: str, index: int, expected: list[dict]) -> list[dict]:
    """Cut before the edited user message, rejecting stale views or active runs."""
    from app.storage.action_store import action_store
    with _history_lock:
        for status in ("running", "awaiting_confirmation", "cancel_requested"):
            if action_store.run_page(session_id=session_id, status=status, limit=1, include_reads=True)["runs"]:
                raise ValueError("Conclua ou cancele o pedido pendente antes de editar.")
        history = get_session_history(session_id)
        if not isinstance(expected, list) or any(not isinstance(m, dict) for m in expected):
            raise ValueError("Histórico inválido.")
        signature = lambda rows: [(m.get("role"), m.get("content") or m.get("text") or "") for m in rows]
        if signature(history) != signature(expected):
            raise ValueError("A conversa mudou. Recarregue antes de editar.")
        if type(index) is not int or not 0 <= index < len(history) or history[index].get("role") != "user":
            raise ValueError("Selecione uma mensagem sua para editar.")
        kept = history[:index]
        _save_history(session_id, kept)
        return kept


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
    with _history_lock:
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
    with _history_lock:
        data = _read()
        sessions = data.get("sessions", [])
        original_length = len(sessions)
        data["sessions"] = [s for s in sessions if s.get("id") != session_id]
        if len(data["sessions"]) < original_length:
            _write(data)
            return True
        return False
