"""
Sandbox Runner — Execução Isolada e Segura de Scripts/Comandos
Inspirado no `CTF-Sandbox-Orchestrator` do reverse-skill.

Fornece um executor de sub-processo com:
  - Timeout automático configurável
  - Mascaramento de variáveis de ambiente sensíveis (API keys, tokens, senhas)
  - Denylist de comandos destrutivos/perigosos
  - Captura de stdout/stderr com limite de tamanho
  - Relatório de recursos utilizados (tempo real de execução)

AVISO: Este módulo não substitui um sandbox de kernel (cgroups, seccomp, namespaces).
Para isolamento total, utilize Docker ou execução em VM separada.
"""
from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any


# ── Configuração de Segurança ────────────────────────────────────────────────

# Padrões de variáveis de ambiente a mascarar (nunca enviar ao sub-processo)
_SENSITIVE_ENV_PATTERNS: list[re.Pattern] = [
    re.compile(r"(api[_-]?key|secret|token|password|passwd|pass|credentials?|auth|private[_-]?key)", re.IGNORECASE),
]

# Comandos ou substrings completamente proibidos em qualquer shell
_DENYLIST_PATTERNS: list[re.Pattern] = [
    re.compile(r"\brm\s+(-[a-zA-Z]+\s+)*(/|\*|C:\\)", re.IGNORECASE),
    re.compile(r"\b(mkfs|dd\s+if=|shutdown|reboot|halt|poweroff)\b", re.IGNORECASE),
    re.compile(r">(>\s*)?/dev/(sd[a-z]|nvme)", re.IGNORECASE),  # gravação em disco raw
    re.compile(r"\bfork\s*bomb\b|:\s*\(\s*\)\s*\{\s*:", re.IGNORECASE),
]

# Variáveis de ambiente seguras a sempre mascarar, além das heurísticas
_ALWAYS_MASK = {
    "GEMINI_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    "FISH_API_KEY", "DATABASE_URL", "REDIS_URL", "SECRET_KEY",
}

# Limite de output em bytes (para evitar payloads de exfiltração via stdout)
_MAX_OUTPUT_BYTES = 64 * 1024  # 64 KB


@dataclass
class SandboxResult:
    ok: bool
    return_code: int | None
    stdout: str
    stderr: str
    elapsed_s: float
    timed_out: bool = False
    blocked: bool = False
    block_reason: str = ""
    command_used: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "return_code": self.return_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "elapsed_s": round(self.elapsed_s, 3),
            "timed_out": self.timed_out,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
            "command_used": self.command_used,
        }


class SandboxRunner:
    """
    Executa comandos shell em sub-processo com isolamento de ambiente e timeout.
    """

    def __init__(
        self,
        default_timeout_s: float = 30.0,
        allow_network: bool = True,
        working_dir: str | None = None,
    ) -> None:
        self.default_timeout_s = default_timeout_s
        self.allow_network = allow_network
        self.working_dir = working_dir or os.getcwd()

    def _sanitize_env(self) -> dict[str, str]:
        """Retorna uma cópia do ambiente com variáveis sensíveis mascaradas."""
        safe_env: dict[str, str] = {}
        for key, val in os.environ.items():
            if key in _ALWAYS_MASK:
                continue
            if any(pat.search(key) for pat in _SENSITIVE_ENV_PATTERNS):
                continue
            safe_env[key] = val
        return safe_env

    def _check_denylist(self, command: str) -> str | None:
        """Retorna a razão de bloqueio se o comando for proibido, ou None se seguro."""
        for pat in _DENYLIST_PATTERNS:
            if pat.search(command):
                return f"Comando bloqueado: padrão perigoso detectado ({pat.pattern!r})"
        return None

    def run(
        self,
        command: str,
        timeout_s: float | None = None,
        shell: bool = True,
        stdin_data: str | None = None,
    ) -> SandboxResult:
        """
        Executa um comando no sandbox.
        command: string do comando a executar.
        timeout_s: tempo máximo em segundos (usa default_timeout_s se None).
        shell: se True, usa shell do sistema (cmd.exe no Windows, bash/sh no Linux).
        """
        timeout = timeout_s if timeout_s is not None else self.default_timeout_s
        t_start = time.monotonic()

        # Verificação de segurança
        block_reason = self._check_denylist(command)
        if block_reason:
            return SandboxResult(
                ok=False,
                return_code=None,
                stdout="",
                stderr=block_reason,
                elapsed_s=0.0,
                blocked=True,
                block_reason=block_reason,
                command_used=command[:200],
            )

        safe_env = self._sanitize_env()

        try:
            proc = subprocess.run(
                command,
                shell=shell,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.working_dir,
                env=safe_env,
                input=stdin_data,
            )
            elapsed = time.monotonic() - t_start
            stdout = proc.stdout[:_MAX_OUTPUT_BYTES]
            stderr = proc.stderr[:_MAX_OUTPUT_BYTES // 4]

            return SandboxResult(
                ok=proc.returncode == 0,
                return_code=proc.returncode,
                stdout=stdout,
                stderr=stderr,
                elapsed_s=elapsed,
                command_used=command[:200],
            )

        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - t_start
            return SandboxResult(
                ok=False,
                return_code=None,
                stdout="",
                stderr=f"Timeout após {timeout:.1f}s.",
                elapsed_s=elapsed,
                timed_out=True,
                command_used=command[:200],
            )

        except Exception as exc:
            elapsed = time.monotonic() - t_start
            return SandboxResult(
                ok=False,
                return_code=None,
                stdout="",
                stderr=str(exc),
                elapsed_s=elapsed,
                command_used=command[:200],
            )

    def run_python_code(self, code: str, timeout_s: float | None = None) -> SandboxResult:
        """
        Executa código Python em um sub-processo isolado usando payload base64.
        Previne problemas de caractere de escape e multilinhas no Windows CMD/PowerShell.
        """
        import sys
        import base64
        b64_code = base64.b64encode(code.encode("utf-8")).decode("ascii")
        wrapper = f"import base64; exec(base64.b64decode('{b64_code}').decode('utf-8'))"
        cmd = f'"{sys.executable}" -c "{wrapper}"'
        return self.run(cmd, timeout_s=timeout_s, shell=True)

    def dry_run_check(self, command: str) -> dict[str, Any]:
        """
        Verifica o comando sem executar. Retorna um relatório de segurança.
        """
        block_reason = self._check_denylist(command)
        masked_vars = [
            k for k in os.environ
            if k in _ALWAYS_MASK or any(pat.search(k) for pat in _SENSITIVE_ENV_PATTERNS)
        ]
        return {
            "would_be_blocked": block_reason is not None,
            "block_reason": block_reason or "Nenhum",
            "masked_env_vars": masked_vars,
            "timeout_s": self.default_timeout_s,
            "working_dir": self.working_dir,
            "command_preview": command[:300],
        }
