"""Coder Subagent: Especialista em Desenvolvimento, Diagnóstico de Código e Execução de Testes."""
from __future__ import annotations

import ast
from typing import Any


class CoderSubagent:
    """Sub-agente especializado em Engenharia de Software e Desenvolvimento."""

    name = "coder_agent"
    description = "Analisa repositórios, gera código limpo, valida sintaxe AST e resolve bugs."

    def __init__(self, llm_service: Any = None) -> None:
        self.llm_service = llm_service

    def execute_task(self, prompt: str, code_snippet: str = "", **kwargs: Any) -> dict[str, Any]:
        """Executa uma tarefa de codificação ou depuração."""
        if not prompt:
            return {"ok": False, "error": "Prompt não fornecido ao CoderSubagent."}

        full_prompt = (
            "Você é o CoderSubagent do Jarvis, especialista em Python/TypeScript.\n"
            f"Instruções: {prompt}\n\n"
        )
        if code_snippet:
            full_prompt += f"Código Relevante:\n```python\n{code_snippet}\n```\n\n"

        full_prompt += "Retorne uma solução completa, modular e com tratamento de erros."

        if self.llm_service:
            generated_code = self.llm_service.ask(full_prompt)
        else:
            generated_code = f"# Solução para: {prompt}\ndef solution():\n    pass\n"

        # Validação de Sintaxe AST (se for código Python)
        clean_code = generated_code.replace("```python", "").replace("```", "").strip()
        ast_valid, ast_error = self.validate_ast(clean_code)

        return {
            "ok": ast_valid,
            "agent": self.name,
            "code": clean_code,
            "ast_valid": ast_valid,
            "ast_error": ast_error,
            "summary": "Código gerado e validado via AST." if ast_valid else f"Falha de sintaxe AST: {ast_error}"
        }

    def validate_ast(self, code: str) -> tuple[bool, str]:
        try:
            ast.parse(code)
            return True, ""
        except SyntaxError as exc:
            return False, f"Linha {exc.lineno}: {exc.msg}"
        except Exception as exc:
            return False, str(exc)
