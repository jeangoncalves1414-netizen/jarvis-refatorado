"""Testes unitários e de integração para BrowserService e BrowserTool."""
from __future__ import annotations

import http.server
import socketserver
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from app.agent.tools.base import ToolResult
from app.agent.tools.browser_tool import BrowserTool
from app.agent.tools.catalog import TOOL_CATALOG
from app.agent.tools.registry import ToolRegistry, GENERAL_TOOL_NAMES
from app.services.browser import BrowserService, get_browser_service, close_browser_service
from app.storage.runtime_settings import get_browser_settings, set_browser_settings


# ---------------------------------------------------------------------------
# Testes do Catálogo e Action Kernel
# ---------------------------------------------------------------------------

def test_browser_tool_catalog_metadata():
    """Verifica mapeamento de risco do Action Kernel para a ferramenta de navegador."""
    assert "browser" in TOOL_CATALOG
    metadata = TOOL_CATALOG["browser"]

    assert metadata.capabilities == ("browser", "automation")
    assert metadata.default_operation == "extract"

    # Mapeamento estrito de risco:
    # Leituras e observações -> observe
    assert metadata.risk_for({"action": "navigate", "url": "https://example.com"}) == "observe"
    assert metadata.risk_for({"action": "extract"}) == "observe"
    assert metadata.risk_for({"action": "extract_content"}) == "observe"
    assert metadata.risk_for({"action": "search_and_extract", "query": "preco"}) == "observe"
    assert metadata.risk_for({"action": "screenshot"}) == "observe"

    # Ações ativas com efeito -> low ou high
    assert metadata.risk_for({"action": "click", "selector": "#btn"}) == "low"
    assert metadata.risk_for({"action": "fill_form", "fields": {"#input": "val"}}) == "high"

    # Ação desconhecida -> critical
    assert metadata.risk_for({"action": "execute_arbitrary_js"}) == "critical"

    # Alias browser_tool possui o mesmo mapeamento
    assert "browser_tool" in TOOL_CATALOG
    assert TOOL_CATALOG["browser_tool"].risk_for({"action": "extract"}) == "observe"


def test_browser_tool_properties():
    tool = BrowserTool()
    assert tool.name == "browser"
    assert "Playwright" in tool.description
    assert "web_search.open_url" in tool.description
    assert "action" in tool.parameters["properties"]
    assert "required" in tool.parameters
    assert "action" in tool.parameters["required"]


def test_tool_registry_contains_browser(tmp_path):
    registry = ToolRegistry(base_folder=str(tmp_path))
    assert "browser" in registry.tools
    assert "browser_tool" in registry.tools
    assert "browser" in GENERAL_TOOL_NAMES
    assert isinstance(registry.tools["browser"], BrowserTool)


# ---------------------------------------------------------------------------
# Testes de Configurações em Runtime
# ---------------------------------------------------------------------------

def test_browser_runtime_settings():
    initial = get_browser_settings()
    assert "headless" in initial
    assert "timeout_seconds" in initial

    # Atualiza configurações
    updated = set_browser_settings({"headless": False, "timeout_seconds": 20})
    assert updated["headless"] is False
    assert updated["timeout_seconds"] == 20

    # Validação de erros
    with pytest.raises(ValueError, match="headless"):
        set_browser_settings({"headless": "not_bool"})  # type: ignore

    with pytest.raises(ValueError, match="tempo limite"):
        set_browser_settings({"timeout_seconds": 999})

    # Restaura padrão
    restored = set_browser_settings({"headless": True, "timeout_seconds": 15})
    assert restored["headless"] is True
    assert restored["timeout_seconds"] == 15


# ---------------------------------------------------------------------------
# Testes Unitários de BrowserService com Mocks
# ---------------------------------------------------------------------------

def test_browser_service_timeout_clamp():
    service = BrowserService(timeout_ms=30000)
    # Deve ser limitado ao teto defensivo de 15000ms
    assert service.timeout_ms <= 15000


def test_browser_service_navigate_mock():
    service = BrowserService()
    mock_page = MagicMock()
    mock_page.url = "https://example.com"
    mock_page.title.return_value = "Example Domain"
    mock_response = MagicMock()
    mock_response.status = 200
    mock_page.goto.return_value = mock_response

    with patch.object(service, "ensure_page", return_value=mock_page):
        res = service.navigate("example.com")
        assert res["ok"] is True
        assert res["url"] == "https://example.com"
        assert res["title"] == "Example Domain"
        mock_page.goto.assert_called_once_with("https://example.com", wait_until="domcontentloaded", timeout=service.timeout_ms)


def test_browser_service_extract_content_mock():
    service = BrowserService()
    mock_page = MagicMock()
    mock_page.url = "https://example.com/test"
    mock_page.title.return_value = "Test Title"
    mock_page.evaluate.return_value = {
        "found": True,
        "text": "Linha 1 com texto\n\nLinha 2 com mais texto",
        "headings": [{"tag": "h1", "text": "Heading 1"}],
        "links": [{"text": "Link 1", "href": "https://example.com/l1"}]
    }

    with patch.object(service, "ensure_page", return_value=mock_page):
        res = service.extract_content()
        assert res["ok"] is True
        assert "Linha 1" in res["text"]
        assert len(res["headings"]) == 1
        assert len(res["links"]) == 1


def test_browser_service_search_and_extract_mock():
    service = BrowserService()
    mock_page = MagicMock()
    mock_page.url = "https://loja.local/produto"
    mock_page.title.return_value = "Produto X"

    content_mock = {
        "ok": True,
        "url": "https://loja.local/produto",
        "title": "Produto X",
        "text": "Smartphone Modelo X com 128GB de memória interna.\nO preço promocional é R$ 1.899,00 à vista no cartão."
    }

    with patch.object(service, "ensure_page", return_value=mock_page), \
         patch.object(service, "extract_content", return_value=content_mock):
        res = service.search_and_extract("preço smartphone")
        assert res["ok"] is True
        assert len(res["matches"]) > 0
        assert "R$ 1.899,00" in res["prices"]


def test_browser_service_click_mock():
    service = BrowserService()
    mock_page = MagicMock()
    mock_page.url = "https://example.com"
    mock_page.title.return_value = "Example"
    mock_locator = MagicMock()
    mock_page.locator.return_value.first = mock_locator

    with patch.object(service, "ensure_page", return_value=mock_page):
        res = service.click("button#submit")
        assert res["ok"] is True
        assert res["selector"] == "button#submit"
        mock_locator.wait_for.assert_called_once()
        mock_locator.click.assert_called_once()


def test_browser_service_fill_form_mock():
    service = BrowserService()
    mock_page = MagicMock()
    mock_page.url = "https://example.com/login"
    mock_locator = MagicMock()
    mock_locator.count.return_value = 1
    mock_page.locator.return_value.first = mock_locator

    with patch.object(service, "ensure_page", return_value=mock_page):
        res = service.fill_form({"#user": "jarvis", "#pass": "secret123"})
        assert res["ok"] is True
        assert len(res["filled"]) == 2
        assert len(res["failed"]) == 0


def test_browser_service_screenshot_mock(tmp_path):
    service = BrowserService()
    mock_page = MagicMock()
    mock_page.url = "https://example.com"
    mock_page.title.return_value = "Example"
    fake_png = b"\x89PNG\r\n\x1a\nfakecontent"
    mock_page.screenshot.return_value = fake_png

    dest = tmp_path / "shot.png"
    with patch.object(service, "ensure_page", return_value=mock_page):
        res = service.screenshot(path=str(dest))
        assert res["ok"] is True
        assert res["size_bytes"] == len(fake_png)
        assert dest.exists()
        assert dest.read_bytes() == fake_png


# ---------------------------------------------------------------------------
# Testes de Execução do BrowserTool
# ---------------------------------------------------------------------------

def test_native_context_keeps_legacy_agent_out_of_browser_service(monkeypatch):
    from app.services.browser_agent import BrowserAgent
    service = MagicMock(spec=BrowserService)
    service.navigate.return_value = {"ok": True, "message": "Página carregada"}
    monkeypatch.setattr('app.agent.tools.browser_tool.get_browser_service', lambda: service)
    legacy = MagicMock(spec=BrowserAgent)
    result = BrowserTool().execute({'action': 'navigate', 'url': 'https://www.youtube.com/'}, {'browser_agent': legacy})
    assert result.ok
    service.navigate.assert_called_once_with('https://www.youtube.com/')
    legacy.goto.assert_not_called()

def test_browser_tool_execute_dispatch():
    mock_service = MagicMock(spec=BrowserService)
    mock_service.navigate.return_value = {"ok": True, "url": "https://example.com", "title": "Test"}
    mock_service.extract_content.return_value = {"ok": True, "text": "Sample text", "links": []}
    mock_service.search_and_extract.return_value = {"ok": True, "matches": ["Match 1"], "prices": []}
    mock_service.click.return_value = {"ok": True, "selector": "#btn"}
    mock_service.fill_form.return_value = {"ok": True, "filled": [{"selector": "#a", "value": "b"}], "failed": []}
    mock_service.screenshot.return_value = {"ok": True, "filename": "shot.png", "size_bytes": 100}

    tool = BrowserTool(browser_service=mock_service)

    # 1. navigate
    r1 = tool.execute({"action": "navigate", "url": "https://example.com"})
    assert r1.ok is True
    mock_service.navigate.assert_called_once_with("https://example.com")

    # 2. extract
    r2 = tool.execute({"action": "extract", "selector": "#content"})
    assert r2.ok is True
    mock_service.extract_content.assert_called_once_with(selector="#content")

    # 3. search_and_extract
    r3 = tool.execute({"action": "search_and_extract", "query": "smartphone"})
    assert r3.ok is True
    mock_service.search_and_extract.assert_called_once_with(query="smartphone", url=None)

    # 4. click
    r4 = tool.execute({"action": "click", "selector": "#btn"})
    assert r4.ok is True
    mock_service.click.assert_called_once_with("#btn")

    # 5. fill_form
    r5 = tool.execute({"action": "fill_form", "fields": {"#input": "value"}})
    assert r5.ok is True
    mock_service.fill_form.assert_called_once_with({"#input": "value"})

    # 6. screenshot
    r6 = tool.execute({"action": "screenshot", "full_page": True})
    assert r6.ok is True
    mock_service.screenshot.assert_called_once_with(path=None, full_page=True)

    # 7. ação desconhecida
    r7 = tool.execute({"action": "invalid_action"})
    assert r7.ok is False
    assert "desconhecida" in r7.message


# ---------------------------------------------------------------------------
# Teste de Integração Local Real com HTTP Server & Playwright Headless
# ---------------------------------------------------------------------------

class _TestHTMLHandler(http.server.SimpleHTTPRequestHandler):
    HTML_CONTENT = """<!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="utf-8">
        <title>Página de Teste Jarvis</title>
    </head>
    <body>
        <h1>Catálogo de Automação Jarvis</h1>
        <h2>Produtos em Destaque</h2>
        <p>Servidor Jarvis Core versão 2.0 ativo e operante.</p>
        <p>Preço da licença profissional: R$ 499,00 à vista.</p>
        <a href="/detalhes" id="link-detalhes">Ver detalhes completos</a>

        <form id="teste-form">
            <input type="text" id="campo-nome" name="nome" placeholder="Digite seu nome">
            <button type="button" id="btn-confirmar" onclick="document.getElementById('status').innerText = 'Confirmado com Sucesso!'">Confirmar</button>
        </form>
        <div id="status">Aguardando</div>
    </body>
    </html>
    """

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(self.HTML_CONTENT.encode("utf-8"))))
        self.end_headers()
        self.wfile.write(self.HTML_CONTENT.encode("utf-8"))

    def log_message(self, format, *args):
        # Silencia logs no terminal durante o teste
        pass


@pytest.fixture(scope="module")
def local_http_server():
    """Servidor HTTP de teste local rodando em porta livre de 127.0.0.1."""
    server = socketserver.TCPServer(("127.0.0.1", 0), _TestHTMLHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()


def test_real_playwright_local_integration(local_http_server, tmp_path):
    """Teste de integração real: navega, extrai, busca, preenche e clica no Playwright local."""
    service = BrowserService(headless=True)
    try:
        # 1. Navega para a página local
        nav_res = service.navigate(local_http_server)
        assert nav_res["ok"] is True
        assert nav_res["title"] == "Página de Teste Jarvis"

        # 2. Extrai conteúdo limpo
        ext_res = service.extract_content()
        assert ext_res["ok"] is True
        assert "Catálogo de Automação Jarvis" in ext_res["text"]
        assert any(h["text"] == "Catálogo de Automação Jarvis" for h in ext_res["headings"])
        assert any(l["text"] == "Ver detalhes completos" for l in ext_res["links"])

        # 3. Busca por palavra-chave e extração de preço
        search_res = service.search_and_extract("licença profissional")
        assert search_res["ok"] is True
        assert len(search_res["matches"]) > 0
        assert "R$ 499,00" in search_res["prices"]

        # 4. Preenche campo de formulário
        fill_res = service.fill_form({"#campo-nome": "Agente Jarvis"})
        assert fill_res["ok"] is True
        assert len(fill_res["filled"]) == 1

        # 5. Clica no botão
        click_res = service.click("#btn-confirmar")
        assert click_res["ok"] is True

        # Confere se o texto mudou no DOM após clique
        after_click = service.extract_content(selector="#status")
        assert after_click["ok"] is True
        assert "Confirmado com Sucesso!" in after_click["text"]

        # 6. Screenshot para arquivo
        shot_path = tmp_path / "test_shot.png"
        shot_res = service.screenshot(path=str(shot_path))
        assert shot_res["ok"] is True
        assert shot_path.exists()
        assert shot_path.stat().st_size > 1000

    finally:
        service.stop()
