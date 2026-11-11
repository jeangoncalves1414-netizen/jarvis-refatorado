"""Gerenciador do ciclo de vida e despacho de servidores MCP."""

from __future__ import annotations

import logging
import threading
from typing import Any

from app.agent.tools.base import ToolResult
from app.mcp.client import MCPClient
from app.mcp.config import (
    MCPServerConfig,
    get_server_config,
    load_server_configs,
    remove_server_config,
    save_server_configs,
    set_server_config,
)

logger = logging.getLogger(__name__)


def _format_result(result: Any) -> ToolResult:
    if isinstance(result, ToolResult):
        return result
    is_error = getattr(result, "isError", False)
    content_list = getattr(result, "content", [])
    texts: list[str] = []
    if isinstance(content_list, list):
        for item in content_list:
            if hasattr(item, "text") and item.text:
                texts.append(str(item.text))
            elif isinstance(item, dict) and "text" in item:
                texts.append(str(item["text"]))
            elif hasattr(item, "model_dump"):
                texts.append(str(item.model_dump()))
            else:
                texts.append(str(item))
    message = "\n".join(texts) if texts else (str(result) if result is not None else "")
    structured = getattr(result, "structuredContent", None)
    data = {"structured": structured} if structured else {}
    return ToolResult(ok=not is_error, message=message, data=data)


class MCPManager:
    """Gerenciador central de clientes e ciclo de vida de servidores MCP."""

    def __init__(self, registry: Any | None = None) -> None:
        self.clients: dict[str, MCPClient] = {}
        self.registry = registry
        self._lock = threading.Lock()
        self._started = False

    def get_registry(self) -> Any:
        if self.registry is not None:
            return self.registry
        try:
            from app.agent.tools.registry import registry
            return registry
        except Exception:
            return None

    def start(self) -> None:
        """Inicia e conecta a todos os servidores configurados e ativos."""
        with self._lock:
            if self._started:
                return
            self._started = True

        configs = load_server_configs()
        for server_id, cfg in configs.items():
            if cfg.enabled:
                try:
                    self._start_server(cfg)
                except Exception as exc:
                    logger.warning("Falha ao iniciar servidor MCP '%s': %s", server_id, exc)

    def stop(self) -> None:
        """Encerra todas as conexões MCP."""
        with self._lock:
            self._started = False
            client_items = list(self.clients.items())
            self.clients.clear()

        reg = self.get_registry()
        for server_id, client in client_items:
            try:
                client.disconnect()
            except Exception as exc:
                logger.debug("Erro ao desconectar servidor MCP '%s': %s", server_id, exc)
            if reg:
                try:
                    reg.unregister_mcp_tools(server_id)
                except Exception:
                    pass

    def _start_server(self, cfg: MCPServerConfig) -> MCPClient:
        # Desconecta cliente anterior se já existir
        old_client = self.clients.get(cfg.id)
        if old_client:
            try:
                old_client.disconnect()
            except Exception:
                pass

        client = MCPClient(
            server_id=cfg.id,
            name=cfg.name,
            command=cfg.command,
            args=cfg.args,
            env=cfg.env,
        )
        self.clients[cfg.id] = client

        try:
            client.connect()
            self._sync_tools_to_registry(cfg.id, client.tools)
        except Exception as exc:
            logger.error("Erro ao conectar ao servidor MCP '%s': %s", cfg.id, exc)

        return client

    def _sync_tools_to_registry(self, server_id: str, tools: list[dict[str, Any]]) -> None:
        reg = self.get_registry()
        if reg is None:
            return

        reg.unregister_mcp_tools(server_id)

        try:
            from app.agent.tools.registry import DynamicMCPTool
        except ImportError:
            return

        for tool_info in tools:
            name = tool_info.get("name")
            if not name:
                continue
            desc = tool_info.get("description", "")
            params = tool_info.get("parameters") or {"type": "object", "properties": {}}
            dynamic_tool = DynamicMCPTool(
                server_id=server_id,
                raw_name=name,
                description=desc,
                parameters=params,
                manager=self,
            )
            reg.register_mcp_tool(dynamic_tool)

    def list_servers(self) -> list[dict[str, Any]]:
        """Lista todos os servidores configurados com status e ferramentas."""
        configs = load_server_configs()
        results = []
        for server_id, cfg in configs.items():
            client = self.clients.get(server_id)
            status = client.status if client else ("offline" if cfg.enabled else "disabled")
            if not cfg.enabled:
                status = "disabled"
            error = client.last_error if client else ""
            tools = client.tools if client else []
            results.append({
                "id": cfg.id,
                "name": cfg.name,
                "command": cfg.command,
                "args": cfg.args,
                "env": cfg.env,
                "enabled": cfg.enabled,
                "status": status,
                "error": error,
                "tools_count": len(tools),
            })
        return results

    def get_server(self, server_id: str) -> dict[str, Any] | None:
        cfg = get_server_config(server_id)
        if not cfg:
            return None
        client = self.clients.get(server_id)
        status = client.status if client else ("offline" if cfg.enabled else "disabled")
        if not cfg.enabled:
            status = "disabled"
        error = client.last_error if client else ""
        tools = client.tools if client else []
        return {
            "id": cfg.id,
            "name": cfg.name,
            "command": cfg.command,
            "args": cfg.args,
            "env": cfg.env,
            "enabled": cfg.enabled,
            "status": status,
            "error": error,
            "tools_count": len(tools),
            "tools": tools,
        }

    def add_or_update_server(self, cfg: MCPServerConfig) -> dict[str, Any]:
        """Salva configuração e atualiza estado de conexão do servidor."""
        set_server_config(cfg)
        if cfg.enabled:
            client = self._start_server(cfg)
            status = client.status
            error = client.last_error
            tools = client.tools
        else:
            old_client = self.clients.pop(cfg.id, None)
            if old_client:
                try:
                    old_client.disconnect()
                except Exception:
                    pass
            reg = self.get_registry()
            if reg:
                reg.unregister_mcp_tools(cfg.id)
            status = "disabled"
            error = ""
            tools = []

        return {
            "id": cfg.id,
            "name": cfg.name,
            "command": cfg.command,
            "args": cfg.args,
            "env": cfg.env,
            "enabled": cfg.enabled,
            "status": status,
            "error": error,
            "tools_count": len(tools),
        }

    def remove_server(self, server_id: str) -> bool:
        """Remove servidor da configuração e desconecta."""
        client = self.clients.pop(server_id, None)
        if client:
            try:
                client.disconnect()
            except Exception:
                pass

        reg = self.get_registry()
        if reg:
            reg.unregister_mcp_tools(server_id)

        return remove_server_config(server_id)

    def restart_server(self, server_id: str) -> dict[str, Any]:
        """Reinicia e reconecta um servidor MCP."""
        cfg = get_server_config(server_id)
        if not cfg:
            raise KeyError(f"Servidor '{server_id}' não encontrado.")

        if not cfg.enabled:
            cfg.enabled = True
            set_server_config(cfg)

        client = self._start_server(cfg)
        return {
            "id": cfg.id,
            "name": cfg.name,
            "command": cfg.command,
            "args": cfg.args,
            "env": cfg.env,
            "enabled": cfg.enabled,
            "status": client.status,
            "error": client.last_error,
            "tools_count": len(client.tools),
        }

    def list_tools(self, server_id: str | None = None) -> list[dict[str, Any]]:
        """Lista todas as ferramentas disponíveis providas por servidores MCP ativos."""
        from app.agent.tools.catalog import classify_mcp_tool_metadata

        tools: list[dict[str, Any]] = []
        for s_id, client in self.clients.items():
            if server_id is not None and s_id != server_id:
                continue
            if client.status != "online":
                continue
            for t in client.tools:
                raw_name = t.get("name", "")
                desc = t.get("description", "")
                full_name = f"mcp_{s_id}_{raw_name}"
                meta = classify_mcp_tool_metadata(s_id, raw_name, desc)
                tools.append({
                    "server_id": s_id,
                    "server_name": client.name,
                    "name": full_name,
                    "raw_name": raw_name,
                    "description": desc,
                    "parameters": t.get("parameters", {}),
                    "risk": meta.default_risk,
                    "requires_confirmation": meta.requires_confirmation,
                })
        return tools

    def call_tool_sync(
        self,
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> ToolResult:
        """Despacha uma chamada de ferramenta para o servidor MCP correspondente."""
        client = self.clients.get(server_id)
        if not client or client.status != "online":
            return ToolResult(
                ok=False,
                message=f"Servidor MCP '{server_id}' não está conectado ou está offline.",
            )

        try:
            raw_result = client.call_tool(tool_name, arguments or {}, timeout=timeout)
            return _format_result(raw_result)
        except Exception as exc:
            return ToolResult(
                ok=False,
                message=f"Erro ao executar '{tool_name}' no servidor MCP '{server_id}': {exc}",
            )


# Instância global do gerenciador
mcp_manager = MCPManager()
