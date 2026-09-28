"""Tool used by the agent to manage the visible planning workspace."""
from __future__ import annotations

from typing import Any

from app.agent.tools.base import BaseTool, ToolResult
from app.core.actions import ToolMetadata
from app.services.planning_workspace import planning_workspace


class PlanningWorkspaceTool(BaseTool):
    @property
    def name(self) -> str:
        return "planning_workspace"

    @property
    def description(self) -> str:
        return (
            "Abre e atualiza o painel persistente de planejamento da conversa. "
            "Use open somente quando o usuário pedir para abrir ou confirmar que quer o painel; "
            "use append/update para registrar decisões de planejamento; use set_auto_open quando ele "
            "autorizar abrir automaticamente em futuros planejamentos."
        )

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            capabilities=("planning", "workspace"), default_risk="low", reversible=True,
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["open", "close", "append", "update", "status", "set_auto_open"]},
                "title": {"type": "string", "description": "Título curto do plano."},
                "content": {"type": "string", "description": "Decisão, próximo passo ou conteúdo atualizado do plano."},
                "enabled": {"type": "boolean", "description": "Permite ou revoga a abertura automática em sessões de planejamento."},
            },
            "required": ["action"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        session_id = str((context or {}).get("session_id") or "default")
        action = str(args.get("action") or "status").strip().lower()
        try:
            if action == "open":
                result = planning_workspace.open(session_id, str(args.get("title") or ""))
                return ToolResult(True, "Painel de planejamento aberto.", result)
            if action == "close":
                result = planning_workspace.close(session_id)
                return ToolResult(True, "Painel de planejamento fechado.", result)
            if action == "append":
                result = planning_workspace.append(session_id, str(args.get("content") or ""))
                return ToolResult(True, "Registro adicionado ao plano.", result)
            if action == "update":
                result = planning_workspace.update(session_id, title=args.get("title"), content=args.get("content"))
                return ToolResult(True, "Plano atualizado.", result)
            if action == "set_auto_open":
                enabled = bool(args.get("enabled"))
                result = planning_workspace.set_auto_open(enabled)
                return ToolResult(True, "Preferência de abertura automática atualizada.", result)
            return ToolResult(True, "Status do painel de planejamento.", planning_workspace.get(session_id))
        except ValueError as exc:
            return ToolResult(False, str(exc))
        except Exception as exc:
            return ToolResult(False, f"Não foi possível atualizar o painel de planejamento: {exc}")
