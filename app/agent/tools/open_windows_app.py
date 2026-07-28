from __future__ import annotations

from typing import Any
from .base import BaseTool, ToolResult


class OpenWindowsAppTool(BaseTool):
    """Gerencia aplicativos Windows (abrir, fechar, verificar status e listar)."""
    
    name = "open_windows_app"
    description = "Gerencia aplicativos Windows: abrir, fechar, verificar se está em execução ou listar apps abertos."
    
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["open", "close", "status", "list"],
                "description": "Ação: 'open' para abrir, 'close' para fechar, 'status' para verificar se está aberto, 'list' para listar apps em execução."
            },
            "app_name": {
                "type": "string",
                "description": "Nome do aplicativo (ex: spotify, chrome, notepad, calculator, code)"
            }
        },
        "required": ["action"]
    }
    
    def __init__(self):
        super().__init__()
        from app.services import AppManager
        self.app_manager = AppManager()
    
    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        action = str(args.get("action", "open")).lower().strip()
        app_name = str(args.get("app_name", "")).strip()

        if action == "list":
            running = self.app_manager.list_running_apps()
            if not running:
                return ToolResult(ok=True, message="Nenhum aplicativo principal em execução no momento.", data={"running": []})
            return ToolResult(ok=True, message=f"Aplicativos em execução no momento: {', '.join(running)}", data={"running": running})

        if not app_name:
            return ToolResult(ok=False, message="Nome do aplicativo não fornecido.")

        if action == "status":
            running, _ = self.app_manager.is_app_running(app_name)
            if running:
                return ToolResult(ok=True, message=f"O aplicativo '{app_name}' está em execução no momento.", data={"is_running": True})
            return ToolResult(ok=True, message=f"O aplicativo '{app_name}' NÃO está em execução.", data={"is_running": False})

        if action == "close":
            running, msg = self.app_manager.close_app(app_name)
            return ToolResult(ok=running, message=msg, data={"closed": running})

        # Default action: open
        # Se o app já estiver rodando, traz a janela para a frente
        is_running, _ = self.app_manager.is_app_running(app_name)
        if is_running:
            self.app_manager.focus_window(app_name)
            return ToolResult(ok=True, message=f"O aplicativo '{app_name}' já está aberto e em execução. Trouxe a janela para a frente.", data={"already_running": True})

        try:
            success = self.app_manager.open_app(app_name)
            if success:
                return ToolResult(ok=True, message=f"Aplicativo '{app_name}' aberto com sucesso.")
            else:
                return ToolResult(ok=False, message=f"Não foi possível abrir '{app_name}'. Verifique se está instalado.")
        except Exception as e:
            return ToolResult(ok=False, message=f"Erro ao abrir '{app_name}': {e}")

