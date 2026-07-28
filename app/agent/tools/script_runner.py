"""
script_runner.py — Fase 5
Ferramenta que solicita ao frontend confirmação antes de executar
um bloco de código Python ou PowerShell no sistema do usuário.

Fluxo:
  1. Jarvis chama script_runner(language, code, description)
  2. A ferramenta retorna {"needs_confirmation": true, ...}
  3. O orchestrator serializa esse resultado no reply
  4. O frontend detecta o campo needs_confirmation → exibe modal
  5. Usuário aprova → POST /api/script/run → executa e retorna stdout/stderr
"""
from __future__ import annotations

import json
from .base import BaseTool, ToolResult


class ScriptRunnerTool(BaseTool):
    """Solicita ao usuário confirmação para executar um script Python ou PowerShell."""

    @property
    def name(self) -> str:
        return "script_runner"

    @property
    def description(self) -> str:
        return (
            "Solicita ao usuário permissão para executar um bloco de código Python ou PowerShell "
            "no computador. Use quando precisar automatizar uma tarefa que requer execução de código. "
            "Nunca execute código diretamente — sempre use esta ferramenta para garantir a confirmação do usuário."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "language": {
                    "type": "string",
                    "enum": ["python", "powershell"],
                    "description": "Linguagem do script: 'python' ou 'powershell'."
                },
                "code": {
                    "type": "string",
                    "description": "O código a ser executado. Deve ser completo e funcional."
                },
                "description": {
                    "type": "string",
                    "description": "Descrição clara do que o script faz, em linguagem natural para o usuário."
                },
            },
            "required": ["language", "code", "description"],
        }

    def execute(self, args: dict, context: dict | None = None) -> ToolResult:
        language = args.get("language", "python").lower()
        code = args.get("code", "").strip()
        description = args.get("description", "Executar script")

        if not code:
            return ToolResult(ok=False, message="Código do script não pode ser vazio.")
        if language not in ("python", "powershell"):
            return ToolResult(ok=False, message=f"Linguagem '{language}' não suportada. Use 'python' ou 'powershell'.")

        # Retorna uma solicitação de confirmação — o frontend detecta esse campo
        payload = json.dumps({
            "needs_confirmation": True,
            "language": language,
            "code": code,
            "description": description,
        }, ensure_ascii=False)

        return ToolResult(
            ok=True,
            message=f"__SCRIPT_CONFIRM__{payload}",
            data={
                "needs_confirmation": True,
                "language": language,
                "code": code,
                "description": description,
            }
        )
