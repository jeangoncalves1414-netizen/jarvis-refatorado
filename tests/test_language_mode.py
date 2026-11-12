"""Modo language: prompt CEFR próprio e só as ferramentas de idiomas."""
import threading
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

import pytest

from app.agent.mode_resolver import ModeResolver
from app.agent.orchestrator import AgentOrchestrator
from app.agent.tools.registry import LANGUAGE_TOOL_NAMES, ToolRegistry
from app.core.actions import ToolMetadata
from app.services import situational_context as sc
from app.storage.language_store import LanguageStore
from app.storage.tutor_store import TutorStore


@pytest.fixture(scope="module")
def registry(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("language_mode")
    return ToolRegistry(
        base_folder=str(tmp),
        tutor_store=TutorStore(str(tmp / "t")),
        language_store=LanguageStore(str(tmp / "l")),
    )


@pytest.mark.parametrize("provider", ["gemini", "groq"])
def test_language_mode_gets_only_language_tools(registry, provider):
    allowed = registry.allowed_tool_names(mode="language", provider=provider, user_text="oi")
    declared = {item["name"] for item in registry.get_tool_declarations(mode="language", provider=provider, user_text="oi")}
    assert allowed == set(LANGUAGE_TOOL_NAMES) == declared
    assert not any(name.startswith("mcp_") or name.startswith("whiteboard_") for name in allowed)
    assert "system_control" not in allowed


def test_tutor_mode_has_no_language_tools(registry):
    tutor = registry.allowed_tool_names(mode="tutor", provider="gemini", user_text="oi")
    assert tutor and not any(name.startswith("language_") for name in tutor)


class CapturingLLM:
    def __init__(self):
        self.systems = []

    def get_active_provider(self):
        return "gemini"

    def _api_key_for(self, _provider):
        return "fixture-key"

    def chat_with_functions_stream(self, **kwargs):
        self.systems.append(kwargs.get("system_instruction", ""))
        return "Hola."

    def ask(self, *_a, **_k):
        return "VAZIO"


class FakeProvider:
    key, label, ttl = "tasks", "Tarefas", 0.0

    def read(self, _now, _settings):
        return "Tarefas pendentes: 4"


def test_language_chat_uses_the_cefr_prompt(isolated_lote6_data, monkeypatch):
    import app.agent.orchestrator as module
    monkeypatch.setattr("app.services.stm_filters.stm_filter", SimpleNamespace(process=lambda value: value))
    monkeypatch.setattr(module, "save_session_history", lambda session, history: None)
    monkeypatch.setattr(module, "get_session_history", lambda _: [])
    monkeypatch.setattr("app.core.logger.logger", SimpleNamespace(record_request=lambda: None, info=lambda *a: None))
    monkeypatch.setattr(sc, "situational_context", sc.SituationalContext(
        [FakeProvider()], now=lambda: datetime(2025, 11, 7, 8, 12, tzinfo=timezone(timedelta(hours=-3)))))
    threads = []
    real_thread = threading.Thread

    class RecordingThread(real_thread):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            threads.append(self)

    monkeypatch.setattr(threading, "Thread", RecordingThread)
    asked = []
    agent = AgentOrchestrator.__new__(AgentOrchestrator)
    agent.llm_service = CapturingLLM()
    agent.semantic_memory = SimpleNamespace(is_available=lambda: False, search_memories=lambda *a, **k: [], add_memory=lambda *a, **k: None)
    agent.memory_store = agent.profile_memory = agent.settings = agent.vision_service = agent.browser_agent = None
    agent.productivity_service = agent.file_action_service = None
    agent.tutor_store = SimpleNamespace(get_summary_for_llm=lambda: "")
    agent.language_store = SimpleNamespace(
        get_progress=lambda: {"target_language": "es", "cefr_level": "B1", "weak_phonemes": ["r"]},
        get_summary_for_llm=lambda: "Vocabulário: 3",
    )
    agent.pattern_learner = SimpleNamespace(record_action=lambda *a: None)
    agent.mode_resolver = ModeResolver()
    agent._resolve_enem_context = lambda *a: None
    agent.registry = SimpleNamespace(
        tools={},
        get_tool_declarations=lambda **k: asked.append(k) or [],
        allowed_tool_names=lambda **k: asked.append(k) or frozenset(),
        get_tool_metadata=lambda _: ToolMetadata(("language",), "observe"),
    )

    agent.handle_request("hola", session_id="s1", mode="language")
    for thread in threads:
        thread.join(timeout=5)

    system = agent.llm_service.systems[-1]
    assert "LANGUAGE TUTOR" in system
    assert "B1" in system and "es" in system and "Vocabulário: 3" in system
    assert "Situação agora" not in system
    assert asked and all(call.get("mode") == "language" for call in asked)
