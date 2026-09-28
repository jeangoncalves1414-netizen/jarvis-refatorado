"""Action executor - executes tools with guardrails and mode filtering."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.agent.tool_guardrails import ToolCallGuardrailController
from app.core.actions import ActionRecord, ToolMetadata, pending_action_broker
from app.storage.action_store import ActionStore, action_store


LegacyExecute = Callable[[str, dict, str], str]


class ActionExecutor:
    """Executes tool actions with guardrails and mode-based filtering."""
    
    def __init__(
        self,
        allowed_tool_names: frozenset[str] | None,
        guardrails: ToolCallGuardrailController,
        legacy_execute: LegacyExecute,
        metadata_for: Callable[[str], ToolMetadata | None] | None = None,
        store: ActionStore | None = None,
        source: str = "conversation",
    ) -> None:
        self.allowed_tool_names = allowed_tool_names
        self.guardrails = guardrails
        self.legacy_execute = legacy_execute
        self.metadata_for = metadata_for or (lambda _name: None)
        self.store = store or action_store
        self.source = source
        self.last_action: ActionRecord | None = None

    def propose(self, name: str, args: dict[str, Any] | None) -> ActionRecord:
        metadata = self.metadata_for(name) or ToolMetadata(
            capabilities=(name,), default_risk="high", requires_confirmation=True,
        )
        preview = f"Executar {name.replace('_', ' ')}"
        if args:
            preview += ". Parâmetros registrados de forma protegida."
        action = self.store.create(ActionRecord.create(
            source=self.source, tool_name=name, metadata=metadata, arguments=args or {}, preview=preview,
        ))
        self.last_action = action
        return action

    def execute(self, name: str, args: dict | None, user_text: str) -> str:
        args = args or {}
        
        # Filter by allowed tools
        if self.allowed_tool_names and name not in self.allowed_tool_names:
            return f"Ferramenta bloqueada pelo modo atual: {name}."

        action = self.propose(name, args)
        if action.status == "awaiting_confirmation":
            pending_action_broker.register(action.id, lambda: self.execute_authorized(action.id, name, args, user_text))
            return (
                f"Ação proposta ({action.id}): {action.preview}. "
                "Ela exige confirmação no painel antes de ser executada."
            )

        # Pre-call guardrail
        before = self.guardrails.before_call(name, args)
        if not before.allow:
            self.store.transition(action.id, "cancelled", result_summary=before.message)
            return before.message

        # Execute
        self.store.transition(action.id, "running")
        try:
            result = self.legacy_execute(name, args, user_text)
        except Exception as exc:
            self.store.transition(action.id, "failed", result_summary=f"Falha ao executar: {exc}")
            raise
        
        # Post-call guardrail
        after = self.guardrails.after_call(name, args, result)
        if not after.allow:
            self.store.transition(action.id, "failed", result_summary=after.message)
            return after.message
        self.store.transition(action.id, "succeeded", result_summary=str(result)[:500])
        return result

    def execute_authorized(self, action_id: str, name: str, args: dict, user_text: str) -> str:
        """Run a once-approved action kept only in this process's memory."""
        action = self.store.get(action_id)
        if not action or action.status != "authorized":
            raise ValueError("Ação não está autorizada ou expirou.")
        before = self.guardrails.before_call(name, args)
        if not before.allow:
            self.store.transition(action_id, "cancelled", result_summary=before.message)
            return before.message
        self.store.transition(action_id, "running")
        try:
            result = self.legacy_execute(name, args, user_text)
        except Exception as exc:
            self.store.transition(action_id, "failed", result_summary=f"Falha ao executar: {exc}")
            raise
        after = self.guardrails.after_call(name, args, result)
        if not after.allow:
            self.store.transition(action_id, "failed", result_summary=after.message)
            return after.message
        self.store.transition(action_id, "succeeded", result_summary=str(result)[:500])
        return result
