from app.agent.orchestrator import AgentOrchestrator
from app.config import Settings
from app.services.llm import LLMService
from app.storage.enem_store import EnemStore


def test_resolve_enem_context_from_id(tmp_path) -> None:
    enem_store = EnemStore(storage_dir=str(tmp_path / "enem"))
    question = enem_store.save_question({
        "text": "Qual é a raiz de 144?",
        "subject": "matematica",
        "year": 2020,
    })
    settings = Settings()
    llm = LLMService(settings=settings)
    orchestrator = AgentOrchestrator(settings=settings, llm_service=llm, enem_store=enem_store)

    resolved = orchestrator._resolve_enem_context(None, question["id"])
    assert resolved is not None
    assert resolved["text"] == "Qual é a raiz de 144?"
    assert resolved["subject"] == "matematica"


def test_resolve_enem_context_prefers_inline(tmp_path) -> None:
    enem_store = EnemStore(storage_dir=str(tmp_path / "enem"))
    saved = enem_store.save_question({"text": "Do banco", "subject": "linguagens"})
    settings = Settings()
    llm = LLMService(settings=settings)
    orchestrator = AgentOrchestrator(settings=settings, llm_service=llm, enem_store=enem_store)

    inline = {"text": "Colada agora", "subject": "matematica"}
    resolved = orchestrator._resolve_enem_context(inline, saved["id"])
    assert resolved["text"] == "Colada agora"


def test_enem_prefix_without_api_key(tmp_path) -> None:
    enem_store = EnemStore(storage_dir=str(tmp_path / "enem"))
    settings = Settings()
    settings.gemini_api_key = ""
    llm = LLMService(settings=settings)
    orchestrator = AgentOrchestrator(settings=settings, llm_service=llm, enem_store=enem_store)

    plan = orchestrator.handle_request(
        "Me ajude",
        mode="tutor",
        enem_context={"text": "2+2=?", "subject": "matematica", "year": 2021},
    )
    assert plan.intent == "general"
    assert "GEMINI_API_KEY" in plan.summary
