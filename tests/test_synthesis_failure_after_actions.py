"""Síntese que falha depois de uma ação concluída vira resposta com aviso, não falha (A3)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.agent.mode_resolver import ModeResolver
from app.agent.orchestrator import AgentOrchestrator
from app.services import personal_records as records

_CREATE = {"action": "create", "kind": "habit", "fields": {"title": "Beber água"}}


class SynthesisFailsLLM:
    def __init__(self, error: Exception, act: bool = True):
        self.error, self.act = error, act
        self.observations: list[str] = []

    def get_active_provider(self):
        return "groq"

    def _api_key_for(self, _provider):
        return "fixture-key"

    def chat_with_functions_stream(self, **kwargs):
        if self.act:
            self.observations.append(kwargs["on_function_call"]("personal_records", dict(_CREATE)))
        raise self.error

    def ask(self, *_a, **_k):
        return "VAZIO"


@pytest.fixture
def agent(isolated_lote6_data, monkeypatch):
    import app.agent.orchestrator as module
    from app.agent.tools.registry import registry
    from app.services import situational_context as sc

    monkeypatch.setattr(module, "build_tutor_system", lambda *a, **k: "tutor")
    monkeypatch.setattr("app.services.stm_filters.stm_filter", SimpleNamespace(process=lambda value: value, avoid_unsolicited_tables=lambda value, _text: value))
    monkeypatch.setattr(module, "save_session_history", lambda session, history: None)
    monkeypatch.setattr(module, "get_session_history", lambda _: [])
    monkeypatch.setattr("app.core.logger.logger", SimpleNamespace(record_request=lambda: None, record_tool_execution=lambda *a: None, info=lambda *a: None))
    monkeypatch.setattr(sc, "situational_context", sc.SituationalContext([]))
    obj = AgentOrchestrator.__new__(AgentOrchestrator)
    obj.semantic_memory = SimpleNamespace(is_available=lambda: False, search_memories=lambda *a, **k: [], add_memory=lambda *a, **k: None)
    obj.memory_store = obj.profile_memory = obj.settings = obj.vision_service = obj.browser_agent = None
    obj.productivity_service = obj.file_action_service = None
    obj.tutor_store = SimpleNamespace(get_summary_for_llm=lambda: "")
    obj.pattern_learner = SimpleNamespace(record_action=lambda *a: None)
    obj.mode_resolver = ModeResolver()
    obj._resolve_enem_context = lambda *a: None
    obj._remember_preferences = lambda *a: None
    obj.registry = SimpleNamespace(
        tools={"personal_records": registry.get_tool("personal_records")},
        get_tool_declarations=lambda **k: [],
        allowed_tool_names=lambda **k: frozenset({"personal_records"}),
        get_tool_metadata=registry.get_tool_metadata,
        execute_tool=registry.execute_tool,
    )
    return SimpleNamespace(obj=obj, store=isolated_lote6_data.store)


def test_encoding_error_after_habit_creation_keeps_receipt_and_warns(agent):
    llm = SynthesisFailsLLM(UnicodeEncodeError("charmap", "\u2192", 0, 1, "x"))
    agent.obj.llm_service = llm
    plan = agent.obj.handle_request("Crie o hábito beber água", session_id="s1")

    assert plan.intent == "tool_execution", plan.summary
    assert "Beber água" in plan.summary
    assert "Erro ao processar" not in plan.summary
    assert len([row for row in records.records("habit") if row.get("title") == "Beber água"]) == 1
    details = agent.store.run_details(plan.context["run_id"])
    assert details["run"]["status"] != "failed"
    warnings = [event for event in details["events"] if event["kind"] == "warning"]
    assert warnings and "UnicodeEncodeError" in warnings[0]["summary"]


def test_failure_without_successful_action_is_still_an_error(agent):
    agent.obj.llm_service = SynthesisFailsLLM(RuntimeError("falha de rede sk-segredo"), act=False)
    plan = agent.obj.handle_request("Crie o hábito beber água", session_id="s1")

    assert plan.intent == "error"
    assert "sk-segredo" not in plan.summary
    assert agent.store.run_details(plan.context["run_id"])["run"]["status"] == "failed"
