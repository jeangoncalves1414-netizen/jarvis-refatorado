"""Fase contexto 1: contexto situacional por código puro, sem chamada ao modelo."""
import threading
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

import pytest

from app.agent import turn_meta
from app.agent.mode_resolver import ModeResolver
from app.agent.orchestrator import AgentOrchestrator
from app.agent.react_loop import ReActLoopEngine
from app.core.actions import ToolMetadata
from app.services import situational_context as sc
from app.storage.contexto_settings import CONTEXT_DEFAULTS, SOURCE_KEYS, get_context_settings, set_context_settings

NOW = datetime(2025, 11, 7, 8, 12, tzinfo=timezone(timedelta(hours=-3)))


class FakeProvider:
    def __init__(self, key, value, ttl=0.0, error=False):
        self.key, self.label, self.ttl = key, f"rótulo {key}", ttl
        self.value, self.error, self.reads = value, error, 0

    def read(self, now, settings):
        self.reads += 1
        if self.error:
            raise RuntimeError("fonte quebrada")
        return self.value(now, settings) if callable(self.value) else self.value


def settings_with(**changes):
    data = {**CONTEXT_DEFAULTS, "sources": dict(CONTEXT_DEFAULTS["sources"])}
    sources = changes.pop("sources", {})
    data.update(changes)
    data["sources"].update(sources)
    return lambda: data


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def engine(providers, clock=None, **settings):
    return sc.SituationalContext(providers, clock=clock or Clock(), now=lambda: NOW, settings=settings_with(**settings))


def test_block_keeps_priority_order_and_fits_600_chars():
    providers = [FakeProvider(key, f"{key} " + "x" * 200) for key in SOURCE_KEYS]
    block = engine(providers).build()
    assert block.text.startswith(sc.HEADER)
    assert block.chars == len(block.text) <= 600
    lines = block.text.splitlines()[1:]
    assert all(len(line) <= 120 for line in lines)
    # Linhas longas: as de menor prioridade saem primeiro.
    assert [s["key"] for s in block.sources] == list(SOURCE_KEYS[: len(lines)])
    assert len(lines) < len(SOURCE_KEYS)


def test_cache_respects_ttl():
    clock = Clock()
    slow = FakeProvider("calendar", "Próximo compromisso hoje: 10:00 Dentista", ttl=30)
    always = FakeProvider("datetime", "Agora", ttl=0)
    ctx = engine([always, slow], clock=clock)
    ctx.build(); ctx.build()
    assert (always.reads, slow.reads) == (2, 1)
    clock.t += 31
    ctx.build()
    assert slow.reads == 2


def test_failing_provider_never_breaks_the_block():
    block = engine([FakeProvider("datetime", "Agora: sexta"), FakeProvider("window", None, error=True)]).build()
    assert "- Agora: sexta" in block.text
    assert [s["key"] for s in block.sources] == ["datetime"]


def test_disabled_source_disappears_and_master_switch_empties():
    providers = [FakeProvider("datetime", "Agora: sexta"), FakeProvider("tasks", "Tarefas pendentes: 4")]
    block = engine(providers, sources={"tasks": False}).build()
    assert "Tarefas" not in block.text and providers[1].reads == 0
    assert engine(providers, enabled=False).build().text == ""


def test_window_title_only_with_privacy_permission():
    reader = sc.make_window_reader(lambda: ("chrome.exe", "Banco - Extrato secreto"))
    provider = sc._Provider("window", 3, reader)
    private = engine([provider]).build().text
    assert "- Em primeiro plano: Chrome" in private and "Extrato" not in private
    shared = engine([provider], send_window_titles=True).build().text
    assert "Chrome — Banco - Extrato secreto" in shared


def test_pc_line_only_for_low_battery_or_high_cpu():
    battery = lambda pct, plugged: (lambda: SimpleNamespace(percent=pct, power_plugged=plugged))
    assert sc.make_pc_reader(battery(80, False), lambda: 20)(NOW, {}) is None
    assert sc.make_pc_reader(battery(18, True), lambda: 20)(NOW, {}) is None
    assert sc.make_pc_reader(battery(18, False), lambda: 92)(NOW, {}) == "PC: bateria 18% (sem carregar); CPU 92%"
    assert sc.make_pc_reader(lambda: None, lambda: 85)(NOW, {}) == "PC: CPU 85%"


def test_datetime_and_media_lines():
    assert sc.read_datetime(NOW, {}) == "Agora: sexta, 07/11/2025 08:12 (America/Sao_Paulo), manhã"
    assert sc.make_media_reader(lambda: "Spotify Premium")(NOW, {}) is None
    assert sc.make_media_reader(lambda: "Artista - Música")(NOW, {}) == "Tocando no Spotify: Artista - Música"


def test_routines_source_is_absent_without_workflow_a(monkeypatch):
    import importlib
    real = importlib.import_module

    def fake_import(name, *a, **k):
        if name == "app.services.routines":
            raise ImportError(name)
        return real(name, *a, **k)

    monkeypatch.setattr(importlib, "import_module", fake_import)
    assert sc.read_routines(NOW, {}) is None
    monkeypatch.setattr(importlib, "import_module", lambda name, *a, **k: SimpleNamespace(list_running=lambda: [{"name": "Manhã produtiva"}]))
    assert sc.read_routines(NOW, {}) == "Rotinas em andamento: Manhã produtiva"


def test_settings_validation(isolated_lote6_data):
    assert get_context_settings() == CONTEXT_DEFAULTS
    with pytest.raises(ValueError, match="desconhecido"):
        set_context_settings({"bogus": True})
    with pytest.raises(ValueError, match="Enviar títulos"):
        set_context_settings({"send_window_titles": "sim"})
    with pytest.raises(ValueError, match="Fonte de contexto desconhecida"):
        set_context_settings({"sources": {"radio": True}})
    with pytest.raises(ValueError, match="Estado do PC"):
        set_context_settings({"sources": {"pc": 1}})
    assert get_context_settings() == CONTEXT_DEFAULTS
    saved = set_context_settings({"send_window_titles": True, "sources": {"media": False}})
    assert saved["send_window_titles"] is True and saved["sources"]["media"] is False and saved["sources"]["pc"] is True


# ------------------------------------------------------------ orquestrador e loop

class CapturingLLM:
    def __init__(self):
        self.calls, self.systems = [], []

    def get_active_provider(self):
        return "gemini"

    def _api_key_for(self, _provider):
        return "fixture-key"

    def chat_with_functions_stream(self, **kwargs):
        self.calls.append("chat_with_functions_stream")
        self.systems.append(kwargs.get("system_instruction", ""))
        return "Resposta do chat."

    def ask(self, *_a, **_k):
        self.calls.append("ask")
        return "VAZIO"


@pytest.fixture
def chat(isolated_lote6_data, monkeypatch):
    import app.agent.orchestrator as module
    monkeypatch.setattr(module, "build_tutor_system", lambda *a, **k: "tutor")
    monkeypatch.setattr("app.services.stm_filters.stm_filter", SimpleNamespace(process=lambda value: value))
    monkeypatch.setattr(module, "save_session_history", lambda session, history: None)
    monkeypatch.setattr(module, "get_session_history", lambda _: [])
    monkeypatch.setattr("app.core.logger.logger", SimpleNamespace(record_request=lambda: None, info=lambda *a: None))
    threads = []
    real_thread = threading.Thread

    class RecordingThread(real_thread):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            threads.append(self)

    monkeypatch.setattr(threading, "Thread", RecordingThread)
    fake = sc.SituationalContext(
        [FakeProvider("datetime", "Agora: sexta, 07/11/2025 08:12"), FakeProvider("tasks", "Tarefas pendentes: 4")],
        now=lambda: NOW,
    )
    monkeypatch.setattr(sc, "situational_context", fake)
    agent = AgentOrchestrator.__new__(AgentOrchestrator)
    agent.llm_service = CapturingLLM()
    agent.semantic_memory = SimpleNamespace(is_available=lambda: False, search_memories=lambda *a, **k: [], add_memory=lambda *a, **k: None)
    agent.memory_store = agent.profile_memory = agent.settings = agent.vision_service = agent.browser_agent = None
    agent.productivity_service = agent.file_action_service = None
    agent.tutor_store = SimpleNamespace(get_summary_for_llm=lambda: "")
    agent.pattern_learner = SimpleNamespace(record_action=lambda *a: None)
    agent.mode_resolver = ModeResolver()
    agent._resolve_enem_context = lambda *a: None
    agent.registry = SimpleNamespace(
        tools={}, get_tool_declarations=lambda **k: [],
        allowed_tool_names=lambda **k: frozenset(),
        get_tool_metadata=lambda _: ToolMetadata(("calendar",), "observe"),
    )

    def run(text, **kwargs):
        plan = agent.handle_request(text, session_id="s1", **kwargs)
        for thread in threads:
            thread.join(timeout=5)
        return plan

    return SimpleNamespace(agent=agent, llm=agent.llm_service, run=run)


def test_chat_system_prompt_carries_the_block_with_one_model_call(chat):
    plan = chat.run("qual a capital da França")
    assert chat.llm.calls == ["chat_with_functions_stream"]
    system = chat.llm.systems[-1]
    assert "## Situação agora" in system and "- Tarefas pendentes: 4" in system
    used = plan.context["situational_context"]
    assert [s["key"] for s in used["sources"]] == ["datetime", "tasks"]
    assert used["chars"] == len(used["text"]) <= 600


def test_voice_origin_uses_the_same_block(chat):
    chat.run("que horas são", origin="voice")
    assert "## Situação agora" in chat.llm.systems[-1]


def test_disabled_context_leaves_prompt_and_meta_clean(chat):
    set_context_settings({"enabled": False})
    plan = chat.run("qual a capital da França")
    assert "Situação agora" not in chat.llm.systems[-1]
    assert "situational_context" not in (plan.context or {})


def test_hidden_detail_keeps_prompt_but_drops_meta(chat):
    set_context_settings({"show_in_chat": False})
    plan = chat.run("qual a capital da França")
    assert "## Situação agora" in chat.llm.systems[-1]
    assert "situational_context" not in (plan.context or {})


def test_tutor_mode_has_no_situational_block(chat):
    chat.run("me explica fotossíntese", mode="tutor")
    assert all("Situação agora" not in system for system in chat.llm.systems)


def test_broken_engine_never_breaks_the_turn(chat, monkeypatch):
    monkeypatch.setattr(sc, "situational_context", SimpleNamespace(build=lambda: 1 / 0))
    plan = chat.run("qual a capital da França")
    assert plan.summary == "Resposta do chat."
    assert "Situação agora" not in chat.llm.systems[-1]


def test_agent_loop_receives_the_block_in_the_observation(chat):
    captured = {}

    def run_loop(text, **kwargs):
        captured.update(kwargs["context"])
        return SimpleNamespace(success=True, pending_action_id=None, final_output="ok", steps=[], total_elapsed_sec=0.0,
                               model_calls=1, max_steps=3, max_model_calls=3, stopped_reason="finish")

    chat.agent.react_loop = SimpleNamespace(run_loop=run_loop)
    plan = chat.run("faça em etapas", mode="react")
    assert captured["session_id"] == "s1"
    assert "- Tarefas pendentes: 4" in captured["situational"]
    observation = ReActLoopEngine()._gather_observation(captured)
    assert observation.startswith("Ambiente Desktop Windows Ativo.") and "## Situação agora" in observation
    assert plan.context["situational_context"]["sources"]


def test_turn_meta_collector_is_top_level_only():
    token = turn_meta.start()
    try:
        assert turn_meta.start() is None
        turn_meta.record("a", 1)
        for i in range(5):
            turn_meta.append("b", i, limit=3)
        assert turn_meta.snapshot() == {"a": 1, "b": [0, 1, 2]}
    finally:
        turn_meta.reset(token)
    assert turn_meta.snapshot() == {}
    turn_meta.record("a", 1)  # sem coletor: ignora
    assert turn_meta.snapshot() == {}
