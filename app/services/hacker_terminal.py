"""Hacker AI Remote Terminal & Motor de Permissões Granulares estilo Hacker.ai.

Gerencia a execução remota de comandos e scripts com 3 políticas de segurança:
  - ask_every_time (🔴 Perguntar sempre com explicação de IA do que o código faz)
  - allow_specific (🟡 Executar direto apenas comandos VIP da lista branca)
  - direct_execution (🟢 Execução autônoma direta sem pausas)
"""
from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

# Comandos considerados seguros por padrão no modo allow_specific
DEFAULT_ALLOWED_WHITELIST = {
    "git status", "git diff", "git log",
    "python --version", "node --version",
    "pytest", "dir", "echo", "where", "whoami"
}


@dataclass
class PendingCommand:
    id: str
    command: str
    risk_level: str  # "low" | "medium" | "high"
    explanation: str
    created_at: float
    status: str = "pending"  # "pending" | "approved" | "rejected" | "executed"


@dataclass
class CommandExecutionLog:
    id: str
    command: str
    timestamp: float
    policy_mode: str
    risk_level: str
    approved: bool
    exit_code: int
    output: str
    elapsed_sec: float


@dataclass
class PolicyChangeLog:
    id: str
    mode: str
    actor: str
    timestamp: float


class HackerTerminalEngine:
    """Motor de execução de comandos remotos estilo Hacker.ai."""

    def __init__(self, llm_service: Any = None, initial_policy: str = "ask_every_time") -> None:
        self.llm_service = llm_service
        self.policy_mode = initial_policy  # "ask_every_time" | "allow_specific" | "direct_execution"
        self.allowed_whitelist: set[str] = set(DEFAULT_ALLOWED_WHITELIST)
        self.pending_commands: dict[str, PendingCommand] = {}
        self.audit_logs: list[CommandExecutionLog] = []
        self.policy_audit: list[PolicyChangeLog] = []

    def set_policy_mode(self, mode: str, *, actor: str = "local") -> bool:
        mode = mode.lower().strip()
        if mode in {"ask_every_time", "allow_specific", "direct_execution"}:
            self.policy_mode = mode
            self.policy_audit.append(PolicyChangeLog(
                id=f"policy_{int(time.time())}_{os.urandom(2).hex()}",
                mode=mode,
                actor=str(actor or "unknown"),
                timestamp=time.time(),
            ))
            del self.policy_audit[:-100]
            return True
        return False

    def add_whitelisted_command(self, cmd: str) -> bool:
        if cmd and cmd.strip():
            self.allowed_whitelist.add(cmd.strip().lower())
            return True
        return False

    def analyze_command(self, command: str) -> dict[str, Any]:
        """Analisa o risco do comando e gera uma explicação clara em linguagem natural."""
        clean_cmd = command.strip()
        if not clean_cmd:
            return {"ok": False, "error": "Comando vazio."}

        # Verificação rápida de padrões perigosos (Heurística)
        high_risk_patterns = [
            r"\brm\s+-rf\b", r"\br mdir\b", r"\bformat\b", r"\bdel\s+/f\b",
            r"\bdrop\s+database\b", r"\bshutdown\b", r"\bcurl\s+.+\|\s*bash\b"
        ]
        is_high_risk = any(re.search(p, clean_cmd, re.IGNORECASE) for p in high_risk_patterns)
        risk_level = "high" if is_high_risk else ("medium" if len(clean_cmd) > 30 else "low")

        # Análise de IA para explicação do código
        if self.llm_service:
            prompt = (
                f"Analise este comando de terminal do Windows/Linux:\n`{clean_cmd}`\n\n"
                "Em no máximo 2 frases, explique exatamente:\n"
                "1. O que este comando faz no sistema.\n"
                "2. Se há risco de deletar arquivos ou alterar configurações sensíveis."
            )
            try:
                explanation = self.llm_service.ask(prompt)
            except Exception:
                explanation = f"Executa o comando de sistema '{clean_cmd[:40]}'."
        else:
            explanation = f"Comando de terminal: executa '{clean_cmd}'."

        return {
            "ok": True,
            "command": clean_cmd,
            "risk_level": risk_level,
            "explanation": explanation,
            "is_whitelisted": clean_cmd.lower() in self.allowed_whitelist
        }

    def prepare_or_execute(self, command: str, force_approved: bool = False) -> dict[str, Any]:
        """Prepara para pedir confirmação ou executa diretamente de acordo com a política."""
        clean_cmd = command.strip()
        if not clean_cmd:
            return {"ok": False, "error": "Comando não pode ser vazio."}

        analysis = self.analyze_command(clean_cmd)

        # Regra de decisão da política
        should_execute = False
        if force_approved:
            should_execute = True
        elif self.policy_mode == "direct_execution":
            should_execute = True
        elif self.policy_mode == "allow_specific":
            if analysis.get("is_whitelisted", False):
                should_execute = True
            else:
                should_execute = False
        elif self.policy_mode == "ask_every_time":
            should_execute = False

        if should_execute:
            return self._run_command_subprocess(clean_cmd, analysis["risk_level"], approved=True)

        # Se precisa de aprovação, registra comando pendente
        cmd_id = f"cmd_{int(time.time())}_{os.urandom(2).hex()}"
        pending = PendingCommand(
            id=cmd_id,
            command=clean_cmd,
            risk_level=analysis["risk_level"],
            explanation=analysis["explanation"],
            created_at=time.time()
        )
        self.pending_commands[cmd_id] = pending

        return {
            "ok": True,
            "status": "pending_approval",
            "cmd_id": cmd_id,
            "command": clean_cmd,
            "policy_mode": self.policy_mode,
            "risk_level": analysis["risk_level"],
            "explanation": analysis["explanation"],
            "message": f"Aviso de Segurança: Confirmação necessária antes de executar em modo '{self.policy_mode}'."
        }

    def prepare_for_approval(self, command: str) -> dict[str, Any]:
        """Create an HTTP-safe terminal preview; receipts authorize execution."""
        clean_cmd = command.strip()
        if not clean_cmd:
            return {"ok": False, "error": "Comando não pode ser vazio."}
        analysis = self.analyze_command(clean_cmd)
        cmd_id = f"cmd_{int(time.time())}_{os.urandom(2).hex()}"
        self.pending_commands[cmd_id] = PendingCommand(
            id=cmd_id, command=clean_cmd, risk_level=analysis["risk_level"],
            explanation=analysis["explanation"], created_at=time.time(),
        )
        return {
            "ok": True, "status": "pending_approval", "cmd_id": cmd_id,
            "command": clean_cmd, "policy_mode": self.policy_mode,
            "risk_level": analysis["risk_level"], "explanation": analysis["explanation"],
            "message": "Confirmação com recibo é necessária antes da execução remota.",
        }

    def approve_and_execute(self, cmd_id: str) -> dict[str, Any]:
        """Aprova e executa um comando previamente registrado como pendente."""
        pending = self.pending_commands.get(cmd_id)
        if not pending:
            return {"ok": False, "error": f"Comando id '{cmd_id}' não encontrado ou expirado."}

        pending.status = "approved"
        res = self._run_command_subprocess(pending.command, pending.risk_level, approved=True)
        pending.status = "executed"
        del self.pending_commands[cmd_id]
        return res

    def reject_pending(self, cmd_id: str) -> dict[str, Any]:
        """Rejeita a execução de um comando pendente."""
        pending = self.pending_commands.get(cmd_id)
        if not pending:
            return {"ok": False, "error": f"Comando id '{cmd_id}' não encontrado."}

        pending.status = "rejected"
        del self.pending_commands[cmd_id]
        return {"ok": True, "message": f"Execução do comando '{pending.command}' rejeitada pelo usuário."}

    def approve_pending(self, cmd_id: str) -> dict[str, Any]:
        """Consume a preview confirmation without executing its command."""
        pending = self.pending_commands.pop(cmd_id, None)
        if not pending:
            return {"ok": False, "error": f"Comando id '{cmd_id}' não encontrado ou expirado."}
        pending.status = "approved"
        return {"ok": True, "command": pending.command, "risk_level": pending.risk_level}

    def _run_command_subprocess(self, command: str, risk_level: str, approved: bool) -> dict[str, Any]:
        """Executa o comando em sub-processo com medição de tempo e salvamento no histórico."""
        start = time.time()
        try:
            completed = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=20
            )
            elapsed = round(time.time() - start, 2)
            stdout = completed.stdout or ""
            stderr = completed.stderr or ""
            output = (stdout + ("\n[STDERR]\n" + stderr if stderr else "")).strip()

            log = CommandExecutionLog(
                id=f"exec_{int(time.time())}",
                command=command,
                timestamp=time.time(),
                policy_mode=self.policy_mode,
                risk_level=risk_level,
                approved=approved,
                exit_code=completed.returncode,
                output=output,
                elapsed_sec=elapsed
            )
            self.audit_logs.append(log)

            return {
                "ok": completed.returncode == 0,
                "status": "executed",
                "command": command,
                "exit_code": completed.returncode,
                "output": output,
                "elapsed_sec": elapsed
            }
        except subprocess.TimeoutExpired:
            elapsed = round(time.time() - start, 2)
            return {"ok": False, "status": "timeout", "command": command, "error": "Comando excedeu limite de 20s.", "elapsed_sec": elapsed}
        except Exception as exc:
            return {"ok": False, "status": "error", "command": command, "error": f"Falha na execução: {exc}"}

    def get_audit_logs(self, limit: int = 20) -> list[dict[str, Any]]:
        """Retorna o histórico de execuções auditadas."""
        logs = self.audit_logs[-limit:]
        return [
            {
                "id": l.id,
                "command": l.command,
                "timestamp": l.timestamp,
                "policy_mode": l.policy_mode,
                "risk_level": l.risk_level,
                "approved": l.approved,
                "exit_code": l.exit_code,
                "output": l.output[:500],
                "elapsed_sec": l.elapsed_sec
            }
            for l in reversed(logs)
        ]


# Instância global do motor de terminal hacker
hacker_terminal = HackerTerminalEngine()
