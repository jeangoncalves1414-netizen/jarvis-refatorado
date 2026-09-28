from __future__ import annotations

import json
from typing import Any

from app.core.actions import ActionRecord, ToolMetadata
from app.storage.action_store import action_store
from app.storage.goal_store import goal_store


def handle_goals_get(parts: list[str], _handler: Any) -> tuple[int, dict] | None:
    if parts == ["api", "goals"]:
        return 200, {"ok": True, "goals": goal_store.list(), "policy": goal_store._read().get("policy", "ask_every_time")}
    return None


def handle_goals_post(path: str, body: bytes, _handler: Any) -> tuple[int, dict] | None:
    if path != "/api/goals": return None
    try: payload = json.loads(body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError): return 400, {"ok": False, "error": "JSON inválido."}
    try:
        command = str(payload.get("action") or "create")
        if command == "create":
            goal = goal_store.create(payload.get("title", ""), payload.get("next_action", ""), policy=payload.get("policy"))
            return 201, {"ok": True, "goal": goal}
        if command == "policy": return 200, {"ok": True, "policy": goal_store.set_policy(str(payload.get("policy") or ""))}
        if command in {"pause", "resume", "complete", "archive"}:
            status = {"pause": "paused", "resume": "active", "complete": "completed", "archive": "archived"}[command]
            goal = goal_store.update_status(str(payload.get("goal_id") or ""), status)
            return (200, {"ok": True, "goal": goal}) if goal else (404, {"ok": False, "error": "Objetivo não encontrado."})
        if command == "suggest":
            goal_id = str(payload.get("goal_id") or ""); goals = {g["id"]: g for g in goal_store.list()}; goal = goals.get(goal_id)
            if not goal or goal["status"] != "active": return 404, {"ok": False, "error": "Objetivo ativo não encontrado."}
            if not goal_store.record_signal(goal_id, "manual_goal_review"): return 200, {"ok": True, "suppressed": True, "reason": "Sugestão recente já registrada."}
            action = action_store.create(ActionRecord.create(source="goal_signal", tool_name="planning_workspace", metadata=ToolMetadata(capabilities=("planning",), default_risk="low", reversible=True), arguments={"goal_id": goal_id}, preview=f"Abrir revisão do objetivo: {goal['title']}"))
            return 201, {"ok": True, "action": action.public_dict()}
        return 400, {"ok": False, "error": "Ação de objetivo desconhecida."}
    except ValueError as exc: return 400, {"ok": False, "error": str(exc)}
