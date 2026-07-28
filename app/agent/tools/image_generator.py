from __future__ import annotations

from typing import Any
from .base import BaseTool, ToolResult


class ImageGeneratorTool(BaseTool):
    @property
    def name(self) -> str:
        return "image_generator"
    
    @property
    def description(self) -> str:
        return "Gera imagens via API (placeholder)."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "size": {"type": "string", "enum": ["256x256", "512x512", "1024x1024"]}
            },
            "required": ["prompt"]
        }
    
    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        prompt = args.get("prompt", "")
        return ToolResult(ok=True, message=f"Imagem gerada para: {prompt[:50]}...")
