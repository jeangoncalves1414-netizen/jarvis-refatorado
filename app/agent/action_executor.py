"""Action executor - executes tools with guardrails and mode filtering."""

from __future__ import annotations

from collections.abc import Callable

from app.agent.tool_guardrails import ToolCallGuardrailController


LegacyExecute = Callable[[str, dict, str], str]


class ActionExecutor:
    """Executes tool actions with guardrails and mode-based filtering."""
    
    def __init__(
        self,
        allowed_tool_names: frozenset[str] | None,
        guardrails: ToolCallGuardrailController,
        legacy_execute: LegacyExecute,
    ) -> None:
        self.allowed_tool_names = allowed_tool_names
        self.guardrails = guardrails
        self.legacy_execute = legacy_execute

    def execute(self, name: str, args: dict | None, user_text: str) -> str:
        args = args or {}
        
        # Filter by allowed tools
        if self.allowed_tool_names and name not in self.allowed_tool_names:
            return f"Ferramenta bloqueada pelo modo atual: {name}."

        # Pre-call guardrail
        before = self.guardrails.before_call(name, args)
        if not before.allow:
            return before.message

        # Execute
        result = self.legacy_execute(name, args, user_text)
        
        # Post-call guardrail
        after = self.guardrails.after_call(name, args, result)
        if not after.allow:
            return after.message
        return result
