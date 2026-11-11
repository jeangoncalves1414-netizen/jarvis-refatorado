from types import SimpleNamespace

from app.agent.context_budget import memory_notes, conversation_messages
from app.agent.loop_policy import requires_tool_action
from app.agent.tools.registry import ToolRegistry


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
