"""Runs use the same host/origin/token boundary as the rest of the panel API."""
import json
from urllib.parse import parse_qs, urlsplit

from app.core.runs import RUN_STATUSES
from app.storage.action_store import action_store


def handle_runs_get(parts, handler):
    if parts[:2] != ["api", "runs"]:
        return None
    query = parse_qs(urlsplit(getattr(handler, "path", "")).query)
    try:
        limit = int(query.get("limit", ["20"])[0])
        before = int(query["before"][0]) if "before" in query else None
        after = int(query.get("after_event_id", ["0"])[0])
        status = query.get("status", [None])[0]
        session = query.get("session_id", [None])[0]
        if not 1 <= limit <= 100 or (before is not None and not 1 <= before <= 2**63 - 1) or not 0 <= after <= 2**63 - 1 or (status is not None and status not in RUN_STATUSES) or (session is not None and len(session) > 200):
            raise ValueError()
    except ValueError:
        return 400, {"ok": False, "error": "Filtro ou cursor inválido."}
    if len(parts) == 2:
        include_reads = query.get("include_reads", ["0"])[0] in {"1", "true"}
        return 200, {"ok": True, **action_store.run_page(limit=limit, before=before, status=status, session_id=session, include_reads=include_reads)}
    if len(parts) == 3 or (len(parts) == 4 and parts[3] == "events"):
        detail = action_store.run_details(parts[2], after_event_id=after)
        return (200, {"ok": True, **detail}) if detail else (404, {"ok": False, "error": "Pedido não encontrado."})
    return None


def handle_runs_post(path, body, _handler):
    parts = path.strip("/").split("/")
    if len(parts) != 4 or parts[:2] != ["api", "runs"] or parts[3] != "cancel":
        return None
    try:
        if not isinstance(json.loads(body.decode("utf-8") or "{}"), dict):
            raise ValueError()
    except (UnicodeDecodeError, ValueError):
        return 400, {"ok": False, "error": "JSON inválido."}
    try:
        return 200, {"ok": True, "run": action_store.cancel_run(parts[2])}
    except KeyError:
        return 404, {"ok": False, "error": "Pedido não encontrado."}
    except ValueError as exc:
        return 409, {"ok": False, "error": str(exc)}
