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
    section = system.split("## Preferências salvas (com fonte)")[1]
    assert len(section.strip()) <= 300
    chat.run("qual a capital da França")
    assert "Preferências salvas" not in chat.llm.systems[-1]
