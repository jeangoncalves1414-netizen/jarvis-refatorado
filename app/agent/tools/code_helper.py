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
        
        if action == "explain":
            return ToolResult(ok=True, message=f"Explicação: {code[:100]}...")
        elif action == "generate":
            return ToolResult(ok=True, message=f"Snippet gerado para {args.get('language', 'python')}")
        elif action == "refactor":
            return ToolResult(ok=True, message="Código refatorado")
        
        return ToolResult(ok=False, message="Ação desconhecida")
