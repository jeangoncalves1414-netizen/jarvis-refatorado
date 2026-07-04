from app.agent.router import AgentRouter
from app.domain.memory import MemoryStore
from app.domain.tasks import TaskStore
from app.ui.panel.app import PanelView


def test_router_creates_task_and_remembers_note(tmp_path) -> None:
    task_store = TaskStore()
    memory_store = MemoryStore(storage_path=str(tmp_path / "memory.json"))
    router = AgentRouter(task_store=task_store, memory_store=memory_store)

    response = router.handle_message("Crie uma tarefa de estudar python")
    note_response = router.handle_message("Lembre que eu prefiro respostas curtas")

    assert response.intent == "task"
    assert task_store.list_tasks()[0].title == "estudar python"
    assert note_response.intent == "memory"
    assert memory_store.get_preferences()[0]["value"] == "short"


def test_panel_view_renders_snapshot() -> None:
    view = PanelView()
    html = view.render(
        status="online",
        task_count=2,
        memory_count=1,
        last_message="Tarefa criada",
    )

    assert "online" in html.lower()
    assert "Tarefa criada" in html
    assert "2" in html
