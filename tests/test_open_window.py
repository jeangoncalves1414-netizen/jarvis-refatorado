from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.agent.action_executor import ActionExecutor
from app.agent.tool_guardrails import ToolCallGuardrailController
from app.agent.tools.open_window import OpenWindowTool, WINDOWS, validate_window_request
from app.agent.tools.registry import GENERAL_TOOL_NAMES, registry
from app.storage.action_store import ActionStore


def test_known_window_opens_with_validated_params():
    result = OpenWindowTool().execute({"window_id": "finance", "params": {"type": "Expense", "category": " Mercado ", "amount": 25.5, "period": "month"}})
    assert result.ok is True
    assert result.data["ui_window"] == {
        "window_id": "finance",
        "params": {"type": "expense", "category": "Mercado", "amount": 25.5, "period": "month"},
    }


def test_known_window_without_params_is_ok():
    result = OpenWindowTool().execute({"window_id": "finance"})
    assert result.ok is True
    assert result.data["ui_window"] == {"window_id": "finance", "params": {}}


def test_marker_path_accepts_window_id_in_command():
    result = OpenWindowTool().execute({"command": "finance"})
    assert result.ok is True
    assert result.data["ui_window"]["window_id"] == "finance"


@pytest.mark.parametrize("window_id", ["", "calculadora", "../finance", "FINANCE ", None, 7])
def test_unknown_window_id_returns_error(window_id):
    result = OpenWindowTool().execute({"window_id": window_id})
    assert result.ok is False
    assert "desconhecida" in result.message
    assert "ui_window" not in result.data


@pytest.mark.parametrize(
    "params",
    [
        {"html": "<script>alert(1)</script>"},
        {"type": "transfer"},
        {"amount": -5},
        {"amount": "10"},
        {"amount": True},
        {"period": "ano"},
        {"date": "31/12/2026"},
        {"category": "x" * 61},
        {"description": 123},
        "finance",
    ],
)
def test_invalid_params_are_rejected(params):
    result = OpenWindowTool().execute({"window_id": "finance", "params": params})
    assert result.ok is False
    assert "ui_window" not in result.data


def test_validate_window_request_raises_for_unknown_id():
    with pytest.raises(ValueError):
        validate_window_request("nao-existe", {})
    assert validate_window_request("finance", None) == ("finance", {})


def test_tool_is_registered_with_enum_of_registry_ids():
    tool = registry.get_tool("open_window")
    assert tool is not None
    assert "open_window" in GENERAL_TOOL_NAMES
    assert tool.parameters["properties"]["window_id"]["enum"] == sorted(WINDOWS)
    declared = {item["name"] for item in registry.get_tool_declarations(mode="general")}
    assert "open_window" in declared


@pytest.fixture
def agent(tmp_path, monkeypatch):
    import app.agent.action_executor as executor_module
    import app.agent.orchestrator as module
    from app.agent.orchestrator import AgentOrchestrator
    from app.core.actions import ToolMetadata

    monkeypatch.chdir(tmp_path)
    store = ActionStore(tmp_path / "actions.sqlite3")
    monkeypatch.setattr(executor_module, "action_store", store)
    monkeypatch.setattr("app.storage.action_store.action_store", store)
    monkeypatch.setattr(module, "build_tutor_system", lambda *_args, **_kwargs: "test")
    monkeypatch.setattr("app.services.stm_filters.stm_filter", SimpleNamespace(process=lambda text: text))
    monkeypatch.setattr("app.core.logger.logger", SimpleNamespace(record_tool_execution=lambda *_: None, info=lambda *_: None))
    tool = OpenWindowTool()
    obj = AgentOrchestrator.__new__(AgentOrchestrator)
    obj.tutor_store = SimpleNamespace(get_summary_for_llm=lambda: "")
    obj.settings = obj.vision_service = obj.browser_agent = None
    obj.pattern_learner = SimpleNamespace(record_action=lambda *_: None)
    obj.registry = SimpleNamespace(
        tools={"open_window": tool}, get_tool_declarations=lambda **_: [],
        get_tool_metadata=lambda _: ToolMetadata(("ui", "window"), "observe"),
        execute_tool=lambda name, args, context=None: tool.execute(args),
        run_by_marker=lambda kind, arg, line: tool.execute({"command": arg}),
    )
    yield obj
    if store._runtime_lock:
        store._runtime_lock.close()


def test_native_turn_carries_the_window_request_to_the_panel(agent):
    agent.llm_service = SimpleNamespace(
        get_active_provider=lambda: "gemini",
        chat_with_functions_stream=lambda **kw: kw["on_function_call"]("open_window", {"window_id": "finance", "params": {"period": "week"}}),
    )
    plan = agent._run_llm_with_tools("abra as finanças", "tutor", "s1", [])
    result = plan.context["tool_results"]["open_window"]
    assert result["ok"] is True
    assert result["data"]["ui_window"] == {"window_id": "finance", "params": {"period": "week"}}


def test_marker_turn_carries_the_window_request_to_the_panel(agent):
    agent.llm_service = SimpleNamespace(
        get_active_provider=lambda: "marker",
        build_contents=lambda *_: [],
        generate=lambda *_args, **_kwargs: SimpleNamespace(text="Abrindo. [tool:open_window:finance]"),
    )
    plan = agent._run_llm_with_tools("abra as finanças", "tutor", "s2", [])
    assert plan.context["tool_results"]["open_window"]["data"]["ui_window"] == {"window_id": "finance", "params": {}}


def test_unknown_window_never_reaches_the_panel(agent):
    agent.llm_service = SimpleNamespace(
        get_active_provider=lambda: "gemini",
        chat_with_functions_stream=lambda **kw: kw["on_function_call"]("open_window", {"window_id": "calculadora"}),
    )
    plan = agent._run_llm_with_tools("abra", "tutor", "s3", [])
    result = plan.context["tool_results"]["open_window"]
    assert result["ok"] is False
    assert "ui_window" not in (result["data"] or {})


def test_open_window_goes_through_action_kernel_as_observe(tmp_path):
    store = ActionStore(tmp_path / "journal.sqlite3")
    metadata = registry.get_tool_metadata("open_window")
    assert metadata is not None and metadata.default_risk == "observe" and not metadata.requires_confirmation
    seen: dict = {}

    def execute(name, args, _user_line):
        result = registry.execute_tool(name, args)
        seen["result"] = result
        return result

    try:
        executor = ActionExecutor(
            frozenset(registry.tools.keys()), ToolCallGuardrailController(), execute,
            metadata_for=registry.get_tool_metadata, store=store, source="function:test",
        )
        executor.execute("open_window", {"window_id": "finance", "params": {"period": "week"}}, "abra as finanças")
        assert executor.last_action is not None
        assert executor.last_action.status == "succeeded"
        assert executor.last_action.risk == "observe"
        assert seen["result"].data["ui_window"] == {"window_id": "finance", "params": {"period": "week"}}

        executor.execute("open_window", {"window_id": "nada"}, "abra")
        assert executor.last_action.status == "failed"
    finally:
        if store._runtime_lock:
            store._runtime_lock.close()
