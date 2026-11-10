"""
script_runner.py — Fase 5
Ferramenta que solicita ao frontend confirmação antes de executar
um bloco de código Python ou PowerShell no sistema do usuário.

Fluxo:
  1. Jarvis chama script_runner(language, code, description)
  2. A ferramenta valida o código (análise estática básica)
  3. A ferramenta retorna {"needs_confirmation": true, ...}
  4. O orchestrator serializa esse resultado no reply
  5. O frontend detecta o campo needs_confirmation → exibe modal
  6. Usuário aprova → POST /api/script/run → executa e retorna stdout/stderr
"""
from __future__ import annotations

import json
import re
import ast
import logging
from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

# Security patterns that are not allowed in scripts
DANGEROUS_PYTHON_PATTERNS = [
    r'__import__\s*\(',
    r'eval\s*\(',
    r'exec\s*\(',
    r'compile\s*\(',
    r'open\s*\(',
    r'\.__class__',
    r'\.__bases__',
    r'\.__subclasses__',
    r'\.__globals__',
    r'\.__code__',
    r'\.__func__',
    r'os\.system',
    r'subprocess\.',
    r'globals\s*\(\)',
    r'locals\s*\(\)',
    r'getattr\s*\(',
    r'setattr\s*\(',
    r'delattr\s*\(',
    r'__builtins__',
]

DANGEROUS_POWERSHELL_PATTERNS = [
    r'Invoke-Expression',
    r'iex\s+',
    r'Invoke-Command',
    r'icm\s+',
    r'Start-Process',
    r'WScript\.Shell',
    r'New-Object\s+System\.Diagnostics\.Process',
    r'\[System\.Reflection\.Assembly\]',
    r'Add-Type',
    r'Invoke-WebRequest',
    r'Invoke-RestMethod',
    r'Out-File',
    r'Set-Content',
    r'Add-Content',
    r'Remove-Item',
    r'Remove-ItemProperty',
    r'Registry::',
    r'HKEY_',
    r'HKLM:',
    r'HKCU:',
    r'HKCR:',
    r'Get-Credential',
    r'Get-Process',
    r'Stop-Process',
    r'Kill-Process',
]

MAX_CODE_LENGTH = 10000


def _validate_python_code(code: str) -> tuple[bool, str]:
    """Validate Python code for security issues.
    
    Args:
        code: The Python code to validate
        
    Returns:
        (is_valid, error_message)
    """
    if len(code) > MAX_CODE_LENGTH:
        return False, f"Código muito longo (máximo {MAX_CODE_LENGTH} caracteres)"
    
    # Check syntax
    try:
        ast.parse(code)
    except SyntaxError as e:
        return False, f"Erro de sintaxe Python: {e}"
    
    # Check for dangerous patterns
    for pattern in DANGEROUS_PYTHON_PATTERNS:
        if re.search(pattern, code, re.IGNORECASE):
            logger.warning(f"Blocked dangerous Python pattern: {pattern}")
            return False, f"Código contém padrão perigoso não permitido: {pattern}"
    
    return True, ""


def _validate_powershell_code(code: str) -> tuple[bool, str]:
    """Validate PowerShell code for security issues.
    
    Args:
        code: The PowerShell code to validate
        
    Returns:
        (is_valid, error_message)
    """
    if len(code) > MAX_CODE_LENGTH:
        return False, f"Código muito longo (máximo {MAX_CODE_LENGTH} caracteres)"
    
    # Check for dangerous patterns
    for pattern in DANGEROUS_POWERSHELL_PATTERNS:
        if re.search(pattern, code, re.IGNORECASE):
            logger.warning(f"Blocked dangerous PowerShell pattern: {pattern}")
            return False, f"Código contém padrão perigoso não permitido: {pattern}"
    
    return True, ""


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
        
        # Validate code based on language
        if language == "python":
            is_valid, error_msg = _validate_python_code(code)
            if not is_valid:
                return ToolResult(ok=False, message=error_msg)
        elif language == "powershell":
            is_valid, error_msg = _validate_powershell_code(code)
            if not is_valid:
                return ToolResult(ok=False, message=error_msg)

        # Se o Modo Liberado estiver ativado, executa diretamente sem exigir confirmação manual
        from app.storage.auto_approvals import auto_approvals
        if auto_approvals.liberated():
            import subprocess, sys, tempfile, os
            try:
                if language == "python":
                    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as f:
                        f.write(code)
                        tmp_path = f.name
                    try:
                        res = subprocess.run(
                            [sys.executable, tmp_path],
                            capture_output=True, text=True, timeout=30,
                            encoding="utf-8", errors="replace"
                        )
                    finally:
                        try:
                            os.unlink(tmp_path)
                        except Exception:
                            pass
                else:
                    res = subprocess.run(
                        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", code],
                        capture_output=True, text=True, timeout=30,
                        encoding="utf-8", errors="replace"
                    )

                stdout = (res.stdout or "").strip()
                stderr = (res.stderr or "").strip()
                if res.returncode == 0:
                    output_msg = stdout or "Código executado com sucesso (sem saída no console)."
                    return ToolResult(
                        ok=True,
                        message=f"Script {language} executado com sucesso (Modo Liberado):\n{output_msg}",
                        data={"stdout": stdout, "stderr": stderr, "exit_code": 0, "auto_approved": True}
                    )
                else:
                    err_msg = stderr or stdout or f"Código de saída: {res.returncode}"
                    return ToolResult(
                        ok=False,
                        message=f"Falha na execução do script {language} (Modo Liberado):\n{err_msg}",
                        data={"stdout": stdout, "stderr": stderr, "exit_code": res.returncode}
                    )
            except subprocess.TimeoutExpired:
                return ToolResult(ok=False, message="Execução do script expirou (timeout de 30 segundos).")
            except Exception as exc:
                return ToolResult(ok=False, message=f"Falha ao executar script: {exc}")

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
