"""HTTP adapter for the persistent planning workspace."""
from __future__ import annotations

import json
from typing import Any

from app.services.planning_workspace import planning_workspace


def handle_planning_get(parts: list[str], _handler: Any) -> tuple[int, dict] | None:
    if len(parts) != 2 or parts[0] != "api" or parts[1] != "planning":
        return None
    session_id = getattr(_handler, "path", "").split("session_id=", 1)[-1].split("&", 1)[0] or "default"
    return 200, {"ok": True, **planning_workspace.get(session_id)}


def handle_planning_post(path: str, body: bytes, _handler: Any) -> tuple[int, dict] | None:
    if path != "/api/planning":
        return None
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return 400, {"ok": False, "error": "JSON inválido."}
    session_id = str(payload.get("session_id") or "default")
    action = str(payload.get("action") or "status")
    try:
        if action == "open":
            result = planning_workspace.open(session_id, str(payload.get("title") or ""))
        elif action == "close":
            result = planning_workspace.close(session_id)
        elif action == "update":
            result = planning_workspace.update(session_id, title=payload.get("title"), content=payload.get("content"))
        elif action == "append":
            result = planning_workspace.append(session_id, str(payload.get("content") or ""))
        elif action == "set_auto_open":
            result = planning_workspace.set_auto_open(bool(payload.get("enabled")))
        else:
            result = planning_workspace.get(session_id)
        return 200, {"ok": True, **result}
    except ValueError as exc:
        return 400, {"ok": False, "error": str(exc)}
    except Exception as exc:
        return 500, {"ok": False, "error": str(exc)}
