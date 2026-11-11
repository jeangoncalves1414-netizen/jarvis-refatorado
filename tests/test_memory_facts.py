"""Fase contexto 2: memórias com fonte, parser de slots, Kernel e gatilho do lote 7."""
import json
import threading
from types import SimpleNamespace

import pytest

from app.agent.mode_resolver import ModeResolver
from app.agent.orchestrator import AgentOrchestrator
from app.agent.tools.catalog import TOOL_CATALOG
from app.core.actions import ToolMetadata
from app.services import memory_kernel, memory_slots
from app.storage import memory_facts


# ------------------------------------------------------------------ parser

@pytest.mark.parametrize("text, expected", [
    ("de manhã prefiro a playlist Foco", ("music", "Foco", "manha")),
    ("Lembra que eu prefiro ouvir Lo-fi Beats à noite", ("music", "Lo-fi Beats", "noite")),
    ("prefiro a playlist Treino Pesado de manhã, valeu", ("music", "Treino Pesado", "manha")),
    ("Eu moro em São José dos Campos", ("city", "São José dos Campos", None)),
    ("minha cidade é Belo Horizonte.", ("city", "Belo Horizonte", None)),
    ("prefiro usar o navegador Firefox", ("app.navegador", "Firefox", None)),
    ("meu editor favorito é o VS Code", ("app.editor", "VS Code", None)),
    ("Meu nome é Jean", ("name", "Jean", None)),
    ("me chamo Maria Clara.", ("name", "Maria Clara", None)),
    ("pode me chamar de Jota", ("name", "Jota", None)),
])
def test_parser_finds_slots(text, expected):
    assert memory_slots.parse(text) == expected


@pytest.mark.parametrize("text", ["eu prefiro respostas curtas", "qual a capital da França", "lembra que tenho prova na sexta", ""])
def test_parser_without_match(text):
    assert memory_slots.parse(text) is None


# ------------------------------------------------------------------ store

def test_save_duplicate_update_delete_with_tombstone(isolated_lote6_data):
    source = {"session_id": "abc", "origin": "voz", "kind": "gatilho"}
    fact = memory_facts.save("De manhã prefiro a playlist Foco", source=source)
    assert fact["id"].startswith("mem_") and (fact["slot"], fact["value"], fact["when"]) == ("music", "Foco", "manha")
    assert fact["source"]["origin"] == "voz" and fact["source"]["session_id"] == "abc" and fact["deleted_at"] is None
    again = memory_facts.save("de manha prefiro a playlist foco", source=source)
    assert again["id"] == fact["id"] and again["updated_at"] >= fact["updated_at"]
    assert len(memory_facts.list_facts()) == 1

    edited = memory_facts.update(fact["id"], "eu moro em Recife")
    assert (edited["slot"], edited["value"], edited["when"]) == ("city", "Recife", None)
    removed = memory_facts.delete(fact["id"])
    assert removed["deleted_at"]
    assert memory_facts.list_facts() == []
    assert memory_facts.list_facts(include_deleted=True)[0]["id"] == fact["id"]
    with pytest.raises(ValueError, match="não encontrada"):
        memory_facts.update(fact["id"], "outra")
    with pytest.raises(ValueError, match="300"):
        memory_facts.save("x" * 301)
    with pytest.raises(ValueError, match="Escreva"):
        memory_facts.save("   ")
    raw = json.loads(memory_facts.facts_path().read_text(encoding="utf-8"))
    assert raw["version"] == 1 and str(isolated_lote6_data.root) in str(memory_facts.facts_path())


def test_relevant_orders_by_overlap_and_subject(isolated_lote6_data):
    memory_facts.save("prefiro a playlist Foco de manhã")
    memory_facts.save("eu moro em Curitiba")
    memory_facts.save("gosto de café sem açúcar")
    assert memory_facts.relevant("toca uma música aí")[0]["slot"] == "music"
    assert memory_facts.relevant("como está o clima hoje")[0]["value"] == "Curitiba"
    assert memory_facts.relevant("faz um café pra mim")[0]["text"].startswith("gosto de café")
    assert memory_facts.relevant("qual a capital da França") == []


def test_essential_orders_pinned_first_and_caps_size(isolated_lote6_data):
    common = memory_facts.save("gosto de café sem açúcar")
    city = memory_facts.save("eu moro em Curitiba")
    name = memory_facts.save("Meu nome é Jean")
    pinned = memory_facts.save("A usuária tem dois gatos", pinned=True)
    assert (common["importance"], city["importance"], name["importance"], pinned["importance"]) == (0.5, 0.9, 0.9, 1.0)
    assert name["slot"] == "name" and pinned["pinned"] is True and common["pinned"] is False
    ids = [fact["id"] for fact in memory_facts.essential()]
    assert ids[0] == pinned["id"] and set(ids) == {pinned["id"], name["id"], city["id"]}
    assert memory_facts.relevant("qual é o meu nome?")[0]["id"] == name["id"]
    for index in range(6):
        memory_facts.save(f"Fato central número {index} " + "x" * 90, pinned=True)
    chosen = memory_facts.essential(500)
    assert len("\n".join(fact["text"] for fact in chosen)) <= 500 and len(chosen) < 9


def test_duplicate_save_keeps_id_and_updates_pinned(isolated_lote6_data):
    fact = memory_facts.save("gosto de café sem açúcar")
    again = memory_facts.save("Gosto de cafe sem acucar", pinned=True)
    assert again["id"] == fact["id"] and again["pinned"] is True and again["importance"] == 1.0
    untouched = memory_facts.save("gosto de café sem açúcar")
    assert untouched["pinned"] is True and len(memory_facts.list_facts()) == 1


# ------------------------------------------------------------------ Kernel

def test_save_via_kernel_creates_low_action_receipt(isolated_lote6_data):
    result = memory_kernel.save_via_kernel("de manhã prefiro a playlist Foco", kind="manual", session_id="s9", origin="window")
    assert result["ok"] and result["fact"]["source"]["origin"] == "painel"
    action = result["action"]
    assert action["tool_name"] == "memory_tool" and action["risk"] == "low" and action["status"] == "succeeded"
    stored = isolated_lote6_data.store.list()
    assert [a.tool_name for a in stored] == ["memory_tool"]
    run = isolated_lote6_data.store.run_details(stored[0].run_id)["run"]
    assert run["origin"] == "window"
    assert memory_kernel.delete_via_kernel(result["fact"]["id"], origin="window")["ok"]
    failed = memory_kernel.update_via_kernel("mem_nao_existe", "x", origin="window")
    assert failed["ok"] is False and "não encontrada" in failed["error"]


def test_memory_tool_risks():
    metadata = TOOL_CATALOG["memory_tool"]
    assert metadata.risk_for({"operation": "list"}) == "observe"
    assert {metadata.risk_for({"operation": op}) for op in ("save", "update", "delete")} == {"low"}
    assert "origem" in metadata.effect_for({"operation": "save"})


# ------------------------------------------------------------------ gatilho e prompt

class CountingLLM:
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
    from app.services import situational_context as sc
    monkeypatch.setattr(module, "build_tutor_system", lambda *a, **k: "tutor")
    monkeypatch.setattr("app.services.stm_filters.stm_filter", SimpleNamespace(process=lambda value: value))
    monkeypatch.setattr(module, "save_session_history", lambda session, history: None)
    monkeypatch.setattr(module, "get_session_history", lambda _: [])
    monkeypatch.setattr("app.core.logger.logger", SimpleNamespace(record_request=lambda: None, info=lambda *a: None))
    monkeypatch.setattr(sc, "situational_context", sc.SituationalContext([]))
    threads = []
    real_thread = threading.Thread

    class RecordingThread(real_thread):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            threads.append(self)

    monkeypatch.setattr(threading, "Thread", RecordingThread)
    agent = AgentOrchestrator.__new__(AgentOrchestrator)
    agent.llm_service = CountingLLM()
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

    return SimpleNamespace(agent=agent, llm=agent.llm_service, run=run, store=isolated_lote6_data.store)


def test_trigger_with_slot_saves_fact_with_source(chat):
    chat.run("lembra que de manhã prefiro a playlist Foco", origin="voice")
    facts = memory_facts.list_facts()
    assert len(facts) == 1
    fact = facts[0]
    assert (fact["slot"], fact["value"]) == ("music", "Foco")
    assert fact["source"]["kind"] == "gatilho" and fact["source"]["origin"] == "voz" and fact["source"]["session_id"] == "s1"
    assert fact["source"]["run_id"].startswith("run_")
    assert any(a.tool_name == "memory_tool" and a.status == "succeeded" for a in chat.store.list())


def test_common_message_saves_nothing_and_costs_one_call(chat):
    chat.run("qual a capital da França")
    assert memory_facts.list_facts(include_deleted=True) == []
    assert chat.llm.calls == ["chat_with_functions_stream"]
    assert "Preferências salvas" not in chat.llm.systems[-1]


def test_trigger_without_slot_saves_no_fact(chat):
    chat.run("eu prefiro respostas curtas")
    assert memory_facts.list_facts() == []


def test_system_prompt_lists_relevant_facts_only(chat):
    memory_facts.save("prefiro a playlist Foco de manhã")
    chat.run("toca uma música")
    system = chat.llm.systems[-1]
    assert "## Preferências salvas (com fonte)" in system
    assert "- prefiro a playlist Foco de manhã (memória de " in system
    from app.agent.turn_context import build_turn_sections, MEMORY_HEADER
    section = build_turn_sections("toca uma música").memories
    assert section in system
    assert len(section.removeprefix(MEMORY_HEADER).strip()) <= 300
    chat.run("qual a capital da França")
    assert "Preferências salvas" not in chat.llm.systems[-1]


def test_essential_profile_every_turn_without_raw_user_profile(chat, monkeypatch):
    from app.agent.turn_context import PROFILE_HEADER
    from app.services.memory_vault import memory_vault
    monkeypatch.setattr(memory_vault, "get_user_profile", lambda: "Nome: Usuário")
    memory_facts.save("O nome da usuária é Jean", pinned=True)
    chat.run("oi")
    system = chat.llm.systems[-1]
    assert "## Perfil essencial do usuário" in system and "- O nome da usuária é Jean" in system
    section = system.split(PROFILE_HEADER, 1)[1].split("\n\n", 1)[0]
    assert len(section) <= 500
    chat.run("Resuma o início deste chat")
    assert "Perfil essencial" not in chat.llm.systems[-1]
    assert all("Nome: Usuário" not in prompt for prompt in chat.llm.systems)


def test_commands_never_create_preferences_or_trigger_memory_extraction(chat, tmp_path):
    from app.storage.memory_store import MemoryStore
    chat.agent.memory_store = MemoryStore(str(tmp_path / "memory.json"))
    for text in ("Olá quero que você abra", "quero que você abra Spotify"):
        chat.agent._remember_preferences(text, text.lower(), session_id="s1")
    assert chat.agent.memory_store.get_preferences() == []
    assert chat.llm.calls == []
    assert memory_facts.list_facts() == []


def test_global_recall_requires_intent_and_is_disclosed(chat, monkeypatch, tmp_path):
    from app.storage.memory_store import MemoryStore
    from app.services.memory_vault import memory_vault
    calls = []
    chat.agent.semantic_memory = SimpleNamespace(is_available=lambda: True,
        search_memories=lambda collection, *a, **k: calls.append(collection) or [{"text": "Mensagem de outro chat", "metadata": {}}])
    chat.agent.profile_memory = SimpleNamespace(context=lambda *a, **k: calls.append("profile") or [{"text": "Conversa privada antiga", "kind": "conversation"}])
    chat.agent.memory_store = MemoryStore(str(tmp_path / "memory.json"))
    chat.agent.memory_store.add_preference("general_preference", "Olá quero que você abra")
    chat.agent.memory_store.add_preference("general_preference", "prefiro usar Firefox")
    monkeypatch.setattr(memory_vault, "get_user_profile", lambda: "Perfil duradouro")
    memory_facts.save("prefiro usar o navegador Firefox")

    plan = chat.run("Olá, tudo bem?", profile_id="jean")
    assert not calls and "memory_lookup" not in plan.context
    assert "Olá quero que você abra" not in chat.llm.systems[-1]
    assert "Firefox" in chat.llm.systems[-1]

    plan = chat.run("Resuma o início deste chat", profile_id="jean")
    assert not calls and "memory_lookup" not in plan.context
    system = chat.llm.systems[-1]
    for foreign in ("Olá quero que você abra", "Firefox", "Perfil duradouro", "Conversa privada antiga"):
        assert foreign not in system
    assert "histórico enviado pode ser parcial" in system

    plan = chat.run("Consulte a memória sobre o projeto", profile_id="jean")
    assert calls == ["user_memory", "episodic_memory", "profile"]
    assert "Mensagem de outro chat" in chat.llm.systems[-1]
    assert "Conversa privada antiga" in chat.llm.systems[-1]
    assert len(plan.context["memory_lookup"]["items"]) == 3
