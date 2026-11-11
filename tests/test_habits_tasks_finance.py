import json
import pytest
from app.services.habits import HabitService
from app.services.tasks import TaskService
from app.services.finance import FinanceService, init_finance_tables
from app.agent.tools.lifestyle_tools import HabitTool, TaskTool, FinanceTool
from app.ui.panel.api.routes.system_routes import handle_system_routes

pytestmark = pytest.mark.usefixtures('isolated_lote6_data')


def test_habits_service_lifecycle():
    habit = HabitService.create_habit(
        habit_id="test_habit_1",
        name="Exercício Físico",
        category="saude",
        routine_block="morning"
    )
    assert habit["name"] == "Exercício Físico"
    assert habit["completed_today"] is False

    checked = HabitService.check_in("test_habit_1")
    assert checked["completed_today"] is True
    assert checked["current_streak"] == 1

    unchecked = HabitService.uncheck_in("test_habit_1")
    assert unchecked["completed_today"] is False

    HabitService.delete_habit("test_habit_1")
    assert HabitService.get_habit("test_habit_1") is None


def test_tasks_service_lifecycle():
    task = TaskService.create_task(
        task_id="test_task_1",
        title="Enviar relatório mensal",
        priority=1,
        project="Trabalho",
        subtasks=["Revisar números", "Gerar PDF"]
    )
    assert task["title"] == "Enviar relatório mensal"
    assert task["priority"] == 1
    assert len(task["subtasks"]) == 2
    assert task["completed"] == 0

    toggled = TaskService.toggle_task("test_task_1")
    assert toggled["completed"] == 1

    TaskService.delete_task("test_task_1")
    assert TaskService.get_task("test_task_1") is None


def test_finance_service_lifecycle():
    summary1 = FinanceService.add_transaction(
        trans_id="t1",
        type_="income",
        amount=5000.0,
        category="Salário",
        description="Pagamento mensal"
    )
    assert summary1["income"] >= 5000.0

    summary2 = FinanceService.add_transaction(
        trans_id="t2",
        type_="expense",
        amount=150.0,
        category="Mercado",
        description="Compras semanais"
    )
    assert summary2["expense"] >= 150.0

    FinanceService.delete_transaction("t1")
    FinanceService.delete_transaction("t2")


def test_lifestyle_ai_tools():
    h_tool = HabitTool()
    t_tool = TaskTool()
    f_tool = FinanceTool()

    # Test HabitTool
    h_res = h_tool.run(action="create", name="Estudar Inglês", habit_id="tool_habit_1")
    assert h_res["ok"] is True
    check_res = h_tool.run(action="check", habit_id="tool_habit_1")
    assert check_res["ok"] is True
    h_tool.run(action="delete", habit_id="tool_habit_1")

    # Test TaskTool
    t_res = t_tool.run(action="create", title="Comprar café", priority=2, task_id="tool_task_1")
    assert t_res["ok"] is True
    toggle_res = t_tool.run(action="toggle", task_id="tool_task_1")
    assert toggle_res["ok"] is True
    t_tool.run(action="delete", task_id="tool_task_1")

    # Test FinanceTool
    f_res = f_tool.run(action="add", type="expense", amount=29.90, category="Lazer", trans_id="tool_fin_1")
    assert f_res["ok"] is True
    f_tool.run(action="delete", trans_id="tool_fin_1")


def test_system_routes_lifestyle_endpoints():
    sent_data = {}
    def mock_send_json(status, data):
        sent_data["status"] = status
        sent_data["data"] = data

    # REST /api/habits
    body = json.dumps({"action": "create", "id": "rest_h1", "name": "Beber 2L água"}).encode("utf-8")
    handled = handle_system_routes("/api/habits", body, mock_send_json)
    assert handled is True
    assert sent_data["status"] == 200
    assert sent_data["data"]["ok"] is True

    # REST /api/tasks
    body = json.dumps({"action": "create", "id": "rest_t1", "title": "Revisar pr", "priority": 1}).encode("utf-8")
    handled = handle_system_routes("/api/tasks", body, mock_send_json)
    assert handled is True
    assert sent_data["status"] == 200

    # REST /api/finance
    body = json.dumps({"action": "add", "id": "rest_f1", "type": "income", "amount": 100.0}).encode("utf-8")
    handled = handle_system_routes("/api/finance", body, mock_send_json)
    assert handled is True
    assert sent_data["status"] == 200

    # Clean up
    HabitService.delete_habit("rest_h1")
    TaskService.delete_task("rest_t1")
    FinanceService.delete_transaction("rest_f1")


@pytest.fixture
def finance_db(tmp_path, monkeypatch):
    """Banco temporário: os testes de finanças da janela nunca tocam data/lifestyle.db."""
    monkeypatch.setattr("app.services.habits.DB_PATH", tmp_path / "lifestyle.db")
    init_finance_tables()
    return tmp_path / "lifestyle.db"


def call_finance(payload: dict) -> tuple[int, dict]:
    sent: dict = {}
    handled = handle_system_routes("/api/finance", json.dumps(payload).encode("utf-8"), lambda status, data: sent.update(status=status, data=data))
    assert handled is True
    return sent["status"], sent["data"]


def seed_finance() -> None:
    rows = [
        ("a1", "income", 3000, "Salário", "Mensal", "2026-05-05"),
        ("a2", "expense", 200.5, "Mercado", "Compras", "2026-05-10"),
        ("a3", "expense", 80, "Lazer", "Cinema", "2026-05-20"),
        ("a4", "expense", 50.25, "Mercado", "Feira", "2026-06-02"),
        ("a5", "income", 100, "Extra", "Venda", "2026-06-03"),
    ]
    for trans_id, kind, amount, category, description, day in rows:
        status, data = call_finance({"action": "add", "id": trans_id, "type": kind, "amount": amount, "category": category, "description": description, "date": day})
        assert status == 200 and data["ok"] is True


def test_finance_api_list_filters_and_totals(finance_db):
    seed_finance()
    _, everything = call_finance({"action": "list"})
    assert everything["totals"] == {
        "income": 3100.0, "expense": 330.75, "net": 2769.25, "count": 5,
        "by_category": everything["totals"]["by_category"],
    }
    assert [t["id"] for t in everything["transactions"]] == ["a5", "a4", "a3", "a2", "a1"]
    assert sorted(everything["categories"]) == ["Extra", "Lazer", "Mercado", "Salário"]

    _, may = call_finance({"action": "list", "date_from": "2026-05-01", "date_to": "2026-05-31"})
    assert (may["totals"]["income"], may["totals"]["expense"], may["totals"]["count"]) == (3000.0, 280.5, 3)

    _, expenses = call_finance({"action": "list", "type": "expense"})
    assert expenses["totals"]["income"] == 0.0 and expenses["totals"]["expense"] == 330.75

    _, market = call_finance({"action": "list", "category": "Mercado", "type": "expense"})
    assert market["totals"]["expense"] == 250.75 and market["totals"]["count"] == 2
    assert market["totals"]["by_category"] == [{"category": "Mercado", "type": "expense", "total": 250.75}]

    _, limited = call_finance({"action": "list", "limit": 2})
    assert len(limited["transactions"]) == 2 and limited["truncated"] is True
    assert limited["totals"]["count"] == 5 and limited["totals"]["income"] == 3100.0


def test_finance_api_add_update_delete_cycle(finance_db):
    status, created = call_finance({"action": "add", "id": "m1", "type": "expense", "amount": 10, "category": "Lazer", "description": "Café", "date": "2026-07-01"})
    assert status == 200 and created["transaction"]["amount"] == 10.0 and created["transaction"]["date_str"] == "2026-07-01"

    # Reenviar o mesmo id (nova tentativa do rascunho) não duplica.
    call_finance({"action": "add", "id": "m1", "type": "expense", "amount": 10, "category": "Lazer", "description": "Café", "date": "2026-07-01"})
    assert call_finance({"action": "list"})[1]["totals"]["count"] == 1

    status, updated = call_finance({"action": "update", "id": "m1", "type": "income", "amount": 12.345, "category": "Reembolso", "description": "Devolvido", "date": "2026-07-02"})
    assert status == 200
    assert updated["transaction"]["type"] == "income" and updated["transaction"]["amount"] == 12.35
    assert updated["transaction"]["category"] == "Reembolso" and updated["transaction"]["date_str"] == "2026-07-02"

    status, missing = call_finance({"action": "update", "id": "nao-existe", "type": "expense", "amount": 1})
    assert status == 404 and missing["ok"] is False

    status, deleted = call_finance({"action": "delete", "id": "m1"})
    assert status == 200 and deleted["ok"] is True
    assert call_finance({"action": "list"})[1]["totals"]["count"] == 0


def test_finance_api_default_date_is_today_and_rejects_bad_input(finance_db):
    from datetime import date

    status, created = call_finance({"action": "add", "id": "d1", "type": "expense", "amount": 5})
    assert status == 200 and created["transaction"]["date_str"] == date.today().isoformat()
    assert created["transaction"]["category"] == "Outros"

    for bad in (
        {"type": "expense", "amount": 0},
        {"type": "expense", "amount": -3},
        {"type": "expense", "amount": "abc"},
        {"type": "expense", "amount": float("inf")},
        {"type": "transferencia", "amount": 5},
        {"type": "expense", "amount": 5, "date": "31/12/2026"},
    ):
        status, data = call_finance({"action": "add", "id": "bad", **bad})
        assert status == 400 and data["ok"] is False and data["error"], bad
    assert call_finance({"action": "add", "id": "../x", "type": "expense", "amount": 1})[0] == 400
    assert call_finance({"action": "list", "date_from": "ontem"})[0] == 400
    assert call_finance({"action": "list", "type": "outro"})[0] == 400
    assert call_finance({"action": "list"})[1]["totals"]["count"] == 1

