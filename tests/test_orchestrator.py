import pytest
from app.agent.orchestrator import AgentOrchestrator
from app.config import Settings
from app.domain.productivity import ProductivityService
from app.domain.actions import FileActionService
from app.services.llm import LLMService
from app.storage.memory_store import MemoryStore

pytestmark = pytest.mark.usefixtures("isolated_conversation_journal")


def test_orchestrator_detects_file_intent(tmp_path) -> None:
    settings = Settings()
    llm = LLMService(settings=settings)
    orchestrator = AgentOrchestrator(settings=settings, llm_service=llm, file_action_service=FileActionService(str(tmp_path)))

    (tmp_path / "Downloads").mkdir()
    plan = orchestrator.handle_request("Liste meus arquivos na pasta Downloads")
    assert plan.intent == "file"
    assert "arquivos" in plan.summary.lower()
    assert plan.actions


def test_orchestrator_detects_productivity_intent() -> None:
    settings = Settings()
    llm = LLMService(settings=settings)
    orchestrator = AgentOrchestrator(settings=settings, llm_service=llm)

    plan = orchestrator.handle_request("Adicione uma tarefa de estudar python")
    assert plan.intent == "productivity"
    assert plan.actions == ["create_local_task"]


def test_orchestrator_remembers_preferences(tmp_path) -> None:
    settings = Settings()
    llm = LLMService(settings=settings)
    memory_store = MemoryStore(storage_path=str(tmp_path / "memory.json"))
    orchestrator = AgentOrchestrator(settings=settings, llm_service=llm, memory_store=memory_store)

    plan = orchestrator.handle_request("Me lembre que eu prefiro respostas curtas")

    assert plan.intent == "general"
    assert memory_store.get_preferences()
    assert any(item["key"] == "preferred_response_style" for item in memory_store.get_preferences())


def test_orchestrator_creates_productivity_tasks() -> None:
    settings = Settings()
    llm = LLMService(settings=settings)
    productivity_service = ProductivityService()
    orchestrator = AgentOrchestrator(
        settings=settings,
        llm_service=llm,
        productivity_service=productivity_service,
    )

    plan = orchestrator.handle_request("Adicione uma tarefa de estudar python")

    assert plan.intent == "productivity"
    assert productivity_service.list_tasks()
    assert productivity_service.list_tasks()[0].title == "estudar python"
