"""Módulo de Suporte a Servidores MCP (Model Context Protocol)."""

from __future__ import annotations

from app.mcp.config import MCPServerConfig, get_server_config, load_server_configs, remove_server_config, save_server_configs, set_server_config
from app.mcp.client import MCPClient
from app.mcp.manager import MCPManager, mcp_manager

__all__ = [
    "MCPServerConfig",
    "load_server_configs",
    "save_server_configs",
    "get_server_config",
    "set_server_config",
    "remove_server_config",
    "MCPClient",
    "MCPManager",
    "mcp_manager",
]
