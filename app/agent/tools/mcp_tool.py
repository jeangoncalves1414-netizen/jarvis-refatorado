from __future__ import annotations

import json
import os
from typing import Any
from .base import BaseTool, ToolResult

MCP_SERVERS_FILE = os.path.join(os.getcwd(), "data", "mcp_servers.json")


def _load_servers() -> dict:
    """Carrega configuração de servidores MCP do arquivo JSON."""
    if not os.path.exists(MCP_SERVERS_FILE):
        return {}
    try:
        with open(MCP_SERVERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


class MCPTool(BaseTool):
    @property
    def name(self) -> str:
        return "mcp"
    
    @property
    def description(self) -> str:
        return (
            "Integração com serviços externos via Model Context Protocol (MCP). "
            "Use para interagir com GitHub, Google Drive, Notion, Jira e outros servidores MCP configurados. "
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
                    "description": "Nome do servidor MCP (ex: 'github', 'google_drive'). Opcional para list_servers."
                },
                "action": {
                    "type": "string",
                    "description": "Ação a executar: 'list_servers', 'list_tools', 'call'"
                },
                "tool": {
                    "type": "string",
                    "description": "Nome da ferramenta MCP a chamar (para action='call')"
                },
                "params": {
                    "type": "object",
                    "description": "Parâmetros para a ferramenta MCP"
                }
            },
            "required": ["action"]
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
                args.get("params", {})
            )
        else:
            return ToolResult(ok=False, message=f"Ação MCP desconhecida: '{action}'. Use: list_servers, list_tools, call")

    def _list_servers(self) -> ToolResult:
        servers = _load_servers()
        if not servers:
            return ToolResult(
                ok=True,
                message=(
                    "Nenhum servidor MCP configurado ainda. "
                    f"Crie o arquivo '{MCP_SERVERS_FILE}' com a configuração dos seus servidores. "
                    "Exemplo de configuração:\n"
                    '{\n'
                    '  "github": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"], "env": {"GITHUB_TOKEN": "seu_token"}},\n'
                    '  "filesystem": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:/Users/maria/Desktop"]}\n'
                    '}'
                )
            )
        names = list(servers.keys())
        return ToolResult(ok=True, message=f"Servidores MCP disponíveis: {', '.join(names)}")

    def _list_tools(self, server_name: str) -> ToolResult:
        servers = _load_servers()
        if server_name not in servers:
            return ToolResult(ok=False, message=f"Servidor MCP '{server_name}' não encontrado. Servidores: {list(servers.keys())}")
        
        config = servers[server_name]
        try:
            tools = self._fetch_mcp_tools(server_name, config)
            if tools:
                tool_list = "\n".join(f"- {t['name']}: {t.get('description', '')}" for t in tools)
                return ToolResult(ok=True, message=f"Ferramentas do servidor '{server_name}':\n{tool_list}")
            return ToolResult(ok=True, message=f"Servidor '{server_name}' não retornou ferramentas.")
        except Exception as e:
            return ToolResult(ok=False, message=f"Erro ao conectar ao servidor MCP '{server_name}': {e}")

    def _call_tool(self, server_name: str, tool_name: str, params: dict) -> ToolResult:
        if not server_name or not tool_name:
            return ToolResult(ok=False, message="Informe 'server' e 'tool' para chamar uma ferramenta MCP.")
        
        servers = _load_servers()
        if server_name not in servers:
            return ToolResult(ok=False, message=f"Servidor MCP '{server_name}' não encontrado.")
        
        config = servers[server_name]
        try:
            result = self._invoke_mcp_tool(server_name, config, tool_name, params)
            return ToolResult(ok=True, message=str(result))
        except Exception as e:
            return ToolResult(ok=False, message=f"Erro ao executar ferramenta MCP '{tool_name}' em '{server_name}': {e}")

    def _fetch_mcp_tools(self, server_name: str, config: dict) -> list:
        """Conecta ao servidor MCP via subprocess e lista as ferramentas disponíveis."""
        import subprocess, json
        cmd = [config["command"]] + config.get("args", [])
        env = {**os.environ, **config.get("env", {})}
        
        # Enviar mensagem de inicialização MCP (JSON-RPC)
        init_msg = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "jarvis", "version": "1.0"}
        }}) + "\n"
        list_msg = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}) + "\n"
        
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env, text=True
        )
        try:
            stdout, _ = proc.communicate(input=init_msg + list_msg, timeout=10)
            tools = []
            for line in stdout.strip().splitlines():
                try:
                    resp = json.loads(line)
                    if resp.get("id") == 2 and "result" in resp:
                        tools = resp["result"].get("tools", [])
                except Exception:
                    pass
            return tools
        except subprocess.TimeoutExpired:
            proc.kill()
            raise RuntimeError("Timeout ao conectar ao servidor MCP")

    def _invoke_mcp_tool(self, server_name: str, config: dict, tool_name: str, params: dict) -> Any:
        """Invoca uma ferramenta específica no servidor MCP."""
        import subprocess, json
        cmd = [config["command"]] + config.get("args", [])
        env = {**os.environ, **config.get("env", {})}
        
        init_msg = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "jarvis", "version": "1.0"}
        }}) + "\n"
        call_msg = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
            "name": tool_name,
            "arguments": params
        }}) + "\n"
        
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env, text=True
        )
        try:
            stdout, _ = proc.communicate(input=init_msg + call_msg, timeout=30)
            for line in stdout.strip().splitlines():
                try:
                    resp = json.loads(line)
                    if resp.get("id") == 2:
                        if "result" in resp:
                            content = resp["result"].get("content", [])
                            texts = [c.get("text", "") for c in content if c.get("type") == "text"]
                            return "\n".join(texts) if texts else str(resp["result"])
                        elif "error" in resp:
                            raise RuntimeError(resp["error"].get("message", "Erro MCP desconhecido"))
                except Exception as parse_err:
                    pass
            return "Ferramenta executada (sem resposta textual)."
        except subprocess.TimeoutExpired:
            proc.kill()
            raise RuntimeError("Timeout ao executar ferramenta MCP")
