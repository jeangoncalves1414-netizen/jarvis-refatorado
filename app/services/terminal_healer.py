"""
Terminal Auto-Healer & Oxyy Code Fixer
Intercepta erros de execução de comandos/scripts e gera correções automáticas em 1-clique.
Integra com modelos Oxyy (gpt-4o / llama-3.3-70b-instruct) e LLM para diagnósticos avançados.
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class HealFixProposal:
    ok: bool
    original_command: str
    error_output: str
    error_type: str
    root_cause: str
    suggested_command: str
    explanation: str
    can_auto_apply: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "original_command": self.original_command,
            "error_output": self.error_output[:2000],
            "error_type": self.error_type,
            "root_cause": self.root_cause,
            "suggested_command": self.suggested_command,
            "explanation": self.explanation,
            "can_auto_apply": self.can_auto_apply,
        }


class TerminalAutoHealer:
    """Diagnostica e gera correções automáticas (Auto-Fix) para falhas de terminal/código."""

    # Padrões comuns de erros
    KNOWN_ERRORS = [
        (re.compile(r"ModuleNotFoundError:\s+No module named ['\"]([^'\"]+)['\"]"), "Dependência Python Ausente", "pip install {1}"),
        (re.compile(r"command not found:\s+(\w+)|'(\w+)' is not recognized"), "Comando Não Encontrado", "Instalar ou verificar PATH do comando"),
        (re.compile(r"PermissionDenied|PermissionError:\s+\[Errno 13\]"), "Erro de Permissão", "Executar como Administrador / chmod +x"),
        (re.compile(r"SyntaxError:\s+(.+)"), "Erro de Sintaxe", "Corrigir caracteres inválidos ou parênteses não fechados"),
        (re.compile(r"Address already in use|Port (\d+) is in use"), "Porta de Rede em Uso", "netstat -ano / taskkill ou escolher outra porta"),
    ]

    def __init__(self, llm_service: Any = None) -> None:
        self.llm_service = llm_service

    def diagnose_and_fix(self, command: str, error_output: str) -> HealFixProposal:
        """Diagnostica a causa do erro e sugere o comando corrigido."""
        cmd = command.strip()
        err = error_output.strip()

        if not err:
            return HealFixProposal(
                ok=False,
                original_command=cmd,
                error_output="",
                error_type="Nenhum Erro",
                root_cause="O comando não produziu saída de erro.",
                suggested_command=cmd,
                explanation="Nenhum ajuste necessário.",
            )

        # 1. Checa erros conhecidos por regex rápida
        for pat, err_type, fix_tmpl in self.KNOWN_ERRORS:
            m = pat.search(err)
            if m:
                pkg_or_cmd = m.group(1) if m.groups() and m.group(1) else (m.group(2) if len(m.groups()) > 1 and m.group(2) else "")
                suggested = fix_tmpl.format(pkg_or_cmd, pkg_or_cmd) if "{1}" in fix_tmpl else fix_tmpl

                return HealFixProposal(
                    ok=True,
                    original_command=cmd,
                    error_output=err,
                    error_type=err_type,
                    root_cause=f"Detectado: {m.group(0)[:150]}",
                    suggested_command=suggested if not suggested.startswith("Instalar") else f"pip install {pkg_or_cmd}" if pkg_or_cmd else cmd,
                    explanation=f"O erro '{err_type}' pode ser resolvido executando a sugestão.",
                    can_auto_apply=True,
                )

        # 2. Chama LLM real (Oxyy / Gemini / Groq) para diagnósticos complexos
        if self.llm_service:
            try:
                prompt = (
                    f"Você é um especialista em debugging de terminal e código.\n"
                    f"Comando executado: `{cmd}`\n"
                    f"Erro retornado:\n```\n{err[:1500]}\n```\n\n"
                    f"Responda em formato JSON estrito:\n"
                    f"{{\n"
                    f'  "error_type": "<nome curto do erro>",\n'
                    f'  "root_cause": "<explicação cirúrgica da causa raiz>",\n'
                    f'  "suggested_command": "<comando exato corrigido>",\n'
                    f'  "explanation": "<como o comando corrige o problema>"\n'
                    f"}}\n"
                )

                # Prioriza provedor Oxyy se disponível
                response_text = self.llm_service.ask(prompt, provider="oxyy")
                if response_text and "suggested_command" in response_text:
                    import json
                    json_str = response_text
                    if "```json" in response_text:
                        json_str = response_text.split("```json")[1].split("```")[0].strip()
                    elif "```" in response_text:
                        json_str = response_text.split("```")[1].split("```")[0].strip()

                    data = json.loads(json_str)
                    return HealFixProposal(
                        ok=True,
                        original_command=cmd,
                        error_output=err,
                        error_type=data.get("error_type", "Diagnóstico por IA"),
                        root_cause=data.get("root_cause", err[:200]),
                        suggested_command=data.get("suggested_command", cmd),
                        explanation=data.get("explanation", "Correção gerada por IA."),
                        can_auto_apply=True,
                    )
            except Exception as llm_exc:
                logger.warning("AutoHealer: Falha na chamada LLM para diagnósticos: %s", llm_exc)

        # Fallback genérico inteligente
        return HealFixProposal(
            ok=True,
            original_command=cmd,
            error_output=err,
            error_type="Erro Genérico de Execução",
            root_cause=err.splitlines()[-1] if err.splitlines() else err[:200],
            suggested_command=f"# Revisar sintaxe e parâmetros de: {cmd}",
            explanation="O erro necessita de verificação manual dos argumentos ou permissões.",
            can_auto_apply=False,
        )
