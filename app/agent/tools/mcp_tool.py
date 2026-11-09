"""Ferramenta MCP para chamada direta ou inspeção de servidores pelo agente."""

from __future__ import annotations

from typing import Any

from app.agent.tools.base import BaseTool, ToolResult
from app.mcp.manager import mcp_manager


class MCPTool(BaseTool):
    """Ferramenta para orquestrar e chamar servidores Model Context Protocol."""

    @property
    def name(self) -> str:
        return "mcp"

    @property
    def description(self) -> str:
        return (
            "Integração com serviços externos via Model Context Protocol (MCP). "
            "Use para interagir com GitHub, Google Drive, Notion, Filesystem e outros servidores MCP configurados. "
            "Para listar servidores disponíveis, use action='list_servers'. "
            "Para listar ferramentas de um servidor, use action='list_tools' com server='<nome>'. "
            "Para executar uma ação, use action='call' com server='<nome>', tool='<ferramenta>', params={...}."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "server": {
                    "type": "string",
                    "description": "Nome ou ID do servidor MCP (ex: 'github', 'filesystem'). Opcional para list_servers.",
                },
                "action": {
                    "type": "string",
                    "description": "Ação a executar: 'list_servers', 'list_tools', 'call'",
                },
                "tool": {
                    "type": "string",
                    "description": "Nome da ferramenta MCP a chamar (para action='call')",
                },
                "params": {
                    "type": "object",
                    "description": "Parâmetros para a ferramenta MCP",
                },
            },
            "required": ["action"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        action = args.get("action", "list_servers")

        if action == "list_servers":
            return self._list_servers()
        elif action == "list_tools":
            return self._list_tools(args.get("server", ""))
        elif action == "call":
            return self._call_tool(
                args.get("server", ""),
                args.get("tool", ""),
                args.get("params", {}),
            )
        else:
            return ToolResult(
                ok=False,
                message=f"Ação MCP desconhecida: '{action}'. Use: list_servers, list_tools, call",
            )

    def _list_servers(self) -> ToolResult:
        servers = mcp_manager.list_servers()
        if not servers:
            return ToolResult(
                ok=True,
                message=(
                    "Nenhum servidor MCP configurado no momento. "
                    "Configure novos servidores nas Configurações > Servidores MCP ou via API."
                ),
            )
        lines = []
        for s in servers:
            status_text = "🟢 online" if s["status"] == "online" else f"⚪ {s['status']}"
            lines.append(f"- {s['name']} (id: {s['id']}): {status_text} | {s['tools_count']} ferramentas")
        return ToolResult(ok=True, message="Servidores MCP configurados:\n" + "\n".join(lines))

    def _list_tools(self, server_name: str) -> ToolResult:
        if not server_name:
            all_tools = mcp_manager.list_tools()
            if not all_tools:
                return ToolResult(ok=True, message="Nenhuma ferramenta MCP ativa encontrada.")
            tool_list = "\n".join(f"- {t['name']}: {t.get('description', '')}" for t in all_tools)
            return ToolResult(ok=True, message=f"Ferramentas MCP disponíveis:\n{tool_list}")

        server_id = server_name
        for s in mcp_manager.list_servers():
            if s["id"] == server_name or s["name"].lower() == server_name.lower():
                server_id = s["id"]
                break

        tools = mcp_manager.list_tools(server_id)
        if tools:
            tool_list = "\n".join(f"- {t['name']}: {t.get('description', '')}" for t in tools)
            return ToolResult(ok=True, message=f"Ferramentas do servidor '{server_name}':\n{tool_list}")
        return ToolResult(ok=True, message=f"Servidor '{server_name}' não possui ferramentas ativas ou está offline.")

    def _call_tool(self, server_name: str, tool_name: str, params: dict[str, Any]) -> ToolResult:
        if not server_name or not tool_name:
            return ToolResult(ok=False, message="Informe 'server' e 'tool' para chamar uma ferramenta MCP.")

        server_id = server_name
        for s in mcp_manager.list_servers():
            if s["id"] == server_name or s["name"].lower() == server_name.lower():
                server_id = s["id"]
                break

        clean_tool = tool_name
        prefix = f"mcp_{server_id}_"
        if clean_tool.startswith(prefix):
            clean_tool = clean_tool[len(prefix):]

        return mcp_manager.call_tool_sync(server_id, clean_tool, params)
