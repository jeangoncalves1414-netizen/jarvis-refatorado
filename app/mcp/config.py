"""Configuração e persistência de servidores MCP."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any

try:
    from app.storage.runtime_settings import DATA_DIR
except ImportError:
    DATA_DIR = os.path.join(os.getcwd(), "data")

MCP_SERVERS_FILE = os.path.join(DATA_DIR, "mcp_servers.json")


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_\-]+", "_", text.strip().lower())
    return cleaned.strip("_") or "server"


@dataclass(slots=True)
class MCPServerConfig:
    id: str
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.id:
            self.id = _slugify(self.name or self.command or "server")
        if not self.name:
            self.name = self.id

    @classmethod
    def from_dict(cls, data: dict[str, Any], fallback_id: str = "") -> MCPServerConfig:
        server_id = str(data.get("id") or fallback_id or "").strip()
        name = str(data.get("name") or server_id or "").strip()
        command = str(data.get("command") or "").strip()
        args = data.get("args") or []
        if isinstance(args, str):
            args = [a for a in args.split() if a]
        elif not isinstance(args, list):
            args = []
        else:
            args = [str(a) for a in args]

        env = data.get("env") or {}
        if not isinstance(env, dict):
            env = {}
        else:
            env = {str(k): str(v) for k, v in env.items()}

        enabled = bool(data.get("enabled", True))
        return cls(
            id=server_id or _slugify(name or command or "server"),
            name=name or server_id or "MCP Server",
            command=command,
            args=args,
            env=env,
            enabled=enabled,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_server_configs(file_path: str | None = None) -> dict[str, MCPServerConfig]:
    """Carrega todos os servidores MCP configurados.

    Suporta tanto formato com dicionário indexado por id quanto lista de servidores.
    """
    path = file_path or MCP_SERVERS_FILE
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return {}

    configs: dict[str, MCPServerConfig] = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            if isinstance(value, dict):
                cfg = MCPServerConfig.from_dict(value, fallback_id=str(key))
                configs[cfg.id] = cfg
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                cfg = MCPServerConfig.from_dict(item)
                configs[cfg.id] = cfg
    return configs


def save_server_configs(configs: dict[str, MCPServerConfig], file_path: str | None = None) -> None:
    """Salva configurações de servidores MCP no arquivo JSON."""
    path = file_path or MCP_SERVERS_FILE
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)

    data = {server_id: cfg.to_dict() for server_id, cfg in configs.items()}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_server_config(server_id: str, file_path: str | None = None) -> MCPServerConfig | None:
    configs = load_server_configs(file_path)
    return configs.get(server_id)


def set_server_config(config: MCPServerConfig, file_path: str | None = None) -> None:
    configs = load_server_configs(file_path)
    configs[config.id] = config
    save_server_configs(configs, file_path)


def remove_server_config(server_id: str, file_path: str | None = None) -> bool:
    configs = load_server_configs(file_path)
    if server_id in configs:
        del configs[server_id]
        save_server_configs(configs, file_path)
        return True
    return False
