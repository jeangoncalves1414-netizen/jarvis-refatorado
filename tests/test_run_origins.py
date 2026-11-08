"""Pedidos de voz, Swarm, Racing e memória em segundo plano na Central, com origem (C6)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.agent.action_gateway import run_action
from app.agent.orchestrator import _record_race_attempts
from app.agent.run_tracking import background_run, in_background, record_run_step, track_run
from app.agent.swarm import AgentSwarmManager
from app.agent.tools.base import ToolResult
from app.core.actions import pending_action_broker
from app.core.runs import RUN_ORIGINS, RunRecord, current_origin, current_run, run_origin
from app.services.llm_racing import MultiLLMRacingService
from app.storage.action_store import ActionStore


@pytest.fixture
def journal(tmp_path, monkeypatch):
    store = ActionStore(tmp_path / "origins.sqlite3")
    monkeypatch.setattr("app.storage.action_store.action_store", store)
    yield store
    for action in store.list(limit=100):
        pending_action_broker.discard(action.id)
    if store._runtime_lock:
        store._runtime_lock.close()


class _Turn:
    @track_run
    def handle_request(self, text, session_id=None, mode="general", origin=None, steps=()):
        for step in steps:
            record_run_step(step)
        return SimpleNamespace(intent="general", summary="ok", context={})


def _events(store, run_id):
    return store.run_details(run_id)["events"]


def test_origins_cover_current_and_future_triggers():
    assert set(RUN_ORIGINS) >= {"chat", "voice", "routine", "clap", "window", "mobile"}
    assert run_origin("voice") == "voice" and run_origin("desconhecida") == "chat" and run_origin(None, "system") == "system"
    # Registro antigo, sem o campo, continua legível e conta como chat.
    assert RunRecord(session_id=None, mode="general").origin == "chat"


def test_voice_turn_creates_run_with_voice_origin(journal):
    plan = _Turn().handle_request("abre o spotify", session_id="s1", origin="voice")
    run = journal.run_details(plan.context["run_id"])["run"]
    assert (run["origin"], run["source"], run["status"]) == ("voice", "conversation", "succeeded")


def test_turn_without_origin_inherits_request_origin_and_unknown_becomes_chat(journal):
    token = current_origin.set("voice")
    try:
        inherited = _Turn().handle_request("oi")
    finally:
        current_origin.reset(token)
    unknown = _Turn().handle_request("oi", origin="hacker")
    assert journal.run_details(inherited.context["run_id"])["run"]["origin"] == "voice"
    assert journal.run_details(unknown.context["run_id"])["run"]["origin"] == "chat"


def test_internal_steps_are_recorded_without_changing_status(journal):
    plan = _Turn().handle_request("oi", steps=("Especialista coder acionado.",))
    details = journal.run_details(plan.context["run_id"])
    steps = [event for event in details["events"] if event["kind"] == "step"]
    assert [event["summary"] for event in steps] == ["Especialista coder acionado."]
    assert details["run"]["status"] == "succeeded"
    record_run_step("fora de pedido")  # sem pedido aberto, não faz nada


def test_swarm_specialist_steps_go_to_current_run(journal):
    manager = AgentSwarmManager.__new__(AgentSwarmManager)
    ok = SimpleNamespace(name="coder", execute_task=lambda task, **kw: {"ok": True, "agent": "coder", "code": "x"})
    bad = SimpleNamespace(name="browser", execute_task=lambda task, **kw: {"ok": False, "error": "URL de destino não informada."})
    with background_run(mode="swarm", source="api:swarm", origin="window"):
        run_id = current_run.get()[1]
        manager._run_specialist(ok, "escreva um script")
        manager._run_specialist(bad, "navegar")
    details = journal.run_details(run_id)
    summaries = [event["summary"] for event in details["events"] if event["kind"] in ("step", "failure")]
    assert summaries == [
        "Especialista coder acionado.", "Especialista coder concluiu a tarefa.",
        "Especialista browser acionado.", "Especialista browser não concluiu: URL de destino não informada.",
    ]
    assert (details["run"]["origin"], details["run"]["source"], details["run"]["mode"]) == ("window", "api:swarm", "swarm")


def test_background_run_failure_marks_run_failed(journal):
    with pytest.raises(RuntimeError):
        with background_run(mode="swarm", source="api:swarm", origin="window"):
            run_id = current_run.get()[1]
            raise RuntimeError("falhou")
    assert journal.run_details(run_id)["run"]["status"] == "failed"


def test_racing_records_each_provider_without_response_text(journal):
    def fast(prompt):
        return "resposta completa do provedor"

    def broken(prompt):
        raise ConnectionError("sem rede")

    race = MultiLLMRacingService().race_prompt("pergunta", candidates=[("Groq", fast), ("Gemini", broken)])
    assert race["ok"] and {a["provider"] for a in race["attempts"]} == {"Groq", "Gemini"}
    plan_id = None
    with background_run(mode="general", source="conversation"):
        plan_id = current_run.get()[1]
        _record_race_attempts(race)
    summaries = [event["summary"] for event in _events(journal, plan_id) if event["kind"] in ("step", "failure")]
    assert any(text.startswith("Corrida: Groq respondeu primeiro") for text in summaries)
    assert not any("resposta completa" in text for text in summaries)
    _record_race_attempts({"ok": False, "error": "Nenhum provedor respondeu no tempo limite.", "attempts": []})


def test_background_memory_is_event_of_the_originating_run_even_after_it_ends(journal):
    plan = _Turn().handle_request("lembra que prefiro café", session_id="s1")
    run_id = plan.context["run_id"]
    in_background(lambda *a, **k: True, label="Conversa salva na memória", run_id=run_id)()
    in_background(lambda *a, **k: False, label="Conversa salva na memória", run_id=run_id)()
    kinds = [(e["kind"], e["summary"]) for e in _events(journal, run_id) if e["kind"].startswith("background")]
    assert kinds == [
        ("background", "Conversa salva na memória: concluído em segundo plano."),
        ("background_failed", "Conversa salva na memória: não foi gravado (memória indisponível)."),
    ]
    # O pedido já encerrado não muda de estado.
    assert journal.run_details(run_id)["run"]["status"] == "succeeded"


def test_background_memory_inside_a_turn_captures_the_turn(journal):
    captured = {}

    class Turn:
        @track_run
        def handle_request(self, text, session_id=None, mode="general", origin=None):
            captured["runner"] = in_background(lambda: True, label="Extração de memória da mensagem")
            captured["run_id"] = current_run.get()[1]
            return SimpleNamespace(intent="general", summary="ok", context={})

    Turn().handle_request("prefiro respostas curtas", origin="voice")
    captured["runner"]()  # como na thread: sem contexto, mas com o pedido capturado
    assert any(e["kind"] == "background" for e in _events(journal, captured["run_id"]))


def test_background_job_without_parent_opens_its_own_run(journal):
    def boom():
        raise ValueError("x")

    in_background(boom, label="Resumo diário")()
    runs = journal.run_page(limit=5)["runs"]
    assert runs[0]["mode"] == "memory" and runs[0]["source"] == "background" and runs[0]["status"] == "failed"


def test_daily_summary_is_a_system_run(journal):
    with background_run(mode="memory", source="background:daily_summary", origin="system") as job:
        job.step("Resumo diário gravado na memória.")
    run = journal.run_page(limit=1)["runs"][0]
    assert (run["origin"], run["status"], run["result_summary"]) == ("system", "succeeded", "Concluído; nenhuma ferramenta registrada.")


def test_direct_routes_default_to_window_origin_and_script_keeps_chat(journal):
    window = run_action("web_search", {"query": "a"}, source="panel:controls", user_text="x", execute=lambda a: ToolResult(True, "ok"))
    chat = run_action("web_search", {"query": "b"}, source="api:script", user_text="x", execute=lambda a: ToolResult(True, "ok"), origin="chat")
    assert journal.run_details(window.action.run_id)["run"]["origin"] == "window"
    assert journal.run_details(chat.action.run_id)["run"]["origin"] == "chat"
    assert journal.run_details(window.action.run_id)["run"]["source"] == "panel:controls"
