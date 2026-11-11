from types import SimpleNamespace

import pytest

from app.agent.action_executor import ActionExecutor
from app.agent.loop_policy import missing_requested_steps
from app.agent.tool_guardrails import ToolCallGuardrailController
from app.agent.tools.base import ToolResult
from app.agent.tools.lifestyle_tools import TaskTool, FinanceTool
from app.core.actions import ToolMetadata
from app.storage.action_store import ActionStore


def executor(tmp_path, callback):
    return ActionExecutor(None, ToolCallGuardrailController(), callback,
                          metadata_for=lambda _: ToolMetadata(default_risk="low"),
                          store=ActionStore(tmp_path / "audit.sqlite3"))


def test_repeated_creation_reuses_receipt_only_within_turn(tmp_path):
    calls = []
    def create(*args):
        calls.append(args)
        return ToolResult(True, "Criada", {"task": {"id": "one", "title": "ler"}})
    run = executor(tmp_path, create)
    for _ in range(3):
        run.execute("task_tool", {"action": "create", "title": "ler"}, "Crie uma tarefa ler")
    assert len(calls) == 1
    run.execute("task_tool", {"action": "create", "title": "andar"}, "Crie uma tarefa andar")
    assert len(calls) == 2


def test_repeated_delete_does_not_report_failure_after_success(tmp_path):
    calls = []
    run = executor(tmp_path, lambda name, args, user: calls.append(args) or ToolResult(True, "Excluída"))
    args = {"action": "delete_list", "title": "Mercado"}
    first = run.execute("checklist_tool", args, "Exclua a checklist Mercado")
    assert run.execute("checklist_tool", args, "Exclua a checklist Mercado") == first
    assert len(calls) == 1
    run.execute("checklist_tool", {"action": "create_list", "title": "Mercado"}, "Crie Mercado")
    run.execute("checklist_tool", args, "Exclua a checklist Mercado")
    assert len(calls) == 3


def test_equivalent_finance_arguments_create_only_one_entry(tmp_path, isolated_lote6_data):
    from datetime import date
    tool = FinanceTool()
    run = executor(tmp_path, lambda name, args, user: tool.execute(args))
    run.execute("finance_tool", {"action": "add", "amount": 1.23, "description": "QA"}, "Registre uma despesa")
    run.execute("finance_tool", {"action": "add", "trans_id": "invented", "amount": 1.23, "type": "expense", "description": "QA", "category": "Outros", "date": date.today().isoformat()}, "Registre uma despesa")
    assert tool.run(action="list", period="all")["totals"]["count"] == 1


@pytest.mark.parametrize("prompt,tool,operation", [
    ("Exclua a tarefa ler", "task_tool", "delete"),
    ("Marque a tarefa ler como concluída", "task_tool", "complete"),
    ("Exclua a checklist Mercado", "checklist_tool", "delete_list"),
    ("Corrija o lançamento de café", "finance_tool", "update"),
])
def test_read_cannot_satisfy_mutation(prompt, tool, operation):
    steps = [{"name": tool, "args": {"action": "list"}, "status": "succeeded"}]
    assert missing_requested_steps(prompt, steps)
    steps.append({"name": tool, "args": {"action": operation}, "status": "succeeded"})
    assert not missing_requested_steps(prompt, steps)


def test_amount_only_edit_preserves_other_fields(tmp_path):
    calls = []
    run = executor(tmp_path, lambda name, args, user: calls.append(args) or ToolResult(True, "Atualizado"))
    run.execute("finance_tool", {"action": "update", "trans_id": "a", "amount": 1.45, "category": "wrong", "type": "income"},
                "Corrija somente o lançamento a para R$1,45")
    assert calls == [{"action": "update", "trans_id": "a", "amount": 1.45}]


def test_task_completion_is_idempotent(isolated_lote6_data):
    tool = TaskTool()
    created = tool.run(action="create", title="Ler", priority=2)
    task_id = created["task"]["id"]
    for _ in range(2):
        assert tool.run(action="complete", task_id=task_id)["task"]["completed"] == 1
    assert tool.run(action="reopen", task_id=task_id)["task"]["completed"] == 0


def test_finance_resolves_description_and_rejects_ambiguity(isolated_lote6_data):
    tool = FinanceTool()
    tool.run(action="add", amount=2, description="café")
    assert tool.run(action="delete", match_description="café")["ok"]
    assert not tool.run(action="delete", trans_id="missing")["ok"]
    tool.run(action="add", amount=2, description="café")
    tool.run(action="add", amount=3, description="café")
    assert not tool.run(action="delete", match_description="café")["ok"]


def test_file_creation_confined_and_no_overwrite(tmp_path):
    from app.domain.file_manager import FileManagerService
    service = FileManagerService(str(tmp_path))
    path = service.create_file("test.txt", "Código 7284")
    assert service.read_file("test.txt") == "Código 7284"
    with pytest.raises(FileExistsError):
        service.create_file("test.txt", "wrong")
    with pytest.raises(ValueError):
        service.create_file("../escape.txt", "wrong")
    assert path.read_text(encoding="utf-8") == "Código 7284"


def test_model_receives_record_ids():
    result = ToolResult(True, "1 tarefa", {"tasks": [{"id": "task_123", "title": "Ler"}]})
    assert "task_123" in result.model_observation()


def test_legacy_tasks_import_once_without_resurrection(isolated_lote6_data):
    from app.storage import task_store
    from app.services.tasks import TaskService
    from pathlib import Path
    legacy = task_store.add_task("Antiga", priority="high")
    original = Path(task_store.TASKS_FILE).read_bytes()
    imported = TaskService.get_task(legacy["id"])
    assert imported["priority"] == 2 and imported["title"] == "Antiga"
    assert TaskTool().run(action="complete", title="Antiga")["task"]["completed"] == 1
    assert TaskService.delete_task(legacy["id"])
    assert TaskService.get_task(legacy["id"]) is None
    assert Path(task_store.TASKS_FILE).read_bytes() == original


def test_financial_edit_has_receipt_and_keeps_category(isolated_lote6_data):
    tool = FinanceTool()
    added = tool.run(action="add", amount=1.23, category="Teste", description="Recibo")
    edited = tool.run(action="update", trans_id=added["trans_ids"][0], amount=1.45)
    assert edited["transaction"]["category"] == "Teste"
    receipt = edited["finance_receipt"]
    assert receipt["after"] - receipt["before"] == pytest.approx(-0.22)


def test_checklist_with_requested_items_cannot_be_created_empty(tmp_path):
    calls = []
    run = executor(tmp_path, lambda *args: calls.append(args) or ToolResult(True, "Criada"))
    result = run.execute("checklist_tool", {"action": "create_list", "title": "Mercado"}, "Crie uma checklist Mercado com Café e Papel")
    assert not calls and "não foi criada" in result


def test_cooldown_is_not_missing_key(monkeypatch):
    from app.services import llm
    rotator = llm.KeyRotator()
    monkeypatch.setattr(llm, "_key_rotator", rotator)
    service = llm.LLMService(SimpleNamespace(groq_api_key="dummy"))
    rotator.mark_cooldown("dummy", 30)
    assert not service._api_key_for("groq")
    assert "429" in service.unavailable_reason("groq")
    assert "não encontrada" not in service.unavailable_reason("groq")


def test_documentation_search_refines_irrelevant_results(monkeypatch):
    from app.agent.tools import web_search
    calls = []
    def search(query, limit):
        calls.append(query)
        return [{"title": "Python" if len(calls) == 1 else "pathlib reference", "url": "https://docs.python.org/3/library/pathlib.html" if len(calls) > 1 else "https://python.org", "snippet": "Python language reference documentation"}]
    monkeypatch.setattr(web_search, "_search", search)
    results, _, _ = web_search.search_with_refinement("Python pathlib official documentation")
    assert len(calls) == 2 and "pathlib" in results[0]["title"]
    assert "noticias" not in calls[1]
