from __future__ import annotations

from app.core.actions import ActionRecord, ToolMetadata
from app.storage.action_store import ActionStore
from app.ui.panel.api import mission_control


def test_mission_snapshot_is_safe_and_uses_action_records(tmp_path, monkeypatch):
    store = ActionStore(tmp_path / "actions.jsonl")
    action = store.create(ActionRecord.create(
        source="test", tool_name="planning_workspace", metadata=ToolMetadata(default_risk="high", requires_confirmation=True),
        arguments={"token": "never-visible"}, preview="Abrir planejamento",
    ))
    monkeypatch.setattr(mission_control, "action_store", store)
    snapshot = mission_control.build_mission_snapshot()
    assert snapshot["version"] == 1
    assert snapshot["summary"]["pending_actions"] == 1
    assert snapshot["pending_actions"][0]["id"] == action.id
    assert "never-visible" not in str(snapshot)
