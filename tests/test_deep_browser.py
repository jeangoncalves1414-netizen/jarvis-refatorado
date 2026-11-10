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


def test_multi_hop_refinement_triggered_on_generic_results():
    from app.agent.tools.web_search import search_with_refinement, WebSearchTool

    # Hop 1 (genérico/dicionário) -> Hop 2 (notícias reais)
    hop1_generic = [
        {"title": "Significado de Bluezão", "url": "https://www.dicio.com.br/bluezao", "source": "dicio.com.br", "snippet": "Significado no dicionário."},
        {"title": "Bluezão Instagram", "url": "https://www.instagram.com/bluezao", "source": "instagram.com", "snippet": "Fotos e vídeos."},
    ]
    hop2_news = [
        {"title": "Bluezão se envolve em polêmica na internet", "url": "https://g1.globo.com/pop-arte/noticia/2026/01/bluezao.ghtml", "source": "g1.globo.com", "snippet": "O influenciador Bluezão foi assunto nos principais portais nesta semana após transmissão ao vivo."},
    ]

    calls = []

    def fake_search(q, limit):
        calls.append(q)
        if "noticias" in q or "ultimas" in q:
            return hop2_news
        return hop1_generic

    with patch("app.agent.tools.web_search._search", side_effect=fake_search):
        results, steps, final_q = search_with_refinement("bluezão", limit=3, max_hops=3)

        # Garante que refinou automaticamente ao detectar apenas dicionário/rede social
        assert len(calls) >= 2
        assert any("noticias" in c or "ultimas" in c for c in calls)
        assert results == hop2_news
        assert any("Refinamento iterativo" in s["label"] for s in steps)


def test_multi_hop_early_stopping():
    from app.agent.tools.web_search import search_with_refinement

    # Resultados já informativos logo no Hop 1
    hop1_informative = [
        {"title": "Lançamento da IA Gemini Flash", "url": "https://g1.globo.com/tecnologia/noticia/ia.ghtml", "source": "g1.globo.com", "snippet": "Nova versão multimodal lançada oficialmente com capacidade de vídeo."},
    ]

    calls = []

    def fake_search(q, limit):
        calls.append(q)
        return hop1_informative

    with patch("app.agent.tools.web_search._search", side_effect=fake_search):
        results, steps, final_q = search_with_refinement("gemini flash", limit=3, max_hops=3)

        # Sabe quando parar: apenas 1 chamada feita, sem desperdício de hops adicionais
        assert len(calls) == 1
        assert results == hop1_informative
        assert len(steps) == 1
        assert steps[0]["label"] == "Busca inicial"


def test_web_search_synthesis_no_raw_links_dump():
    from app.agent.tools.web_search import WebSearchTool

    fake_news = [
        {"title": "Notícia Relevante 1", "url": "https://portal.com.br/noticia1", "source": "portal.com.br", "snippet": "Primeiro fato apurado sobre o ocorrido."},
        {"title": "Notícia Relevante 2", "url": "https://jornal.com.br/noticia2", "source": "jornal.com.br", "snippet": "Segundo fato com detalhes adicionais."},
    ]

    tool = WebSearchTool()
    with patch("app.agent.tools.web_search._search", return_value=fake_news):
        res = tool.execute({"action": "search", "query": "assunto importante"})

        assert res.ok is True
        msg = res.message
        # Deve conter síntese e fatos
        assert "Síntese informativa" in msg
        assert "Primeiro fato apurado" in msg
        assert "Segundo fato com detalhes adicionais" in msg
        # NUNCA deve conter despejos brutos robóticos
        assert "Resultados das ferramentas:" not in msg
        assert "Link: https://" not in msg


def test_stm_filter_removes_robotic_tool_headers():
    from app.services.stm_filters import stm_filter

    robotic_output = (
        "Resultados das ferramentas:\n"
        "Link: https://www.dicio.com.br/bluezao\n"
        "Bluezão é um influenciador digital conhecido por seus vídeos na internet."
    )

    cleaned = stm_filter.process(robotic_output)
    assert "Resultados das ferramentas:" not in cleaned
    assert "Link: https://" not in cleaned
    assert cleaned.startswith("Bluezão é um influenciador")


def test_tool_declarations_never_have_duplicates(tmp_path):
    from app.agent.tools.registry import ToolRegistry

    registry = ToolRegistry(base_folder=str(tmp_path))
    declarations = registry.get_tool_declarations(mode="general")
    names = [d["name"] for d in declarations]
    
    assert len(names) == len(set(names)), f"Ferramentas duplicadas encontradas: {[n for n in set(names) if names.count(n) > 1]}"
    assert names.count("browser") == 1


def test_gemini_tool_declarations_defensive_dedup():
    from app.services.llm import LLMService

    llm = LLMService(settings=MagicMock())
    # Lista propositalmente com ferramentas duplicadas
    duplicate_tools = [
        {"name": "web_search", "description": "Busca 1", "parameters": {}},
        {"name": "browser", "description": "Browser 1", "parameters": {}},
        {"name": "browser", "description": "Browser 2", "parameters": {}},
        {"name": "web_search", "description": "Busca 2", "parameters": {}},
    ]

    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = MagicMock(text="Resposta ok", candidates=[])

        # Executa _generate_gemini
        llm._generate_gemini(
            contents="teste",
            tools=duplicate_tools,
            system_instruction="teste",
            api_key="fake-key",
        )

        # Inspeciona chamada do generate_content
        call_kwargs = mock_client.models.generate_content.call_args[1]
        config = call_kwargs.get("config")
        assert config is not None
        assert len(config.tools) == 1
        tool_decl_names = [d.name for d in config.tools[0].function_declarations]
        assert len(tool_decl_names) == 2
        assert sorted(tool_decl_names) == ["browser", "web_search"]



