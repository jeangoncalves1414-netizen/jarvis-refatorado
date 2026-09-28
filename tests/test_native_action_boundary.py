from __future__ import annotations

from app.agent.action_executor import ActionExecutor
from app.agent.tool_guardrails import ToolCallGuardrailController
from app.core.actions import ToolMetadata
from app.storage.action_store import ActionStore


def test_native_function_style_execution_cannot_bypass_high_risk_proposal(tmp_path):
    calls: list[str] = []
    executor = ActionExecutor(
        frozenset({"browser_agent"}), ToolCallGuardrailController(),
        lambda name, args, user: calls.append(name) or "executado",
        metadata_for=lambda _name: ToolMetadata(("browser",), "high", requires_confirmation=True),
        store=ActionStore(tmp_path / "journal.jsonl"), source="function:test",
    )
    response = executor.execute("browser_agent", {"goal": "abrir site"}, "abra")
    assert "exige confirmação" in response
    assert calls == []
    assert executor.last_action is not None
    assert executor.last_action.status == "awaiting_confirmation"
