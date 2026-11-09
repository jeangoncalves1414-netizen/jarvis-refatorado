"""Testes para extração limpa de texto, snapshots interativos e deep search."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from app.agent.tools.base import ToolResult
from app.agent.tools.browser_agent import BrowserAgentTool
from app.services.browser import (
    BrowserService,
    extract_clean_text,
    get_interactive_snapshot,
)


SAMPLE_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Notícias de Tecnologia 2026</title>
    <style>
        .ad { color: red; font-size: 10px; }
        .sidebar { background: #eee; }
    </style>
    <script>
        console.log("tracking script");
    </script>
</head>
<body>
    <header>
        <nav>
            <a href="/">Início</a>
            <a href="/sobre">Sobre Nós</a>
            <a href="/contato">Contato</a>
        </nav>
    </header>

    <div class="cookie-banner">
        <p>Utilizamos cookies para melhorar sua experiência. <button id="btn-cookie">Aceitar Cookies</button></p>
    </div>

    <div class="advertisement">
        <p>Anúncio Patrocinado: Compre o Novo Teclado Mecânico com 40% OFF!</p>
    </div>

    <main>
        <article>
            <h1>Revolução dos Agentes Multimodais em 2026</h1>
            <p>Os novos sistemas autônomos agora combinam visão computacional de alta fidelidade com processamento direto de arquivos de vídeo e navegação profunda no DOM.</p>
            <p>Com a eliminação de ruídos como banners de cookies e menus, a extração de artigos atinge precisão superior a 99% sem estourar o limite de tokens dos modelos de linguagem.</p>
        </article>
        <section>
            <h2>Interação com Usuário</h2>
            <form action="/login" method="post">
                <label for="username">Usuário:</label>
                <input type="text" id="username" name="username" placeholder="Digite seu usuário">
                <label for="pwd">Senha:</label>
                <input type="password" id="pwd" name="pwd" placeholder="Digite sua senha">
                <button type="submit" id="btn-submit">Entrar no Sistema</button>
            </form>
        </section>
    </main>

    <aside class="sidebar">
        <h3>Outros Artigos</h3>
        <p>Veja as novidades da semana passada...</p>
    </aside>

    <footer>
        <p>&copy; 2026 Portal Tech. Todos os direitos reservados.</p>
    </footer>
</body>
</html>
"""


def test_extract_clean_text_from_html_string():
    clean_text = extract_clean_text(SAMPLE_HTML)

    # Conteúdo principal deve estar presente
    assert "Revolução dos Agentes Multimodais em 2026" in clean_text
    assert "Os novos sistemas autônomos agora combinam visão computacional" in clean_text
    assert "extração de artigos atinge precisão superior a 99%" in clean_text

    # Ruídos visuais e estruturais devem ser removidos
    assert "console.log" not in clean_text
    assert "tracking script" not in clean_text
    assert ".ad {" not in clean_text
    assert "Anúncio Patrocinado" not in clean_text
    assert "Utilizamos cookies" not in clean_text
    assert "Sobre Nós" not in clean_text
    assert "Todos os direitos reservados" not in clean_text


def test_extract_clean_text_with_playwright_mock():
    mock_page = MagicMock()
    mock_page.evaluate.return_value = "Artigo limpo extraído via JavaScript do DOM."

    result = extract_clean_text(mock_page)
    assert result == "Artigo limpo extraído via JavaScript do DOM."
    mock_page.evaluate.assert_called_once()


def test_get_interactive_snapshot_from_html_string():
    snapshot = get_interactive_snapshot(SAMPLE_HTML)

    assert isinstance(snapshot, list)
    assert len(snapshot) > 0

    # Verifica se os botões e inputs foram identificados com numeração
    labels = [item["label"] for item in snapshot]

    # Verifica Botão Entrar ou Aceitar
    assert any("Entrar no Sistema" in l or "btn-submit" in l for l in labels)
    # Verifica Campos de input
    assert any("Digite seu usuário" in l or "username" in l for l in labels)
    assert any("Digite sua senha" in l or "pwd" in l for l in labels)

    # Verifica formato do rótulo [N] Tipo 'Nome'
    for item in snapshot:
        assert item["label"].startswith(f"[{item['id']}]")
        assert "kind" in item
        assert "text" in item


def test_get_interactive_snapshot_with_playwright_mock():
    mock_page = MagicMock()
    mock_page.evaluate.return_value = [
        {"id": 1, "label": "[1] Botão 'Entrar'", "kind": "Botão", "text": "Entrar"},
        {"id": 2, "label": "[2] Campo 'Pesquisar'", "kind": "Campo", "text": "Pesquisar"},
    ]

    snapshot = get_interactive_snapshot(mock_page)
    assert len(snapshot) == 2
    assert snapshot[0]["label"] == "[1] Botão 'Entrar'"
    assert snapshot[1]["label"] == "[2] Campo 'Pesquisar'"


def test_browser_service_deep_search():
    service = BrowserService()

    fake_search_items = [
        {"title": "Doc Oficial IA 2026", "url": "https://ia.local/doc", "source": "ia.local", "snippet": "Resumo doc."},
        {"title": "Artigo Multimodal", "url": "https://portal.local/artigo", "source": "portal.local", "snippet": "Resumo artigo."},
    ]

    fake_llm_response = (
        "Síntese aprofundada: os agentes em 2026 utilizam navegação limpa no DOM [Doc Oficial IA 2026 - https://ia.local/doc] "
        "e modelos multimodais de vídeo [Artigo Multimodal - https://portal.local/artigo]."
    )

    with patch("app.agent.tools.web_search._fallback_search", return_value=fake_search_items), \
         patch("app.services.llm.LLMService.ask", return_value=fake_llm_response):

        res = service.deep_search(query="inteligência artificial multimodal 2026", max_sites=2)

        assert res["ok"] is True
        assert res["query"] == "inteligência artificial multimodal 2026"
        assert "[Doc Oficial IA 2026 - https://ia.local/doc]" in res["synthesis"]
        assert len(res["sources"]) == 2


def test_browser_agent_tool_deep_search_action():
    tool = BrowserAgentTool()

    mock_service = MagicMock()
    mock_service.deep_search.return_value = {
        "ok": True,
        "query": "modelos de vídeo",
        "synthesis": "Síntese com fontes [Fonte 1 - https://exemplo.com].",
        "sources": [{"title": "Fonte 1", "url": "https://exemplo.com", "source": "exemplo.com"}],
    }

    context = {"browser": mock_service}

    result = tool.execute({"action": "deep_search", "query": "modelos de vídeo"}, context=context)
    assert result.ok is True
    assert "Síntese com fontes" in result.message
    mock_service.deep_search.assert_called_once_with(query="modelos de vídeo", max_sites=3)


def test_browser_agent_tool_clean_text_action():
    tool = BrowserAgentTool()

    mock_service = MagicMock()
    mock_service.navigate.return_value = {"ok": True}
    mock_service.extract_clean_text.return_value = "Texto totalmente limpo do artigo principal."

    context = {"browser": mock_service}

    result = tool.execute({"action": "clean_text", "url": "https://noticia.local/artigo"}, context=context)
    assert result.ok is True
    assert "Texto totalmente limpo" in result.message
    mock_service.navigate.assert_called_once_with("https://noticia.local/artigo")
    mock_service.extract_clean_text.assert_called_once()


def test_browser_agent_tool_interactive_snapshot_action():
    tool = BrowserAgentTool()

    mock_service = MagicMock()
    mock_service.navigate.return_value = {"ok": True}
    mock_service.get_interactive_snapshot.return_value = [
        {"id": 1, "label": "[1] Botão 'Entrar'"},
        {"id": 2, "label": "[2] Campo 'Email'"},
    ]

    context = {"browser": mock_service}

    result = tool.execute({"action": "interactive_snapshot", "url": "https://app.local"}, context=context)
    assert result.ok is True
    assert "[1] Botão 'Entrar'" in result.message
    assert "[2] Campo 'Email'" in result.message
    assert len(result.data["elements"]) == 2


def test_browser_agent_tool_click_and_type_element():
    tool = BrowserAgentTool()

    mock_service = MagicMock()
    mock_service.click_interactive_element.return_value = {"ok": True, "message": "Elemento [1] clicado."}
    mock_service.type_interactive_element.return_value = {"ok": True, "message": "Texto digitado no elemento [2]."}

    context = {"browser": mock_service}

    # Teste clique numerado
    res_click = tool.execute({"action": "click_element", "element_id": 1}, context=context)
    assert res_click.ok is True
    mock_service.click_interactive_element.assert_called_once_with(1)

    # Teste digitação numerada
    res_type = tool.execute({"action": "type_element", "element_id": 2, "text": "Jarvis User"}, context=context)
    assert res_type.ok is True
    mock_service.type_interactive_element.assert_called_once_with(2, text="Jarvis User")

