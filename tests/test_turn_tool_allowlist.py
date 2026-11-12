"""C3: o servidor aplica a lista de ferramentas do modo e do turno ao executor."""

from types import SimpleNamespace

import pytest

from app.agent.orchestrator import AgentOrchestrator
from app.agent.tools.base import ToolResult
from app.agent.tools.registry import GENERAL_TOOL_NAMES, LANGUAGE_TOOL_NAMES, TUTOR_TOOL_NAMES, ToolRegistry
from app.core.actions import ToolMetadata
from app.storage.action_store import ActionStore
from app.storage.language_store import LanguageStore
from app.storage.tutor_store import TutorStore


@pytest.fixture(scope="module")
def registry(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("tools")
    return ToolRegistry(
        base_folder=str(tmp),
        tutor_store=TutorStore(str(tmp / "tutor")),
        language_store=LanguageStore(str(tmp / "language")),
    )


@pytest.mark.parametrize("mode,provider,text", [
    ("general", "gemini", "oi"),
    ("planning", "gemini", "monte um plano"),
    ("research", "marker", "pesquise"),
    ("tutor", "gemini", "explique"),
    ("general", "groq", "abra o spotify e use habit tool"),
    ("language", "gemini", "vamos praticar"),
    ("language", "groq", "oi"),
])
def test_allowed_names_match_what_the_model_receives(registry, mode, provider, text):
    declared = {item["name"] for item in registry.get_tool_declarations(mode=mode, provider=provider, user_text=text)}
    allowed = registry.allowed_tool_names(mode=mode, provider=provider, user_text=text)
    assert allowed == declared
    assert allowed < frozenset(registry.tools)


def test_modes_do_not_share_tools(registry):
    general = registry.allowed_tool_names(mode="general")
    tutor = registry.allowed_tool_names(mode="tutor")
    assert general <= GENERAL_TOOL_NAMES and tutor <= TUTOR_TOOL_NAMES
    assert "system_control" in general and "system_control" not in tutor
    assert not (general & tutor)
    language = registry.allowed_tool_names(mode="language")
    assert language and language <= LANGUAGE_TOOL_NAMES
    assert not (language & general) and not (language & tutor)


def test_groq_turn_list_is_narrower_than_the_mode_list(registry):
    mode_list = registry.allowed_tool_names(mode="general", provider="gemini")
    groq_list = registry.allowed_tool_names(mode="general", provider="groq", user_text="oi")
    assert groq_list < mode_list
    assert "web_search" in groq_list and "kasa_control" not in groq_list


@pytest.fixture
def agent(tmp_path, monkeypatch):
    import app.agent.action_executor as executor_module
    import app.agent.orchestrator as module
    monkeypatch.chdir(tmp_path)
    store = ActionStore(tmp_path / "actions.sqlite3")
    monkeypatch.setattr(executor_module, "action_store", store)
    monkeypatch.setattr("app.storage.action_store.action_store", store)
    monkeypatch.setattr(module, "build_tutor_system", lambda *_a, **_k: "test")
    monkeypatch.setattr("app.services.stm_filters.stm_filter", SimpleNamespace(process=lambda text: text))
    monkeypatch.setattr("app.core.logger.logger", SimpleNamespace(record_tool_execution=lambda *_: None, info=lambda *_: None))
    executed = []
    obj = AgentOrchestrator.__new__(AgentOrchestrator)
    obj.tutor_store = SimpleNamespace(get_summary_for_llm=lambda: "")
    obj.settings = obj.vision_service = obj.browser_agent = None
    obj.pattern_learner = SimpleNamespace(record_action=lambda *_: None)
    obj.registry = SimpleNamespace(
        tools={"allowed": object(), "registered_only": object()},
        get_tool_declarations=lambda **_: [],
        allowed_tool_names=lambda **_: frozenset({"allowed"}),
        get_tool_metadata=lambda _: ToolMetadata(("fixture",), "observe"),
        execute_tool=lambda name, *_a, **_k: executed.append(name) or ToolResult(True, "feito"),
        run_by_marker=lambda name, *_a: executed.append(name) or ToolResult(True, "feito"),
    )
    return obj, store, executed


@pytest.mark.parametrize("provider", ["gemini", "marker"])
def test_executor_blocks_registered_tool_outside_the_turn_list(agent, provider):
    obj, store, executed = agent
    obj.llm_service = SimpleNamespace(
        get_active_provider=lambda: provider,
        chat_with_functions_stream=lambda **kw: (
            kw["on_function_call"]("allowed", {}) + "|" + kw["on_function_call"]("registered_only", {})
        ),
        build_contents=lambda *_: [],
        generate=lambda *_a, **_k: SimpleNamespace(text="[tool:allowed] [tool:registered_only]"),
    )
    obj._run_llm_with_tools("faça", "tutor", "session-c3", [])
    assert executed == ["allowed"]
    assert [action.tool_name for action in store.list()] == ["allowed"]
