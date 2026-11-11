"""Read-only operational snapshot for the local Jarvis Mission Control."""
from __future__ import annotations

from typing import Any

from app.storage.action_store import action_store
from app.core.actions import redact


def build_health_details() -> dict[str, Any]:
    from app.storage.runtime_settings import get_mic_settings
    from app.services.voice import mic_capture
    from app.mcp.manager import mcp_manager

    mic = get_mic_settings()
    capture = mic_capture.capture.status()
    try:
        # Nunca enviar command, args ou env: podem conter credenciais MCP.
        servers = [{"id": s["id"], "name": s["name"], "status": s["status"], "tools_count": s["tools_count"],
                    "error": "Falha na conexão MCP." if s.get("error") else ""} for s in mcp_manager.list_servers()]
        mcp_error = ""
    except Exception:
        servers, mcp_error = [], "Não foi possível consultar os servidores MCP."
    verified = action_store.last_verified()
    return {
        "microphone": {"configured_engine": mic["engine"], "configured_device": mic["device_name"],
                       "active": capture["active"], "state": capture["state"], "device": capture.get("device", "")},
        "tools": sorted(mcp_manager.get_registry().tools), "mcp_servers": servers, "mcp_error": mcp_error,
        "last_verified_action": verified.public_dict() if verified else None,
    }


def build_mission_snapshot() -> dict[str, Any]:
    actions = action_store.list(limit=20)
    pending = action_store.pending(limit=10)
    counts = action_store.status_counts()
    awaiting = counts.get("awaiting_confirmation", 0)
    running = counts.get("authorized", 0) + counts.get("running", 0)
    try:
        from app.storage.runtime_settings import resolve_ai_routes
        routes = resolve_ai_routes()
        provider_status = "healthy" if routes.get("chat", {}).get("configured") else "degraded"
        provider_reason = routes.get("chat", {}).get("reason", "")[:180]
    except Exception:
        provider_status, provider_reason = "unavailable", "Configuração de IA indisponível."
    # O1: "Dispositivos" só fica saudável com algum dispositivo online; zero ou erro de leitura não.
    device_count, device_error = 0, ""
    try:
        from app.services.device_bridge import DeviceBridgeService
        devices = DeviceBridgeService().get_status().get("devices", [])
        device_count = len(devices)
        online = sum(1 for device in devices if device.get("connected"))
        if not devices:
            bridge_status, bridge_reason = "off", "Nenhum dispositivo pareado."
        elif not online:
            bridge_status, bridge_reason = "degraded", f"{device_count} dispositivo(s) pareado(s), nenhum online."
        else:
            bridge_status, bridge_reason = "healthy", f"{device_count} dispositivo(s) pareado(s), {online} online."
    except Exception as exc:
        device_error = f"Não foi possível ler a ponte de dispositivos ({type(exc).__name__})."
        bridge_status, bridge_reason = "unavailable", device_error
    try:
        from app.ui.panel.api.voice_capture import capture_component_status
        capture_status = capture_component_status()
    except Exception:
        capture_status = {"status": "unavailable", "reason": "Estado da escuta do PC indisponível."}
    try:
        from app.ui.panel.api.capabilities import build_capabilities, capabilities_meta
        capabilities, capability_meta = build_capabilities(), capabilities_meta()
    except Exception:
        capabilities, capability_meta = [], {}
    try:
        from app.storage.goal_store import goal_store
        goals = goal_store.list()
        active_goals = [goal for goal in goals if goal.get("status") == "active"]
    except Exception:
        active_goals = []
    try:
        health = build_health_details()
    except Exception:
        health = {"error": "Não foi possível consultar os detalhes de saúde."}
    return {
        "version": 1,
        "health": redact(health, limit=500) if health.get("error") else health,
        "components": [
            {"id": "action_kernel", "label": "Ações", "status": "healthy", "reason": f"{awaiting + running} em andamento/aguardando confirmação."},
            {"id": "providers", "label": "IA e voz", "status": provider_status, "reason": provider_reason},
            {"id": "bridge", "label": "Dispositivos", "status": bridge_status, "reason": bridge_reason},
            {"id": "voice_capture", "label": "Escuta do PC", **capture_status},
        ],
        "capabilities": capabilities,
        **capability_meta,
        "summary": {"pending_actions": awaiting + running, "awaiting_approvals": awaiting, "running_actions": running, "failed_actions": counts.get("failed", 0), "devices": device_count, "devices_error": device_error, "active_goals": len(active_goals)},
        "goals": active_goals[:10],
        "pending_actions": [item.public_dict() for item in pending[:10]],
        "recent_actions": [item.public_dict() for item in actions[:20]],
    }


def handle_mission_control_get(parts: list[str], _handler: Any) -> tuple[int, dict[str, Any]] | None:
    if parts == ["api", "mission-control"]:
        return 200, {"ok": True, **build_mission_snapshot()}
    return None
