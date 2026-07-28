"""Ferramenta para controle do System Tray e Boot Automático do Jarvis."""
from __future__ import annotations

from typing import Any
from .base import BaseTool, ToolResult


class SystemTrayTool(BaseTool):
    @property
    def name(self) -> str:
        return "system_tray"

    @property
    def description(self) -> str:
        return (
            "Controla o System Tray e a inicialização automática do Jarvis com o Windows. "
            "Permite ativar/desativar o boot automático e verificar o status atual."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["enable_boot", "disable_boot", "status"],
                    "description": (
                        "'enable_boot': ativar inicialização automática com Windows, "
                        "'disable_boot': remover da inicialização automática, "
                        "'status': verificar estado atual."
                    ),
                },
            },
            "required": ["action"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        action = args.get("action")

        try:
            from app.services.tray import BootService
        except ImportError:
            return ToolResult(ok=False, message="Módulo de System Tray não disponível neste ambiente.")

        if action == "status":
            active = BootService.is_enabled()
            if active:
                msg = "✅ Jarvis está configurado para iniciar automaticamente com o Windows."
            else:
                msg = "🔲 Jarvis NÃO está na inicialização automática do Windows."
            return ToolResult(ok=True, message=msg, data={"boot_enabled": active})

        elif action == "enable_boot":
            ok = BootService.enable()
            if ok:
                return ToolResult(ok=True, message="✅ Jarvis configurado para iniciar automaticamente com o Windows, Sir. Na próxima reinicialização ele já estará rodando.")
            return ToolResult(ok=False, message="❌ Falha ao registrar a inicialização automática. Verifique permissões do Registro.")

        elif action == "disable_boot":
            ok = BootService.disable()
            if ok:
                return ToolResult(ok=True, message="🔲 Jarvis removido da inicialização automática do Windows, Sir.")
            return ToolResult(ok=False, message="❌ Falha ao remover a inicialização automática.")

        return ToolResult(ok=False, message=f"Ação desconhecida: {action}")
