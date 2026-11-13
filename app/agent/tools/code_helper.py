from __future__ import annotations

from typing import Any
from .base import BaseTool, ToolResult


class CodeHelperTool(BaseTool):
    @property
    def name(self) -> str:
        return "code_helper"
    
    @property
    def description(self) -> str:
        return "Auxilia em tarefas de código: gerar snippets, explicar, refatorar."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["generate", "explain", "refactor"]},
                "code": {"type": "string"},
                "language": {"type": "string"}
            },
            "required": ["action", "code"]
        }
    
    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        action = args.get("action")
        code = args.get("code", "")
        
        if action in {"explain", "generate", "refactor"}:
            return ToolResult(ok=False, message="Esta ferramenta de código ainda não possui implementação. Nenhum código foi gerado, explicado ou refatorado.")

        return ToolResult(ok=False, message="Ação desconhecida")
