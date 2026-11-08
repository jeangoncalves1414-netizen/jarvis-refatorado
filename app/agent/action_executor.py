"""Action executor - executes tools with guardrails and mode filtering."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from threading import local
from typing import Any

from app.agent.tool_guardrails import ToolCallGuardrailController
from app.agent.tools.base import ToolResult
from app.core.action_proposals import build_proposal_preview
from app.core.actions import ActionRecord, ToolMetadata, arguments_digest, pending_action_broker, summarize_result
from app.storage.action_store import ActionStore, action_store
from app.core.runs import current_run


LegacyExecute = Callable[[str, dict, str], ToolResult]


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
        context = current_run.get()
        self.store = store or (context[0] if context else action_store)
        self.run_id = context[1] if context and self.store is context[0] else None
        self.source = source
        # The approval worker must not overwrite what the planner just proposed.
        self._thread = local()

    @property
    def last_action(self) -> ActionRecord | None:
        return getattr(self._thread, "last_action", None)

    @last_action.setter
    def last_action(self, value: ActionRecord | None) -> None:
        self._thread.last_action = value

    def propose(self, name: str, args: dict[str, Any] | None, *, user_text: str | None = None) -> ActionRecord:
        metadata = self.metadata_for(name) or ToolMetadata(
            capabilities=(name,), default_risk="high", requires_confirmation=True,
        )
        # Alvo, mudança, reversibilidade e escopo (C1); valores sensíveis dos argumentos não entram.
        preview = build_proposal_preview(name, args, metadata)
        proposal = ActionRecord.create(
            source=self.source, tool_name=name, metadata=metadata, arguments=args or {}, preview=preview,
        )
        proposal.run_id = self.run_id
        if proposal.status == "awaiting_confirmation" and user_text is not None:
            pending_action_broker.register(proposal.id, lambda: self.execute_authorized(proposal.id, name, args, user_text))
        try:
            action = self.store.create(proposal)
        except BaseException:
            pending_action_broker.discard(proposal.id)
            raise
        self.last_action = action
        return action

    def execute(self, name: str, args: dict | None, user_text: str) -> str:
        self.last_action = None
        if self.run_id:
            self.store.check_cancelled(self.run_id)
        args = deepcopy(args or {})
        
        # Filter by allowed tools
        if self.allowed_tool_names is not None and name not in self.allowed_tool_names:
            return f"Ferramenta bloqueada pelo modo atual: {name}."

        action = self.propose(name, args, user_text=user_text)
        if action.status == "awaiting_confirmation":
            return (
                f"Ação proposta ({action.id}): {action.preview} "
                "Ela exige confirmação no painel antes de ser executada."
            )

        return self._execute(action, name, args, user_text)

    def execute_authorized(self, action_id: str, name: str, args: dict, user_text: str) -> str:
        """Run a once-approved action kept only in this process's memory."""
        action = self.store.get(action_id)
        if not action or action.status != "authorized":
            raise ValueError("Ação não está autorizada ou expirou.")
        if action.tool_name != name or action.arguments_digest != arguments_digest(args):
            raise ValueError("Os parâmetros não correspondem à proposta autorizada.")
        return self._execute(action, name, args, user_text)

    def _execute(self, action: ActionRecord, name: str, args: dict, user_text: str) -> str:
        action_id = action.id
        before = self.guardrails.before_call(name, args)
        if not before.allow:
            self.last_action = self.store.transition(action_id, "cancelled", result_summary=before.message, expected_status=action.status)
            return before.message
        self.last_action = self.store.transition(action_id, "running", expected_status=action.status)
        try:
            result = self.legacy_execute(name, args, user_text)
            if not isinstance(result, ToolResult) or type(result.ok) is not bool or not isinstance(result.message, str):
                result = ToolResult(False, "A ferramenta retornou um resultado inválido; conclusão não confirmada.")
        except Exception:
            self.last_action = self.store.transition(action_id, "failed", result_summary="A ferramenta lançou uma exceção; conclusão não confirmada.")
            raise
        after = self.guardrails.after_call(name, args, result.message)
        message = result.message if after.allow else after.message
        succeeded = result.ok and after.allow
        self.last_action = self.store.transition(action_id, "succeeded" if succeeded else "failed", result_summary=summarize_result(message, args))
        return message
