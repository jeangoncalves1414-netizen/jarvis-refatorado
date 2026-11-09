"""Rotas da janela Rotinas: CRUD direto (ação da janela sobre dados do app, como Finanças).

As ETAPAS sempre passam pelo Action Kernel ao executar. Erros em português: 400 (validação),
404 (rotina inexistente) e 409 (já em execução).
"""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qs, urlsplit

from app.routines.models import RoutineError, operation_spec, step_tool_names
from app.routines.runner import RoutineBusy
from app.routines.service import RoutineNotFound, routine_service

_NOT_FOUND = (404, {"ok": False, "error": "Rotina não encontrada."})


def _limit(handler: Any, default: int, high: int) -> int:
    query = parse_qs(urlsplit(getattr(handler, "path", "")).query)
    value = int(query.get("limit", [str(default)])[0])
    if not 1 <= value <= high:
        raise ValueError()
    return value


def routine_meta() -> list[dict[str, Any]]:
    """Ferramentas permitidas em etapas, com operações, risco de cada uma e parâmetros do schema."""
    registry = routine_service.registry
    if registry is None:
        from app.agent.tools.registry import registry
    items = []
    for name in step_tool_names(registry):
        tool = registry.get_tool(name)
        metadata = registry.get_tool_metadata(name)
        argument, operations = operation_spec(tool, metadata)
        properties = ((tool.parameters or {}).get("properties") or {})
        params = {
            key: {"type": str(spec.get("type") or "string"), "description": str(spec.get("description") or "")[:200],
                  **({"enum": spec["enum"]} if isinstance(spec.get("enum"), list) else {})}
            for key, spec in properties.items() if key != argument and isinstance(spec, dict)
        }
        description = " ".join(str(tool.description or "").split())
        items.append({
            "tool": name,
            "label": description[:120],
            "operation_argument": argument,
            "operations": [{"name": op, "risk": metadata.risk_for({argument: op})} for op in operations] if argument else [],
            "risk": metadata.risk_for({}),
            "params": params,
        })
    return items


def handle_routines_get(parts: list[str], handler: Any) -> tuple[int, dict] | None:
    if parts[:2] != ["api", "routines"]:
        return None
    try:
        if len(parts) == 2:
            return 200, {"ok": True, "routines": routine_service.list_with_next(), "commands": routine_service.command_triggers()}
        if len(parts) == 3 and parts[2] == "next":
            return 200, {"ok": True, "next_runs": routine_service.next_runs(_limit(handler, 10, 50))}
        if len(parts) == 3 and parts[2] == "meta":
            return 200, {"ok": True, "tools": routine_meta()}
        if len(parts) == 3 and parts[2] == "alerts":
            return 200, {"ok": True, "alerts": routine_service.store().alerts(_limit(handler, 30, 200))}
        if len(parts) == 3:
            routine = routine_service.describe(routine_service.get(parts[2]))
            return 200, {"ok": True, "routine": routine, "history": routine_service.history(parts[2], 50)}
    except ValueError:
        return 400, {"ok": False, "error": "Limite inválido."}
    except RoutineNotFound:
        return _NOT_FOUND
    return None


def handle_routines_post(path: str, body: bytes, _handler: Any) -> tuple[int, dict] | None:
    parts = [part for part in urlsplit(path).path.split("/") if part]
    if parts[:2] != ["api", "routines"] or len(parts) > 4:
        return None
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
        if not isinstance(payload, dict):
            raise ValueError()
    except (UnicodeDecodeError, ValueError):
        return 400, {"ok": False, "error": "JSON inválido."}
    try:
        if len(parts) == 2:
            created = routine_service.create(payload)
            return 200, {"ok": True, **created}
        routine_id = parts[2]
        if len(parts) == 3:
            return 200, {"ok": True, **routine_service.update(routine_id, payload)}
        command = parts[3]
        if command == "enable":
            if not isinstance(payload.get("enabled"), bool):
                return 400, {"ok": False, "error": "Envie enabled verdadeiro ou falso."}
            return 200, {"ok": True, "routine": routine_service.set_enabled(routine_id, payload["enabled"])}
        if command == "run":
            return 200, {"ok": True, "run_id": routine_service.run_now(routine_id, trigger_kind="manual")}
        if command == "delete":
            routine_service.delete(routine_id)
            return 200, {"ok": True}
        return None
    except RoutineNotFound:
        return _NOT_FOUND
    except RoutineBusy as exc:
        return 409, {"ok": False, "error": str(exc)}
    except RoutineError as exc:
        return 400, {"ok": False, "error": str(exc)}
