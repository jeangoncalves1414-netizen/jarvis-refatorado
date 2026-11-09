"""Endpoints de API para gerenciamento de servidores e ferramentas MCP."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlsplit

from app.mcp.config import MCPServerConfig, get_server_config
from app.mcp.manager import mcp_manager


def handle_mcp_get(parts: list[str], handler: Any) -> tuple[int, dict] | None:
    """Manipula requisições GET para /api/mcp/*."""
    if len(parts) < 2 or parts[:2] != ["api", "mcp"]:
        return None

    if len(parts) == 3 and parts[2] == "servers":
        return 200, {"ok": True, "servers": mcp_manager.list_servers()}

    if len(parts) == 4 and parts[2] == "servers":
        server_id = parts[3]
        server = mcp_manager.get_server(server_id)
        if not server:
            return 404, {"ok": False, "error": f"Servidor MCP '{server_id}' não encontrado."}
        return 200, {"ok": True, "server": server}

    if len(parts) == 3 and parts[2] == "tools":
        return 200, {"ok": True, "tools": mcp_manager.list_tools()}

    return None


def handle_mcp_post(path: str, body: bytes, handler: Any) -> tuple[int, dict] | None:
    """Manipula requisições POST para /api/mcp/*."""
    parts = [p for p in urlsplit(path).path.split("/") if p]
    if len(parts) < 2 or parts[:2] != ["api", "mcp"]:
        return None

    try:
        payload = json.loads(body.decode("utf-8") or "{}")
        if not isinstance(payload, dict):
            return 400, {"ok": False, "error": "Corpo da requisição deve ser um objeto JSON."}
    except (UnicodeDecodeError, ValueError):
        return 400, {"ok": False, "error": "JSON inválido."}

    # POST /api/mcp/servers (adicionar ou atualizar servidor)
    if len(parts) == 3 and parts[2] == "servers":
        command = str(payload.get("command") or "").strip()
        if not command:
            return 400, {"ok": False, "error": "O campo 'command' é obrigatório para o servidor MCP."}
        cfg = MCPServerConfig.from_dict(payload)
        res = mcp_manager.add_or_update_server(cfg)
        return 200, {"ok": True, "server": res}

    # POST /api/mcp/servers/{id}
    if len(parts) == 4 and parts[2] == "servers":
        server_id = parts[3]
        payload["id"] = server_id
        existing = get_server_config(server_id)
        if existing:
            merged = {**existing.to_dict(), **payload}
            cfg = MCPServerConfig.from_dict(merged)
        else:
            cfg = MCPServerConfig.from_dict(payload)
        res = mcp_manager.add_or_update_server(cfg)
        return 200, {"ok": True, "server": res}

    # POST /api/mcp/servers/{id}/restart
    if len(parts) == 5 and parts[2] == "servers" and parts[4] == "restart":
        server_id = parts[3]
        try:
            res = mcp_manager.restart_server(server_id)
            return 200, {"ok": True, "server": res}
        except KeyError:
            return 404, {"ok": False, "error": f"Servidor MCP '{server_id}' não encontrado."}
        except Exception as exc:
            return 500, {"ok": False, "error": f"Erro ao reiniciar servidor MCP: {exc}"}

    # POST /api/mcp/servers/{id}/toggle
    if len(parts) == 5 and parts[2] == "servers" and parts[4] == "toggle":
        server_id = parts[3]
        existing = get_server_config(server_id)
        if not existing:
            return 404, {"ok": False, "error": f"Servidor MCP '{server_id}' não encontrado."}
        enabled = payload.get("enabled")
        if enabled is None:
            enabled = not existing.enabled
        existing.enabled = bool(enabled)
        res = mcp_manager.add_or_update_server(existing)
        return 200, {"ok": True, "server": res}

    return None


def handle_mcp_delete(path: str, handler: Any) -> tuple[int, dict] | None:
    """Manipula requisições DELETE para /api/mcp/servers/{id}."""
    parts = [p for p in urlsplit(path).path.split("/") if p]
    if len(parts) == 4 and parts[:3] == ["api", "mcp", "servers"]:
        server_id = parts[3]
        deleted = mcp_manager.remove_server(server_id)
        if not deleted:
            return 404, {"ok": False, "error": f"Servidor MCP '{server_id}' não encontrado."}
        return 200, {"ok": True}
    return None
