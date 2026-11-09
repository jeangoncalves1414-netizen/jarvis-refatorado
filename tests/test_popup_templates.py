"""Modelos de popup com dados (lote 6, Fase 4): hábitos, agenda, água e anotação ao vivo."""
import http.client
import json
from contextlib import closing
from datetime import date, timedelta
from http.server import ThreadingHTTPServer
from threading import Thread
from types import SimpleNamespace

import pytest

from app.agent import popups
from app.agent.orchestrator import AgentOrchestrator
from app.agent.react_loop import ReActLoopEngine
from app.agent.tools.calendar_tool import CalendarTool
from app.agent.tools.lifeos_tool import LifeOSTool
from app.agent.tools.lifestyle_tools import HabitTool
from app.agent.tools.memory_vault_tool import VaultSaveNoteTool, VaultSearchTool
from app.agent.tools.open_screen import OpenScreenTool
from app.agent.tools.registry import ToolRegistry
from app.agent.tools.show_popup import ShowPopupTool
from app.core import loop_checkpoints, ui_events
from app.core.actions import pending_action_broker
from app.services.lifeos import LifeOSService
from app.storage import runtime_settings
from app.ui.panel.api import notes_live

USER_REQUEST = (
    "abre o painel, adiciona ler e meditar nos hábitos, depois agenda dentista amanhã às 15h "
    "e depois coloca que bebi 3L de água hoje"
)
TOMORROW = (date.today() + timedelta(days=1)).isoformat()


def real_registry():
    registry = ToolRegistry.__new__(ToolRegistry)
    registry.tools = {tool.name: tool for tool in (
        OpenScreenTool(), HabitTool(), CalendarTool(), LifeOSTool(), ShowPopupTool(), VaultSaveNoteTool(), VaultSearchTool(),
    )}
    return registry


@pytest.fixture
def env(isolated_lote6_data, monkeypatch):
    import app.agent.orchestrator as module
    monkeypatch.setattr(module, "build_tutor_system", lambda *a, **k: "test")
    monkeypatch.setattr("app.services.stm_filters.stm_filter", SimpleNamespace(process=lambda value: value))
    monkeypatch.setattr(module, "save_session_history", lambda session, history: None)
    monkeypatch.setattr(module, "get_session_history", lambda _: [])
    monkeypatch.setattr("app.core.logger.logger", SimpleNamespace(record_request=lambda: None, info=lambda *a: None))
    monkeypatch.setattr(loop_checkpoints, "resume_runner", lambda checkpoint, status: checkpoint.resume(status))
    # O gateway das rotas (POST /api/notes/live) usa o registro global: aqui só as ferramentas do teste.
    registry = real_registry()
    monkeypatch.setattr("app.agent.tools.registry.registry", registry)
    loop_checkpoints.loop_checkpoints.clear()
    agent = AgentOrchestrator.__new__(AgentOrchestrator)
    agent.llm_service = SimpleNamespace(get_active_provider=lambda: "gemini", _api_key_for=lambda _: "fixture-key")
    agent.profile_memory = agent.settings = agent.vision_service = agent.browser_agent = None
    agent._remember_preferences = lambda *a: None
    agent._resolve_enem_context = lambda *a: None
    agent.productivity_service = agent.file_action_service = None
    agent.registry = registry
    events = []
    unsubscribe = ui_events.subscribe(events.append)
    yield SimpleNamespace(agent=agent, store=isolated_lote6_data.store, root=isolated_lote6_data.root, events=events)
    unsubscribe()
    for action in isolated_lote6_data.store.list(limit=200):
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


def acoes(*items):
    return "ACOES: " + json.dumps([{"ferramenta": name, "args": args} for name, args in items], ensure_ascii=False)


def popup_events(env):
    return [event["popup"] for event in env.events if event.get("type") == "ui_popup"]


# ── Hábitos ──────────────────────────────────────────────────────────────────

def test_create_many_in_chat_turn_emits_one_habit_list_with_added_ids_in_order(env):
    script(env, [acoes(("habit_tool", {"action": "create_many", "habits": [{"name": "Ler"}, {"name": "Meditar"}, {"name": "Correr"}]})), "FINISH: Criei."])
    plan = env.agent.handle_request("adiciona ler, meditar e correr nos hábitos e depois confere se ficou certo", session_id="s1")
    published = popup_events(env)
    assert [p["template"] for p in published] == ["habit_list"]
    popup = published[0]
    assert popup["key"] == "habits" and popup["origin"] == "chat"
    names = [item["name"] for item in popup["data"]["items"]]
    assert names == ["Ler", "Meditar", "Correr"]
    ids = [item["id"] for item in popup["data"]["items"]]
    assert popup["animate"] == {"added_ids": ids}
    assert popup["data"]["highlight_ids"] == ids and popup["data"]["total"] == 3
    assert plan.context["ui_popups"] == published


def test_two_habit_calls_reuse_the_same_key(env):
    script(env, [
        acoes(("habit_tool", {"action": "create", "name": "Ler"})),
        acoes(("habit_tool", {"action": "check", "name": "Ler"})),
        "FINISH: Pronto.",
    ])
    env.agent.handle_request("adiciona ler nos hábitos e depois marca ler como feito", session_id="s1")
    published = [p for p in popup_events(env) if p["template"] == "habit_list"]
    assert len(published) == 2 and {p["key"] for p in published} == {"habits"}
    assert "added_ids" in published[0]["animate"] and "checked_ids" in published[1]["animate"]
    assert published[1]["data"]["items"][0]["completed_today"] is True
    assert published[1]["data"]["completed"] == 1


def test_habit_list_today_includes_highlighted_habit_from_other_day(env):
    other_day = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][(date.today().weekday() + 1) % 7]
    HabitTool().execute({"action": "create", "name": "Yoga", "days_of_week": [other_day]})
    assert popups.build_popup("habit_list", {}, origin="command")["data"]["items"] == []
    popup = popups.build_popup("habit_list", {"highlight": ["yoga"]}, origin="command")
    assert [item["name"] for item in popup["data"]["items"]] == ["Yoga"]
    assert len(popups.build_popup("habit_list", {"filter": "all"}, origin="command")["data"]["items"]) == 1


# ── Agenda ───────────────────────────────────────────────────────────────────

def test_create_reminder_emits_schedule_of_that_day(env):
    script(env, [acoes(("calendar", {"action": "create_reminder", "title": "Dentista", "start": f"{TOMORROW}T15:00"})), "FINISH: Agendei."])
    env.agent.handle_request("agenda dentista amanhã às 15h e depois confere se ficou certo", session_id="s1")
    published = popup_events(env)
    assert [p["template"] for p in published] == ["schedule"]
    popup = published[0]
    assert popup["key"] == f"schedule:{TOMORROW}" and popup["data"]["date"] == TOMORROW
    assert [(e["title"], e["start"]) for e in popup["data"]["events"]] == [("Dentista", f"{TOMORROW}T15:00")]
    assert popup["animate"] == {"added_ids": [popup["data"]["events"][0]["id"]]}


# ── Água ─────────────────────────────────────────────────────────────────────

def test_set_water_emits_water_popup_with_previous_current_and_target(env):
    LifeOSService.set_water(1000)
    script(env, [acoes(("lifeos_tool", {"action": "set_water", "total_ml": 3000})), "FINISH: Registrei."])
    env.agent.handle_request("coloca que bebi 3 litros de água hoje e depois confere se ficou certo", session_id="s1")
    published = popup_events(env)
    assert [p["template"] for p in published] == ["water"]
    data = published[0]["data"]
    target = LifeOSService.get_daily_summary()["water"]["target_ml"]
    assert (data["previous_ml"], data["current_ml"], data["target_ml"]) == (1000, 3000, target)
    assert published[0]["animate"] == {"from_ml": 1000, "to_ml": 3000}
    assert published[0]["key"] == f"water:{date.today().isoformat()}"


def test_auto_popups_disabled_do_not_emit(env):
    runtime_settings.set_popup_settings({"auto": False})
    script(env, [acoes(("lifeos_tool", {"action": "set_water", "total_ml": 2000})), "FINISH: ok"])
    plan = env.agent.handle_request("coloca que bebi 2 litros de água hoje e depois confere se ficou certo", session_id="s1")
    assert popup_events(env) == [] and "ui_popups" not in plan.context


def test_failed_tool_never_emits(env):
    assert popups.popups_for_result("lifeos_tool", {"action": "set_water"}, SimpleNamespace(ok=False, data={"data": {"total_ml": 1}})) == []


# ── Anotação ao vivo ─────────────────────────────────────────────────────────

def test_live_notes_validation_and_sticky_envelope(env):
    tool = ShowPopupTool()
    assert not tool.execute({"template": "live_notes", "params": {"format": "tabela"}}).ok
    assert tool.execute({"template": "live_notes", "params": {"title": "Compras", "format": "checklist"}}).ok
    with pytest.raises(ValueError):
        popups.validate_popup_request("live_notes", {"title": "x" * 81})
    assert popups.validate_popup_request("live_notes", {"dictate": "false"})[1] == {"dictate": False}
    popup = popups.build_popup("live_notes", {"title": "Compras", "format": "checklist"}, origin="chat")
    assert popup["ttl_ms"] == 0
    data = popup["data"]
    assert data["title"] == "Compras" and data["format"] == "checklist" and data["dictate"] is True and data["content"] == ""
    assert popup["key"] == f"notes:{data['draft_id']}"


class FakeHandler:
    def __init__(self, client="127.0.0.1"):
        self.client_address = (client, 50000)


def post_note(payload, client="127.0.0.1"):
    return notes_live.handle_notes_live_post("/api/notes/live", json.dumps(payload).encode("utf-8"), FakeHandler(client))


def test_live_note_saves_in_vault_through_kernel_and_overwrites_same_file(env):
    payload = {"draft_id": "abc123def456", "title": "Compras", "format": "checklist", "content": "- [ ] pão\n- [ ] leite"}
    status, data = post_note(payload)
    assert status == 200 and data["ok"] is True
    assert data["path"] == "05-Notas/Compras-abc123.md"
    note = env.root / "vault" / "05-Notas" / "Compras-abc123.md"
    assert "- [ ] pão" in note.read_text(encoding="utf-8")
    assert data["action"]["tool_name"] == "vault_save_note" and data["action"]["status"] == "succeeded"
    runs = env.store.run_page(include_reads=True)["runs"]
    assert runs and runs[0]["origin"] == "window"
    status, _ = post_note({**payload, "content": "- [x] pão\n- [ ] leite\n- [ ] café"})
    assert status == 200
    assert list((env.root / "vault" / "05-Notas").glob("*.md")) == [note]
    assert "- [ ] café" in note.read_text(encoding="utf-8")
    assert popup_events(env) == []


@pytest.mark.parametrize("payload, message", [
    ({"draft_id": "abc123def456", "title": "Big", "content": "x" * 20_001}, "20.000"),
    ({"draft_id": "../etc", "title": "Big", "content": "x"}, "Rascunho"),
    ({"draft_id": "abc123def456", "title": "", "content": "x"}, "título"),
    ({"draft_id": "abc123def456", "title": "A", "format": "tabela", "content": "x"}, "Formato"),
    ({"draft_id": "abc123def456", "title": "A", "content": "  "}, "vazia"),
])
def test_live_note_rejects_invalid_payload(env, payload, message):
    status, data = post_note(payload)
    assert status == 400 and message in data["error"]
    assert not (env.root / "vault" / "05-Notas").exists() or not list((env.root / "vault" / "05-Notas").glob("*.md"))


def test_live_note_rejects_non_local_request(env):
    status, data = post_note({"draft_id": "abc123def456", "title": "A", "content": "x"}, client="192.168.0.10")
    assert status == 403 and "locais" in data["error"]
    assert notes_live.handle_notes_live_post("/api/outra", b"{}", FakeHandler()) is None


# ── Rotas HTTP (comandos sem IA) ─────────────────────────────────────────────

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
            return res.status, json.loads(res.read().decode("utf-8"))
    try:
        yield request
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(2)


def test_command_routes_build_data_popups_and_water_add_returns_popup(env, http_server):
    LifeOSService.set_water(500)
    status, data = http_server("/api/evolute/water/add", {"amount_ml": 250})
    assert status == 200 and data["total_ml"] == 750 and data["added_ml"] == 250
    assert data["popup"]["template"] == "water" and data["popup"]["origin"] == "command"
    assert (data["popup"]["data"]["previous_ml"], data["popup"]["data"]["current_ml"]) == (500, 750)
    status, data = http_server("/api/popups/water")
    assert status == 200 and data["popup"]["data"]["previous_ml"] == data["popup"]["data"]["current_ml"] == 750
    assert http_server("/api/popups/habit_list?filter=all&highlight=Ler&highlight=Correr")[0] == 200
    status, data = http_server(f"/api/popups/schedule?date={TOMORROW}")
    assert status == 200 and data["popup"]["key"] == f"schedule:{TOMORROW}"
    assert http_server("/api/popups/schedule?date=amanha")[0] == 400
    status, data = http_server("/api/popups/live_notes?title=Compras&dictate=false")
    assert status == 200 and data["popup"]["data"]["dictate"] is False and data["popup"]["ttl_ms"] == 0
    status, data = http_server("/api/notes/live", {"draft_id": "feed1234beef", "title": "Ideias", "format": "text", "content": "uma ideia"})
    assert status == 200 and data["path"] == "05-Notas/Ideias-feed12.md"
    assert env.store.run_page(include_reads=True)["runs"][0]["origin"] == "window"


# ── Cenário completo da usuária pelo loop ────────────────────────────────────

def test_full_user_scenario_through_the_loop(env):
    batch = acoes(
        ("open_screen", {"screen": "Painel pessoal"}),
        ("habit_tool", {"action": "create_many", "habits": [{"name": "Ler"}, {"name": "Meditar"}]}),
        ("calendar", {"action": "create_reminder", "title": "Dentista", "start": f"{TOMORROW}T15:00"}),
        ("lifeos_tool", {"action": "set_water", "total_ml": 3000}),
    )
    prompts = script(env, [batch, "FINISH: Tudo feito."])
    plan = env.agent.handle_request(USER_REQUEST, session_id="s1")
    assert plan.intent == "agent_loop" and plan.summary == "Tudo feito." and len(prompts) == 2
    actions = env.store.run_details(plan.context["run_id"])["actions"]
    writes = [(a["tool_name"], a["status"]) for a in actions if a["risk"] != "observe" or a["tool_name"] == "open_screen"]
    assert ("open_screen", "succeeded") in writes
    tools = [a["tool_name"] for a in actions]
    # 4 ações + leituras de verificação (hábitos, agenda, água) no mesmo Run.
    assert tools.count("habit_tool") == 2 and tools.count("calendar") == 2 and tools.count("lifeos_tool") == 2
    assert all(a["status"] == "succeeded" for a in actions)
    templates = [p["template"] for p in plan.context["ui_popups"]]
    assert templates == ["habit_list", "schedule", "water"]
    water = plan.context["ui_popups"][2]["data"]
    assert water["current_ml"] == 3000 and water["previous_ml"] == 0
    assert [item["name"] for item in plan.context["ui_popups"][0]["data"]["items"]] == ["Ler", "Meditar"]
