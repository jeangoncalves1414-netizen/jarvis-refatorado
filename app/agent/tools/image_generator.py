from __future__ import annotations

from typing import Any
from .base import BaseTool, ToolResult


class ImageGeneratorTool(BaseTool):
    @property
    def name(self) -> str:
        return "image_generator"
    
    @property
    def description(self) -> str:
        return "Gera uma imagem com o modelo configurado (Oxyy quando disponível)."
    
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
        prompt = str(args.get("prompt", "")).strip()
        if not prompt:
            return ToolResult(ok=False, message="Descreva a imagem que deseja gerar.")
        settings = (context or {}).get("settings")
        keys = getattr(settings, "oxyy_api_keys", []) or [getattr(settings, "oxyy_api_key", "")]
        keys = [str(key).strip() for key in keys if str(key).strip()]
        if not keys:
            return ToolResult(ok=False, message="Configure uma chave Oxyy para gerar imagens.")
        try:
            from openai import OpenAI
            last_error: Exception | None = None
            for key in keys:
                try:
                    client = OpenAI(api_key=key, base_url=getattr(settings, "oxyy_base_url", "https://api.oxyy.ai/v1"))
                    result = client.images.generate(
                        model=getattr(settings, "oxyy_image_model", "dall-e-3"),
                        prompt=prompt,
                        n=1,
                        size=str(args.get("size", "1024x1024")),
                    )
                    item = result.data[0]
                    url = getattr(item, "url", None) or (item.get("url") if isinstance(item, dict) else None)
                    if url:
                        return ToolResult(ok=True, message="Imagem gerada com sucesso.", data={"url": url, "model": getattr(settings, "oxyy_image_model", "dall-e-3")})
                    last_error = RuntimeError("Oxyy não retornou uma URL de imagem.")
                except Exception as exc:
                    last_error = exc
            return ToolResult(ok=False, message=f"Falha ao gerar imagem via Oxyy: {last_error}")
        except Exception as exc:
            return ToolResult(ok=False, message=f"Falha ao gerar imagem via Oxyy: {exc}")
