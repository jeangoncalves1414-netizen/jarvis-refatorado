from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

import pytest

from app.agent.orchestrator import AgentOrchestrator
from app.agent.tools.base import ToolResult
from app.core.actions import ToolMetadata
from app.storage.action_store import ActionStore


@pytest.fixture
def agent(tmp_path, monkeypatch):
    import app.agent.action_executor as executor_module
    import app.agent.orchestrator as module
    monkeypatch.chdir(tmp_path)
    store = ActionStore(tmp_path / "actions.sqlite3")
    monkeypatch.setattr(executor_module, "action_store", store)
    monkeypatch.setattr("app.storage.action_store.action_store", store)
    monkeypatch.setattr(module, "build_tutor_system", lambda *_args, **_kwargs: "test")
    monkeypatch.setattr("app.services.stm_filters.stm_filter", SimpleNamespace(process=lambda text: text))
    monkeypatch.setattr("app.core.logger.logger", SimpleNamespace(record_tool_execution=lambda *_: None, info=lambda *_: None))
    obj = AgentOrchestrator.__new__(AgentOrchestrator)
    obj.tutor_store = SimpleNamespace(get_summary_for_llm=lambda: "")
    obj.settings = obj.vision_service = obj.browser_agent = None
    obj.pattern_learner = SimpleNamespace(record_action=lambda *_: None)
    obj.registry = SimpleNamespace(
        tools={"fixture": object()}, get_tool_declarations=lambda **_: [],
        allowed_tool_names=lambda **_: frozenset({"fixture"}),
        get_tool_metadata=lambda _: ToolMetadata(),
        execute_tool=lambda *_args, **_kwargs: ToolResult(False, "Arquivo não encontrado."),
        run_by_marker=lambda *_args: ToolResult(False, "Arquivo não encontrado."),
    )
    return obj, store


@pytest.mark.parametrize("provider", ["gemini", "marker"])
def test_orchestrator_keeps_typed_tool_failures(agent, provider):
    obj, store = agent
    obj.llm_service = SimpleNamespace(
        get_active_provider=lambda: provider,
        chat_with_functions_stream=lambda **kw: kw["on_function_call"]("fixture", {}),
        build_contents=lambda *_: [],
        generate=lambda *_args, **_kwargs: SimpleNamespace(text="Concluído. [tool:fixture]"),
    )
    result = obj._run_llm_with_tools("leia", "tutor", "session-test", [])
    assert "Arquivo não encontrado" in result.summary
    assert store.list()[0].status == "failed"
    if provider == "gemini":
        assert result.context["tool_results"]["fixture"]["ok"] is False
    else:
        assert "Concluído" not in result.summary


def test_two_concurrent_turns_have_independent_guardrails(agent):
    obj, store = agent
    barrier = Barrier(2)
    obj.registry.execute_tool = lambda *_args, **_kwargs: ToolResult(True, "feito")
    def chat(**kw):
        barrier.wait(timeout=10)
        results = [kw["on_function_call"]("fixture", {}) for _ in range(4)]
        assert results[:3] == ["feito"] * 3
        assert "repetida bloqueada" in results[3]
        return "ok"
    obj.llm_service = SimpleNamespace(get_active_provider=lambda: "gemini", chat_with_functions_stream=chat)
    with ThreadPoolExecutor(max_workers=2) as pool:
        plans = list(pool.map(lambda session: obj._run_llm_with_tools("faça", "tutor", session, []), ["one", "two"]))
    assert len(plans) == 2
    assert store.status_counts() == {"succeeded": 6, "cancelled": 2}
    run_ids = {plan.context["run_id"] for plan in plans}
    assert len(run_ids) == 2
    assert {store.run_details(run_id)["run"]["session_id"] for run_id in run_ids} == {"one", "two"}
    assert all(len(store.run_details(run_id)["actions"]) == 4 for run_id in run_ids)
