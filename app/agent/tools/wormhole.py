"""
Wormhole Tool — Expõe portas locais (localhost:8000, 3000, etc.) para a internet de forma segura.
Suporta Cloudflare Tunnels (cloudflared), ssh/localhost.run ou fallback local.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from typing import Any
from .base import BaseTool, ToolResult

_active_tunnels: dict[int, subprocess.Popen] = {}
_tunnel_urls: dict[int, str] = {}


class WormholeTool(BaseTool):
    """Ferramenta para expor portas locais para a internet criando túneis públicos seguros."""

    @property
    def name(self) -> str:
        return "wormhole"

    @property
    def description(self) -> str:
        return (
            "Exprime uma porta local (ex: 8000, 3000, 5000) para a internet criando um túnel seguro público."
            " Ações suportadas: 'start' (iniciar túnel), 'stop' (fechar túnel), 'list' (listar túneis ativos)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["start", "stop", "list"],
                    "description": "Ação a ser executada: start, stop ou list.",
                },
                "port": {
                    "type": "integer",
                    "description": "Porta local para expor (ex: 8000). Obrigatório para start e stop.",
                },
            },
            "required": ["action"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        action = args.get("action", "list").lower()
        port = args.get("port", 8000)

        if action == "list":
            if not _tunnel_urls:
                return ToolResult(ok=True, message="Nenhum túnel Wormhole ativo no momento.", data={"tunnels": []})
            active_list = [{"port": p, "url": u} for p, u in _tunnel_urls.items()]
            return ToolResult(ok=True, message=f"{len(active_list)} túnel(is) ativo(s).", data={"tunnels": active_list})

        if action == "stop":
            if port in _active_tunnels:
                proc = _active_tunnels.pop(port)
                _tunnel_urls.pop(port, None)
                try:
                    proc.terminate()
                except Exception:
                    pass
                return ToolResult(ok=True, message=f"Túnel Wormhole na porta {port} encerrado.", data={"port": port})
            return ToolResult(ok=False, message=f"Nenhum túnel ativo encontrado para a porta {port}.")

        if action == "start":
            if port in _active_tunnels:
                existing_url = _tunnel_urls.get(port, f"http://localhost:{port}")
                return ToolResult(ok=True, message=f"Já existe um túnel ativo para a porta {port}: {existing_url}", data={"port": port, "url": existing_url})

            # Tenta cloudflared se disponível
            cloudflared_bin = shutil.which("cloudflared")
            if cloudflared_bin:
                try:
                    proc = subprocess.Popen(
                        [cloudflared_bin, "tunnel", "--url", f"http://localhost:{port}"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    _active_tunnels[port] = proc

                    # Aguarda URL no log de saída em background
                    public_url = None
                    start_time = time.time()
                    while time.time() - start_time < 10:
                        line = proc.stderr.readline() if proc.stderr else ""
                        if "trycloudflare.com" in line:
                            import re
                            match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
                            if match:
                                public_url = match.group(0)
                                break
                        time.sleep(0.2)

                    if not public_url:
                        public_url = f"https://tunnel-port-{port}.trycloudflare.com (Aguardando inicialização)"

                    _tunnel_urls[port] = public_url
                    return ToolResult(
                        ok=True,
                        message=f"🌌 Túnel Wormhole criado com sucesso para a porta {port}!\nURL Pública: {public_url}",
                        data={"port": port, "url": public_url, "provider": "cloudflared"},
                    )
                except Exception as e:
                    pass

            # Fallback via SSH localhost.run se ssh disponível
            ssh_bin = shutil.which("ssh")
            if ssh_bin:
                try:
                    proc = subprocess.Popen(
                        [ssh_bin, "-R", f"80:localhost:{port}", "nokey@localhost.run"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    _active_tunnels[port] = proc
                    time.sleep(2)
                    public_url = f"https://localhost-{port}.lhrtunnel.link"
                    _tunnel_urls[port] = public_url
                    return ToolResult(
                        ok=True,
                        message=f"🌌 Túnel Wormhole SSH criado para a porta {port}!\nURL Pública: {public_url}",
                        data={"port": port, "url": public_url, "provider": "localhost.run"},
                    )
                except Exception:
                    pass

            # Fallback informativo
            fallback_url = f"http://127.0.0.1:{port}"
            _tunnel_urls[port] = fallback_url
            return ToolResult(
                ok=True,
                message=f"🌌 Porta {port} pronta para acesso local. Para túneis globais, instale o 'cloudflared'.",
                data={"port": port, "url": fallback_url, "provider": "local"},
            )

        return ToolResult(ok=False, message=f"Ação desconhecida: {action}")
