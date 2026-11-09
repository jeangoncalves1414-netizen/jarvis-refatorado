"""Aprovações automáticas: regras com escopo e duração e o Modo liberado."""
from __future__ import annotations

import json
from typing import Any

from app.storage.auto_approvals import DURATION_LABELS, LIBERATED_VALIDITY_LABELS, auto_approvals, needs_exact_arguments

_RISK_ORDER = ("observe", "low", "high", "critical")


def _state() -> dict[str, Any]:
    return {
        "ok": True, "mode": auto_approvals.mode(), "rules": auto_approvals.list_rules(),
        "durations": DURATION_LABELS, "validities": LIBERATED_VALIDITY_LABELS,
    }


def _tool_risk(tool: str, operation: str) -> str:
    """Maior risco da ferramenta (ou da operação pedida); ferramenta desconhecida conta como alta."""
    from app.agent.tools.catalog import TOOL_CATALOG
    metadata = TOOL_CATALOG.get(tool)
    if metadata is None:
        return "high"
    operation = operation.strip().lower()
    risks = dict(metadata.operation_risks)
    if operation and operation in risks:
        return risks[operation]
    return max([metadata.default_risk, *risks.values()], key=_RISK_ORDER.index)


def handle_approvals_get(parts: list[str], _handler: Any) -> tuple[int, dict] | None:
    if parts[:2] != ["api", "approvals"] or len(parts) != 2:
        return None
    return 200, _state()


def handle_approvals_post(path: str, body: bytes, _handler: Any) -> tuple[int, dict] | None:
    pieces = [part for part in path.split("?")[0].split("/") if part]
    if pieces[:2] != ["api", "approvals"]:
        return None
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
        if not isinstance(payload, dict):
            raise ValueError()
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return 400, {"ok": False, "error": "JSON inválido."}
    try:
        if pieces[2:] == ["mode"]:
            persist, validity = payload.get("persist"), payload.get("validity")
            auto_approvals.set_mode(
                bool(payload.get("enabled")), persist if isinstance(persist, bool) else None,
                validity if isinstance(validity, str) and validity else None,
            )
            return 200, _state()
        if pieces[2:] == ["rules"]:
            action_id = str(payload.get("action_id") or "")
            digest, broad = "", False
            if action_id:
                scope = auto_approvals.scope_detail(action_id)
                if scope is None:
                    return 404, {"ok": False, "error": "Proposta não encontrada ou expirada; peça a ação de novo."}
                tool, operation, target, risk = scope["tool"], scope["operation"], scope["target"], scope["risk"] or "high"
                # Ação crítica, ou alta sem alvo: a regra vale só para estes argumentos exatos.
                digest = scope["digest"] if needs_exact_arguments(risk, target) else ""
                origin = "tela de aprovação"
            else:
                tool, operation, target = str(payload.get("tool") or ""), str(payload.get("operation") or ""), str(payload.get("target") or "")
                risk, broad = _tool_risk(tool.strip(), operation), payload.get("confirm_broad") is True
                origin = "manual"
            rule = auto_approvals.add_rule(
                tool, operation, target, str(payload.get("duration") or "now"),
                origin=origin, risk=risk, digest=digest, broad=broad,
            )
            return 200, {**_state(), "rule": rule}
        if len(pieces) == 4 and pieces[2] == "rules" and pieces[3]:
            rule_id = pieces[3]
            if payload.get("revoke"):
                return (200, _state()) if auto_approvals.revoke_rule(rule_id) else (404, {"ok": False, "error": "Regra não encontrada."})
            auto_approvals.update_rule(rule_id, str(payload.get("duration") or ""))
            return 200, _state()
    except KeyError:
        return 404, {"ok": False, "error": "Regra não encontrada."}
    except ValueError as exc:
        return 400, {"ok": False, "error": str(exc)}
    return None
