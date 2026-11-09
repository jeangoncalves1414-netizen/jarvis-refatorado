from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.agent import popups
from app.agent.tools.catalog import TOOL_CATALOG
from app.agent.tools.registry import ToolRegistry
from app.routines import service as service_module
from app.routines.runner import RoutineRunner
from app.storage import routine_store as routine_store_module

# Como o modelo mandaria "todo dia às 8h abre o Chrome e 30 s depois toca a playlist Foco".
MORNING = {
    "action": "create",
    "name": "Manhã com foco",
    "triggers": [{"type": "daily", "time": "08:00"}],
    "steps": [
        {"tool": "open_windows_app", "operation": "open", "params": {"app_name": "chrome"}},
        {"tool": "spotify", "operation": "search_play", "params": {"query": "Foco"}, "delay_before": 30},
    ],
}


@pytest.fixture(scope="module")
def registry():
    return ToolRegistry()


@pytest.fixture
def quiet_runner(monkeypatch, isolated_lote6_data):
    """Executar agora só cria o Run (Central em tmp); nenhuma ferramenta real roda."""
    runner = RoutineRunner(spawn=lambda fn: None)
    monkeypatch.setattr(service_module.routine_service, "runner", runner)
    return runner


def test_create_from_natural_language_args_stores_routine_and_next_run(registry, quiet_runner):
    result = registry.get_tool("routine").execute(dict(MORNING))
    assert result.ok, result.message
    routine = result.data["routine"]
    stored = routine_store_module.routine_store.get(routine["id"])
    assert [step["tool"] for step in stored["steps"]] == ["open_windows_app", "spotify"]
    assert stored["steps"][1]["delay_before"] == 30
    assert result.data["next_run"].endswith("08:00:00-03:00")
    assert "Próxima execução:" in result.message and "Todo dia às 08:00" in result.message
    assert "2. após 30 s: Tocar Foco no Spotify" in result.message


def test_create_emits_summary_popup(registry, quiet_runner):
    result = registry.get_tool("routine").execute(dict(MORNING))
    requests = popups.popups_for_result("routine", {"action": "create"}, result)
    assert len(requests) == 1
    template, params, _animate = requests[0]
    assert template == "info" and params["title"] == "Rotina criada" and params["tone"] == "ok"
    assert params["lines"][:2] == ["Manhã com foco", "Todo dia às 08:00"]
    assert params["lines"][2:4] == ["1. Abrir chrome", "2. após 30 s: Tocar Foco no Spotify"]
    assert params["lines"][-1].startswith("Próxima: ")
    popups.validate_popup_request(template, params)


def test_tool_list_update_enable_disable_run_now_and_errors(registry, quiet_runner):
    tool = registry.get_tool("routine")
    created = tool.execute(dict(MORNING)).data["routine"]
    listed = tool.execute({"action": "list"})
    assert listed.ok and created["id"] in listed.data["routine_ids"]
    updated = tool.execute({"action": "update", "name": "Manhã com foco", "triggers": [{"type": "weekdays", "time": "07:30"}]})
    assert updated.ok and "Dias úteis às 07:30" in updated.message
    assert tool.execute({"action": "disable", "routine_id": created["id"]}).message.endswith("desativada.")
    assert routine_store_module.routine_store.get(created["id"])["enabled"] is False
    assert tool.execute({"action": "enable", "routine_id": created["id"]}).ok
    started = tool.execute({"action": "run_now", "routine_id": created["id"]})
    assert started.ok and started.data["run_id"].startswith("run_")
    busy = tool.execute({"action": "run_now", "routine_id": created["id"]})
    assert busy.ok is False and "já está em execução" in busy.message
    bad = tool.execute({"action": "create", "name": "x", "steps": [{"tool": "routine", "operation": "list"}]})
    assert bad.ok is False and "não pode ser etapa" in bad.message
    assert tool.execute({"action": "delete", "routine_id": "rt_nao"}).ok is False


def test_catalog_risk_delete_needs_approval(tmp_path):
    from app.agent.action_executor import ActionExecutor
    from app.agent.tool_guardrails import ToolCallGuardrailController
    from app.agent.tools.base import ToolResult
    from app.storage.action_store import ActionStore

    metadata = TOOL_CATALOG["routine"]
    assert metadata.risk_for({"action": "list"}) == "observe"
    assert metadata.risk_for({"action": "create"}) == "low"
    assert metadata.risk_for({"action": "delete"}) == "high"
    store = ActionStore(tmp_path / "journal.sqlite3")
    calls = []
    executor = ActionExecutor(None, ToolCallGuardrailController(), lambda name, args, user: calls.append(args) or ToolResult(True, "ok"),
                              metadata_for=TOOL_CATALOG.get, store=store, source="test")
    try:
        executor.execute("routine", {"action": "delete", "routine_id": "rt_1"}, "apague a rotina")
        assert executor.last_action.status == "awaiting_confirmation" and calls == []
    finally:
        if store._runtime_lock:
            store._runtime_lock.close()


def test_routine_tool_offered_only_for_scheduled_requests(registry):
    scheduled = "todo dia às 8h abre o Chrome e 30 s depois toca a playlist Foco"
    immediate = "abre o Spotify, espera 50 s e abre o YouTube"
    assert "routine" in registry.allowed_tool_names(mode="general", user_text=scheduled, narrow=True)
    assert "routine" not in registry.allowed_tool_names(mode="general", user_text=immediate, narrow=True)
    assert "routine" in registry.allowed_tool_names(mode="general", provider="groq", user_text="toda segunda as 9:00 abre o chrome")
    assert "routine" not in registry.allowed_tool_names(mode="general", provider="groq", user_text=immediate)


def test_voice_phrase_runs_routine_without_calling_the_model(registry, quiet_runner, monkeypatch):
    from app.agent.orchestrator import AgentOrchestrator

    monkeypatch.setattr("app.core.logger.logger", SimpleNamespace(record_request=lambda: None, info=lambda *a: None))

    service_module.routine_service.create({
        "name": "Modo foco", "steps": [{"tool": "spotify", "operation": "open"}],
        "triggers": [{"type": "voice", "phrase": "modo foco"}],
    })

    def forbidden(*_args, **_kwargs):
        raise AssertionError("o modelo não deve ser chamado")

    agent = AgentOrchestrator.__new__(AgentOrchestrator)
    agent.llm_service = SimpleNamespace(get_active_provider=forbidden, chat=forbidden, ask=forbidden)
    plan = agent._dispatch_request("Jarvis, modo foco!", "s1", "general", [], None, None, None, None, None, None, False, None)
    assert plan.intent == "routine" and 'Rotina "Modo foco" iniciada' in plan.summary
    assert plan.context["routine_run_id"].startswith("run_")
    assert agent._run_routine_phrase("o que é modo foco?", "general") is None
