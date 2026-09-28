"""Auditor de Segurança de LLM e Injeção de Prompt.

Inspirado nas diretrizes do OWASP LLM Top 10 e no repositório reverse-skill (llm-security skill).
Inspeciona prompts contra injeções diretas/indiretas, vazamentos de system prompt e comandos maliciosos.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class VulnerabilityFinding:
    name: str
    risk_level: str  # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    description: str
    matched_pattern: str


class LLMSecurityAuditorEngine:
    """Motor de auditoria de segurança de LLMs e agentes."""

    def __init__(self, llm_service: Any = None) -> None:
        self.llm_service = llm_service

        # Padrões conhecidos de injeção de prompt e jailbreak
        self.patterns = [
            (
                "Direct Prompt Injection",
                "CRITICAL",
                "Tentativa direta de sobrescrever as instruções do sistema.",
                r"(?:ignore\s+(?:all\s+)?previous\s+instructions|ignore\s+(?:all\s+)?prior\s+prompts|forget\s+everything\s+you\s+were\s+told)"
            ),
            (
                "System Prompt Leakage",
                "HIGH",
                "Tentativa de extrair o prompt de sistema ou chaves secretas.",
                r"(?:print\s+your\s+system\s+prompt|reveal\s+your\s+instructions|show\s+me\s+your\s+initial\s+prompt)"
            ),
            (
                "DAN / Jailbreak Pattern",
                "HIGH",
                "Simulação de persona sem restrições ou regras de segurança.",
                r"(?:do\s+anything\s+now|DAN\s+mode|unrestricted\s+ai|no\s+ethics\s+mode)"
            ),
            (
                "Roleplay Override",
                "MEDIUM",
                "Tentativa de forçar o agente a assumir papel malicioso.",
                r"(?:you\s+are\n+now\s+an?\s+unfiltered|pretend\s+you\s+have\s+no\s+rules)"
            ),
            (
                "Command Injection Attempt",
                "CRITICAL",
                "Comandos de sistema de alto risco embutidos no prompt.",
                r"(?:rm\s+-rf|del\s+/f|format\s+c:|curl\s+http.*\|\s*sh)"
            )
        ]

    def audit_prompt(self, text: str) -> dict[str, Any]:
        """Inspeciona um texto/prompt e retorna relatório de vulnerabilidades."""
        if not text or not text.strip():
            return {"ok": True, "findings": [], "overall_risk": "SAFE"}

        findings: list[dict[str, str]] = []
        highest_risk = "SAFE"

        for name, risk, desc, pattern in self.patterns:
            if re.search(pattern, text, re.IGNORECASE):
                findings.append({
                    "vulnerability": name,
                    "risk_level": risk,
                    "description": desc,
                    "matched": pattern
                })
                if risk in ("CRITICAL", "HIGH") or highest_risk == "SAFE":
                    highest_risk = risk

        return {
            "ok": True,
            "prompt_length": len(text),
            "findings_count": len(findings),
            "overall_risk": highest_risk,
            "is_safe": len(findings) == 0,
            "findings": findings
        }


# Instância global do auditor
llm_security_auditor = LLMSecurityAuditorEngine()
