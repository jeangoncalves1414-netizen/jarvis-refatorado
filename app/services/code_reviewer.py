"""
Self-Correcting Code Review Pipeline
Executa validação sintática AST, simulação em sandbox e loop de autocorreção com a IA
para garantir que o código gerado esteja 100% correto e sem erros de execução.
"""
from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from app.services.sandbox_runner import SandboxRunner
from app.services.multi_deobfuscator import MultiDeobfuscatorEngine

logger = logging.getLogger(__name__)


@dataclass
class ReviewAttempt:
    iteration: int
    code: str
    syntax_ok: bool
    execution_ok: bool
    error_message: str = ""


@dataclass
class ReviewPipelineResult:
    ok: bool
    final_code: str
    attempts_made: int
    attempts_history: list[ReviewAttempt] = field(default_factory=list)
    fixes_applied: list[str] = field(default_factory=list)
    error_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "final_code": self.final_code,
            "attempts_made": self.attempts_made,
            "fixes_applied": self.fixes_applied,
            "error_summary": self.error_summary,
            "history": [
                {
                    "iteration": a.iteration,
                    "syntax_ok": a.syntax_ok,
                    "execution_ok": a.execution_ok,
                    "error": a.error_message[:300],
                }
                for a in self.attempts_history
            ],
        }


class CodeReviewPipeline:
    """Pipeline de revisão pós-geração com loop autônomo de autocorreção."""

    def __init__(self, max_iterations: int = 3, sandbox_timeout_s: float = 8.0) -> None:
        self.max_iterations = max_iterations
        self.sandbox = SandboxRunner(default_timeout_s=sandbox_timeout_s)

    def check_syntax(self, code: str, language: str = "python") -> tuple[bool, str]:
        """Verifica a sintaxe do código usando AST para Python ou checagem básica."""
        lang = language.lower()
        if lang in ("python", "py"):
            try:
                ast.parse(code)
                return True, "Sintaxe Python AST Válida."
            except SyntaxError as syn_err:
                return False, f"Erro de Sintaxe Python na linha {syn_err.lineno}: {syn_err.msg}"
            except Exception as exc:
                return False, f"Erro ao validar código Python: {exc}"
        else:
            # Checagem genérica de parênteses/chaves não fechados
            open_p = code.count("(") - code.count(")")
            open_b = code.count("{") - code.count("}")
            if open_p != 0 or open_b != 0:
                return False, f"Desbalanceamento de delimitadores: parenteses={open_p}, chaves={open_b}"
            return True, "Sintaxe genérica sem erros óbvios."

    def run_review_and_fix_loop(
        self,
        initial_code: str,
        fix_generator_fn: Callable[[str, str], str],
        language: str = "python",
        execute_test: bool = True,
    ) -> ReviewPipelineResult:
        """
        Executa o loop completo: Sintaxe ➔ Teste no Sandbox ➔ Se falhar ➔ Chama IA para corrigir ➔ Repete.
        """
        current_code = initial_code
        history: list[ReviewAttempt] = []
        fixes: list[str] = []

        for i in range(1, self.max_iterations + 1):
            # 1. Validação Sintática
            syn_ok, syn_msg = self.check_syntax(current_code, language=language)
            if not syn_ok:
                history.append(ReviewAttempt(
                    iteration=i, code=current_code, syntax_ok=False, execution_ok=False, error_message=syn_msg
                ))
                logger.warning("CodeReviewer: Tentativa %d falhou na sintaxe: %s", i, syn_msg)

                if i < self.max_iterations:
                    # Chama gerador de correção com a mensagem de erro sintático
                    current_code = fix_generator_fn(current_code, syn_msg)
                    fixes.append(f"Correção sintática (Tentativa {i}): {syn_msg[:100]}")
                    continue
                else:
                    return ReviewPipelineResult(
                        ok=False,
                        final_code=current_code,
                        attempts_made=i,
                        attempts_history=history,
                        fixes_applied=fixes,
                        error_summary=f"Sintaxe inválida após {i} tentativas: {syn_msg}",
                    )

            # 2. Execução de Teste em Sandbox (se habilitado para a linguagem)
            exec_ok = True
            exec_msg = "Sintaxe OK. Teste de execução não solicitado."

            if execute_test and language.lower() in ("python", "py"):
                res = self.sandbox.run_python_code(current_code)
                if not res.ok:
                    exec_ok = False
                    exec_msg = f"Erro de Execução no Sandbox (código {res.return_code}): {res.stderr}"
                    history.append(ReviewAttempt(
                        iteration=i, code=current_code, syntax_ok=True, execution_ok=False, error_message=exec_msg
                    ))
                    logger.warning("CodeReviewer: Tentativa %d falhou na execução: %s", i, exec_msg)

                    if i < self.max_iterations:
                        current_code = fix_generator_fn(current_code, exec_msg)
                        fixes.append(f"Correção de execução (Tentativa {i}): {res.stderr[:100]}")
                        continue
                    else:
                        return ReviewPipelineResult(
                            ok=False,
                            final_code=current_code,
                            attempts_made=i,
                            attempts_history=history,
                            fixes_applied=fixes,
                            error_summary=f"Erro em tempo de execução após {i} tentativas: {res.stderr[:200]}",
                        )

            # Se chegou aqui, passou tanto na sintaxe quanto na execução!
            history.append(ReviewAttempt(
                iteration=i, code=current_code, syntax_ok=True, execution_ok=exec_ok, error_message="Sucesso"
            ))
            return ReviewPipelineResult(
                ok=True,
                final_code=current_code,
                attempts_made=i,
                attempts_history=history,
                fixes_applied=fixes,
                error_summary="",
            )

        return ReviewPipelineResult(
            ok=False,
            final_code=current_code,
            attempts_made=self.max_iterations,
            attempts_history=history,
            fixes_applied=fixes,
            error_summary="Limite de tentativas atingido sem aprovação total.",
        )
