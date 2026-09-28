import json
import pytest
from app.services.habits import HabitService
from app.services.tasks import TaskService
from app.services.finance import FinanceService
from app.agent.tools.lifestyle_tools import HabitTool, TaskTool, FinanceTool
from app.ui.panel.api.routes.system_routes import handle_system_routes


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
