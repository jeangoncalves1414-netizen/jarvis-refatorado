"""Lote 7, pacote 3 (MG6, MG7): economia de tokens.

Mensagem comum custa uma chamada ao modelo; a extração de memória só roda com gatilho
(ou com a opção ligada); o loop filtra o catálogo de ferramentas pelo pedido.
"""
import threading
from types import SimpleNamespace

import pytest

from app.agent.mode_resolver import ModeResolver
from app.agent.orchestrator import AgentOrchestrator
from app.agent.tools.registry import LOOP_DATA_TOOLS, ToolRegistry
from app.core.actions import ToolMetadata
from app.storage import runtime_settings


class CountingLLM:
    """Conta toda chamada ao modelo, venha da resposta principal ou da extração em segundo plano."""

    def __init__(self, extraction_reply="VAZIO"):
        self.calls = []
        self.extraction_reply = extraction_reply

    def get_active_provider(self):
        return "gemini"

    def _api_key_for(self, _provider):
        return "fixture-key"

    def chat_with_functions_stream(self, **_kwargs):
        self.calls.append("chat_with_functions_stream")
        return "Resposta do chat."

    def ask(self, prompt, *_a, **_k):
        self.calls.append("ask")
        return self.extraction_reply

    def generate(self, *_a, **_k):
        self.calls.append("generate")
        return SimpleNamespace(text="x")


class FakeMemory:
    def __init__(self):
        self.saved = []

    def is_available(self):
        return False

    def search_memories(self, *_a, **_k):
        return []

    def add_memory(self, collection, text, **_k):
        self.saved.append((collection, text))


@pytest.fixture
def economy(isolated_lote6_data, monkeypatch):
    import app.agent.orchestrator as module
    monkeypatch.setattr(module, "build_tutor_system", lambda *a, **k: "test")
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
    agent = AgentOrchestrator.__new__(AgentOrchestrator)
    agent.llm_service = CountingLLM()
    agent.semantic_memory = FakeMemory()
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

    def run(text):
        plan = agent.handle_request(text, session_id="s1")
        for thread in threads:
            thread.join(timeout=5)
        return plan

    return SimpleNamespace(agent=agent, llm=agent.llm_service, memory=agent.semantic_memory, run=run)


@pytest.mark.parametrize("text", [
    "me conta uma curiosidade sobre o espaço",
    "qual a capital da França",
    "obrigado, ficou ótimo",
])
def test_simple_message_costs_exactly_one_model_call(economy, text):
    plan = economy.run(text)
    assert plan.summary == "Resposta do chat."
    assert economy.llm.calls == ["chat_with_functions_stream"]
    assert economy.memory.saved == []


@pytest.mark.parametrize("text", [
    "meu nome é Maria e eu moro em Recife",
    "eu prefiro respostas curtas",
    "lembra que eu tenho prova na sexta",
    "Eu moro em Salvador",
])
def test_trigger_message_adds_one_background_extraction(economy, text):
    economy.llm.extraction_reply = "- O usuário mora em Recife"
    economy.run(text)
    assert sorted(economy.llm.calls) == ["ask", "chat_with_functions_stream"]
    assert economy.memory.saved == [("user_memory", "O usuário mora em Recife")]


def test_extract_every_message_option_restores_the_old_behavior(economy):
    assert runtime_settings.get_agent_loop_settings()["extract_memory_always"] is False
    runtime_settings.set_agent_loop_settings({"extract_memory_always": True})
    economy.run("me conta uma curiosidade sobre o espaço")
    assert sorted(economy.llm.calls) == ["ask", "chat_with_functions_stream"]


def test_extract_option_validation_and_default(isolated_lote6_data):
    with pytest.raises(ValueError, match="extração de memórias"):
        runtime_settings.set_agent_loop_settings({"extract_memory_always": "sim"})
    assert runtime_settings.get_agent_loop_settings()["extract_memory_always"] is False


@pytest.fixture(scope="module")
def registry(tmp_path_factory):
    return ToolRegistry(base_folder=str(tmp_path_factory.mktemp("tools")))


@pytest.mark.parametrize("provider", ["gemini", "groq", "oxyy", "marker"])
def test_loop_catalog_is_filtered_for_every_provider(registry, provider):
    full = registry.allowed_tool_names(mode="general", provider=provider, user_text="adiciona ler e agenda dentista")
    narrow = registry.allowed_tool_names(mode="general", provider=provider, user_text="adiciona ler e agenda dentista", narrow=True)
    assert narrow < registry.allowed_tool_names(mode="general", provider="gemini")
    assert LOOP_DATA_TOOLS <= narrow
    assert not {"kasa_control", "telegram_bot", "mobile_adb", "hacker_mode", "wallpaper_engine"} & narrow
    assert len(narrow) <= 14 and (provider != "gemini" or len(narrow) < len(full))


def test_loop_catalog_follows_the_words_of_the_request(registry):
    names = lambda text: registry.allowed_tool_names(mode="general", provider="gemini", user_text=text, narrow=True)
    assert {"web_search", "spotify", "finance_tool"} <= names("pesquisa receita de bolo, toca música e anota que gastei 20 no mercado")
    plain = names("abre o painel, adiciona ler nos hábitos, depois bebi 2L de água")
    assert not {"web_search", "spotify", "finance_tool", "whatsapp"} & plain
    assert {"habit_tool", "task_tool", "lifeos_tool", "calendar", "vault_save_note", "open_window", "open_screen"} <= plain
    # Sem o parâmetro, o provedor Gemini continua recebendo o catálogo completo do modo.
    assert len(registry.allowed_tool_names(mode="general", provider="gemini", user_text="oi")) > len(plain) + 10
