"""Read-only operational snapshot for the local Jarvis Mission Control."""
from __future__ import annotations

from typing import Any

from app.storage.action_store import action_store


def build_mission_snapshot() -> dict[str, Any]:
    actions = action_store.list(limit=100)
    pending = [item for item in actions if item.status in {"awaiting_confirmation", "authorized", "running"}]
    failed = [item for item in actions if item.status == "failed"]
    try:
        from app.storage.runtime_settings import resolve_ai_routes
        routes = resolve_ai_routes()
        provider_status = "healthy" if routes.get("chat", {}).get("configured") else "degraded"
        provider_reason = routes.get("chat", {}).get("reason", "")[:180]
    except Exception:
        provider_status, provider_reason = "unavailable", "Configuração de IA indisponível."
    try:
        from app.services.device_bridge import DeviceBridgeService
        bridge = DeviceBridgeService().get_status()
        device_count = len(bridge.get("devices", []))
    except Exception:
        device_count = 0
    try:
        from app.storage.goal_store import goal_store
        goals = goal_store.list()
        active_goals = [goal for goal in goals if goal.get("status") == "active"]
    except Exception:
        active_goals = []
    return {
        "version": 1,
        "components": [
            {"id": "action_kernel", "label": "Ações", "status": "healthy", "reason": f"{len(pending)} em andamento/aguardando confirmação."},
            {"id": "providers", "label": "IA e voz", "status": provider_status, "reason": provider_reason},
            {"id": "bridge", "label": "Dispositivos", "status": "healthy", "reason": f"{device_count} dispositivo(s) registrado(s)."},
        ],
        "summary": {"pending_actions": len(pending), "failed_actions": len(failed), "devices": device_count, "active_goals": len(active_goals)},
        "goals": active_goals[:10],
        "pending_actions": [item.public_dict() for item in pending[:10]],
        "recent_actions": [item.public_dict() for item in actions[:20]],
    }


def handle_mission_control_get(parts: list[str], _handler: Any) -> tuple[int, dict[str, Any]] | None:
    if parts == ["api", "mission-control"]:
        return 200, {"ok": True, **build_mission_snapshot()}
    return None
