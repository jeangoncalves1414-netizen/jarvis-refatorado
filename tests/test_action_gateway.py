"""Ponto de entrada único do Action Kernel para rotas diretas (C10, AQ1)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.agent.action_executor import ActionExecutor
from app.agent.action_gateway import request_origin, run_action
from app.agent.tool_guardrails import ToolCallGuardrailController
from app.agent.tools.base import ToolResult
from app.core.actions import ToolMetadata, pending_action_broker
from app.core.runs import current_origin, current_run
from app.storage.action_store import ActionStore


@pytest.fixture
def journal(tmp_path, monkeypatch):
    store = ActionStore(tmp_path / "gateway.sqlite3")
    monkeypatch.setattr("app.storage.action_store.action_store", store)
    yield store
    for action in store.list(limit=100):
        pending_action_broker.discard(action.id)
    if store._runtime_lock:
        store._runtime_lock.close()


def test_low_risk_action_runs_once_and_is_recorded_with_its_run(journal):
    calls = []
    outcome = run_action(
        "web_search", {"query": "clima"}, source="api:test", user_text="buscar clima",
        execute=lambda args: calls.append(args) or ToolResult(True, "ok", {"n": 1}),
    )
    assert outcome.succeeded and calls == [{"query": "clima"}]
    assert (outcome.action.source, outcome.action.status) == ("api:test", "succeeded")
    run = journal.run_details(outcome.action.run_id)["run"]
    assert run["status"] == "succeeded" and run["session_id"] == "api:test"
    assert current_run.get() is None


def test_high_risk_action_waits_for_approval_and_nothing_runs(journal):
    calls = []
    outcome = run_action(
        "browser_agent", {"goal": "abrir site"}, source="api:browser", user_text="abrir site",
        execute=lambda args: calls.append(args) or ToolResult(True, "ok"),
    )
    assert outcome.pending and not outcome.succeeded and calls == []
    assert journal.run_details(outcome.action.run_id)["run"]["status"] == "awaiting_confirmation"
    pending_action_broker.take(outcome.action.id)  # a aprovação é testada pela rota do servidor


def test_confirmed_route_records_the_confirmation_and_runs(journal):
    calls = []
    outcome = run_action(
        "script_runner", {"language": "python", "code": "print(1)"}, source="api:script", user_text="script",
        execute=lambda args: calls.append(args) or ToolResult(True, "concluído"), confirmed_by="Confirmada no chat.",
    )
    assert outcome.succeeded and len(calls) == 1
    events = journal.details(outcome.action.id)["events"]
    assert [event["status"] for event in events] == ["awaiting_confirmation", "authorized", "running", "succeeded"]
    assert events[1]["summary"] == "Confirmada no chat."
    assert pending_action_broker.take(outcome.action.id) is None


def test_tool_exception_is_recorded_as_failure(journal):
    def boom(_args):
        raise RuntimeError("falhou")

    outcome = run_action("web_search", {"query": "x"}, source="api:test", user_text="x", execute=boom)
    assert outcome.crashed and not outcome.succeeded and outcome.action.status == "failed"
    assert journal.run_details(outcome.action.run_id)["run"]["status"] == "failed"


def test_registry_tool_is_used_when_the_route_has_no_executor(journal, monkeypatch):
    from app.agent.tools import registry as registry_module

    calls = []
    fake = SimpleNamespace(
        get_tool_metadata=lambda _: ToolMetadata(("fixture",), "low"),
        execute_tool=lambda name, args, context=None: calls.append((name, args, context)) or ToolResult(True, "feito"),
    )
    monkeypatch.setattr(registry_module, "registry", fake)
    outcome = run_action("fixture", {"a": 1}, source="panel:test", user_text="x", context={"k": "v"})
    assert outcome.succeeded and calls == [("fixture", {"a": 1}, {"k": "v"})]


def test_executor_prefixes_the_source_with_the_request_origin(journal):
    token = current_origin.set("voice")
    try:
        executor = ActionExecutor(frozenset({"fixture"}), ToolCallGuardrailController(), lambda *_: ToolResult(True, "ok"),
                                  metadata_for=lambda _: ToolMetadata(("fixture",), "low"), store=journal, source="function:s1")
    finally:
        current_origin.reset(token)
    executor.execute("fixture", {}, "faça")
    assert executor.last_action.source == "voice:function:s1"


@pytest.mark.parametrize(("value", "expected"), [("voice", "voice"), ("chat", "chat"), ("root", "chat"), (None, "chat"), (1, "chat")])
def test_request_origin_only_accepts_known_values(value, expected):
    assert request_origin(value) == expected
