from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from app.agent.tools.base import ToolResult
from app.agent.tools.registry import ToolRegistry
from app.core import loop_checkpoints, waits
from app.routines.runner import RoutineBusy, RoutineRunner
from app.routines.service import RoutineService
from app.storage import routine_store as routine_store_module
from app.storage.action_store import ActionStore
from app.ui.panel.api import actions as actions_api


class FakeRegistry:
    """Ferramentas reais (schema e risco); a execução é falsa e registra a ordem no relógio falso."""

    def __init__(self, real, clock):
        self.real, self.clock = real, clock
        self.calls: list[tuple[str, str, float]] = []
        self.behavior: dict[tuple[str, str], object] = {}

    def get_tool(self, name):
        return self.real.get_tool(name)

    def get_tool_metadata(self, name):
        return self.real.get_tool_metadata(name)

    def execute_tool(self, name, args, context=None):
        operation = args.get("action", "")
        self.calls.append((name, operation, self.clock[0]))
        behave = self.behavior.get((name, operation))
        if callable(behave):
            return behave()
        return behave or ToolResult(True, f"{name} {operation} ok")


@pytest.fixture(scope="module")
def real_registry():
    return ToolRegistry()


@pytest.fixture
def env(tmp_path, monkeypatch, real_registry, isolated_auto_approvals):
    store = ActionStore(tmp_path / "journal.sqlite3")
    monkeypatch.setattr("app.storage.action_store.action_store", store)
    monkeypatch.setattr(actions_api, "action_store", store)
    monkeypatch.setattr(loop_checkpoints, "resume_runner", lambda checkpoint, status: checkpoint.resume(status))
    clock = [0.0]
    hooks: list = []

    def sleep(seconds):
        clock[0] += seconds
        for hook in list(hooks):
            hook(clock[0])

    monkeypatch.setattr(waits, "_monotonic", lambda: clock[0])
    monkeypatch.setattr(waits, "_sleep", sleep)
    registry = FakeRegistry(real_registry, clock)
    runner = RoutineRunner(registry=registry, spawn=lambda fn: fn())
    service = RoutineService(runner=runner, registry=registry)
    yield SimpleNamespace(store=store, registry=registry, runner=runner, service=service, clock=clock, hooks=hooks, approvals=isolated_auto_approvals)
    loop_checkpoints.loop_checkpoints.clear()
    if store._runtime_lock:
        store._runtime_lock.close()


def _create(env, steps, **extra):
    return env.service.create({"name": "Teste", "steps": steps, **extra})["routine"]


def _entry(routine_id):
    return routine_store_module.routine_store.history(routine_id)[0]


def _run(env, run_id):
    return env.store.run_details(run_id)["run"]


SPOTIFY_OPEN = {"tool": "spotify", "operation": "open"}
SPOTIFY_NEXT = {"tool": "spotify", "operation": "next"}
DELETE_TASK = {"tool": "task_tool", "operation": "delete", "params": {"task_id": "t1"}}


def test_steps_run_in_order_with_delay_and_run_has_routine_origin(env):
    routine = _create(env, [SPOTIFY_OPEN, {"tool": "web_search", "operation": "open_url", "params": {"query": "https://youtube.com"}, "delay_before": 50}])
    run_id = env.service.run_now(routine["id"])
    assert [(name, op) for name, op, _ in env.registry.calls] == [("spotify", "open"), ("web_search", "open_url")]
    assert env.registry.calls[1][2] - env.registry.calls[0][2] == 50
    run = _run(env, run_id)
    assert (run["origin"], run["status"]) == ("routine", "succeeded")
    assert run_id in [item["id"] for item in env.store.run_page()["runs"]]
    entry = _entry(routine["id"])
    assert (entry["status"], entry["run_id"], entry["trigger_kind"]) == ("succeeded", run_id, "manual")
    assert "concluída: 2 etapa(s)" in entry["summary"]
    stored = routine_store_module.routine_store.get(routine["id"])
    assert (stored["last_status"], stored["last_run_id"]) == ("succeeded", run_id)
    events = [event["summary"] for event in env.store.run_details(run_id)["events"] if event["kind"] == "routine"]
    assert events[0].startswith('Rotina "Teste" iniciada (gatilho: executar agora)')


def test_high_step_pauses_and_approval_resumes(env):
    routine = _create(env, [SPOTIFY_OPEN, DELETE_TASK, SPOTIFY_NEXT])
    run_id = env.service.run_now(routine["id"])
    assert [op for _, op, _ in env.registry.calls] == ["open"]
    assert _entry(routine["id"])["status"] == "paused"
    assert _run(env, run_id)["status"] == "awaiting_confirmation"
    pending = [action for action in env.store.run_details(run_id)["actions"] if action["status"] == "awaiting_confirmation"]
    status, payload = actions_api.handle_actions_post(f"/api/actions/{pending[0]['id']}/approve", b"{}", None)
    assert status == 200 and payload["resumed"] is True
    assert [op for _, op, _ in env.registry.calls] == ["open", "delete", "next"]
    assert _entry(routine["id"])["status"] == "succeeded"
    assert _run(env, run_id)["status"] == "succeeded"
    assert not env.runner.is_running(routine["id"])


def test_rejected_step_fails_routine_even_with_continue(env):
    routine = _create(env, [dict(DELETE_TASK, on_failure="continue"), SPOTIFY_NEXT])
    run_id = env.service.run_now(routine["id"])
    action = [item for item in env.store.run_details(run_id)["actions"] if item["status"] == "awaiting_confirmation"][0]
    actions_api.handle_actions_post(f"/api/actions/{action['id']}/reject", b"{}", None)
    entry = _entry(routine["id"])
    assert entry["status"] == "failed" and "Etapa 1 foi recusada" in entry["summary"]
    assert env.registry.calls == []
    assert _run(env, run_id)["status"] in {"failed", "cancelled"}


def test_expired_approval_fails_routine_clearly(env, monkeypatch):
    routine = _create(env, [DELETE_TASK, SPOTIFY_NEXT])
    run_id = env.service.run_now(routine["id"])
    # Relógio adiantado: toda proposta pendente já passou do prazo.
    monkeypatch.setattr(loop_checkpoints.loop_checkpoints, "ttl_seconds", 0)
    monkeypatch.setattr(actions_api, "_CHECKPOINT_GRACE_SECONDS", -5)
    assert actions_api.sweep_expired_proposals(env.store) == 1
    entry = _entry(routine["id"])
    assert entry["status"] == "failed" and "não foi aprovada a tempo (expirou)" in entry["summary"]
    assert _run(env, run_id)["status"] == "failed"
    assert not env.runner.is_running(routine["id"])


def test_reconcile_closes_paused_run_cancelled_in_central(env):
    routine = _create(env, [DELETE_TASK])
    run_id = env.service.run_now(routine["id"])
    env.store.cancel_run(run_id)
    assert env.runner.reconcile() == 1
    assert _entry(routine["id"])["status"] == "cancelled"


def test_auto_approval_rule_and_liberated_mode_run_without_pausing(env):
    env.approvals.add_rule("task_tool", "delete", "t1", "always", risk="high")
    routine = _create(env, [DELETE_TASK])
    env.service.run_now(routine["id"])
    assert _entry(routine["id"])["status"] == "succeeded"
    env.approvals.set_mode(True)
    other = _create(env, [{"tool": "task_tool", "operation": "delete", "params": {"task_id": "t2"}}])
    env.service.run_now(other["id"])
    assert _entry(other["id"])["status"] == "succeeded"
    assert [op for _, op, _ in env.registry.calls] == ["delete", "delete"]


def test_on_failure_continue_retry_and_stop(env):
    env.registry.behavior[("spotify", "next")] = ToolResult(False, "Spotify não respondeu.")
    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        return ToolResult(attempts["n"] > 2, f"tentativa {attempts['n']}")

    env.registry.behavior[("spotify", "previous")] = flaky
    routine = _create(env, [
        dict(SPOTIFY_NEXT, on_failure="continue"),
        {"tool": "spotify", "operation": "previous", "on_failure": "retry", "retries": 2},
        dict(SPOTIFY_NEXT, on_failure="stop", label="Próxima de novo"),
        SPOTIFY_OPEN,
    ])
    env.service.run_now(routine["id"])
    assert [op for _, op, _ in env.registry.calls] == ["next", "previous", "previous", "previous", "next"]
    entry = _entry(routine["id"])
    assert entry["status"] == "failed" and "parou na etapa 3 (Próxima de novo)" in entry["summary"]


def test_step_timeout_returns_clear_failure(env):
    release = threading.Event()

    class Slow:
        def execute_tool(self, name, args, context=None):
            release.wait(5)
            return ToolResult(True, "tarde demais")

    try:
        result = RoutineRunner._call(Slow(), "spotify", {}, 0.05)
    finally:
        release.set()
    assert result.ok is False and "Tempo esgotado" in result.message


def test_cancel_during_delay_stops_before_next_step(env):
    routine = _create(env, [SPOTIFY_OPEN, dict(SPOTIFY_NEXT, delay_before=30)])
    done = {}

    def cancel_midway(now):
        # "Parar pedido" na Central no 10º segundo da espera de 30 s.
        if now >= 10 and not done:
            done["yes"] = True
            env.store.cancel_run(env.runner.active()[0].run_id)

    env.hooks.append(cancel_midway)
    env.service.run_now(routine["id"])
    assert done
    assert [op for _, op, _ in env.registry.calls] == ["open"]
    assert _entry(routine["id"])["status"] == "cancelled"


def test_overlapping_start_is_skipped(env):
    routine = _create(env, [DELETE_TASK])
    env.service.run_now(routine["id"])
    assert env.runner.start(routine_store_module.routine_store.get(routine["id"]), "schedule") is None
    assert _entry(routine["id"])["summary"] == "Ainda em execução; este disparo foi ignorado."
    with pytest.raises(RoutineBusy):
        env.service.run_now(routine["id"])
