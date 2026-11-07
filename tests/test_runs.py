from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
import sqlite3

import pytest

from app.agent.action_executor import ActionExecutor
from app.agent.run_tracking import track_run
from app.agent.orchestrator import AgentPlan
from app.agent.tool_guardrails import ToolCallGuardrailController
from app.agent.tools.base import ToolResult
from app.core.actions import ActionRecord, ToolMetadata, pending_action_broker
from app.core.runs import RunCancelled, current_run
from app.storage.action_store import ActionStore
from app.ui.panel.api import actions, runs


@pytest.fixture
def store(tmp_path, monkeypatch):
    journal = ActionStore(tmp_path / "actions.sqlite3")
    monkeypatch.setattr("app.storage.action_store.action_store", journal)
    monkeypatch.setattr(actions, "action_store", journal)
    monkeypatch.setattr(runs, "action_store", journal)
    yield journal
    if journal._runtime_lock:
        journal._runtime_lock.close()


def executor(store, run, callback=None, confirm=False):
    token = current_run.set((store, run.id))
    try:
        return ActionExecutor(None, ToolCallGuardrailController(), callback or (lambda *_: ToolResult(True, "feito")), metadata_for=lambda _: ToolMetadata(requires_confirmation=confirm))
    finally:
        current_run.reset(token)


def test_request_group_is_atomic_and_survives_reopen(store):
    run = store.create_run(session_id="session-one", mode="research")
    agent = executor(store, run)
    agent.execute("search", {}, "do not persist prompt")
    agent.execute("read", {}, "do not persist prompt")
    assert store.finish_run(run.id).status == "succeeded"
    detail = ActionStore(store.path).run_details(run.id)
    assert detail["run"]["session_id"] == "session-one"
    assert len(detail["actions"]) == 2
    assert all(a["run_id"] == run.id for a in detail["actions"])
    assert [e["id"] for e in detail["events"]] == sorted(e["id"] for e in detail["events"])
    assert "do not persist prompt" not in str(detail)
    cursor = detail["events"][2]["id"]
    assert store.run_details(run.id, after_event_id=cursor)["events"] == detail["events"][3:]


def test_action_waits_for_approval_after_response_finished(store):
    run = store.create_run(session_id="one", mode="general")
    agent = executor(store, run, confirm=True)
    agent.execute("fixture", {}, "faça")
    assert store.finish_run(run.id).status == "awaiting_confirmation"
    status, _ = actions.handle_actions_post(f"/api/actions/{agent.last_action.id}/approve", b"{}", None)
    assert status == 200
    assert store.run_details(run.id)["run"]["status"] == "succeeded"


def test_cancel_waiting_run_discards_callback_and_is_idempotent(store):
    run = store.create_run(session_id=None, mode="general")
    agent = executor(store, run, confirm=True)
    agent.execute("fixture", {}, "faça")
    store.finish_run(run.id)
    assert store.cancel_run(run.id)["status"] == "cancelled"
    assert store.cancel_run(run.id)["status"] == "cancelled"
    assert pending_action_broker.take(agent.last_action.id) is None
    assert actions.handle_actions_post(f"/api/actions/{agent.last_action.id}/approve", b"{}", None)[0] == 409


def test_cancel_during_noncooperative_tool_waits_and_blocks_next_step(store):
    run = store.create_run(session_id="one", mode="general")
    entered, release = Event(), Event()
    def tool(*_):
        entered.set()
        assert release.wait(10)
        return ToolResult(True, "efeito concluído")
    agent = executor(store, run, tool)
    with ThreadPoolExecutor() as pool:
        future = pool.submit(agent.execute, "fixture", {}, "faça")
        try:
            assert entered.wait(10)
            assert store.cancel_run(run.id)["status"] == "cancel_requested"
            assert store.run_details(run.id)["actions"][0]["status"] == "running"
        finally:
            release.set()
        assert future.result(10) == "efeito concluído"
    with pytest.raises(RunCancelled):
        agent.execute("another", {}, "faça")
    assert store.finish_run(run.id).status == "cancelled"
    assert store.run_details(run.id)["actions"][0]["status"] == "succeeded"


def test_cancel_approved_tool_waits_for_callback_to_finish(store):
    run = store.create_run(session_id=None, mode="general")
    entered, release = Event(), Event()
    def tool(*_):
        entered.set()
        assert release.wait(10)
        return ToolResult(True, "feito")
    agent = executor(store, run, tool, confirm=True)
    agent.execute("fixture", {}, "faça")
    store.finish_run(run.id)
    with ThreadPoolExecutor() as pool:
        future = pool.submit(actions.handle_actions_post, f"/api/actions/{agent.last_action.id}/approve", b"{}", None)
        try:
            assert entered.wait(10)
            assert store.cancel_run(run.id)["status"] == "cancel_requested"
        finally:
            release.set()
        assert future.result(10)[0] == 200
    assert store.run_details(run.id)["run"]["status"] == "cancelled"


def test_cancel_before_execution_claim_prevents_side_effect(store, monkeypatch):
    run = store.create_run(session_id=None, mode="general")
    calls = []
    agent = executor(store, run, lambda *_: calls.append(1) or ToolResult(True, "feito"))
    original = agent.guardrails.before_call
    def cancel_then_check(*args):
        store.cancel_run(run.id)
        return original(*args)
    monkeypatch.setattr(agent.guardrails, "before_call", cancel_then_check)
    with pytest.raises((RunCancelled, ValueError)):
        agent.execute("fixture", {}, "faça")
    assert calls == []
    assert store.finish_run(run.id).status == "cancelled"


def test_recovery_requires_exclusive_owner_and_does_not_replay(store):
    run = store.create_run(session_id="one", mode="general")
    agent = executor(store, run, confirm=True)
    agent.execute("waiting", {}, "faça")
    pending = agent.last_action.id
    active = ActionRecord.create(source="test", tool_name="active", metadata=ToolMetadata(), arguments={}, preview="x")
    active.run_id = run.id
    store.create(active)
    store.transition(active.id, "running")
    reader = ActionStore(store.path)
    assert reader.get(active.id).status == "running"  # reads never trigger recovery
    with pytest.raises(RuntimeError, match="outro backend"):
        reader.start_runtime()
    store._runtime_lock.close()  # simulate owner process exit
    store._runtime_lock = None
    reader.start_runtime()
    try:
        assert reader.get(active.id).status == "interrupted"
        assert reader.get(pending).status == "expired"
        detail = reader.run_details(run.id)
        assert detail["run"]["status"] == "interrupted"
        before = len(detail["events"])
        reader.start_runtime()
        assert len(reader.run_details(run.id)["events"]) == before
        assert detail["events"][-1]["kind"] == "recovery"
    finally:
        reader._runtime_lock.close()
        pending_action_broker.discard(pending)


def test_run_event_failure_rolls_back_action_snapshot(store):
    run = store.create_run(session_id=None, mode="general")
    agent = executor(store, run)
    action = agent.propose("fixture", {})
    with sqlite3.connect(store.path) as db:
        db.execute("CREATE TRIGGER reject_event BEFORE INSERT ON run_events BEGIN SELECT RAISE(ABORT, 'disk full'); END")
    with pytest.raises(sqlite3.IntegrityError):
        store.transition(action.id, "running")
    assert store.get(action.id).status == "proposed"
    assert len(store.details(action.id)["events"]) == 1


def test_run_filters_pagination_validation_and_terminal_cancel(store):
    first = store.create_run(session_id="one", mode="general")
    store.finish_run(first.id)
    second = store.create_run(session_id="two", mode="research")
    store.finish_run(second.id, failed=True)
    page = store.run_page(limit=1)
    assert page["runs"][0]["id"] == second.id
    assert store.run_page(limit=1, before=page["next_cursor"])["runs"][0]["id"] == first.id
    assert len(store.run_page(session_id="one")["runs"]) == 1
    assert store.run_page(status="failed")["runs"][0]["id"] == second.id
    assert runs.handle_runs_post(f"/api/runs/{first.id}/cancel", b"{}", None)[0] == 409
    assert runs.handle_runs_post("/api/runs/missing/cancel", b"{}", None)[0] == 404
    assert runs.handle_runs_post(f"/api/runs/{first.id}/cancel", b"[]", None)[0] == 400
    for query in ("limit=0", "status=unknown", "before=-1", "after_event_id=999999999999999999999"):
        assert runs.handle_runs_get(["api", "runs"], SimpleNamespace(path="/api/runs?" + query))[0] == 400
    assert runs.handle_runs_get(["api", "runs", first.id, "events"], SimpleNamespace(path="/api/runs/x/events?after_event_id=0"))[1]["events"]


def test_retention_keeps_active_groups_and_prunes_terminal_groups_whole(store):
    store.max_records = 1
    active = store.create_run(session_id="active", mode="general")
    old = store.create_run(session_id="old", mode="general")
    agent = executor(store, old)
    agent.execute("fixture", {}, "faça")
    store.finish_run(old.id)
    store.create_run(session_id="new", mode="general")
    assert store.run_details(active.id)
    assert store.run_details(old.id) is None
    assert store.details(agent.last_action.id) is None


def test_tracking_cancellation_and_context_cleanup(store):
    @track_run
    def turn(text, mode, session_id, history, on_chunk=None):
        _, run_id = current_run.get()
        store.cancel_run(run_id)
        on_chunk("must not be emitted")
        raise AssertionError("unreachable")
    chunks = []
    plan = turn("private", "general", "session", [], on_chunk=chunks.append)
    assert plan.intent == "cancelled"
    assert not chunks
    assert store.run_details(plan.context["run_id"])["run"]["status"] == "cancelled"
    assert current_run.get() is None


def test_tracking_exception_records_generic_failure_without_secret(store):
    @track_run
    def turn(text, mode, session_id, history):
        raise RuntimeError("password=never-persist")
    with pytest.raises(RuntimeError):
        turn("private", "general", None, [])
    run = store.run_page()["runs"][0]
    assert run["status"] == "failed"
    assert "never-persist" not in str(store.run_details(run["id"]))
    assert current_run.get() is None


def test_cancelling_one_request_does_not_cancel_another(store):
    first = store.create_run(session_id="one", mode="general")
    second = store.create_run(session_id="two", mode="general")
    store.cancel_run(first.id)
    executor(store, second).execute("fixture", {}, "faça")
    assert store.finish_run(second.id).status == "succeeded"
    assert store.finish_run(first.id).status == "cancelled"
