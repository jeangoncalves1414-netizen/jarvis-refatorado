"""Fase contexto 2: memória preenche parâmetros vazios e gera citação, sem chamada ao modelo."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.agent import memory_params, turn_meta
from app.agent.action_executor import ActionExecutor
from app.agent.mode_resolver import ModeResolver
from app.agent.orchestrator import AgentOrchestrator
from app.agent.tool_guardrails import ToolCallGuardrailController
from app.agent.tools.base import ToolResult
from app.core.actions import ToolMetadata, arguments_digest
from app.storage import memory_facts

TZ = timezone(timedelta(hours=-3))
MORNING = datetime(2025, 11, 7, 8, 0, tzinfo=TZ)
NIGHT = datetime(2025, 11, 7, 21, 0, tzinfo=TZ)


@pytest.fixture
def facts(isolated_lote6_data, monkeypatch):
    monkeypatch.setattr(memory_params, "clock", lambda: MORNING)
    stamp = datetime(2025, 11, 7, 7, 30, tzinfo=TZ).timestamp()
    source = {"created_at": stamp, "origin": "chat", "session_id": "abc", "kind": "gatilho"}
    return SimpleNamespace(
        morning=memory_facts.save("de manhã prefiro a playlist Foco", source=source),
        anytime=memory_facts.save("prefiro ouvir Jazz Calmo", source=source),
        city=memory_facts.save("eu moro em São José dos Campos", source=source),
        browser=memory_facts.save("prefiro usar o navegador Firefox", source=source),
    )


@pytest.fixture
def meta():
    token = turn_meta.start()
    yield lambda: turn_meta.snapshot().get("memory_used", [])
    turn_meta.reset(token)


def test_morning_play_request_fills_focus_playlist(facts, meta):
    args = memory_params.apply_memory_params("spotify", {"action": "play_pause"}, "toca música")
    assert args == {"action": "search_play", "query": "Foco"}
    [cite] = meta()
    assert cite["id"] == facts.morning["id"] and cite["how"] == "preenchido"
    assert cite["label"] == "memória de 07/11" and cite["date"] == "2025-11-07"
    assert cite["applied_to"] == {"tool": "spotify", "param": "query", "value": "Foco"}
    assert cite["origin"] == "chat" and cite["session_id"] == "abc"


def test_night_without_night_fact_uses_untimed_fact(facts, meta, monkeypatch):
    monkeypatch.setattr(memory_params, "clock", lambda: NIGHT)
    args = memory_params.apply_memory_params("spotify", {"action": "search_play"}, "coloca algo")
    assert args["query"] == "Jazz Calmo"
    assert meta()[0]["id"] == facts.anytime["id"]


def test_given_query_is_kept_but_cited(facts, meta):
    args = memory_params.apply_memory_params("spotify", {"action": "search_play", "query": "playlist Foco"}, "toca a Foco")
    assert args == {"action": "search_play", "query": "playlist Foco"}
    assert [(c["id"], c["how"]) for c in meta()] == [(facts.morning["id"], "citado")]


def test_pause_without_play_words_is_untouched(facts, meta):
    assert memory_params.apply_memory_params("spotify", {"action": "play_pause"}, "pausa aí") == {"action": "play_pause"}
    assert meta() == []


def test_weather_places_and_browser(facts, meta):
    assert memory_params.apply_memory_params("realtime", {"action": "get_weather"}, "clima")["city"] == "São José dos Campos"
    assert memory_params.apply_memory_params("realtime", {"action": "get_weather", "city": "Recife"}, "clima")["city"] == "Recife"
    assert memory_params.apply_memory_params("places_search", {"query": "farmácia"}, "farmácia perto")["near"] == "São José dos Campos"
    assert memory_params.apply_memory_params("open_windows_app", {"action": "open", "app_name": "navegador"}, "abre o navegador")["app_name"] == "Firefox"
    assert memory_params.apply_memory_params("open_windows_app", {"action": "open", "app_name": "notepad"}, "abre o bloco")["app_name"] == "notepad"
    assert len(meta()) <= memory_params.MAX_CITATIONS


def test_no_facts_or_broken_store_keeps_args(isolated_lote6_data, meta, monkeypatch):
    args = {"action": "search_play"}
    assert memory_params.apply_memory_params("spotify", args, "toca música") == args
    monkeypatch.setattr(memory_facts, "list_facts", lambda *a, **k: 1 / 0)
    assert memory_params.apply_memory_params("realtime", {"action": "get_weather"}, "clima") == {"action": "get_weather"}
    assert memory_params.apply_memory_params("task_tool", {"action": "list"}, "x") == {"action": "list"}
    assert meta() == []


def test_executor_runs_with_filled_args(facts, meta, isolated_lote6_data):
    calls = []
    executor = ActionExecutor(
        None, ToolCallGuardrailController(), lambda name, args, text: calls.append(args) or ToolResult(True, "tocando"),
        metadata_for=lambda _: ToolMetadata(("media",), "low"), store=isolated_lote6_data.store,
    )
    executor.execute("spotify", {"action": "play_pause"}, "toca uma música")
    assert calls == [{"action": "search_play", "query": "Foco"}]
    assert executor.last_action.arguments_digest == arguments_digest({"action": "search_play", "query": "Foco"})
    assert meta()[0]["how"] == "preenchido"


def test_handle_request_carries_memory_used(facts, isolated_lote6_data, monkeypatch):
    import app.agent.orchestrator as module
    from app.services import situational_context as sc
    monkeypatch.setattr(module, "build_tutor_system", lambda *a, **k: "tutor")
    monkeypatch.setattr("app.services.stm_filters.stm_filter", SimpleNamespace(process=lambda value: value))
    monkeypatch.setattr(module, "save_session_history", lambda session, history: None)
    monkeypatch.setattr(module, "get_session_history", lambda _: [])
    monkeypatch.setattr("app.core.logger.logger", SimpleNamespace(record_request=lambda: None, info=lambda *a: None,
                                                                  record_tool_execution=lambda *a: None))
    monkeypatch.setattr(sc, "situational_context", sc.SituationalContext([]))
    executed = []
    calls = []

    def chat(**kw):
        calls.append("chat")
        kw["on_function_call"]("spotify", {"action": "play_pause"})
        return "Tocando a playlist Foco."

    agent = AgentOrchestrator.__new__(AgentOrchestrator)
    agent.llm_service = SimpleNamespace(get_active_provider=lambda: "gemini", _api_key_for=lambda _: "k",
                                        chat_with_functions_stream=chat, ask=lambda *a, **k: calls.append("ask"))
    agent.semantic_memory = SimpleNamespace(is_available=lambda: False, search_memories=lambda *a, **k: [], add_memory=lambda *a, **k: None)
    agent.memory_store = agent.profile_memory = agent.settings = agent.vision_service = agent.browser_agent = None
    agent.productivity_service = agent.file_action_service = None
    agent.tutor_store = SimpleNamespace(get_summary_for_llm=lambda: "")
    agent.pattern_learner = SimpleNamespace(record_action=lambda *a: None)
    agent.mode_resolver = ModeResolver()
    agent._resolve_enem_context = lambda *a: None
    agent.registry = SimpleNamespace(
        tools={"spotify": object()}, get_tool_declarations=lambda **k: [],
        allowed_tool_names=lambda **k: frozenset({"spotify"}),
        get_tool_metadata=lambda _: ToolMetadata(("media",), "low"),
        execute_tool=lambda name, args, **k: executed.append(args) or ToolResult(True, "Tocando."),
    )
    plan = agent.handle_request("toca música", session_id="s1")
    assert executed == [{"action": "search_play", "query": "Foco"}]
    [cite] = plan.context["memory_used"]
    assert cite["text"] == "de manhã prefiro a playlist Foco" and cite["how"] == "preenchido"
    assert calls == ["chat"]
