from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from app.agent.action_executor import ActionExecutor
from app.agent.tool_guardrails import ToolCallGuardrailController
from app.agent.tools.base import ToolResult
from app.core.actions import ActionRecord, PendingActionBroker, ToolMetadata
from app.storage.action_store import ActionStore
from app.ui.panel.api import actions


@pytest.fixture
def kernel(tmp_path, monkeypatch):
    import app.agent.action_executor as module
    import app.core.diagnostics as diagnostics
    monkeypatch.setattr(diagnostics, "_DIRECTORY", tmp_path / "diagnostics")
    store = ActionStore(tmp_path / "actions.sqlite3")
    broker = PendingActionBroker()
    monkeypatch.setattr(module, "pending_action_broker", broker)
    monkeypatch.setattr(actions, "pending_action_broker", broker)
    monkeypatch.setattr(actions, "action_store", store)
    return store, broker


def executor(store, callback=None, *, confirm=False):
    return ActionExecutor(
        frozenset({"fixture"}), ToolCallGuardrailController(), callback or (lambda *_: ToolResult(True, "feito")),
        metadata_for=lambda _: ToolMetadata(requires_confirmation=confirm), store=store,
    )


def proposal(store, *, confirm=False, name="fixture"):
    return store.create(ActionRecord.create(source="test", tool_name=name, metadata=ToolMetadata(requires_confirmation=confirm), arguments={}, preview="Proposta de teste"))


def test_events_persist_and_replay_from_cursor(kernel):
    store, _ = kernel
    agent = executor(store)
    agent.execute("fixture", {}, "faça")
    action = agent.last_action
    reopened = ActionStore(store.path)
    detail = reopened.details(action.id)
    assert detail["action"]["status"] == "succeeded"
    assert [event["status"] for event in detail["events"]] == ["proposed", "running", "succeeded"]
    assert [event["timestamp"] for event in detail["events"]] == sorted(event["timestamp"] for event in detail["events"])
    assert reopened.details(action.id, after_event_id=detail["events"][1]["id"])["events"] == detail["events"][2:]


def test_failed_event_write_rolls_back_state(kernel, monkeypatch):
    store, _ = kernel
    action = proposal(store)
    def fail(*_):
        raise sqlite3.OperationalError("disk full")
    monkeypatch.setattr(store, "_event", fail)
    with pytest.raises(sqlite3.OperationalError):
        store.transition(action.id, "running")
    reopened = ActionStore(store.path)
    assert reopened.get(action.id).status == "proposed"
    assert len(reopened.details(action.id)["events"]) == 1


def test_legacy_import_preserves_file_and_records_only_known_snapshot(tmp_path):
    legacy = tmp_path / "actions.jsonl"
    item = ActionRecord.create(source="test", tool_name="fixture", metadata=ToolMetadata(), arguments={}, preview="legado")
    item.status = "succeeded"
    original = json.dumps(asdict(item)) + "\n"
    legacy.write_text(original, encoding="utf-8")
    store = ActionStore(legacy)
    detail = store.details(item.id)
    assert legacy.read_text(encoding="utf-8") == original
    assert detail["action"]["status"] == "succeeded"
    assert [event["kind"] for event in detail["events"]] == ["legacy_import"]
    assert len(ActionStore(legacy).details(item.id)["events"]) == 1


def test_legacy_corrupt_line_does_not_erase_good_snapshots(tmp_path, monkeypatch):
    monkeypatch.setattr("app.storage.action_store.record", lambda *_args, **_kwargs: None)
    legacy = tmp_path / "actions.jsonl"
    item = ActionRecord.create(source="test", tool_name="fixture", metadata=ToolMetadata(), arguments={}, preview="legado")
    legacy.write_text("broken\n" + json.dumps(asdict(item)) + "\n{}", encoding="utf-8")
    assert ActionStore(legacy).get(item.id).status == "proposed"


def test_double_approval_and_replayed_callback_execute_once(kernel):
    store, broker = kernel
    calls = []
    agent = executor(store, lambda *_: calls.append(1) or ToolResult(True, "feito"), confirm=True)
    agent.execute("fixture", {}, "faça")
    action = agent.last_action
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(lambda _: actions.handle_actions_post(f"/api/actions/{action.id}/approve", b"{}", None), range(8)))
    assert calls == [1]
    assert sorted(status for status, _ in responses) == [200] + [409] * 7
    assert broker.take(action.id) is None
    assert [event["status"] for event in store.details(action.id)["events"]] == ["awaiting_confirmation", "authorized", "running", "succeeded"]
    with pytest.raises(ValueError):
        agent.execute_authorized(action.id, "fixture", {}, "faça")


def test_different_store_instances_claim_one_transition(kernel):
    store, _ = kernel
    action = proposal(store, confirm=True)
    def claim(_):
        try:
            ActionStore(store.path).transition(action.id, "authorized", expected_status="awaiting_confirmation")
            return True
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(claim, range(8))) == 1


def test_rejection_discards_execution_and_cannot_cancel_running(kernel):
    store, broker = kernel
    agent = executor(store, confirm=True)
    agent.execute("fixture", {}, "faça")
    action = agent.last_action
    assert actions.handle_actions_post(f"/api/actions/{action.id}/reject", b"{}", None)[0] == 200
    assert broker.take(action.id) is None
    active = proposal(store)
    store.transition(active.id, "running")
    assert actions.handle_actions_post(f"/api/actions/{active.id}/reject", b"{}", None)[0] == 409
    assert store.get(active.id).status == "running"


def test_restart_cannot_replay_pending_approval(kernel, monkeypatch):
    store, _ = kernel
    agent = executor(store, confirm=True)
    agent.execute("fixture", {}, "faça")
    action = agent.last_action
    monkeypatch.setattr(actions, "action_store", ActionStore(store.path))
    monkeypatch.setattr(actions, "pending_action_broker", PendingActionBroker())
    status, payload = actions.handle_actions_post(f"/api/actions/{action.id}/approve", b"{}", None)
    assert status == 410 and payload["action"]["status"] == "expired"


def test_failed_approval_reports_failure_and_sanitizes_journal(kernel):
    store, _ = kernel
    agent = executor(store, lambda *_: ToolResult(False, "Falha na credencial private-value; token=hidden", {"secret": "data-only-secret"}), confirm=True)
    agent.execute("fixture", {"api_key": "private-value"}, "faça")
    status, payload = actions.handle_actions_post(f"/api/actions/{agent.last_action.id}/approve", b"{}", None)
    assert status == 200 and payload["ok"] is False and payload["action"]["status"] == "failed"
    assert "Falha" in payload["error"]
    history = str(store.details(agent.last_action.id)) + store.path.read_bytes().decode("utf-8", errors="ignore")
    assert all(secret not in history for secret in ["private-value", "hidden", "data-only-secret"])


def test_frozen_arguments_and_digest_binding(kernel):
    store, broker = kernel
    received = []
    agent = executor(store, lambda _, args, __: received.append(args) or ToolResult(True, "feito"), confirm=True)
    args = {"nested": {"target": "original"}}
    agent.execute("fixture", args, "faça")
    action = agent.last_action
    args["nested"]["target"] = "alterado"
    store.transition(action.id, "authorized")
    with pytest.raises(ValueError):
        agent.execute_authorized(action.id, "fixture", args, "faça")
    broker.take(action.id)()
    assert received == [{"nested": {"target": "original"}}]


@pytest.mark.parametrize("invalid", ["texto sem contrato", None, ToolResult("false", "inválido")])
def test_untyped_results_fail_closed(kernel, invalid):
    store, _ = kernel
    agent = executor(store, lambda *_: invalid)
    assert "resultado inválido" in agent.execute("fixture", {}, "faça")
    assert agent.last_action.status == "failed"


def test_exception_records_terminal_failure_without_exception_body(kernel):
    store, _ = kernel
    def fail(*_):
        raise RuntimeError("private-exception-body")
    agent = executor(store, fail)
    with pytest.raises(RuntimeError):
        agent.execute("fixture", {}, "faça")
    detail = store.details(agent.last_action.id)
    assert detail["events"][-1]["status"] == "failed"
    assert "private-exception-body" not in str(detail)


def test_empty_allowlist_blocks_every_tool(kernel):
    store, _ = kernel
    agent = executor(store)
    agent.allowed_tool_names = frozenset()
    assert "bloqueada" in agent.execute("fixture", {}, "faça")
    assert store.list() == []


def test_pagination_stays_stable_when_new_actions_arrive(kernel):
    store, _ = kernel
    created = [proposal(store).id for _ in range(4)]
    first = store.page(limit=2)
    proposal(store)
    second = store.page(limit=2, before=first["next_cursor"])
    assert [item["id"] for item in first["actions"] + second["actions"]] == created[::-1]
    assert second["next_cursor"] is None
    assert store.page(query="fixture")["actions"]
    assert store.page(query="%_")["actions"] == []


def test_retention_keeps_active_actions_and_removes_related_old_events(tmp_path):
    store = ActionStore(tmp_path / "actions.sqlite3", max_records=2)
    active = proposal(store, confirm=True)
    agent = executor(store)
    agent.execute("fixture", {}, "faça")
    completed = agent.last_action
    proposal(store)
    assert store.get(active.id) is not None and store.get(completed.id) is None
    with sqlite3.connect(store.path) as db:
        assert db.execute("SELECT COUNT(*) FROM action_events WHERE action_id = ?", (completed.id,)).fetchone()[0] == 0


def test_history_api_filter_replay_and_invalid_cursors(kernel):
    store, _ = kernel
    agent = executor(store)
    agent.execute("fixture", {}, "faça")
    item = agent.last_action
    status, payload = actions.handle_actions_get(["api", "actions"], SimpleNamespace(path="/api/actions?status=succeeded&q=fixture&limit=1"))
    assert status == 200 and payload["actions"][0]["id"] == item.id
    events = store.details(item.id)["events"]
    status, payload = actions.handle_actions_get(["api", "actions", item.id, "events"], SimpleNamespace(path=f"/api/actions/{item.id}/events?after_event_id={events[1]['id']}"))
    assert status == 200 and payload["events"] == events[2:]
    assert actions.handle_actions_get(["api", "actions", "missing"], None)[0] == 404
    for query in ["limit=0", "before=-1", "before=nope", "after_event_id=-2", "status=unknown"]:
        assert actions.handle_actions_get(["api", "actions"], SimpleNamespace(path="/api/actions?" + query))[0] == 400
