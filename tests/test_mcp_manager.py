"""Testes unitários do módulo MCP (configuração, cliente, gerenciador, catálogo e rotas de API)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.agent.tools.catalog import (
    TOOL_CATALOG,
    classify_mcp_tool_metadata,
    metadata_for,
    register_mcp_tool_metadata,
    unregister_mcp_tool_metadata,
)
from app.agent.tools.registry import DynamicMCPTool, ToolRegistry
from app.mcp.client import MCPClient
from app.mcp.config import (
    MCPServerConfig,
    get_server_config,
    load_server_configs,
    remove_server_config,
    save_server_configs,
    set_server_config,
)
from app.mcp.manager import MCPManager, _format_result
from app.ui.panel.api.mcp import (
    handle_mcp_delete,
    handle_mcp_get,
    handle_mcp_post,
)


# ───────────────────────────────────────────────────────────── Config Tests ──

def test_mcp_server_config_creation():
    cfg = MCPServerConfig(
        id="github",
        name="GitHub MCP",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        env={"GITHUB_TOKEN": "token123"},
        enabled=True,
    )
    assert cfg.id == "github"
    assert cfg.name == "GitHub MCP"
    assert cfg.command == "npx"
    assert cfg.args == ["-y", "@modelcontextprotocol/server-github"]
    assert cfg.env == {"GITHUB_TOKEN": "token123"}
    assert cfg.enabled is True

    d = cfg.to_dict()
    assert d["id"] == "github"
    assert d["command"] == "npx"


def test_mcp_server_config_auto_slug():
    cfg = MCPServerConfig.from_dict({
        "name": "Meu Servidor Especial!",
        "command": "python",
        "args": "run.py",
    })
    assert cfg.id == "meu_servidor_especial"
    assert cfg.args == ["run.py"]
    assert cfg.enabled is True


def test_mcp_config_persistence(tmp_path):
    config_file = str(tmp_path / "mcp_servers.json")

    # Inicialmente vazio
    assert load_server_configs(config_file) == {}

    cfg1 = MCPServerConfig(id="srv1", name="Server 1", command="node", args=["server.js"])
    cfg2 = MCPServerConfig(id="srv2", name="Server 2", command="python", args=["-m", "mcp"])

    save_server_configs({"srv1": cfg1, "srv2": cfg2}, config_file)
    loaded = load_server_configs(config_file)
    assert len(loaded) == 2
    assert loaded["srv1"].command == "node"
    assert loaded["srv2"].command == "python"

    # get, set, remove
    assert get_server_config("srv1", config_file).name == "Server 1"

    cfg3 = MCPServerConfig(id="srv3", name="Server 3", command="uvx")
    set_server_config(cfg3, config_file)
    assert get_server_config("srv3", config_file) is not None

    removed = remove_server_config("srv1", config_file)
    assert removed is True
    assert get_server_config("srv1", config_file) is None


# ────────────────────────────────────────── Risk & Catalog Classification ──

def test_mcp_risk_classification():
    # Ferramentas de leitura -> observe (sem confirmação)
    for read_name in ["read_file", "list_directory", "get_status", "search_issues", "fetch_data"]:
        meta = classify_mcp_tool_metadata("fs", read_name)
        assert meta.default_risk == "observe", f"{read_name} deveria ser observe"
        assert meta.requires_confirmation is False

    # Ferramentas de escrita crítica -> high (com confirmação)
    for high_name in ["delete_file", "remove_branch", "destroy_table", "drop_db", "execute_command"]:
        meta = classify_mcp_tool_metadata("fs", high_name)
        assert meta.default_risk == "high", f"{high_name} deveria ser high"
        assert meta.requires_confirmation is True

    # Ferramentas de escrita padrão -> low (com confirmação requerida)
    for write_name in ["create_issue", "update_file", "write_record", "post_comment"]:
        meta = classify_mcp_tool_metadata("github", write_name)
        assert meta.requires_confirmation is True


def test_mcp_catalog_dynamic_registration():
    full_name = "mcp_testserver_custom_action"
    meta = classify_mcp_tool_metadata("testserver", "custom_action")

    register_mcp_tool_metadata(full_name, meta)
    assert full_name in TOOL_CATALOG

    # metadata_for deve encontrar no TOOL_CATALOG
    found = metadata_for(full_name, None)
    assert found is not None
    assert found.capabilities == ("mcp", "testserver")

    # Desregistro
    unregister_mcp_tool_metadata("testserver")
    assert full_name not in TOOL_CATALOG


# ────────────────────────────────────────────── DynamicMCPTool & Registry ──

def test_dynamic_mcp_tool_and_registry():
    mock_manager = MagicMock()
    mock_manager.call_tool_sync.return_value = MagicMock(ok=True, message="resultado sucesso")

    tool = DynamicMCPTool(
        server_id="filesystem",
        raw_name="read_file",
        description="Lê arquivo do disco",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}},
        manager=mock_manager,
    )

    assert tool.name == "mcp_filesystem_read_file"
    assert tool.description == "Lê arquivo do disco"
    assert tool.metadata.default_risk == "observe"

    # Executa a ferramenta
    res = tool.execute({"path": "test.txt"})
    assert res.ok is True
    mock_manager.call_tool_sync.assert_called_once_with("filesystem", "read_file", {"path": "test.txt"})

    # Teste de registro no ToolRegistry
    registry = ToolRegistry()
    registry.register_mcp_tool(tool)

    assert "mcp_filesystem_read_file" in registry.tools
    assert "mcp_filesystem_read_file" in registry.allowed_tool_names("general")

    # Desregistrar
    registry.unregister_mcp_tools("filesystem")
    assert "mcp_filesystem_read_file" not in registry.tools


# ───────────────────────────────────────────────────────── MCPManager Tests ──

def test_mcp_manager_lifecycle(tmp_path):
    config_file = str(tmp_path / "mcp_servers.json")
    mock_reg = MagicMock()
    manager = MCPManager(registry=mock_reg)

    with patch("app.mcp.manager.load_server_configs") as mock_load, \
         patch("app.mcp.manager.set_server_config") as mock_set, \
         patch("app.mcp.manager.remove_server_config") as mock_rem:

        # 1. Adicionar servidor com mock do MCPClient
        with patch("app.mcp.manager.MCPClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.status = "online"
            mock_client.last_error = ""
            mock_client.tools = [
                {"name": "fetch_page", "description": "Baixa uma página", "parameters": {}},
                {"name": "delete_cache", "description": "Apaga cache", "parameters": {}},
            ]
            mock_client_cls.return_value = mock_client

            cfg = MCPServerConfig(id="web", name="Web Tools", command="node", args=["web.js"])
            server_info = manager.add_or_update_server(cfg)

            assert server_info["id"] == "web"
            assert server_info["status"] == "online"
            assert server_info["tools_count"] == 2
            mock_client.connect.assert_called_once()
            assert mock_reg.register_mcp_tool.call_count == 2

            # 2. Listar ferramentas do manager
            tools = manager.list_tools("web")
            assert len(tools) == 2
            names = [t["name"] for t in tools]
            assert "mcp_web_fetch_page" in names
            assert "mcp_web_delete_cache" in names

            # 3. Invocar ferramenta sync
            mock_client.call_tool.return_value = MagicMock(
                isError=False,
                content=[MagicMock(type="text", text="Conteúdo HTML")],
                structuredContent={"status": 200},
            )
            call_res = manager.call_tool_sync("web", "fetch_page", {"url": "https://example.com"})
            assert call_res.ok is True
            assert "Conteúdo HTML" in call_res.message
            assert call_res.data["structured"] == {"status": 200}

            # 4. Reiniciar servidor
            with patch("app.mcp.manager.get_server_config", return_value=cfg):
                restart_res = manager.restart_server("web")
                assert restart_res["status"] == "online"

            # 5. Parar servidor desativado
            cfg_disabled = MCPServerConfig(id="web", name="Web Tools", command="node", enabled=False)
            update_res = manager.add_or_update_server(cfg_disabled)
            assert update_res["status"] == "disabled"
            mock_client.disconnect.assert_called()

            # 6. Remover servidor
            mock_rem.return_value = True
            removed = manager.remove_server("web")
            assert removed is True
            mock_reg.unregister_mcp_tools.assert_called_with("web")


# ───────────────────────────────────────────────────────────── API Endpoints ──

def test_mcp_api_endpoints():
    mock_handler = MagicMock()

    with patch("app.ui.panel.api.mcp.mcp_manager") as mock_mgr:
        mock_mgr.list_servers.return_value = [
            {"id": "git", "name": "Git MCP", "command": "npx", "status": "online", "tools_count": 3}
        ]
        mock_mgr.get_server.return_value = {
            "id": "git", "name": "Git MCP", "command": "npx", "status": "online", "tools_count": 3
        }
        mock_mgr.list_tools.return_value = [
            {"name": "mcp_git_commit", "server_id": "git", "risk": "low"}
        ]

        # GET /api/mcp/servers
        status, data = handle_mcp_get(["api", "mcp", "servers"], mock_handler)
        assert status == 200
        assert data["ok"] is True
        assert len(data["servers"]) == 1
        assert data["servers"][0]["id"] == "git"

        # GET /api/mcp/servers/git
        status, data = handle_mcp_get(["api", "mcp", "servers", "git"], mock_handler)
        assert status == 200
        assert data["server"]["id"] == "git"

        # GET /api/mcp/tools
        status, data = handle_mcp_get(["api", "mcp", "tools"], mock_handler)
        assert status == 200
        assert len(data["tools"]) == 1

        # POST /api/mcp/servers (adicionar)
        mock_mgr.add_or_update_server.return_value = {
            "id": "fs", "name": "Filesystem", "status": "online", "tools_count": 5
        }
        post_body = json.dumps({
            "id": "fs",
            "name": "Filesystem",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
        }).encode("utf-8")
        status, data = handle_mcp_post("/api/mcp/servers", post_body, mock_handler)
        assert status == 200
        assert data["ok"] is True
        assert data["server"]["id"] == "fs"

        # POST /api/mcp/servers/{id}/restart
        mock_mgr.restart_server.return_value = {"id": "fs", "status": "online"}
        status, data = handle_mcp_post("/api/mcp/servers/fs/restart", b"{}", mock_handler)
        assert status == 200
        assert data["server"]["status"] == "online"

        # DELETE /api/mcp/servers/{id}
        mock_mgr.remove_server.return_value = True
        status, data = handle_mcp_delete("/api/mcp/servers/fs", mock_handler)
        assert status == 200
        assert data["ok"] is True
