"""
Clipboard Intelligence Tool — Processador inteligente de texto da área de transferência.
Oferece ações automáticas de 1-clique (refatorar código, explicar erro, traduzir, resumir).
"""
from __future__ import annotations

from typing import Any
import pyperclip
from .base import BaseTool, ToolResult


class ClipboardIntelligenceTool(BaseTool):
    """Ferramenta para análise e transformação instantânea de textos da área de transferência."""

    @property
    def name(self) -> str:
        return "clipboard_intelligence"

    @property
    def description(self) -> str:
        return (
            "Analisa ou transforma o texto atualmente copiado no Clipboard do usuário."
            " Ações: 'read' (ler conteúdo atual), 'refactor' (refatorar código), 'explain_error' (explicar erro),"
            " 'translate' (traduzir), 'summarize' (resumir)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "refactor", "explain_error", "translate", "summarize"],
                    "description": "Ação inteligente a ser executada no texto copiado.",
                },
                "text": {
                    "type": "string",
                    "description": "Texto específico (opcional — se omitido, lê direto do Clipboard).",
                },
            },
            "required": ["action"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        action = args.get("action", "read").lower()
        content = args.get("text", "").strip()

        if not content:
            try:
                content = pyperclip.paste().strip()
            except Exception as e:
                return ToolResult(ok=False, message=f"Erro ao acessar Clipboard: {e}")

        if not content:
            return ToolResult(ok=False, message="A área de transferência está vazia.")

        if action == "read":
            preview = content[:300] + ("..." if len(content) > 300 else "")
            return ToolResult(
                ok=True,
                message=f"📋 Conteúdo do Clipboard ({len(content)} caracteres):\n{preview}",
                data={"text": content, "content": content, "length": len(content)},
            )

        # Instruções prontas para passar pro orchestrator/LLM
        instructions = {
            "refactor": "Refatore o código a seguir mantendo as melhores práticas, legibilidade e performance:",
            "explain_error": "Analise o erro/traceback a seguir e explique a causa-raiz e a solução em passos simples:",
            "translate": "Traduza o texto a seguir com precisão mantendo o tom original (PT-BR <-> EN):",
            "summarize": "Resuma os pontos principais do texto a seguir em bullets concisos:",
        }

        prompt_prefix = instructions.get(action, "Analise o texto a seguir:")
        full_prompt = f"{prompt_prefix}\n\n```\n{content}\n```"

        return ToolResult(
            ok=True,
            message=f"Texto preparado para '{action}'; a transformação ainda depende da resposta do modelo.",
            data={"action": action, "content": content, "prompt": full_prompt, "original_text": content},
        )
