"""Infraestrutura de popups (lote 6, Fase 3): validação, show_popup, coletor do turno, rotas."""
import dataclasses
import http.client
import json
from contextlib import closing
from http.server import ThreadingHTTPServer
from threading import Thread
from types import SimpleNamespace

import pytest

from app.agent import popups
from app.agent.action_gateway import run_action
from app.agent.orchestrator import AgentOrchestrator
from app.agent.react_loop import ReActLoopEngine
from app.agent.tools.base import ToolResult
from app.agent.tools.catalog import TOOL_CATALOG
from app.agent.tools.registry import GENERAL_TOOL_NAMES, ToolRegistry
from app.agent.tools.show_popup import ShowPopupTool
from app.core import loop_checkpoints, ui_events
from app.core.actions import ToolMetadata, pending_action_broker
from app.storage import runtime_settings

MULTI = "mostra um aviso no popup e depois agenda dentista amanhã às 15h"
SHOW = 'ACOES: [{"ferramenta": "show_popup", "args": {"template": "info", "params": {"title": "Pronto", "lines": ["Tudo certo"], "tone": "ok"}}}]'


class PopupRegistry:
    """Registro com o show_popup real e ferramentas falsas de baixo risco."""

    def __init__(self):
        self.real = ShowPopupTool()
        self.tools = {"show_popup": self.real, "timer": SimpleNamespace(description="timer", parameters={})}
        self.calls = []

    def allowed_tool_names(self, **_kwargs):
        return frozenset(self.tools)

    def get_tool_metadata(self, name):
        return TOOL_CATALOG.get(name) or ToolMetadata((name,), "observe")

    def execute_tool(self, name, args, **_kwargs):
        self.calls.append((name, args))
        if name == "show_popup":
            return self.real.execute(args)
        return ToolResult(True, f"{name} ok")


@pytest.fixture
def env(isolated_lote6_data, monkeypatch):
    import app.agent.orchestrator as module
    store = isolated_lote6_data.store
    monkeypatch.setattr(module, "build_tutor_system", lambda *a, **k: "test")
    monkeypatch.setattr("app.services.stm_filters.stm_filter", SimpleNamespace(process=lambda value: value))
    monkeypatch.setattr(module, "save_session_history", lambda session, history: None)
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
    agent.registry = PopupRegistry()
    events = []
    unsubscribe = ui_events.subscribe(events.append)
    yield SimpleNamespace(agent=agent, store=store, events=events)
    unsubscribe()
    for action in store.list(limit=200):
        pending_action_broker.discard(action.id)
    loop_checkpoints.loop_checkpoints.clear()


def script(env, replies):
    sequence = iter(replies)
    env.agent.react_loop = ReActLoopEngine(SimpleNamespace(ask=lambda _prompt: next(sequence)), env.agent.registry)


def popup_events(env):
    return [event for event in env.events if event.get("type") == "ui_popup"]


# ── Validação ────────────────────────────────────────────────────────────────

def test_validation_rejects_unknown_template_extra_param_and_long_text():
    assert popups.validate_popup_request("info", {"title": "Oi", "lines": ["a"], "tone": "OK"}) == ("info", {"title": "Oi", "lines": ["a"], "tone": "ok"})
    with pytest.raises(ValueError, match="Popup desconhecido"):
        popups.validate_popup_request("nada", {})
    with pytest.raises(ValueError, match="Parâmetro 'cor' não existe"):
        popups.validate_popup_request("info", {"title": "Oi", "cor": "azul"})
    with pytest.raises(ValueError, match="no máximo 60"):
        popups.validate_popup_request("info", {"title": "x" * 61})
    with pytest.raises(ValueError, match="no máximo 6"):
        popups.validate_popup_request("info", {"title": "Oi", "lines": ["a"] * 7})
    with pytest.raises(ValueError, match="obrigatório"):
        popups.validate_popup_request("info", {})
    with pytest.raises(ValueError, match="objeto"):
        popups.validate_popup_request("info", ["x"])


def test_show_popup_tool_registered_observe_and_validates():
    assert "show_popup" in GENERAL_TOOL_NAMES and ToolRegistry().get_tool("show_popup") is not None
    assert TOOL_CATALOG["show_popup"].risk_for({"template": "info"}) == "observe"
    ok = ShowPopupTool().execute({"template": "info", "params": {"title": "Oi"}})
    assert ok.ok and ok.data["ui_popup"] == {"template": "info", "params": {"title": "Oi"}}
    bad = ShowPopupTool().execute({"template": "info", "params": {"title": "Oi", "x": 1}})
    assert not bad.ok and "não existe" in bad.message


def test_build_popup_envelope_uses_settings(isolated_lote6_data):
    runtime_settings.set_popup_settings({"ttl_seconds": 0})
    popup = popups.build_popup("info", {"title": "Oi"}, origin="command")
    assert popup["id"].startswith("pop_") and popup["key"].startswith("info:")
    assert popup["template"] == "info" and popup["version"] == 1 and popup["origin"] == "command"
    assert popup["ttl_ms"] == 0 and popup["pinned"] is False
    assert popup["data"] == {"title": "Oi", "lines": [], "tone": "info"}


def test_popup_settings_validate_before_saving(isolated_lote6_data):
    assert runtime_settings.get_popup_settings() == {"enabled": True, "auto": True, "ttl_seconds": 8, "max_visible": 3}
    for bad in ({"max_visible": 6}, {"ttl_seconds": -1}, {"enabled": "sim"}, {"cor": 1}, {"max_visible": True}):
        with pytest.raises(ValueError):
            runtime_settings.set_popup_settings(bad)
    assert runtime_settings.get_popup_settings()["max_visible"] == 3
    assert runtime_settings.set_popup_settings({"max_visible": 5, "auto": False})["max_visible"] == 5


# ── Turnos de chat e voz ─────────────────────────────────────────────────────

@pytest.mark.parametrize("origin", ["chat", "voice"])
def test_show_popup_in_turn_publishes_and_lands_in_plan_context(env, origin):
    script(env, [SHOW, "FINISH: Mostrei."])
    plan = env.agent.handle_request(MULTI, session_id="s1", origin=origin)
    published = popup_events(env)
    assert len(published) == 1
    event = published[0]
    assert event["session_id"] == "s1" and event["run_id"] == plan.context["run_id"]
    assert event["popup"]["origin"] == origin and event["popup"]["data"]["title"] == "Pronto"
    assert plan.context["ui_popups"] == [event["popup"]]
    actions = env.store.run_details(plan.context["run_id"])["actions"]
    assert [(a["tool_name"], a["status"], a["risk"]) for a in actions] == [("show_popup", "succeeded", "observe")]


def test_window_route_never_emits_popup(env):
    outcome = run_action("show_popup", {"template": "info", "params": {"title": "Oi"}}, source="test", user_text="x", origin="window")
    assert outcome.succeeded
    assert popup_events(env) == []


def test_popups_disabled_do_not_emit(env):
    runtime_settings.set_popup_settings({"enabled": False})
    script(env, [SHOW, "FINISH: ok"])
    plan = env.agent.handle_request(MULTI, session_id="s1")
    assert popup_events(env) == [] and "ui_popups" not in plan.context


def test_builder_failure_keeps_action_succeeded(env, monkeypatch):
    def broken(_params, _context):
        raise RuntimeError("serviço fora do ar")
    monkeypatch.setitem(popups.POPUP_TEMPLATES, "info", dataclasses.replace(popups.POPUP_TEMPLATES["info"], builder=broken))
    script(env, [SHOW, "FINISH: ok"])
    plan = env.agent.handle_request(MULTI, session_id="s1")
    assert popup_events(env) == []
    actions = env.store.run_details(plan.context["run_id"])["actions"]
    assert [a["status"] for a in actions] == ["succeeded"]


def test_auto_popups_follow_auto_setting(env, monkeypatch):
    monkeypatch.setitem(popups.AUTO_POPUPS, ("timer", "list"), lambda args, result: [("info", {"title": "Timers"}, {})])
    script(env, ['ACOES: [{"ferramenta": "timer", "args": {"action": "list"}}]', "FINISH: ok"])
    env.agent.handle_request(MULTI, session_id="s1")
    assert [event["popup"]["data"]["title"] for event in popup_events(env)] == ["Timers"]
    env.events.clear()
    runtime_settings.set_popup_settings({"auto": False})
    script(env, ['ACOES: [{"ferramenta": "timer", "args": {"action": "list"}}]', "FINISH: ok"])
    env.agent.handle_request(MULTI, session_id="s1")
    assert popup_events(env) == []


# ── Rotas HTTP ───────────────────────────────────────────────────────────────

@pytest.fixture
def http_server(env, monkeypatch):
    from app.config import Settings
    from app.ui.panel import server
    monkeypatch.setattr(server, "_orchestrator", env.agent)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.PanelHandler)
    monkeypatch.setattr(server.PanelHandler, "settings", Settings(host="127.0.0.1", port=httpd.server_address[1]))
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    def request(path, payload=None):
        with closing(http.client.HTTPConnection(*httpd.server_address, timeout=5)) as client:
            client.request("GET" if payload is None else "POST", path, None if payload is None else json.dumps(payload), {"Content-Type": "application/json"})
            res = client.getresponse()
            return res.status, res.read().decode("utf-8")
    try:
        yield request
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(2)


def test_get_popup_route_builds_without_ai_and_without_run(env, http_server):
    status, raw = http_server("/api/popups/info?title=Oi&lines=um&lines=dois&tone=warn")
    data = json.loads(raw)
    assert status == 200 and data["ok"] is True
    assert data["popup"]["origin"] == "command" and data["popup"]["data"] == {"title": "Oi", "lines": ["um", "dois"], "tone": "warn"}
    assert env.store.run_page(include_reads=True)["runs"] == []
    assert http_server("/api/popups/nada")[0] == 400
    assert http_server("/api/popups/info?title=Oi&cor=azul")[0] == 400
    status, raw = http_server("/api/settings/popups")
    assert status == 200 and json.loads(raw)["settings"]["max_visible"] == 3
    status, raw = http_server("/api/settings/popups", {"max_visible": 9})
    assert status == 400 and "1 a 5" in json.loads(raw)["error"]
    status, raw = http_server("/api/settings/popups", {"settings": {"max_visible": 2}})
    assert status == 200 and json.loads(raw)["settings"]["max_visible"] == 2


def test_chat_stream_sse_emits_popup_status(env, http_server):
    script(env, [SHOW, "FINISH: Mostrei."])
    status, raw = http_server("/api/chat/stream", {"message": MULTI, "session_id": "s2", "origin": "voice"})
    events = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: ")]
    statuses = [event["status"] for event in events]
    assert status == 200 and "popup" in statuses and statuses[-1] == "complete"
    popup = next(event["popup"] for event in events if event["status"] == "popup")
    assert popup["origin"] == "voice"
    assert events[-1]["plan"]["context"]["ui_popups"][0]["id"] == popup["id"]
    assert statuses.index("popup") < statuses.index("complete")
