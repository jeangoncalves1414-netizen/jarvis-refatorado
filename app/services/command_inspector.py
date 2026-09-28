"""
Command Inspector & Dry-Run Security Guard
Analisa comandos de terminal e scripts do Hacker Mode antes da execução real.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RiskLevel(str, Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class CommandAudit:
    command: str
    risk_level: RiskLevel
    risk_score: int              # 0 (100% seguro) a 100 (crítico)
    affected_paths: list[str] = field(default_factory=list)
    detected_actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    can_auto_execute: bool = True
    dry_run_supported: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "risk_level": self.risk_level.value,
            "risk_score": self.risk_score,
            "affected_paths": self.affected_paths,
            "detected_actions": self.detected_actions,
            "warnings": self.warnings,
            "can_auto_execute": self.can_auto_execute,
            "dry_run_supported": self.dry_run_supported,
        }


class CommandInspector:
    """Analisador estático de comandos de terminal com auditoria de segurança."""

    # Padrões de risco
    HIGH_RISK_PATTERNS = [
        (re.compile(r"\brm\b|\bdel\b|\brmdir\b", re.I), "Remoção de arquivos/diretórios", 40),
        (re.compile(r"\bchmod\b|\bchown\b|\bicacls\b", re.I), "Alteração de permissões de acesso", 30),
        (re.compile(r"\bformat\b|\bmkfs\b|\bdiskpart\b", re.I), "Formatação de disco", 90),
        (re.compile(r"\bnet\s+user\b|\buseradd\b|\bgroupadd\b", re.I), "Modificação de usuários do SO", 70),
        (re.compile(r"\breg\s+(add|delete)\b", re.I), "Modificação do Registro do Windows", 60),
        (re.compile(r"\bcurl\b.*\|.*\bsh\b|\bwget\b.*\|.*\bbash\b", re.I), "Download e execução direta de script remoto", 80),
        (re.compile(r"\bpip\s+install\b|\bnpm\s+install\b|\bapt\s+install\b", re.I), "Instalação de pacotes", 15),
        (re.compile(r"\bgit\s+clone\b|\bgit\s+pull\b", re.I), "Download de repositório Git", 10),
    ]

    PATH_PATTERN = re.compile(r"(?:[a-zA-Z]:\\[^ \t\r\n\"']+|/[^ \t\r\n\"']+|\./[^ \t\r\n\"']+)")

    def inspect(self, command: str) -> CommandAudit:
        """Examina o comando e gera relatório detalhado de riscos."""
        cmd = command.strip()
        if not cmd:
            return CommandAudit(
                command=cmd,
                risk_level=RiskLevel.SAFE,
                risk_score=0,
                detected_actions=["Comando vazio"],
            )

        score = 0
        actions: list[str] = []
        warnings: list[str] = []

        # Detecta caminhos de arquivos afetados
        paths = self.PATH_PATTERN.findall(cmd)
        paths = list(set(paths))[:10]  # deduplicate and limit

        # Checa padrões de risco
        for pat, desc, pts in self.HIGH_RISK_PATTERNS:
            if pat.search(cmd):
                actions.append(desc)
                score += pts

        # Ajusta nível de risco com base no score acumulado
        score = min(score, 100)
        if score == 0:
            level = RiskLevel.SAFE
        elif score < 30:
            level = RiskLevel.LOW
        elif score < 60:
            level = RiskLevel.MEDIUM
        elif score < 85:
            level = RiskLevel.HIGH
        else:
            level = RiskLevel.CRITICAL

        can_auto = level in (RiskLevel.SAFE, RiskLevel.LOW)
        if level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            warnings.append("🚨 Este comando requer confirmação explícita do usuário antes da execução.")

        return CommandAudit(
            command=cmd,
            risk_level=level,
            risk_score=score,
            affected_paths=paths,
            detected_actions=actions or ["Leitura/Execução padrão"],
            warnings=warnings,
            can_auto_execute=can_auto,
            dry_run_supported=True,
        )

    def generate_dry_run_preview(self, command: str) -> str:
        """Gera um resumo visual de prévia (Dry-Run) em Markdown."""
        audit = self.inspect(command)
        lines = [
            f"🔍 **Análise de Segurança do Comando** (Risco: `{audit.risk_level.value.upper()}` - Score: {audit.risk_score}/100)\n",
            f"```bash\n{audit.command}\n```\n",
            "**Ações Detectadas:**",
        ]
        for act in audit.detected_actions:
            lines.append(f"  - {act}")

        if audit.affected_paths:
            lines.append("\n**Caminhos Identificados:**")
            for p in audit.affected_paths:
                lines.append(f"  - `{p}`")

        if audit.warnings:
            lines.append("\n**Alertas:**")
            for w in audit.warnings:
                lines.append(f"  {w}")

        return "\n".join(lines)
