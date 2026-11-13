from types import SimpleNamespace

from app.agent.context_budget import memory_notes, conversation_messages
from app.agent.loop_policy import requires_tool_action
from app.agent.tools.registry import ToolRegistry


def test_budget_preserves_rules_profile_and_last_request():
    from app.agent.context_budget import fit_request, estimate_tokens
    rows = [{"role": "system", "content": "Regras\n## Perfil essencial do usuário\nJean"},
            {"role": "user", "content": "antigo" * 10000},
            {"role": "assistant", "content": "resposta"},
            {"role": "user", "content": "crie hábitos às 5h"}]
    tools = [{"name": "unused", "parameters": {"description": "x" * 20000}},
             {"name": "personal_records", "parameters": {"type": "object"}}]
    fitted, kept = fit_request(rows, tools)
    assert estimate_tokens(fitted, kept) <= 6000
    assert fitted[0] == rows[0] and fitted[-1] == rows[-1]
    assert [t["name"] for t in kept] == ["personal_records"]
    assert len(rows) == 4


def test_irreducible_request_is_never_silently_truncated():
    from app.agent.context_budget import fit_request, estimate_tokens
    rows = [{"role": "user", "content": "restrição " * 10000}]
    fitted, kept = fit_request(rows)
    assert fitted == rows and estimate_tokens(fitted, kept) > 6000


def test_memory_is_bounded_and_deduplicated():
    result = memory_notes(["Ler livros", " ler  LIVROS "] + [str(i) * 400 for i in range(30)])
    assert result.count("Ler livros") == 1
    assert len(result) <= 2400


def test_style_filter_preserves_uncertainty_and_sources():
    from app.services.stm_filters import stm_filter
    text = "Acho que é compatível; se eu não me engano, depende da versão.\nFonte: https://example.org/doc"
    assert stm_filter.process(text) == text


def test_context_keeps_latest_request_and_removes_ui_metadata():
    latest = "pedido com restrições " * 100
    rows = [{"role": "assistant", "content": "antigo" * 400}, {"role": "user", "content": latest, "activity": [{"tool": "fake"}]}]
    assert conversation_messages(rows, 100) == [{"role": "user", "content": latest}]
    assert requires_tool_action("Abra o Spotify")
    assert not requires_tool_action("Como abrir o Spotify?")
    assert not requires_tool_action("Crie um poema")


def test_playback_request_keeps_browser_search_and_spotify_in_loop():
    registry = ToolRegistry.__new__(ToolRegistry)
    registry.tools = {n: SimpleNamespace() for n in ["spotify", "browser", "web_search", "open_windows_app", "media_tool", "wait"]}
    allowed = registry.allowed_tool_names(provider="groq", user_text="Abra o spotify, aguarde 10 segundos e abra um video aleatório no youtube", narrow=True)
    assert {"spotify", "browser", "web_search", "wait"} <= allowed


def test_portuguese_clipboard_requests_offer_the_tool():
    registry = ToolRegistry.__new__(ToolRegistry)
    registry.tools = {n: SimpleNamespace() for n in ["clipboard", "memory", "web_search"]}
    for text in ("Copie o texto TESTE", "copia para a área de transferência", "leia a area de transferencia"):
        for narrow in (True, False):
            assert "clipboard" in registry.allowed_tool_names(provider="groq", user_text=text, narrow=narrow)


def test_context_usage_survives_history_reload_and_stale_client(tmp_path, monkeypatch):
    from app.storage import session_store
    monkeypatch.setattr(session_store, 'SESSIONS_FILE', str(tmp_path / 'sessions.json'))
    usage = [{'provider': 'groq', 'model': 'test', 'estimated_tokens': 100,
              'before_tokens': 200, 'budget': 6000, 'reduced': True}]
    session_store.save_turn('test', 'run-test', 'oi', 'olá', timestamp=1, context_usage=usage)
    history = session_store.get_session_history('test')
    assert history[-1]['meta']['context_usage'] == usage
    stale = [{key: value for key, value in row.items() if key != 'meta'} for row in history]
    session_store.save_session_history('test', stale)
    assert session_store.get_session_history('test')[-1]['meta']['context_usage'] == usage
