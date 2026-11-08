from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import http.client
import json
from http.server import ThreadingHTTPServer
from threading import Event, Thread
from types import SimpleNamespace

import pytest

from app.agent.orchestrator import AgentOrchestrator
from app.agent.react_loop import ReActLoopEngine
from app.agent.tools.base import ToolResult
from app.core.actions import ToolMetadata, pending_action_broker
from app.domain.actions import FileActionService
from app.storage import task_store
from app.storage.action_store import ActionStore
from app.ui.panel.api import actions


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    import app.agent.orchestrator as module
    monkeypatch.chdir(tmp_path)
    store = ActionStore(tmp_path / "journal.sqlite3")
    monkeypatch.setattr("app.storage.action_store.action_store", store)
    monkeypatch.setattr(actions, "action_store", store)
    monkeypatch.setattr(module, "build_tutor_system", lambda *a, **k: "test")
    monkeypatch.setattr("app.services.stm_filters.stm_filter", SimpleNamespace(process=lambda value: value))
    saved = []
    monkeypatch.setattr(module, "save_session_history", lambda session, history: saved.append((session, history)))
    monkeypatch.setattr(module, "get_session_history", lambda _: [])
    monkeypatch.setattr("app.core.logger.logger", SimpleNamespace(record_request=lambda: None, info=lambda *a: None))
    agent = AgentOrchestrator.__new__(AgentOrchestrator)
    agent.llm_service = agent.profile_memory = agent.settings = agent.vision_service = agent.browser_agent = None
    agent._remember_preferences = lambda *a: None
    agent._resolve_enem_context = lambda *a: None
    monkeypatch.setattr(task_store, "TASKS_FILE", str(tmp_path / "tasks.json"))
    agent.productivity_service = task_store
    agent.file_action_service = FileActionService(str(tmp_path))
    agent.tutor_store = SimpleNamespace(get_summary_for_llm=lambda: "")
    agent.pattern_learner = SimpleNamespace(record_action=lambda *a: None)
    calls = []
    agent.registry = SimpleNamespace(
        tools={"calendar": object()}, get_tool_declarations=lambda **k: [],
        allowed_tool_names=lambda **k: frozenset({"calendar"}),
        get_tool_metadata=lambda _: ToolMetadata(("calendar",), "observe"),
        execute_tool=lambda name, args, **k: calls.append((name, args)) or ToolResult(True, "feito"),
    )
    yield agent, store, calls, saved
    for action in store.list(limit=100):
        pending_action_broker.discard(action.id)
    if store._runtime_lock:
        store._runtime_lock.close()


def detail(store, plan):
    return store.run_details(plan.context["run_id"])


@pytest.mark.parametrize("stream", [False, True])
def test_voice_turn_records_actions_with_voice_origin(runtime, stream):
    from app.core.runs import current_origin

    agent, store, _, _ = runtime
    text = "Adicione uma tarefa de estudar Python"
    if stream:
        plan = list(agent.handle_request_stream(text, session_id="one", origin="voice"))[-1]["plan"]
    else:
        plan = agent.handle_request(text, session_id="one", origin="voice")
    [action] = detail(store, plan)["actions"]
    assert action["source"] == "voice:shortcut:one"
    assert current_origin.get() == "chat"
    # Sem origem (ou com valor desconhecido) o turno continua sendo do chat.
    plan = agent.handle_request(text + " de novo", session_id="one", origin="phone-hack")
    assert detail(store, plan)["actions"][0]["source"] == "shortcut:one"


@pytest.mark.parametrize("text", ["Como organizar minhas tarefas?", "Explique metabolismo", "O que é uma pasta?", "Não crie uma tarefa", "Quero abrir a pasta Downloads"])
def test_mentions_do_not_trigger_local_mutations(runtime, text):
    agent, store, _, _ = runtime
    plan = agent.handle_request(text)
    assert not agent.productivity_service.list_tasks()
    assert detail(store, plan)["actions"] == []
    assert detail(store, plan)["run"]["status"] == "failed"


@pytest.mark.parametrize("stream", [False, True])
def test_local_task_has_one_real_execution_and_one_request(runtime, stream):
    agent, store, _, _ = runtime
    if stream:
        events = list(agent.handle_request_stream("Adicione uma tarefa de estudar Python", session_id="one"))
        assert events[0]["status"] == "thinking"
        plan = events[-1]["plan"]
    else:
        plan = agent.handle_request("Adicione uma tarefa de estudar Python", session_id="one")
    assert plan.intent == "productivity"
    from app.ui.panel.api.dashboard import handle_tasks_get
    items = handle_tasks_get(["api", "tasks"], SimpleNamespace(path="/api/tasks"))[1]["tasks"]
    assert [task["title"] for task in items] == ["estudar Python"]
    assert plan.context["task_id"] == items[0]["id"]
    request = detail(store, plan)
    assert request["run"]["session_id"] == "one"
    assert request["run"]["status"] == "succeeded"
    assert len(request["actions"]) == len(store.run_page()["runs"]) == 1
    assert request["actions"][0]["tool_name"] == "create_local_task"


def test_local_failure_cannot_be_reported_as_success(runtime, monkeypatch):
    agent, store, _, _ = runtime
    def fail(_):
        raise RuntimeError("SECRET-DO-NOT-JOURNAL")
    monkeypatch.setattr(agent.productivity_service, "add_task", fail)
    plan = agent.handle_request("Crie uma tarefa de estudar")
    request = detail(store, plan)
    assert plan.intent == "error"
    assert request["run"]["status"] == request["actions"][0]["status"] == "failed"
    assert "SECRET-DO-NOT-JOURNAL" not in str(request)
    assert "registrada" not in plan.summary


def test_unreadable_tasks_survive_creation_attempt(runtime, tmp_path):
    agent, store, _, _ = runtime
    (tmp_path / "tasks.json").write_bytes(b"{broken")
    plan = agent.handle_request("Crie uma tarefa de estudo")
    assert detail(store, plan)["run"]["status"] == "failed"
    assert (tmp_path / "tasks.json").read_bytes() == b"{broken"


def test_concurrent_task_creations_remain_visible_after_reload(runtime):
    agent, _, _, _ = runtime
    with ThreadPoolExecutor(max_workers=4) as pool:
        plans = list(pool.map(agent.handle_request, [f"Crie uma tarefa de estudo {i}" for i in range(6)]))
    saved = task_store.list_tasks()
    assert len(saved) == 6
    assert {task["id"] for task in saved} == {p.context["task_id"] for p in plans}


def test_listing_result_and_missing_folder_are_truthful(runtime, tmp_path):
    agent, store, _, _ = runtime
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "fixture.txt").write_text("test")
    plan = agent.handle_request("Liste os arquivos da pasta notes")
    assert plan.intent == "file"
    assert plan.context["action_result"]["items"] == ["fixture.txt"]
    assert detail(store, plan)["run"]["status"] == "succeeded"
    failed = agent.handle_request("Liste os arquivos da pasta missing")
    assert failed.intent == "error" and "não foi encontrada" in failed.summary
    assert detail(store, failed)["actions"][0]["status"] == "failed"


@pytest.mark.parametrize("stream", [False, True])
def test_native_nested_entry_points_keep_one_run_and_one_history_save(runtime, stream):
    agent, store, calls, saved = runtime
    def chat(**kw):
        kw["on_function_call"]("calendar", {"item": 1})
        if kw["on_chunk"]:
            kw["on_chunk"]("resposta")
        return "resposta"
    agent.llm_service = SimpleNamespace(get_active_provider=lambda: "gemini", _api_key_for=lambda _: "fixture-key", chat_with_functions_stream=chat)
    if stream:
        events = list(agent.handle_request_stream("oi", session_id="one", mode="tutor"))
        assert any(e["status"] == "streaming" for e in events)
        plan = events[-1]["plan"]
    else:
        plan = agent.handle_request("oi", session_id="one", mode="tutor")
    assert calls == [("calendar", {"item": 1})]
    assert len(saved) == 1 and len(saved[0][1]) == 2
    assert saved[0][1][-1]["run_id"] == plan.context["run_id"]
    assert len(store.run_page()["runs"]) == 1
    assert detail(store, plan)["actions"][0]["run_id"] == plan.context["run_id"]


def react(agent, replies):
    prompts = []
    sequence = iter(replies)
    def ask(prompt):
        prompts.append(prompt)
        return next(sequence)
    agent.react_loop = ReActLoopEngine(SimpleNamespace(ask=ask), agent.registry)
    return prompts


@pytest.mark.parametrize("stream", [False, True])
def test_react_waits_for_bound_approval_without_resuming_loop(runtime, stream):
    agent, store, calls, _ = runtime
    agent.registry.get_tool_metadata = lambda _: ToolMetadata(("calendar",), "high", requires_confirmation=True)
    prompts = react(agent, ['FERRAMENTA: calendar\nARGS: {"path": "original"}', 'FINISH: feito'])
    plan = list(agent.handle_request_stream("faça", mode="react", session_id="one"))[-1]["plan"] if stream else agent.handle_request("faça", mode="react", session_id="one")
    request = detail(store, plan)
    assert request["run"]["status"] == "awaiting_confirmation"
    assert calls == [] and len(prompts) == 1
    action_id = plan.context["pending_action_id"]
    assert action_id == request["actions"][0]["id"]
    status, _ = actions.handle_actions_post(f"/api/actions/{action_id}/approve", b"{}", None)
    assert status == 200 and calls == [("calendar", {"path": "original"})]
    assert detail(store, plan)["run"]["status"] == "succeeded"
    assert len(prompts) == 1
    assert actions.handle_actions_post(f"/api/actions/{action_id}/approve", b"{}", None)[0] == 409


@pytest.mark.parametrize("reply", ['FERRAMENTA: calendar\nARGS: []', 'FERRAMENTA: calendar\nARGS: {broken}', 'nonsense', 'FINISH: feito\nFERRAMENTA: calendar\nARGS: {}'])
def test_react_invalid_plan_never_executes_or_claims_success(runtime, reply):
    agent, store, calls, _ = runtime
    react(agent, [reply])
    plan = agent.handle_request("faça", mode="react")
    assert plan.intent == "error" and not calls
    assert detail(store, plan)["run"]["status"] == "failed"


def test_react_tool_failure_stays_failed_even_if_model_claims_finish(runtime):
    agent, store, _, _ = runtime
    agent.registry.execute_tool = lambda *a, **k: ToolResult(False, "Não encontrado")
    react(agent, ['FERRAMENTA: calendar\nARGS: {}', 'FINISH: feito'])
    plan = agent.handle_request("faça", mode="react")
    request = detail(store, plan)
    assert request["run"]["status"] == request["actions"][0]["status"] == "failed"
    assert plan.intent == "error" and "Não encontrado" in plan.summary


@pytest.mark.parametrize("during", ["planning", "tool"])
def test_react_cancel_does_not_fall_through_or_start_another_stage(runtime, during):
    agent, store, calls, _ = runtime
    entered, release = Event(), Event()
    prompts = react(agent, ['FERRAMENTA: calendar\nARGS: {}', 'FINISH: feito'])
    target = agent.react_loop.llm_service if during == "planning" else agent.registry
    attr = "ask" if during == "planning" else "execute_tool"
    original = getattr(target, attr)
    def slow(*a, **k):
        entered.set()
        assert release.wait(10)
        return original(*a, **k)
    setattr(target, attr, slow)
    with ThreadPoolExecutor() as pool:
        future = pool.submit(agent.handle_request, "faça", mode="react")
        try:
            assert entered.wait(10)
            run = store.run_page()["runs"][0]
            assert store.cancel_run(run["id"])["status"] == "cancel_requested"
        finally:
            release.set()
        plan = future.result(10)
    assert plan.intent == "cancelled"
    assert detail(store, plan)["run"]["status"] == "cancelled"
    assert len(prompts) == 1
    assert len(calls) == (1 if during == "tool" else 0)


def test_react_without_provider_never_simulates_success(runtime):
    agent, store, calls, _ = runtime
    agent.react_loop = ReActLoopEngine(None, agent.registry)
    plan = agent.handle_request("faça", mode="react")
    assert plan.intent == "error" and not calls
    assert detail(store, plan)["run"]["status"] == "failed"


def test_specialist_failure_is_not_a_successful_run(runtime):
    agent, store, _, _ = runtime
    agent.swarm = SimpleNamespace(route_and_execute=lambda _: {"ok": False, "summary": "Falhou"})
    plan = agent.handle_request("faça", mode="swarm")
    assert plan.intent == "error"
    assert detail(store, plan)["run"]["status"] == "failed"


def test_react_rejects_registered_tool_outside_step_mode(runtime):
    agent, store, calls, _ = runtime
    agent.registry.tools["other"] = object()
    react(agent, ["FERRAMENTA: other\nARGS: {}", "FINISH: feito"])
    plan = agent.handle_request("faça", mode="react")
    assert plan.intent == "error" and "bloqueada" in plan.summary
    assert not calls and detail(store, plan)["actions"] == []


def test_approval_can_arrive_as_soon_as_react_proposal_is_visible(runtime, monkeypatch):
    agent, store, calls, _ = runtime
    agent.registry.get_tool_metadata = lambda _: ToolMetadata(default_risk="high")
    create = store.create
    def publish(action):
        created = create(action)
        with ThreadPoolExecutor() as pool:
            assert pool.submit(actions.handle_actions_post, f"/api/actions/{action.id}/approve", b"{}", None).result(5)[0] == 200
        return created
    monkeypatch.setattr(store, "create", publish)
    prompts = react(agent, ["FERRAMENTA: calendar\nARGS: {}", "FINISH: feito"])
    plan = agent.handle_request("faça", mode="react")
    assert len(prompts) == len(calls) == 1
    assert plan.context["pending_action_id"]
    assert detail(store, plan)["run"]["status"] == "succeeded"


def test_react_real_whiteboard_approval_targets_only_original_conversation(runtime, tmp_path, monkeypatch):
    from app.agent.tools.registry import ToolRegistry
    from app.agent.tools.whiteboard import WhiteboardClearTool
    from app.storage import session_store
    agent, store, _, _ = runtime
    monkeypatch.setattr(session_store, "SESSIONS_FILE", str(tmp_path / "sessions.json"))
    for session in ("one", "two"):
        session_store.add_session({"id": session, "whiteboard": [{"id": session}]})
    agent.registry = ToolRegistry.__new__(ToolRegistry)
    agent.registry.tools = {"whiteboard_clear": WhiteboardClearTool()}
    react(agent, ['FERRAMENTA: whiteboard_clear\nARGS: {"session_id":"two"}'])
    plan = agent.handle_request("Limpe meu quadro", session_id="one", mode="react")
    proposal = detail(store, plan)["actions"][0]
    assert proposal["status"] == "awaiting_confirmation"
    assert "quadro da conversa" in proposal["preview"]
    assert session_store.get_whiteboard("one") == [{"id": "one"}]
    status, result = actions.handle_actions_post(f"/api/actions/{proposal['id']}/approve", b"{}", None)
    assert status == 200 and result["ok"]
    assert session_store.get_whiteboard("one") == []
    assert session_store.get_whiteboard("two") == [{"id": "two"}]
    assert detail(store, plan)["run"]["status"] == "succeeded"


def test_http_react_and_stream_publish_same_request_contract(runtime, monkeypatch):
    from app.config import Settings
    from app.ui.panel import server
    from app.ui.panel.api import runs
    agent, store, calls, _ = runtime
    monkeypatch.setattr(server, "_orchestrator", agent)
    monkeypatch.setattr(runs, "action_store", store)
    agent.registry.get_tool_metadata = lambda _: ToolMetadata(default_risk="high")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.PanelHandler)
    monkeypatch.setattr(server.PanelHandler, "settings", Settings(host="127.0.0.1", port=httpd.server_address[1]))
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    def request(path, payload=None):
        with closing(http.client.HTTPConnection(*httpd.server_address, timeout=4)) as client:
            client.request("GET" if payload is None else "POST", path, None if payload is None else json.dumps(payload), {"Content-Type": "application/json"})
            res = client.getresponse()
            return res.status, res.read().decode("utf-8")
    try:
        assert request("/api/react", {"goal": "faça", "max_steps": True})[0] == 400
        assert store.run_page()["runs"] == []
        react(agent, ["FERRAMENTA: calendar\nARGS: {}"])
        status, raw = request("/api/react", {"goal": "faça", "max_steps": 2, "session_id": "one"})
        pending = json.loads(raw)
        assert status == 200 and pending["ok"] is False and pending["pending_action_id"]
        assert json.loads(request("/api/runs/" + pending["run_id"])[1])["run"]["status"] == "awaiting_confirmation"
        assert not calls
        assert request("/api/actions/" + pending["pending_action_id"] + "/approve", {})[0] == 200
        assert calls == [("calendar", {})]
        status, raw = request("/api/chat/stream", {"message": "Crie uma tarefa de Estudo", "session_id": "two"})
        events = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: ")]
        assert status == 200 and [event["status"] for event in events] == ["thinking", "complete"]
        ref = events[-1]["plan"]["context"]["run_id"]
        assert ref != pending["run_id"]
        assert json.loads(request("/api/runs/" + ref)[1])["run"]["session_id"] == "two"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(2)
