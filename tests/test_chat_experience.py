from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
import pytest

from app.agent import turn_meta
from app.agent.tool_activity import action_description, emit_activity, public_sources, record_memory_lookup
from app.agent.tools.base import ToolResult
from app.core.model_routing import current_model_mode, route_key
from app.services.llm import LLMService
from app.storage import runtime_settings, session_store


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime_settings, "RUNTIME_SETTINGS_FILE", str(tmp_path / "runtime.json"))
    monkeypatch.setattr(session_store, "SESSIONS_FILE", str(tmp_path / "sessions.json"))
    monkeypatch.setattr("app.storage.action_store.action_store", SimpleNamespace(run_page=lambda **kw: {"runs": []}))
    for provider in ("GEMINI", "GROQ", "OXYY"):
        monkeypatch.setenv(provider + "_API_KEY", "test-key")
    monkeypatch.setenv("LLM_PROVIDER", "groq")


def test_mode_models_are_persisted_inherited_and_isolated(isolated):
    runtime_settings.set_ai_routes({"chat": {"provider": "groq", "model": "chat-test"}, "thinking": {"provider": "gemini", "model": "think-test"}, "voice": {"provider": "oxyy", "model": "voice-test"}})
    service = LLMService(SimpleNamespace(llm_provider="groq"))
    def resolve(mode, origin="chat"):
        token = current_model_mode.set(route_key(mode, origin))
        try:
            return service.get_active_provider(), service._effective_chat_model()
        finally:
            current_model_mode.reset(token)
    with ThreadPoolExecutor(3) as pool:
        results = list(pool.map(lambda args: resolve(*args), [("thinking",), ("general", "voice"), ("research",)]))
    assert results == [("gemini", "think-test"), ("oxyy", "voice-test"), ("groq", "chat-test")]
    assert current_model_mode.get() == "chat"
    runtime_settings.set_ai_routes({"thinking": {"inherit": True}})
    assert resolve("thinking") == ("groq", "chat-test")


def test_edit_cuts_persisted_context_and_rejects_stale_or_pending(isolated, monkeypatch):
    rows = [{"role": "user", "content": "primeira"}, {"role": "assistant", "content": "resposta"}, {"role": "user", "content": "segunda"}, {"role": "assistant", "content": "posterior"}]
    session_store.save_session_history("s", rows)
    assert session_store.truncate_session_history("s", 2, rows) == rows[:2]
    assert session_store.get_session_history("s") == rows[:2]
    with pytest.raises(ValueError, match="mudou"):
        session_store.truncate_session_history("s", 0, rows)
    with pytest.raises(ValueError, match="mensagem sua"):
        session_store.truncate_session_history("s", 1, rows[:2])
    monkeypatch.setattr("app.storage.action_store.action_store", SimpleNamespace(run_page=lambda **kw: {"runs": [{}]}))
    with pytest.raises(ValueError, match="pendente"):
        session_store.truncate_session_history("s", 0, rows[:2])
    assert session_store.get_session_history("s") == rows[:2]


def test_activity_receipts_replace_running_and_only_include_public_sources(monkeypatch):
    events = []
    monkeypatch.setattr("app.core.ui_events.publish", events.append)
    token = turn_meta.start()
    try:
        action = SimpleNamespace(id="a", tool_name="web_search", status="running", run_id="r")
        emit_activity(action, "s")
        action.status = "succeeded"
        emit_activity(action, "s", {"results": [{"url": "https://example.org/page?token=secret", "title": "Fonte", "read_status": "read"}, {"url": "javascript:alert(1)"}, {"url": "https://user:pass@example.org"}]})
        assert [e["activity"]["status"] for e in events] == ["running", "succeeded"]
        [receipt] = turn_meta.snapshot()["tool_activity"]
        assert receipt["sources"] == [{"url": "https://example.org/page", "title": "Fonte", "read": True}]
        assert "memory_lookup" not in turn_meta.snapshot()
        record_memory_lookup("vault_search", ToolResult(True, "Uma nota", {"results": [{"title": "Projeto", "snippet": "Plano"}]}))
        assert turn_meta.snapshot()["memory_lookup"]["items"][0]["text"] == "Plano"
        assert public_sources({"results": 123}) == []
        assert public_sources({"url": "https://example.org/article?id=42&api_key=hidden"})[0]["url"] == "https://example.org/article?id=42"
    finally:
        turn_meta.reset(token)


def test_tool_labels_separate_open_from_search_and_hide_url_secrets():
    opened = action_description("web_search", {"action": "open_url", "query": "https://user:secret@www.roblox.com/path?token=private"})
    assert opened == {"label": "Abrir www.roblox.com", "speech": "Abrindo Roblox.", "completion": "Abri Roblox."}
    assert action_description("web_search", {"query": "Roblox.com"})["speech"] == "Pesquisando na web."
    assert action_description("wait", {"seconds": 10})["speech"] == "Aguardando 10 segundos."
