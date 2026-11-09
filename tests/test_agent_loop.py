"""Loop agêntico (lote 6, Fase 2): lote, orçamento, verificação, retomada após aprovação."""
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from app.agent.orchestrator import AgentOrchestrator, AgentPlan
from app.agent.react_loop import ReActLoopEngine, parse_plan
from app.agent.tools.base import ToolResult
from app.core import loop_checkpoints, ui_events
from app.core.actions import ToolMetadata, pending_action_broker
from app.storage import runtime_settings
from app.ui.panel.api import actions, runs

MULTI = "adiciona ler e meditar nos hábitos e depois agenda dentista amanhã às 15h"


class FakeRegistry:
    """Registro falso: grava as chamadas; ``high`` pede aprovação; ``responses`` define resultados."""

    def __init__(self, names=("timer", "calendar", "habit_tool"), high=()):
        self.tools = {name: SimpleNamespace(description=f"Ferramenta {name}", parameters={"type": "object", "properties": {"action": {"type": "string"}}}) for name in names}
        self.high = set(high)
        self.calls = []
        self.responses = {}

    def allowed_tool_names(self, **_kwargs):
        return frozenset(self.tools)

    def get_tool_metadata(self, name):
        if name in self.high:
            return ToolMetadata((name,), "high", requires_confirmation=True)
        return ToolMetadata((name,), "observe")

    def execute_tool(self, name, args, **_kwargs):
        self.calls.append((name, args))
        handler = self.responses.get((name, args.get("action")))
        return handler(args) if handler else ToolResult(True, f"{name} ok")


@pytest.fixture
def env(isolated_lote6_data, monkeypatch):
    import app.agent.orchestrator as module
    store = isolated_lote6_data.store
    monkeypatch.setattr(actions, "action_store", store)
    monkeypatch.setattr(module, "build_tutor_system", lambda *a, **k: "test")
    monkeypatch.setattr("app.services.stm_filters.stm_filter", SimpleNamespace(process=lambda value: value))
    saved = []
    monkeypatch.setattr(module, "save_session_history", lambda session, history: saved.append((session, history)))
    monkeypatch.setattr(module, "get_session_history", lambda _: [])
    monkeypatch.setattr("app.core.logger.logger", SimpleNamespace(record_request=lambda: None, info=lambda *a: None))
    monkeypatch.setattr(loop_checkpoints, "resume_runner", lambda checkpoint, status: checkpoint.resume(status))
    loop_checkpoints.loop_checkpoints.clear()
    agent = AgentOrchestrator.__new__(AgentOrchestrator)
    agent.llm_service = SimpleNamespace(get_active_provider=lambda: "gemini", _api_key_for=lambda _: "fixture-key")
    agent.profile_memory = agent.settings = agent.vision_service = agent.browser_agent = None
    agent._remember_preferences = lambda *a: None
    agent._resolve_enem_context = lambda *a: None
    agent.productivity_service = agent.file_action_service = None
    agent.registry = FakeRegistry()
    events = []
    unsubscribe = ui_events.subscribe(events.append)
    yield SimpleNamespace(agent=agent, store=store, saved=saved, events=events)
    unsubscribe()
    for action in store.list(limit=200):
        pending_action_broker.discard(action.id)
    loop_checkpoints.loop_checkpoints.clear()


def script(env, replies):
    prompts = []
    sequence = iter(replies)

    def ask(prompt):
        prompts.append(prompt)
        return next(sequence)
    env.agent.react_loop = ReActLoopEngine(SimpleNamespace(ask=ask), env.agent.registry)
    return prompts


def detail(env, plan):
    return env.store.run_details(plan.context["run_id"])


def approve(action_id):
    return actions.handle_actions_post(f"/api/actions/{action_id}/approve", b"{}", None)


BATCH3 = 'ACOES: [{"ferramenta": "timer", "args": {"n": 1}}, {"ferramenta": "calendar", "args": {"n": 2}}, {"ferramenta": "timer", "args": {"n": 3}}]'


def test_batch_of_three_actions_costs_two_model_calls_and_one_run(env):
    prompts = script(env, [BATCH3, "FINISH: Tudo pronto."])
    plan = env.agent.handle_request(MULTI, session_id="s1")
    assert plan.intent == "agent_loop" and plan.summary == "Tudo pronto."
    assert len(prompts) == 2 and plan.context["model_calls"] == 2
    assert [args["n"] for _, args in env.agent.registry.calls] == [1, 2, 3]
    request = detail(env, plan)
    assert [a["tool_name"] for a in request["actions"]] == ["timer", "calendar", "timer"]
    assert request["run"]["status"] == "succeeded"
    assert len(env.store.run_page(include_reads=True)["runs"]) == 1
    # O prompt é compacto: só as ferramentas do turno, com descrição e esquema reduzido.
    assert '"nome": "timer"' in prompts[0] and "ACOES:" in prompts[0] and "create_many" in prompts[0]


def test_model_call_limit_stops_without_extra_call_and_answers_by_rule(env):
    runtime_settings.set_agent_loop_settings({"max_model_calls": 2})
    one = 'ACOES: [{"ferramenta": "timer", "args": {"n": 1}}]'
    prompts = script(env, [one, one, "FINISH: nunca chega"])
    plan = env.agent.handle_request(MULTI, session_id="s1")
    assert len(prompts) == 2
    assert plan.context["stopped_reason"] == "limit_calls"
    assert plan.summary.startswith("Fiz 2 de 2 etapa(s)") and "Parei no limite de 2 chamada(s) ao modelo." in plan.summary
    assert detail(env, plan)["run"]["status"] == "succeeded"


def test_step_limit_stops_the_batch(env):
    runtime_settings.set_agent_loop_settings({"max_steps": 2})
    prompts = script(env, [BATCH3, "FINISH: nunca chega"])
    plan = env.agent.handle_request(MULTI, session_id="s1")
    assert len(prompts) == 1 and len(env.agent.registry.calls) == 2
    assert plan.context["stopped_reason"] == "limit_steps"
    assert "Fiz 2 de 3 etapa(s)" in plan.summary and "Parei no limite de 2 etapa(s)." in plan.summary


@pytest.mark.parametrize("forgets", [False, True])
def test_verification_reads_in_same_run_and_detects_divergence(env, forgets):
    registry = env.agent.registry
    registry.responses[("habit_tool", "create_many")] = lambda args: ToolResult(True, "2 hábitos criados", data={"habits": [{"name": "Ler"}, {"name": "Meditar"}], "habit_ids": ["h1", "h2"]})
    listed = [] if forgets else [{"id": "h1", "name": "Ler"}, {"id": "h2", "name": "Meditar"}]
    registry.responses[("habit_tool", "list")] = lambda args: ToolResult(True, "lista", data={"habits": listed})
    prompts = script(env, ['ACOES: [{"ferramenta": "habit_tool", "args": {"action": "create_many", "habits": [{"name": "Ler"}, {"name": "Meditar"}]}}]', "FINISH: Criei Ler e Meditar."])
    plan = env.agent.handle_request(MULTI, session_id="s1")
    request = detail(env, plan)
    assert [(a["tool_name"], a["risk"]) for a in request["actions"]] == [("habit_tool", "observe"), ("habit_tool", "observe")]
    assert registry.calls[1] == ("habit_tool", {"action": "list"})
    assert len(prompts) == 2
    if forgets:
        assert "Ler, Meditar não apareceu na leitura de hábitos" in prompts[1]
        assert "Atenção:" in plan.summary
    else:
        assert "SUCESSO" in prompts[1] and "Atenção" not in plan.summary


def test_verification_with_real_tools_uses_isolated_data(env):
    from app.agent.tools.registry import ToolRegistry
    from app.agent.tools.lifeos_tool import LifeOSTool
    registry = ToolRegistry.__new__(ToolRegistry)
    registry.tools = {"lifeos_tool": LifeOSTool()}
    env.agent.registry = registry
    prompts = script(env, ['ACOES: [{"ferramenta": "lifeos_tool", "args": {"action": "set_water", "total_ml": 3000}}]', "FINISH: Registrei 3 L."])
    plan = env.agent.handle_request("coloca que bebi 3 litros de água hoje e depois confere se ficou certo", session_id="s1")
    request = detail(env, plan)
    assert [a["tool_name"] for a in request["actions"]] == ["lifeos_tool", "lifeos_tool"]
    assert request["actions"][1]["risk"] == "observe"
    assert plan.summary == "Registrei 3 L." and "SUCESSO" in prompts[1]


def test_approval_resumes_remaining_batch_and_planning_in_same_run(env):
    env.agent.registry.high = {"calendar"}
    prompts = script(env, [BATCH3, "FINISH: Tudo feito depois da aprovação."])
    plan = env.agent.handle_request(MULTI, session_id="s1")
    assert plan.context["stopped_reason"] == "waiting_approval"
    assert "precisa da sua aprovação" in plan.summary and "continuo sozinho" in plan.summary
    assert [args["n"] for _, args in env.agent.registry.calls] == [1]
    run = detail(env, plan)["run"]
    assert run["status"] == "awaiting_confirmation" and run["resume_pending"] is True
    status, body = approve(plan.context["pending_action_id"])
    assert status == 200 and body["resumed"] is True
    assert [args["n"] for _, args in env.agent.registry.calls] == [1, 2, 3]
    assert len(prompts) == 2
    request = detail(env, plan)
    assert request["run"]["status"] == "succeeded" and request["run"]["reply"] == "Tudo feito depois da aprovação."
    assert {a["run_id"] for a in request["actions"]} == {plan.context["run_id"]}
    assert env.saved[-1] == ("s1", [{"role": "assistant", "content": "Tudo feito depois da aprovação.", "run_id": plan.context["run_id"]}])
    replies = [e for e in env.events if e["type"] == "agent_reply"]
    assert replies == [{"type": "agent_reply", "session_id": "s1", "run_id": plan.context["run_id"], "reply": "Tudo feito depois da aprovação."}]
    assert approve(plan.context["pending_action_id"])[0] == 409


def test_reject_ends_sequence_without_new_model_call(env):
    env.agent.registry.high = {"calendar"}
    prompts = script(env, [BATCH3, "FINISH: nunca chega"])
    plan = env.agent.handle_request(MULTI, session_id="s1")
    status, body = actions.handle_actions_post(f"/api/actions/{plan.context['pending_action_id']}/reject", b"{}", None)
    assert status == 200 and body["resumed"] is False
    assert len(prompts) == 1 and [args["n"] for _, args in env.agent.registry.calls] == [1]
    run = detail(env, plan)["run"]
    assert run["status"] == "cancelled" and run["resume_pending"] is False
    assert "Etapa recusada" in run["reply"] and run["reply"].startswith("Fiz 1 de 3 etapa(s)")
    assert any(e["type"] == "agent_reply" and "recusada" in e["reply"] for e in env.events)


def test_cancel_while_waiting_discards_checkpoint_and_approval_never_resumes(env):
    env.agent.registry.high = {"calendar"}
    prompts = script(env, [BATCH3, "FINISH: nunca chega"])
    plan = env.agent.handle_request(MULTI, session_id="s1")
    action_id = plan.context["pending_action_id"]
    assert env.store.cancel_run(plan.context["run_id"])["status"] == "cancelled"
    assert loop_checkpoints.take(action_id) is None
    assert approve(action_id)[0] == 409
    assert len(prompts) == 1 and len(env.agent.registry.calls) == 1
    run = detail(env, plan)["run"]
    assert run["status"] == "cancelled" and run["resume_pending"] is False


def test_approval_during_turn_continues_once(env, monkeypatch):
    env.agent.registry.high = {"calendar"}
    create = env.store.create

    def publish(action):
        created = create(action)
        if action.status == "awaiting_confirmation":
            with ThreadPoolExecutor() as pool:
                assert pool.submit(approve, action.id).result(5)[0] == 200
        return created
    monkeypatch.setattr(env.store, "create", publish)
    prompts = script(env, [BATCH3, "FINISH: feito uma vez"])
    plan = env.agent.handle_request(MULTI, session_id="s1")
    assert plan.summary == "feito uma vez" and len(prompts) == 2
    assert [args["n"] for _, args in env.agent.registry.calls] == [1, 2, 3]
    assert detail(env, plan)["run"]["status"] == "succeeded"
    assert not [e for e in env.events if e["type"] == "agent_reply"]


def test_progress_events_are_published_and_stored(env):
    script(env, [BATCH3, "FINISH: ok"])
    stream = list(env.agent.handle_request_stream(MULTI, session_id="s1"))
    plan = stream[-1]["plan"]
    progress = [e for e in env.events if e["type"] == "agent_progress"]
    phases = [e["phase"] for e in progress]
    assert phases[0] == "planning" and "acting" in phases and phases[-1] == "done"
    assert all(e["session_id"] == "s1" and e["run_id"] == plan.context["run_id"] for e in progress)
    assert progress[-1]["step"] == 3 and progress[-1]["max_steps"] == 8 and progress[-1]["max_model_calls"] == 10
    streamed = [item for item in stream if item["status"] == "progress"]
    assert streamed and streamed[0]["phase"] == "planning" and "type" not in streamed[0]
    assert detail(env, plan)["run"]["progress"]["phase"] == "done"


def test_tool_outside_turn_list_is_blocked(env):
    env.agent.registry.allowed_tool_names = lambda **k: frozenset({"timer"})
    script(env, ['ACOES: [{"ferramenta": "calendar", "args": {}}]', "FINISH: feito"])
    plan = env.agent.handle_request(MULTI, session_id="s1")
    assert plan.intent == "error" and "bloqueada" in plan.summary
    assert env.agent.registry.calls == [] and detail(env, plan)["actions"] == []


def test_orchestrator_uses_loop_for_multi_part_and_native_for_simple(env):
    native = []
    env.agent._run_llm_with_tools = lambda text, *a, **k: native.append(text) or AgentPlan(intent="general", summary="nativo", actions=[])
    prompts = script(env, ["FINISH: loop"])
    assert env.agent.handle_request(MULTI, session_id="s1").intent == "agent_loop"
    assert env.agent.handle_request("abre minhas finanças", session_id="s1").summary == "nativo"
    assert native == ["abre minhas finanças"] and len(prompts) == 1
    runtime_settings.set_agent_loop_settings({"mode": "off"})
    assert env.agent.handle_request(MULTI, session_id="s1").summary == "nativo"


@pytest.mark.parametrize("raw", [
    'ACOES: []', 'ACOES: [{"ferramenta": "x"}]', 'ACOES: [{"ferramenta": "", "args": {}}]',
    'ACOES: [{"ferramenta": "x", "args": []}]', 'ACOES: {"ferramenta": "x", "args": {}}',
    'FINISH: ok\nACOES: [{"ferramenta": "x", "args": {}}]',
    'ACOES: ' + str([{"ferramenta": "x", "args": {}}] * 6).replace("'", '"'),
    'ACOES: [broken', 'FINISH:',
])
def test_invalid_batch_plans_are_rejected(raw):
    with pytest.raises(ValueError):
        parse_plan(raw)


def test_batch_plan_accepts_code_fences():
    assert parse_plan('```json\nACOES: [{"ferramenta": "timer", "args": {"label": "chá"}}]\n```') == ("actions", [("timer", {"label": "chá"})])
    assert parse_plan("FERRAMENTA: timer\nARGS: {}") == ("actions", [("timer", {})])


# ── lote 7, pacote 1: expiração sem estado preso e autocorreção ──────────────
_REAL_TIME, _REAL_MONOTONIC = time.time, time.monotonic


def advance(monkeypatch, seconds):
    """Relógio falso: avança o relógio de parede (propostas) e o monotônico (prazo do ponto de retomada)."""
    monkeypatch.setattr(time, "time", lambda: _REAL_TIME() + seconds)
    monkeypatch.setattr(time, "monotonic", lambda: _REAL_MONOTONIC() + seconds)


def waiting_plan(env):
    env.agent.registry.high = {"calendar"}
    prompts = script(env, [BATCH3, "FINISH: nunca chega"])
    plan = env.agent.handle_request(MULTI, session_id="s1")
    assert plan.context["stopped_reason"] == "waiting_approval"
    return plan, prompts


def test_late_approval_after_checkpoint_expired_closes_run_as_failure(env, monkeypatch):
    plan, prompts = waiting_plan(env)
    action_id = plan.context["pending_action_id"]
    assert detail(env, plan)["run"]["resume_pending"] is True
    advance(monkeypatch, 11 * 60)
    status, body = approve(action_id)
    assert status == 410 and body["action"]["status"] == "expired"
    run = detail(env, plan)["run"]
    assert run["status"] == "failed" and run["resume_pending"] is False
    assert "ponto de retomada" in run["reply"] and "expirou" in run["reply"]
    assert len(prompts) == 1 and [args["n"] for _, args in env.agent.registry.calls] == [1]
    assert [e["reply"] for e in env.events if e["type"] == "agent_reply"] == [run["reply"]]


def test_late_reject_after_checkpoint_expired_also_leaves_no_running_run(env, monkeypatch):
    plan, _prompts = waiting_plan(env)
    advance(monkeypatch, 11 * 60)
    status, body = actions.handle_actions_post(f"/api/actions/{plan.context['pending_action_id']}/reject", b"{}", None)
    assert status == 200 and body["resumed"] is False
    run = detail(env, plan)["run"]
    assert run["status"] == "failed" and run["resume_pending"] is False


def test_sweep_expires_stale_proposals_and_ends_the_stuck_run(env, monkeypatch):
    plan, prompts = waiting_plan(env)
    action_id = plan.context["pending_action_id"]
    assert actions.sweep_expired_proposals() == 0  # dentro do prazo nada muda
    assert env.store.get(action_id).status == "awaiting_confirmation"
    assert detail(env, plan)["run"]["status"] == "awaiting_confirmation"
    advance(monkeypatch, 11 * 60)
    monkeypatch.setattr(runs, "action_store", env.store)
    status, body = runs.handle_runs_get(["api", "runs"], None)  # a varredura roda ao consultar a Central
    assert status == 200
    assert env.store.get(action_id).status == "expired"
    assert pending_action_broker.take(action_id) is None
    run = detail(env, plan)["run"]
    assert run["status"] == "failed" and run["resume_pending"] is False
    assert [item["status"] for item in body["runs"]] == ["failed"]
    assert len(prompts) == 1
    assert approve(action_id)[0] == 409  # já não está aguardando


def test_sweep_marks_expired_even_without_a_loop_run(env, monkeypatch):
    from app.core.actions import ActionRecord
    proposal = ActionRecord.create(source="conversation", tool_name="calendar", metadata=ToolMetadata(("calendar",), "high", requires_confirmation=True),
                                   arguments={"n": 1}, preview="Agendar.")
    env.store.create(proposal)
    advance(monkeypatch, 11 * 60)
    assert actions.sweep_expired_proposals() == 1
    assert env.store.get(proposal.id).status == "expired"
    assert actions.sweep_expired_proposals() == 0


def flaky_timer(env, fail_for):
    """Ferramenta ``timer`` que falha enquanto ``n`` estiver em ``fail_for`` e só na primeira tentativa de cada ``n``."""
    tried = set()

    def handler(args):
        first = args["n"] not in tried
        tried.add(args["n"])
        return ToolResult(False, f"timer {args['n']} indisponível") if first and args["n"] in fail_for else ToolResult(True, f"timer {args['n']} ok")
    env.agent.registry.responses[("timer", None)] = handler


def with_targets(env):
    """Metadados com alvo (argumento ``n``), como as ferramentas reais que nomeiam o que alteram."""
    env.agent.registry.get_tool_metadata = lambda name: ToolMetadata((name,), "observe", target_arguments=("n",))


def test_failure_corrected_by_a_later_success_does_not_fail_the_request(env):
    flaky_timer(env, {1})
    prompts = script(env, [
        'ACOES: [{"ferramenta": "timer", "args": {"n": 1}}]',
        'ACOES: [{"ferramenta": "timer", "args": {"n": 1}}]',
        "FINISH: Corrigi e terminei.",
    ])
    plan = env.agent.handle_request(MULTI, session_id="s1")
    assert plan.intent == "agent_loop" and plan.summary == "Corrigi e terminei."
    assert "FALHA" in prompts[1] and "SUCESSO" in prompts[2]
    assert env.saved and env.saved[-1][1][-1]["content"] == "Corrigi e terminei."  # entra no histórico
    assert plan.context["stopped_reason"] == "finish"


def test_failure_without_a_later_success_still_fails_with_the_failed_step(env):
    flaky_timer(env, {1})
    script(env, ['ACOES: [{"ferramenta": "timer", "args": {"n": 1}}]', "FINISH: Tudo certo."])
    plan = env.agent.handle_request(MULTI, session_id="s1")
    assert plan.intent == "error"
    assert plan.summary.startswith("Execução encerrada com falha na etapa 1.") and "timer 1 indisponível" in plan.summary


def test_success_on_a_different_target_does_not_hide_the_failure(env):
    with_targets(env)
    flaky_timer(env, {1})
    script(env, ['ACOES: [{"ferramenta": "timer", "args": {"n": 1}}, {"ferramenta": "timer", "args": {"n": 2}}]', "FINISH: Tudo certo."])
    plan = env.agent.handle_request(MULTI, session_id="s1")
    assert plan.intent == "error" and "etapa 1" in plan.summary


def test_success_on_the_same_target_corrects_the_failure(env):
    with_targets(env)
    flaky_timer(env, {1})
    script(env, ['ACOES: [{"ferramenta": "timer", "args": {"n": 2}}, {"ferramenta": "timer", "args": {"n": 1}}, {"ferramenta": "timer", "args": {"n": 1, "retry": true}}]', "FINISH: Tudo certo."])
    plan = env.agent.handle_request(MULTI, session_id="s1")
    assert plan.intent == "agent_loop" and plan.summary == "Tudo certo."


def test_success_text_mentioning_error_or_failure_is_not_a_failure(env):
    env.agent.registry.responses[("timer", None)] = lambda args: ToolResult(True, "0 erros e nenhuma falha encontrados")
    prompts = script(env, ['ACOES: [{"ferramenta": "timer", "args": {"n": 1}}]', "FINISH: Sem problemas."])
    plan = env.agent.handle_request(MULTI, session_id="s1")
    assert plan.intent == "agent_loop" and plan.summary == "Sem problemas."
    assert "SUCESSO" in prompts[1] and "FALHA" not in prompts[1] and "Atenção" not in plan.summary


# ── rotinas, fase 1: espera real em ordem e resposta só com evidência ────────
WAIT_REQUEST = "Abra o spotify, aguarde 50 segundos e abra uma música no youtube"
WAIT_PLAN = ('ACOES: [{"ferramenta": "spotify", "args": {"action": "open"}}, {"ferramenta": "wait", "args": {"seconds": 50}}, '
             '{"ferramenta": "web_search", "args": {"action": "open_url", "query": "https://www.youtube.com/watch?v=abc"}}]')


@pytest.fixture
def wait_env(env, monkeypatch):
    """Registro falso com spotify, wait (espera real com relógio falso) e web_search; marca o tempo de cada chamada."""
    from app.agent import effect_checks
    from app.agent.tools.wait import WaitTool
    from app.core import waits

    clock = SimpleNamespace(now=0.0)
    monkeypatch.setattr(waits, "_monotonic", lambda: clock.now)
    monkeypatch.setattr(waits, "_sleep", lambda seconds: setattr(clock, "now", clock.now + seconds))
    monkeypatch.setattr(effect_checks, "_monotonic", lambda: clock.now)
    monkeypatch.setattr(effect_checks, "_sleep", lambda seconds: setattr(clock, "now", clock.now + seconds))
    registry = FakeRegistry(names=("timer", "spotify", "wait", "web_search"))
    stamps = []
    execute = registry.execute_tool

    def stamped(name, args, **kwargs):
        stamps.append((name, clock.now))
        if name == "wait":
            return WaitTool().execute(args)
        return execute(name, args, **kwargs)
    registry.execute_tool = stamped
    env.agent.registry = registry
    return SimpleNamespace(clock=clock, stamps=stamps, registry=registry)


def test_wait_request_runs_in_order_and_hides_timer(env, wait_env):
    prompts = script(env, [WAIT_PLAN, "FINISH: Abri o Spotify, esperei 50 s e abri o YouTube."])
    plan = env.agent.handle_request(WAIT_REQUEST, session_id="s1")
    assert [name for name, _ in wait_env.stamps] == ["spotify", "wait", "web_search"]
    assert wait_env.stamps[2][1] >= 50 and wait_env.stamps[0][1] == 0  # a 3ª ação só depois do fim da espera
    assert '"nome": "wait"' in prompts[0] and '"nome": "timer"' not in prompts[0]
    assert "timer só agenda um bipe e NÃO pausa" in prompts[0] and "'Confirmado'" in prompts[0]
    request = detail(env, plan)
    assert [a["tool_name"] for a in request["actions"]] == ["spotify", "wait", "web_search"]
    assert request["run"]["status"] == "succeeded"


def test_alarm_request_keeps_timer(env, wait_env):
    prompts = script(env, ["FINISH: ok"])
    env.agent.handle_request("abre o spotify, aguarde 5 segundos e me avisa com um alarme", session_id="s1")
    assert '"nome": "timer"' in prompts[0]


def test_wait_progress_counts_down_in_chat_and_central(env, wait_env):
    script(env, ['ACOES: [{"ferramenta": "wait", "args": {"seconds": 3}}]', "FINISH: Esperei."])
    plan = env.agent.handle_request(WAIT_REQUEST, session_id="s1")
    waiting = [e for e in env.events if e["type"] == "agent_progress" and e["phase"] == "waiting"]
    assert [e["wait_remaining"] for e in waiting] == [3, 2, 1, 0] and {e["wait_total"] for e in waiting} == {3}
    assert all(e["run_id"] == plan.context["run_id"] for e in waiting)
    # A Central guarda o último contador (fase final "done" sobrescreve depois).
    assert detail(env, plan)["run"]["progress"]["phase"] == "done"


def test_cancel_during_wait_stops_the_sequence(env, wait_env, monkeypatch):
    from app.core import waits
    run_ids = []

    def sleep_then_cancel(seconds):
        wait_env.clock.now += seconds
        if wait_env.clock.now >= 2 and not run_ids:
            run = env.store.run_page(include_reads=True)["runs"][0]
            run_ids.append(run["id"])
            env.store.cancel_run(run["id"])
    monkeypatch.setattr(waits, "_sleep", sleep_then_cancel)
    script(env, [WAIT_PLAN, "FINISH: nunca chega"])
    env.agent.handle_request(WAIT_REQUEST, session_id="s1")
    assert [name for name, _ in wait_env.stamps] == ["spotify", "wait"]
    request = env.store.run_details(run_ids[0])
    assert [a["status"] for a in request["actions"]] == ["succeeded", "cancelled"]
    assert request["run"]["status"] == "cancelled"


def effects_on(monkeypatch, processes, titles):
    from app.agent import effect_checks
    monkeypatch.setattr(effect_checks, "enabled", True)
    monkeypatch.setattr(effect_checks, "_processes", lambda: set(processes))
    monkeypatch.setattr(effect_checks, "_window_titles", lambda: list(titles))


def test_unconfirmed_effect_replaces_the_model_claim(env, wait_env, monkeypatch):
    effects_on(monkeypatch, {"spotify.exe"}, ["Spotify Premium"])  # sem navegador: YouTube não confirma
    script(env, [WAIT_PLAN, "FINISH: Pronto, tocando!"])
    plan = env.agent.handle_request(WAIT_REQUEST, session_id="s1")
    assert "Pronto, tocando" not in plan.summary
    assert "não consegui confirmar" in plan.summary and "Etapa 1 (spotify): confirmado" in plan.summary
    assert "Esperei 50 s" in plan.summary


def test_all_confirmed_keeps_model_text_with_evidence(env, wait_env, monkeypatch):
    effects_on(monkeypatch, {"spotify.exe", "chrome.exe"}, ["Spotify Premium", "Lofi - YouTube - Google Chrome"])
    script(env, [WAIT_PLAN, "FINISH: Abri tudo."])
    plan = env.agent.handle_request(WAIT_REQUEST, session_id="s1")
    assert plan.summary.startswith("Abri tudo.") and "Confirmado:" in plan.summary
    assert "abri o vídeo no YouTube" in plan.summary
