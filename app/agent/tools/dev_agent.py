from __future__ import annotations

from typing import Any
from .base import BaseTool, ToolResult


class DevAgentTool(BaseTool):
    @property
    def name(self) -> str:
        return "dev_agent"
    
    @property
    def description(self) -> str:
        return "Agente especializado em desenvolvimento de software."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {"type": "string", "enum": ["review", "debug", "test"]},
                "code": {"type": "string"}
            },
            "required": ["task"]
        }
    
    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        task = args.get("task")
        if task in {"review", "debug", "test"}:
            return ToolResult(ok=False, message="O agente de desenvolvimento ainda não está implementado. Nenhuma revisão, depuração ou teste foi executado.")

        return ToolResult(ok=False, message="Tarefa desconhecida")
