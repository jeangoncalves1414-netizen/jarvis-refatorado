"""HTTP surface for reviewing the local Action Kernel journal."""
from __future__ import annotations

import json
from typing import Any

from app.storage.action_store import action_store
from app.core.actions import pending_action_broker


def _action_payload(action_id: str) -> dict[str, Any] | None:
    action = action_store.get(action_id)
    return action.public_dict() if action else None


def handle_actions_get(parts: list[str], _handler: Any) -> tuple[int, dict] | None:
    if len(parts) < 2 or parts[:2] != ["api", "actions"]:
        return None
    if len(parts) == 2:
        return 200, {"ok": True, "actions": [item.public_dict() for item in action_store.list()]}
    if len(parts) == 3:
        action = _action_payload(parts[2])
        return (200, {"ok": True, "action": action}) if action else (404, {"ok": False, "error": "Ação não encontrada."})
    return None


def handle_actions_post(path: str, body: bytes, _handler: Any) -> tuple[int, dict] | None:
    if not path.startswith("/api/actions/"):
        return None
    pieces = [part for part in path.split("/") if part]
    if len(pieces) != 4 or pieces[0:2] != ["api", "actions"] or pieces[3] not in {"approve", "reject"}:
        return None
    try:
        json.loads(body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return 400, {"ok": False, "error": "JSON inválido."}
    action_id, command = pieces[2], pieces[3]
    action = action_store.get(action_id)
    if not action:
        return 404, {"ok": False, "error": "Ação não encontrada."}
    try:
        if command == "reject":
            updated = action_store.transition(action_id, "cancelled", result_summary="Cancelada pelo usuário.")
            return 200, {"ok": True, "action": updated.public_dict()}
        if action.status != "awaiting_confirmation":
            return 409, {"ok": False, "error": "Esta ação não está aguardando confirmação."}
        updated = action_store.transition(action_id, "authorized", result_summary="Confirmada; aguardando execução segura.")
        callback = pending_action_broker.take(action_id)
        if callback is None:
            expired = action_store.transition(action_id, "expired", result_summary="Ação expirou; solicite novamente pela conversa.")
            return 410, {"ok": False, "error": "Ação expirou; solicite novamente pela conversa.", "action": expired.public_dict()}
        try:
            result = callback()
            final = action_store.get(action_id) or updated
            return 200, {"ok": final.status == "succeeded", "action": final.public_dict(), "result": str(result)[:500]}
        except Exception:
            final = action_store.get(action_id) or updated
            return 500, {"ok": False, "error": "Ação confirmada, mas falhou ao executar.", "action": final.public_dict()}
    except ValueError as exc:
        return 409, {"ok": False, "error": str(exc)}
