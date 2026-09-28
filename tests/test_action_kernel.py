from __future__ import annotations

import pytest

from app.agent.action_executor import ActionExecutor
from app.agent.tool_guardrails import ToolCallGuardrailController
from app.agent.tools.workflow import WorkflowTool, validate_recipe
from app.core.actions import ActionRecord, ToolMetadata
from app.storage.action_store import ActionStore
from app.core.actions import pending_action_broker


def _executor(tmp_path, metadata: ToolMetadata, calls: list[str]) -> ActionExecutor:
    return ActionExecutor(
        frozenset({"fixture"}), ToolCallGuardrailController(),
        lambda name, args, user: calls.append(name) or "feito",
        metadata_for=lambda name: metadata,
        store=ActionStore(tmp_path / "actions.jsonl"), source="test",
    )


def test_high_risk_is_proposed_without_execution(tmp_path):
    calls: list[str] = []
    executor = _executor(tmp_path, ToolMetadata(default_risk="high", requires_confirmation=True), calls)
    message = executor.execute("fixture", {"target": "x"}, "faça")
    assert "exige confirmação" in message
    assert calls == []
    assert executor.store.list()[0].status == "awaiting_confirmation"


def test_approved_high_risk_callback_executes_once(tmp_path):
    calls: list[str] = []
    executor = _executor(tmp_path, ToolMetadata(default_risk="high", requires_confirmation=True), calls)
    executor.execute("fixture", {}, "faça")
    action = executor.store.list()[0]
    executor.store.transition(action.id, "authorized")
    callback = pending_action_broker.take(action.id)
    assert callback is not None and callback() == "feito"
    assert calls == ["fixture"]
    assert executor.store.get(action.id).status == "succeeded"
    assert pending_action_broker.take(action.id) is None


def test_observation_is_journaled_and_runs(tmp_path):
    calls: list[str] = []
    executor = _executor(tmp_path, ToolMetadata(default_risk="observe"), calls)
    assert executor.execute("fixture", {}, "observe") == "feito"
    assert calls == ["fixture"]
    assert executor.store.list()[0].status == "succeeded"


def test_store_rejects_invalid_transition(tmp_path):
    store = ActionStore(tmp_path / "actions.jsonl")
    item = store.create(ActionRecord.create(source="test", tool_name="x", metadata=ToolMetadata(), arguments={}, preview="x"))
    with pytest.raises(ValueError):
        store.transition(item.id, "succeeded")


def test_public_history_redacts_script_payload(tmp_path):
    item = ActionRecord.create(source="test", tool_name="x", metadata=ToolMetadata(), arguments={"script": "secret"}, preview="Executar script")
    assert "secret" not in str(item.public_dict())


def test_workflow_is_declarative_and_dry_run_only():
    tool = WorkflowTool()
    result = tool.execute({"recipe_id": "planejamento_semanal", "dry_run": True})
    assert result.ok and result.data["dry_run"] is True
    with pytest.raises(ValueError):
        validate_recipe({"name": "x", "capabilities": ["a"], "steps": [{"tool": "other"}]})
