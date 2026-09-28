"""Ferramenta do Agente para Auditoria de Segurança em LLMs e Injeção de Prompt."""
from __future__ import annotations

from typing import Any
from .base import BaseTool, ToolResult
from app.services.llm_security_auditor import llm_security_auditor


class LLMSecurityTool(BaseTool):
    name = "llm_security_audit"
    description = "Inspeciona prompts e instruções em busca de injeções de prompt, jailbreaks e riscos OWASP LLM Top 10."

    def run(self, prompt_text: str = "", **kwargs: Any) -> dict[str, Any]:
        return llm_security_auditor.audit_prompt(prompt_text)

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        text = str(args.get("prompt_text") or args.get("text") or "").strip()
        if not text:
            return ToolResult(ok=False, message="Texto para auditoria não informado.")

        res = self.run(prompt_text=text)
        risk = res.get("overall_risk", "SAFE")
        count = res.get("findings_count", 0)
        msg = f"Auditoria de Segurança LLM: Risco Geral = [{risk}] ({count} vulnerabilidade(s) encontrada(s))."
        return ToolResult(ok=True, message=msg, data=res)
