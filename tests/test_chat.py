from app.agent.orchestrator import AgentOrchestrator
from app.config import Settings
from app.domain.actions import FileActionService
from app.domain.chat import ChatSession
from app.domain.productivity import ProductivityService
from app.services.llm import LLMService
from app.storage.memory_store import MemoryStore


def test_chat_session_records_user_and_assistant_messages(tmp_path, isolated_conversation_journal) -> None:
    settings = Settings()
    llm = LLMService(settings=settings)
    memory_store = MemoryStore(storage_path=str(tmp_path / "memory.json"))
    productivity_service = ProductivityService()
    orchestrator = AgentOrchestrator(
        settings=settings,
        llm_service=llm,
        memory_store=memory_store,
        file_action_service=FileActionService(base_folder=str(tmp_path)),
        productivity_service=productivity_service,
    )

    chat = ChatSession(orchestrator=orchestrator)
    reply = chat.handle_message("Adicione uma tarefa de estudar python")

    assert reply["intent"] == "productivity"
    assert len(chat.get_messages()) == 2
    assert chat.get_messages()[0]["role"] == "user"
    assert chat.get_messages()[1]["role"] == "assistant"
    assert "estudar python" in reply["message"].lower()
