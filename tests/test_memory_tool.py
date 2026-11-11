"""Ferramenta ``memory``: ciclo save/search/list/forget pelo Action Kernel, riscos e oferta ao modelo."""
from types import SimpleNamespace

import pytest

from app.agent.action_executor import ActionExecutor
from app.agent.tool_guardrails import ToolCallGuardrailController
from app.agent.tools.catalog import TOOL_CATALOG, metadata_for
from app.agent.tools.memory_tool import MemoryTool
from app.agent.tools.registry import ToolRegistry
from app.core.actions import pending_action_broker
from app.core.runs import current_run
from app.storage import memory_facts


class FakeSemantic:
    def __init__(self):
        self.added, self.deleted, self.searched = [], [], []

    def is_available(self):
        return True

    def add_memory(self, collection, text, metadata=None, importance=1.0):
        self.added.append((collection, text, dict(metadata or {}), importance))
        return True

    def search_memories(self, collection, query, n_results=5, **kwargs):
        self.searched.append((collection, query, kwargs))
        return [{"text": text, "metadata": meta, "distance": 0.2} for _c, text, meta, _i in self.added]

    def delete_where(self, collection, where):
        self.deleted.append((collection, where))
        return 1


@pytest.fixture(scope="module")
def registry(tmp_path_factory):
    return ToolRegistry(base_folder=str(tmp_path_factory.mktemp("tools")))


def _turn(store, context):
    run = store.create_run(session_id="s1", mode="chat")
    tool = MemoryTool()
    results = []

    def execute(_name, args, _user):
        result = tool.execute(args, context)
        results.append(result)
        return result

    token = current_run.set((store, run.id))
    try:
        executor = ActionExecutor(
            frozenset({"memory"}), ToolCallGuardrailController(), execute,
            metadata_for=lambda name: metadata_for(name, tool.metadata),
        )
    finally:
        current_run.reset(token)

    def call(args, text="pedido"):
        token = current_run.set((store, run.id))
        try:
            return executor.execute("memory", args, text)
        finally:
            current_run.reset(token)

    call.results = results
    return run, executor, call


def test_save_search_list_forget_cycle_with_single_receipt(isolated_lote6_data):
    semantic = FakeSemantic()
    store = isolated_lote6_data.store
    run, executor, call = _turn(store, {"session_id": "s1", "semantic_memory": semantic})

    reply = call({"action": "save", "text": "O nome da usuária é Jean", "pinned": True})
    assert "Memória salva" in reply
    actions = store.list()
    assert [a.tool_name for a in actions] == ["memory"] and actions[0].status == "succeeded"
    fact = memory_facts.list_facts()[0]
    assert fact["pinned"] is True and fact["source"]["run_id"] == run.id and fact["source"]["session_id"] == "s1"
    assert semantic.added[0][0] == "user_memory" and semantic.added[0][2]["fact_id"] == fact["id"]

    assert "encontrada" in call({"action": "search", "query": "qual é o meu nome?"})
    observation = call.results[-1].model_observation()
    assert fact["id"] in observation and observation.count("O nome da usuária é Jean") == 1
    assert semantic.searched[0][2]["max_distance"] == pytest.approx(0.45)
    call({"action": "list"})
    assert fact["id"] in call.results[-1].model_observation()

    proposal = call({"action": "forget", "id": fact["id"]})
    pending = executor.last_action
    assert pending.status == "awaiting_confirmation" and "exige confirmação" in proposal
    assert memory_facts.list_facts()  # nada apagado antes da aprovação
    store.transition(pending.id, "authorized")
    callback = pending_action_broker.take(pending.id)
    assert callback is not None and "Memória apagada" in callback()
    assert memory_facts.list_facts() == []
    assert semantic.deleted == [("user_memory", {"fact_id": fact["id"]})]
    assert {a.tool_name for a in store.list()} == {"memory"}


def test_works_without_semantic_memory_and_validates(isolated_lote6_data):
    tool = MemoryTool()
    assert tool.execute({"action": "save", "text": "A usuária gosta de pizza"}).ok
    result = tool.execute({"action": "search", "query": "pizza"})
    assert result.ok and result.data["results"][0]["text"] == "A usuária gosta de pizza"
    assert "Dados da ferramenta" in result.model_observation()
    assert not tool.execute({"action": "save"}).ok
    assert not tool.execute({"action": "apagar"}).ok
    tool.execute({"action": "save", "text": "A usuária gosta de pizza de calabresa"})
    ambiguous = tool.execute({"action": "forget", "query": "pizza"})
    assert not ambiguous.ok and "id" in ambiguous.message
    assert tool.execute({"action": "forget", "query": "a usuaria gosta de pizza"}).ok
    assert [f["text"] for f in memory_facts.list_facts()] == ["A usuária gosta de pizza de calabresa"]


def test_risks_and_description():
    metadata = TOOL_CATALOG["memory"]
    assert {metadata.risk_for({"action": op}) for op in ("search", "list")} == {"observe"}
    assert metadata.risk_for({"action": "save"}) == "low"
    assert metadata.risk_for({"action": "forget"}) == "high"
    assert len(MemoryTool().description) <= 250


def test_memory_is_offered_on_groq_and_in_the_loop(registry):
    text = "O que você sabe sobre mim?"
    assert "memory" in registry.allowed_tool_names(mode="general", provider="groq", user_text=text)
    assert "memory" in registry.allowed_tool_names(mode="general", provider="gemini", user_text=text, narrow=True)
    assert "vault_update_profile" not in registry.allowed_tool_names(mode="general", provider="gemini", user_text=text)
    declared = {d["name"] for d in registry.get_tool_declarations(mode="general", provider="groq", user_text=text)}
    assert "memory" in declared
