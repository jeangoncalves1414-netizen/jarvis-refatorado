"""
Desktop Automation Tool - Ferramenta para automação de desktop.
"""

from __future__ import annotations

from typing import Any
from .base import BaseTool, ToolResult
from ..automation.desktop_automation import get_automation


class DesktopAutomationTool(BaseTool):
    @property
    def name(self) -> str:
        return "desktop_automation"

    @property
    def description(self) -> str:
        return (
            "Automação de desktop: abrir aplicações, URLs, arquivos, pastas, "
            "controlar janelas. Use action='open_app' para apps, 'open_url' para URLs, "
            "'open_file' para arquivos, 'open_folder' para pastas, 'list_windows' para janelas, "
            "'focus_window' para focar, 'minimize_window' para minimizar."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "open_app",
                        "open_url",
                        "open_file",
                        "open_folder",
                        "list_windows",
                        "focus_window",
                        "minimize_window",
                        "system_info",
                        "screen_resolution"
                    ],
                    "description": "Ação a executar.",
                },
                "app_name": {
                    "type": "string",
                    "description": "Nome da aplicação (ex: chrome, notepad, vscode).",
                },
                "url": {
                    "type": "string",
                    "description": "URL para abrir.",
                },
                "path": {
                    "type": "string",
                    "description": "Caminho do arquivo ou pasta.",
                },
                "title": {
                    "type": "string",
                    "description": "Título da janela (para focus/minimize).",
                },
            },
            "required": ["action"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        automation = get_automation()
        action = str(args.get("action", ""))

        if action == "open_app":
            app_name = str(args.get("app_name", "")).strip()
            if not app_name:
                return ToolResult(ok=False, message="Nome da aplicação é obrigatório.")
            
            success = automation.open_app(app_name)
            if success:
                return ToolResult(ok=True, message=f"Aplicação {app_name} aberta.")
            else:
                return ToolResult(ok=False, message=f"Não foi possível abrir {app_name}.")

        elif action == "open_url":
            url = str(args.get("url", "")).strip()
            if not url:
                return ToolResult(ok=False, message="URL é obrigatória.")
            
            success = automation.open_url(url)
            if success:
                return ToolResult(ok=True, message=f"URL aberta: {url}")
            else:
                return ToolResult(ok=False, message="Não foi possível abrir a URL.")

        elif action == "open_file":
            path = str(args.get("path", "")).strip()
            if not path:
                return ToolResult(ok=False, message="Caminho do arquivo é obrigatório.")
            
            success = automation.open_file(path)
            if success:
                return ToolResult(ok=True, message=f"Arquivo aberto: {path}")
            else:
                return ToolResult(ok=False, message="Não foi possível abrir o arquivo.")

        elif action == "open_folder":
            path = str(args.get("path", "")).strip()
            if not path:
                return ToolResult(ok=False, message="Caminho da pasta é obrigatório.")
            
            success = automation.open_folder(path)
            if success:
                return ToolResult(ok=True, message=f"Pasta aberta: {path}")
            else:
                return ToolResult(ok=False, message="Não foi possível abrir a pasta.")

        elif action == "list_windows":
            windows = automation.list_open_windows()
            if not windows:
                return ToolResult(ok=True, message="Nenhuma janela encontrada ou OS não suportado.", data={"windows": []})
            
            lines = [f"Encontradas {len(windows)} janelas:"]
            for i, win in enumerate(windows[:10], 1):
                lines.append(f"{i}. {win['title']}")
            
            return ToolResult(
                ok=True,
                message="\n".join(lines),
                data={"windows": windows, "count": len(windows)}
            )

        elif action == "focus_window":
            title = str(args.get("title", "")).strip()
            if not title:
                return ToolResult(ok=False, message="Título da janela é obrigatório.")
            
            success = automation.focus_window(title)
            if success:
                return ToolResult(ok=True, message=f"Janela focada: {title}")
            else:
                return ToolResult(ok=False, message="Não foi possível focar a janela.")

        elif action == "minimize_window":
            title = str(args.get("title", "")).strip()
            if not title:
                return ToolResult(ok=False, message="Título da janela é obrigatório.")
            
            success = automation.minimize_window(title)
            if success:
                return ToolResult(ok=True, message=f"Janela minimizada: {title}")
            else:
                return ToolResult(ok=False, message="Não foi possível minimizar a janela.")

        elif action == "system_info":
            info = automation.get_system_info()
            lines = [
                f"SO: {info['os']} {info['os_version']}",
                f"Processador: {info['processor']}",
                f"Arquitetura: {info['machine']}",
                f"Python: {info['python_version']}"
            ]
            return ToolResult(
                ok=True,
                message="\n".join(lines),
                data=info
            )

        elif action == "screen_resolution":
            resolution = automation.get_screen_resolution()
            if resolution:
                return ToolResult(
                    ok=True,
                    message=f"Resolução: {resolution[0]}x{resolution[1]}",
                    data={"width": resolution[0], "height": resolution[1]}
                )
            else:
                return ToolResult(ok=False, message="Não foi possível obter a resolução.")

        return ToolResult(ok=False, message=f"Ação desconhecida: {action}")
