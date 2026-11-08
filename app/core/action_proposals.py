"""Texto das propostas de aprovação (C1): alvo, mudança prevista, reversibilidade e escopo.

O texto vem só dos metadados da ferramenta e de argumentos já redigidos
(``redact``). O que a ferramenta não declara aparece como "não declarado", nunca
como garantia inventada. A proposta cabe numa linha para o histórico da Central.
"""
from __future__ import annotations

from typing import Any

from app.core.actions import PREVIEW_LIMIT, ToolMetadata, redact

_RISK_LABELS = {"observe": "de leitura", "low": "baixo", "high": "alto", "critical": "crítico"}
_MAX_ARGUMENT_NAMES = 6
_APPROVAL_SCOPE = "Autorizar vale só para esta execução; não cria permissão permanente."


def _sentence(text: str) -> str:
    text = " ".join(str(text).split())
    return text if text.endswith((".", "!", "?")) else text + "."


def _argument_names(arguments: dict[str, Any]) -> str:
    names = [str(key)[:40] for key in arguments][:_MAX_ARGUMENT_NAMES]
    return ", ".join(names)


def _target(name: str, arguments: dict[str, Any], metadata: ToolMetadata) -> str:
    base = metadata.target_for(arguments) or metadata.default_target
    detail = metadata.detail_for(arguments)
    if base and detail:
        return f"{base} ({detail})"
    if base or detail:
        return base or detail
    humanized = f"ferramenta {name.replace('_', ' ')}"
    names = _argument_names(arguments)
    return f"{humanized}; alvo não declarado (parâmetros informados: {names}, valores protegidos)" if names else f"{humanized}; alvo não declarado"


def _effect(arguments: dict[str, Any], metadata: ToolMetadata, risk: str) -> str:
    declared = metadata.effect_for(arguments)
    if declared:
        return declared
    if risk == "observe":
        return "Apenas consulta; nada é alterado."
    operation = metadata.operation_for(arguments)
    unknown = f"Operação '{redact(operation, limit=40)}' não reconhecida. " if operation else ""
    return f"{unknown}Mudança não declarada pela ferramenta; tratada como risco {_RISK_LABELS.get(risk, risk)}."


def _reversibility(arguments: dict[str, Any], metadata: ToolMetadata, risk: str) -> str:
    declared = metadata.reversibility_for(arguments)
    if declared:
        return declared
    if risk == "observe":
        return "Nada a desfazer."
    if metadata.reversible:
        return "Reversível: o que foi criado ou alterado pode ser removido ou editado depois."
    return "Não declarada; trate como irreversível."


def build_proposal_preview(name: str, arguments: dict[str, Any] | None, metadata: ToolMetadata) -> str:
    """Proposta em quatro campos: Alvo, Mudança, Reversibilidade e Escopo.

    Não chama a ferramenta. Para ``open_windows_app`` com ``close``, o alvo lista
    os processos em execução que serão encerrados (consulta só de leitura).
    """
    arguments = arguments if isinstance(arguments, dict) else {}
    risk = metadata.risk_for(arguments)
    needs_approval = metadata.requires_confirmation or risk in {"high", "critical"}
    scope = metadata.scope.strip()
    if needs_approval:
        scope = f"{_sentence(scope)} {_APPROVAL_SCOPE}" if scope else _APPROVAL_SCOPE
    elif not scope:
        scope = "Não declarado; vale só para esta execução."
    parts = (
        f"Alvo: {_sentence(_target(name, arguments, metadata))}",
        f"Mudança: {_sentence(_effect(arguments, metadata, risk))}",
        f"Reversibilidade: {_sentence(_reversibility(arguments, metadata, risk))}",
        f"Escopo: {_sentence(scope)}",
    )
    text = " ".join(parts)
    return text if len(text) <= PREVIEW_LIMIT else text[: PREVIEW_LIMIT - 1].rstrip() + "…"
