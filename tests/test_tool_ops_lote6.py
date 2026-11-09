"""Operações novas e em lote das ferramentas pessoais (lote 6, fase 1).

Todos os testes usam ``isolated_lote6_data``: banco, Life OS, cofre e Central em tmp.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app.agent.action_executor import ActionExecutor
from app.agent.tool_guardrails import ToolCallGuardrailController
from app.agent.tools.calendar_tool import CalendarTool
from app.agent.tools.lifeos_tool import LifeOSTool
from app.agent.tools.lifestyle_tools import FinanceTool, HabitTool, TaskTool
from app.agent.tools.memory_vault_tool import VaultSaveNoteTool, VaultSearchTool
from app.agent.tools.registry import ToolRegistry
from app.agent.tools.timer import TimerTool
from app.services.finance import FinanceService
from app.services.habits import HabitService
from app.services.lifeos import LifeOSService
from app.services.tasks import TaskService


@pytest.fixture
def data(isolated_lote6_data):
    return isolated_lote6_data


def _habit(args):
    return HabitTool().execute(args)


# ── hábitos ──────────────────────────────────────────────────────────────────

def test_habit_create_many_creates_all_and_returns_ids(data):
    result = _habit({"action": "create_many", "habits": [
        {"name": "Ler"}, {"name": "Correr", "routine_block": "morning", "days_of_week": ["segunda", "quarta"]},
        {"name": "Meditar", "start_time": "7h"},
    ]})
    assert result.ok, result.message
    ids = result.data["habit_ids"]
    assert len(ids) == 3
    stored = {h["id"]: h for h in HabitService.list_habits()}
    assert [stored[i]["name"] for i in ids] == ["Ler", "Correr", "Meditar"]
    assert stored[ids[1]]["days_of_week"] == ["mon", "wed"] and stored[ids[1]]["routine_block"] == "morning"
    assert stored[ids[2]]["start_time"] == "07:00"


def test_habit_batch_with_invalid_item_writes_nothing(data):
    result = _habit({"action": "create_many", "habits": [{"name": "Ler"}, {"name": "Correr", "routine_block": "madrugada"}]})
    assert not result.ok and "Hábito 2" in result.message and "Nada foi criado" in result.message
    assert HabitService.list_habits() == []
    result = _habit({"action": "create_many", "habits": [{"name": "Ler"}, {"name": "  "}]})
    assert not result.ok and HabitService.list_habits() == []


def test_habit_batch_limit_is_refused(data):
    result = _habit({"action": "create_many", "habits": [{"name": f"H{i}"} for i in range(21)]})
    assert not result.ok and "20" in result.message
    assert HabitService.list_habits() == []


def test_habit_check_and_delete_by_name(data):
    _habit({"action": "create_many", "habits": [{"name": "Meditação"}, {"name": "Ler livro"}, {"name": "Ler notícias"}]})
    checked = _habit({"action": "check", "name": "meditacao"})
    assert checked.ok, checked.message
    by_name = {h["name"]: h for h in HabitService.list_habits()}
    assert by_name["Meditação"]["completed_today"] is True

    ambiguous = _habit({"action": "check", "name": "ler"})
    assert not ambiguous.ok and "Ler livro" in ambiguous.message and "Ler notícias" in ambiguous.message

    # delete exige nome exato; parte do nome não basta.
    partial = _habit({"action": "delete", "name": "Ler liv"})
    assert not partial.ok
    deleted = _habit({"action": "delete", "name": "LER LIVRO"})
    assert deleted.ok, deleted.message
    assert sorted(h["name"] for h in HabitService.list_habits()) == ["Ler notícias", "Meditação"]


def test_habit_check_many_and_update_rename(data):
    _habit({"action": "create_many", "habits": [{"name": "Ler"}, {"name": "Correr"}, {"name": "Água"}]})
    many = _habit({"action": "check_many", "names": ["ler", "correr"]})
    assert many.ok and len(many.data["habit_ids"]) == 2
    missing = _habit({"action": "check_many", "names": ["ler", "nadar"]})
    assert not missing.ok and "nadar" in missing.message
    updated = _habit({"action": "update", "name": "Correr", "new_name": "Corrida", "category": "saúde", "routine_block": "evening"})
    assert updated.ok, updated.message
    habit = HabitService.get_habit(updated.data["habit_ids"][0])
    assert (habit["name"], habit["category"], habit["routine_block"]) == ("Corrida", "saúde", "evening")


def test_habit_list_only_today(data):
    today = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")[date.today().weekday()]
    other = "sun" if today != "sun" else "mon"
    _habit({"action": "create_many", "habits": [{"name": "Hoje", "days_of_week": [today]}, {"name": "Outro dia", "days_of_week": [other]}]})
    listed = _habit({"action": "list", "only_today": True})
    assert [h["name"] for h in listed.data["habits"]] == ["Hoje"]


# ── tarefas ──────────────────────────────────────────────────────────────────

def test_task_create_many_update_and_list_completed(data):
    tool = TaskTool()
    created = tool.execute({"action": "create_many", "tasks": [
        {"title": "Pagar luz", "priority": 1, "due_date": "2026-08-10"}, {"title": "Comprar pão"},
    ]})
    assert created.ok and len(created.data["task_ids"]) == 2
    bad = tool.execute({"action": "create_many", "tasks": [{"title": "Ok"}, {"title": "Ruim", "priority": 9}]})
    assert not bad.ok and len(TaskService.list_tasks(completed=None)) == 2

    updated = tool.execute({"action": "update", "title": "pagar luz", "new_title": "Pagar conta de luz", "priority": 2})
    assert updated.ok, updated.message
    task = TaskService.get_task(created.data["task_ids"][0])
    assert (task["title"], task["priority"], task["due_date"]) == ("Pagar conta de luz", 2, "2026-08-10")

    assert tool.execute({"action": "toggle", "title": "Comprar pão"}).ok
    pending = tool.execute({"action": "list"}).data["tasks"]
    everything = tool.execute({"action": "list", "include_completed": True}).data["tasks"]
    assert [t["title"] for t in pending] == ["Pagar conta de luz"]
    assert len(everything) == 2

    assert tool.execute({"action": "delete", "title": "Comprar pão"}).ok
    assert [t["title"] for t in TaskService.list_tasks(completed=None)] == ["Pagar conta de luz"]


# ── finanças ─────────────────────────────────────────────────────────────────

def test_finance_add_many_list_filtered_and_update(data):
    tool = FinanceTool()
    result = tool.execute({"action": "add_many", "entries": [
        {"amount": 50, "category": "Mercado"}, {"amount": 30, "category": "Transporte"},
        {"type": "income", "amount": 1000, "category": "Salário"},
    ]})
    assert result.ok, result.message
    ids = result.data["trans_ids"]
    assert len(ids) == 3 and result.data["total"] == 1080

    invalid = tool.execute({"action": "add_many", "entries": [{"amount": 10}, {"amount": -5}]})
    assert not invalid.ok and "Lançamento 2" in invalid.message
    assert FinanceService.query_transactions()["totals"]["count"] == 3

    expenses = tool.execute({"action": "list", "type": "expense", "period": "month"})
    assert expenses.ok and expenses.data["totals"]["expense"] == 80 and expenses.data["totals"]["count"] == 2
    market = tool.execute({"action": "list", "category": "Mercado", "period": "all"})
    assert [t["id"] for t in market.data["transactions"]] == [ids[0]]
    assert not tool.execute({"action": "list", "period": "ano"}).ok

    updated = tool.execute({"action": "update", "trans_id": ids[0], "amount": 55.5})
    assert updated.ok, updated.message
    stored = FinanceService.get_transaction(ids[0])
    assert (stored["amount"], stored["category"], stored["type"]) == (55.5, "Mercado", "expense")


# ── água ─────────────────────────────────────────────────────────────────────

def test_set_water_defines_total_and_reports_previous(data):
    tool = LifeOSTool()
    assert tool.execute({"action": "add_water", "amount": 1000}).ok
    result = tool.execute({"action": "set_water", "total_ml": 3000})
    assert result.ok, result.message
    water = result.data["data"]
    assert water["previous_ml"] == 1000 and water["total_ml"] == 3000 and water["target_ml"] == 3000
    assert LifeOSService.get_daily_summary()["water"]["current_ml"] == 3000
    assert not tool.execute({"action": "set_water", "total_ml": 20000}).ok
    assert not tool.execute({"action": "add_water", "amount": 9000}).ok
    assert LifeOSService.get_daily_summary()["water"]["current_ml"] == 3000
    assert (data.root / "lifeos" / "lifeos_db.json").exists()


# ── calendário e timer ───────────────────────────────────────────────────────

def test_calendar_create_many_and_list_by_day(data):
    tool = CalendarTool()
    tomorrow = (datetime.now() + timedelta(days=1)).replace(hour=15, minute=0, second=0, microsecond=0)
    later = tomorrow + timedelta(days=3)
    created = tool.execute({"action": "create_many", "reminders": [
        {"title": "Dentista", "start": tomorrow.isoformat(timespec="minutes")},
        {"title": "Reunião", "start": later.isoformat(timespec="minutes")},
    ]})
    assert created.ok, created.message
    assert len(created.data["event_ids"]) == 2
    day = tool.execute({"action": "list", "day": tomorrow.date().isoformat()})
    assert [e["title"] for e in day.data["events"]] == ["Dentista"]
    soon = tool.execute({"action": "list", "upcoming_days": 2})
    assert [e["title"] for e in soon.data["events"]] == ["Dentista"]
    bad = tool.execute({"action": "create_many", "reminders": [{"title": "Ok", "start": tomorrow.isoformat()}, {"title": "Sem data"}]})
    assert not bad.ok and "Lembrete 2" in bad.message
    assert len(tool.execute({"action": "list"}).data["events"]) == 2
    assert (data.root / "data" / "calendar.json").exists()


def test_timer_cancel_by_label(data):
    tool = TimerTool()
    assert tool.execute({"action": "set_timer", "duration": "30 minutos", "label": "Lote6 pizza"}).ok
    cancelled = tool.execute({"action": "cancel", "label": "lote6 pizza"})
    assert cancelled.ok and cancelled.data["cancelled"] == ["Lote6 pizza"]
    assert all(t["label"] != "Lote6 pizza" for t in tool.manager.list_active())
    assert not tool.execute({"action": "cancel", "label": "lote6 pizza"}).ok


# ── cofre ────────────────────────────────────────────────────────────────────

def test_vault_save_note_refuses_unknown_folder_and_saves_in_tmp(data):
    tool = VaultSaveNoteTool()
    escaped = tool.execute({"title": "x", "content": "y", "folder": "../x"})
    assert not escaped.ok and "Pasta inválida" in escaped.message
    assert not (data.root / "x").exists()
    assert not tool.execute({"title": "", "content": "y"}).ok
    assert not tool.execute({"title": "Grande", "content": "a" * 20001}).ok

    saved = tool.execute({"title": "Lista de compras", "content": "- pão\n- leite"})
    assert saved.ok, saved.message
    assert saved.data["path"] == "05-Notas/Lista-de-compras.md"
    assert (data.root / "vault" / "05-Notas" / "Lista-de-compras.md").read_text(encoding="utf-8").endswith("- pão\n- leite\n")
    found = VaultSearchTool().execute({"query": "leite"})
    assert found.ok and found.data["results"][0]["path"] == "05-Notas/Lista-de-compras.md"


# ── pelo Action Kernel ───────────────────────────────────────────────────────

def test_batch_goes_through_executor_with_batch_target_in_preview(data):
    registry = ToolRegistry()
    executor = ActionExecutor(
        None, ToolCallGuardrailController(),
        lambda name, args, _user: registry.execute_tool(name, args),
        metadata_for=registry.get_tool_metadata, store=data.store, source="test",
    )
    message = executor.execute("habit_tool", {"action": "create_many", "habits": [{"name": "Ler"}, {"name": "Correr"}, {"name": "Meditar"}]}, "adiciona")
    action = executor.last_action
    assert (action.risk, action.status) == ("low", "succeeded"), message
    assert "3 hábitos: Ler, Correr, Meditar" in action.preview
    assert len(HabitService.list_habits()) == 3

    executor.execute("finance_tool", {"action": "add_many", "entries": [{"amount": 50}, {"amount": 30}]}, "gastei")
    assert "2 lançamentos, total R$ 80,00" in executor.last_action.preview
    executor.execute("lifeos_tool", {"action": "set_water", "total_ml": 3000}, "bebi 3L")
    assert "total do dia: 3.000 ml" in executor.last_action.preview and executor.last_action.status == "succeeded"

    executor.execute("habit_tool", {"action": "delete", "name": "Ler"}, "apaga")
    assert executor.last_action.status == "awaiting_confirmation"
    assert len(HabitService.list_habits()) == 3
    assert [a.tool_name for a in data.store.list()].count("habit_tool") == 2
