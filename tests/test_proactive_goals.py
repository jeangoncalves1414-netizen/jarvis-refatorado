from __future__ import annotations

from app.storage.goal_store import GoalStore


def test_goals_are_local_scoped_and_signals_are_deduplicated(tmp_path):
    store = GoalStore(tmp_path / "goals.json")
    goal = store.create("Estudar Python", "Resolver uma lista", profile_id="jean", policy="notify_only")
    assert store.list("other") == []
    assert store.list("jean")[0]["id"] == goal["id"]
    assert store.record_signal(goal["id"], "weekly_review") is True
    assert store.record_signal(goal["id"], "weekly_review") is False
    assert store.update_status(goal["id"], "paused")["status"] == "paused"
