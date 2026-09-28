"""Ferramenta do Agente para Deobfuscamento JS/AST."""
from __future__ import annotations

from typing import Any
from .base import BaseTool, ToolResult
from app.services.js_deobfuscator import js_deobfuscator


class JsReverseTool(BaseTool):
    name = "js_deobfuscate"
    description = "Analisa e deobfusca trechos de código JavaScript ou TypeScript via AST e expressões regulares."

    def run(self, code: str = "", **kwargs: Any) -> dict[str, Any]:
        return js_deobfuscator.deobfuscate(code)

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        code = str(args.get("code") or args.get("script") or "").strip()
        if not code:
            return ToolResult(ok=False, message="Código JS não informado.")
        res = self.run(code=code)
        if not res.get("ok"):
            return ToolResult(ok=False, message=res.get("error", "Falha no deobfuscamento."))
        msg = f"Deobfuscamento concluído ({res.get('reduction_percentage')}% de redução de obfuscadores):\n\n{res.get('code')}"
        return ToolResult(ok=True, message=msg, data=res)
