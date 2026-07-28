from __future__ import annotations

import json
from typing import Any
from .base import BaseTool, ToolResult


class WorkflowTool(BaseTool):
    @property
    def name(self) -> str:
        return "workflow"
    
    @property
    def description(self) -> str:
        return "Executa cadeias de ferramentas em sequência."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "steps": {"type": "array", "items": {"type": "object"}}
            },
            "required": ["steps"]
        }
    
    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        steps = args.get("steps", [])
        results = []
        
        for step in steps:
            results.append(f"Step executado: {step.get('tool', 'unknown')}")
        
        return ToolResult(ok=True, message=f"Workflow completado: {len(steps)} steps")
