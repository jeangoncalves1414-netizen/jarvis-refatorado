"""HTTP surface for reviewing the local Action Kernel journal."""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qs, urlsplit

from app.storage.action_store import action_store
from app.core.actions import STATUSES, pending_action_broker
from app.core.runs import RunCancelled


def handle_actions_get(parts: list[str], _handler: Any) -> tuple[int, dict] | None:
    if len(parts) < 2 or parts[:2] != ["api", "actions"]:
        return None
    query = parse_qs(urlsplit(getattr(_handler, "path", "")).query)
    try:
        limit = int(query.get("limit", ["30"])[0])
        before = int(query["before"][0]) if "before" in query else None
        after = int(query.get("after_event_id", ["0"])[0])
        status = query.get("status", [None])[0]
        if not 1 <= limit <= 100 or (before is not None and not 1 <= before <= 2**63 - 1) or not 0 <= after <= 2**63 - 1 or (status is not None and status not in STATUSES):
            raise ValueError()
    except ValueError:
        return 400, {"ok": False, "error": "Filtro ou cursor inválido."}
    if len(parts) == 2:
        include_reads = query.get("include_reads", ["0"])[0] in {"1", "true"}
        return 200, {"ok": True, **action_store.page(limit=limit, before=before, status=status, query=query.get("q", [""])[0][:200], include_reads=include_reads)}
    if len(parts) == 3 or (len(parts) == 4 and parts[3] == "events"):
        detail = action_store.details(parts[2], after_event_id=after)
        return (200, {"ok": True, **detail}) if detail else (404, {"ok": False, "error": "Ação não encontrada."})
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
            updated = action_store.transition(action_id, "cancelled", result_summary="Cancelada pelo usuário.", expected_status="awaiting_confirmation")
            pending_action_broker.discard(action_id)
            return 200, {"ok": True, "action": updated.public_dict()}
        if action.status != "awaiting_confirmation":
            return 409, {"ok": False, "error": "Esta ação não está aguardando confirmação."}
        updated = action_store.transition(action_id, "authorized", result_summary="Confirmada; aguardando execução segura.", expected_status="awaiting_confirmation")
        callback = pending_action_broker.take(action_id)
        if callback is None:
            expired = action_store.transition(action_id, "expired", result_summary="Ação expirou; solicite novamente pela conversa.")
            return 410, {"ok": False, "error": "Ação expirou; solicite novamente pela conversa.", "action": expired.public_dict()}
        try:
            callback()
            final = action_store.get(action_id) or updated
            payload = {"ok": final.status == "succeeded", "action": final.public_dict(), "result": final.result_summary}
            if not payload["ok"]:
                payload["error"] = final.result_summary or "A ferramenta não confirmou a conclusão."
            return 200, payload
        except Exception:
            final = action_store.get(action_id) or updated
            if final.status == "cancelled":
                return 409, {"ok": False, "error": "A ação foi cancelada antes de iniciar.", "action": final.public_dict()}
            return 500, {"ok": False, "error": "Ação confirmada, mas falhou ao executar.", "action": final.public_dict()}
    except (ValueError, RunCancelled) as exc:
        return 409, {"ok": False, "error": str(exc)}
