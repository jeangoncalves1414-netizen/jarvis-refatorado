from __future__ import annotations

import re
import html as html_lib
import base64
import urllib.parse
import urllib.request
import webbrowser
from html.parser import HTMLParser
from typing import Any

from .base import BaseTool, ToolResult


class _DuckDuckGoParser(HTMLParser):
    """Parser pequeno e sem dependencias para o fallback HTML do DuckDuckGo."""

    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._current: dict[str, str] | None = None
        self._capture: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = values.get("class", "") or ""
        if tag == "a" and "result__a" in classes:
            self._current = {"title": "", "href": values.get("href", "") or "", "body": ""}
            self._capture = "title"
        elif self._current and "result__snippet" in classes:
            self._capture = "body"

    def handle_data(self, data: str) -> None:
        if self._current and self._capture:
            self._current[self._capture] += data

    def handle_endtag(self, tag: str) -> None:
        if not self._current:
            return
        if self._capture == "body" and tag in {"div", "a"}:
            item = {key: re.sub(r"\s+", " ", value).strip() for key, value in self._current.items()}
            if item.get("title") and item.get("href"):
                self.results.append(item)
            self._current = None
            self._capture = None
        elif tag == "a" and self._capture == "title":
            self._capture = None


def _source_name(url: str) -> str:
    try:
        return urllib.parse.urlparse(url).netloc.removeprefix("www.") or "web"
    except Exception:
        return "web"


def _unwrap_bing_url(url: str) -> str:
    """Converte o redirect do Bing em URL final quando o parâmetro estiver disponível."""
    try:
        parsed = urllib.parse.urlparse(url)
        encoded = urllib.parse.parse_qs(parsed.query).get("u", [""])[0]
        if encoded.startswith("a1"):
            raw = base64.b64decode(encoded[2:] + "===").decode("utf-8", errors="ignore")
            if raw.startswith(("http://", "https://")):
                return raw
    except Exception:
        pass
    return url


def _normalise_result(item: dict[str, Any]) -> dict[str, str]:
    url = str(item.get("href") or item.get("url") or "").strip()
    return {
        "title": str(item.get("title") or "Sem titulo").strip(),
        "url": url,
        "source": _source_name(url),
        "snippet": str(item.get("body") or item.get("snippet") or "").strip(),
    }


def _fallback_search(query: str, limit: int) -> list[dict[str, str]]:
    # Bing is used as the dependency-free fallback because DuckDuckGo can
    # occasionally return a bot challenge to desktop clients.
    url = "https://www.bing.com/search?q=" + urllib.parse.quote_plus(query)
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Jarvis research client)"})
    with urllib.request.urlopen(request, timeout=12) as response:
        document = response.read().decode("utf-8", errors="replace")
    rows = re.findall(
        r'<li[^>]+class="b_algo"[\s\S]*?<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>\s*</h2>[\s\S]*?(?:<p[^>]*>([\s\S]*?)</p>)?',
        document,
        flags=re.I,
    )
    results: list[dict[str, str]] = []
    for href, title, snippet in rows[:limit]:
        clean = lambda value: re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", value))).strip()
        results.append(_normalise_result({"title": clean(title), "href": _unwrap_bing_url(html_lib.unescape(href)), "body": clean(snippet)}))
    if results:
        return results
    # Last fallback: DuckDuckGo HTML, useful when Bing is rate limited.
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote_plus(query)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Jarvis research client)"}), timeout=12) as response:
        document = response.read().decode("utf-8", errors="replace")
    parser = _DuckDuckGoParser()
    parser.feed(document)
    return [_normalise_result(item) for item in parser.results[:limit]]


def _search(query: str, limit: int) -> list[dict[str, str]]:
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            rows = list(ddgs.text(query, max_results=limit))
        return [_normalise_result(item) for item in rows if item.get("href") or item.get("url")]
    except Exception:
        return _fallback_search(query, limit)


def _page_excerpt(url: str) -> str:
    """Extrai somente um trecho curto para mostrar que a fonte foi consultada."""
    if not url.startswith(("http://", "https://")):
        return ""
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Jarvis research client)"})
        with urllib.request.urlopen(request, timeout=8) as response:
            raw = response.read(180_000).decode("utf-8", errors="replace")
        raw = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>|<[^>]+>", " ", raw, flags=re.I)
        return re.sub(r"\s+", " ", raw).strip()[:420]
    except Exception:
        return ""


class WebSearchTool(BaseTool):
    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "Pesquisa na web sem chave paga. Use action='search' para resultados rapidos ou "
            "action='research' para um workflow: buscar, abrir e extrair pequenos trechos de varias fontes. "
            "Use action='open_url' apenas quando o usuario pedir para abrir um link."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["search", "research", "open_url"],
                    "description": "search lista fontes; research consulta varias fontes; open_url abre um link.",
                },
                "query": {"type": "string", "description": "Termo de pesquisa ou URL a abrir."},
                "max_results": {
                    "type": "integer",
                    "description": "Quantidade de fontes, de 1 a 8. O padrao e 5.",
                    "minimum": 1,
                    "maximum": 8,
                },
            },
            "required": ["action", "query"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        action = str(args.get("action", "search"))
        query = str(args.get("query", "")).strip()
        try:
            limit = max(1, min(int(args.get("max_results") or 5), 8))
        except (TypeError, ValueError):
            limit = 5

        if not query:
            return ToolResult(ok=False, message="Nenhum termo ou URL fornecido.")

        if action in {"search", "research"}:
            try:
                results = _search(query, limit)
                if not results:
                    return ToolResult(ok=True, message=f"Nenhum resultado encontrado para '{query}'.", data={"query": query, "results": []})
                steps = [{"label": "Busca inicial", "status": "completed", "detail": f"{len(results)} fontes encontradas"}]
                if action == "research":
                    steps.append({"label": "Leitura das fontes", "status": "running", "detail": "Abrindo fontes relevantes"})
                    for result in results:
                        result["excerpt"] = _page_excerpt(result["url"])
                    steps[-1]["status"] = "completed"
                    steps[-1]["detail"] = f"{len(results)} fontes consultadas"
                lines = []
                for i, result in enumerate(results, 1):
                    excerpt = f"\n   Trecho consultado: {result['excerpt']}" if result.get("excerpt") else ""
                    lines.append(f"{i}. {result['title']}\n   {result.get('snippet', '')}{excerpt}\n   Link: {result['url']}")
                return ToolResult(
                    ok=True,
                    message=f"Resultados para '{query}':\n\n" + "\n\n".join(lines),
                    data={"query": query, "results": results, "steps": steps, "workflow": action},
                )
            except Exception as exc:
                return ToolResult(ok=False, message=f"Nao foi possivel pesquisar agora: {exc}")

        if action == "open_url":
            url = query if query.startswith(("http://", "https://")) else "https://" + query
            try:
                webbrowser.open(url)
                return ToolResult(ok=True, message=f"Navegador aberto na URL: {url}", data={"url": url})
            except Exception as exc:
                return ToolResult(ok=False, message=f"Erro ao abrir URL: {exc}")

        return ToolResult(ok=False, message=f"Acao desconhecida: {action}")
