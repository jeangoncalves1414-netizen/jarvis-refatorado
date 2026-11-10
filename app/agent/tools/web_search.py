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
from ..tool_router import tool, TaskCategory


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


GENERIC_DOMAINS = frozenset({
    "dicio.com.br",
    "priberam.pt",
    "dicionario.priberam.org",
    "significados.com.br",
    "michaelis.uol.com.br",
    "wiktionary.org",
    "urbandictionary.com",
    "dicionarioinformal.com.br",
    "instagram.com",
    "facebook.com",
    "tiktok.com",
    "twitter.com",
    "x.com",
    "threads.net",
    "linkedin.com",
    "pinterest.com",
})


def _is_informative_result(item: dict[str, Any]) -> bool:
    """Verifica se um resultado é informativo (não apenas link genérico de rede social ou dicionário)."""
    url = str(item.get("url") or item.get("href") or "").lower()
    source = _source_name(url).lower()

    # Dicionários e redes sociais genéricas são não-informativos para fatos/notícias
    for gen in GENERIC_DOMAINS:
        if gen in source or gen in url:
            return False

    snippet = str(item.get("snippet") or item.get("body") or "").strip()
    title = str(item.get("title") or "").strip()

    if not snippet and not title:
        return False

    low_text = (title + " " + snippet).lower()
    boilerplates = (
        "veja fotos e vídeos", "see instagram photos and videos", "entrar no facebook",
        "log in to facebook", "sign up", "sign in", "criar uma conta",
        "significado de ", "definição de ", "o que significa",
    )
    if any(b in low_text for b in boilerplates) and len(snippet) < 60:
        return False

    return True


def _needs_refinement(results: list[dict[str, Any]]) -> bool:
    """Indica se a busca retornou 0 resultados ou apenas itens genéricos que exigem refinamento."""
    if not results:
        return True
    informative_count = sum(1 for r in results if _is_informative_result(r))
    return informative_count == 0


def _generate_refinement_queries(query: str) -> list[str]:
    """Gera termos de busca refinados para multi-hop (notícias recentes, fontes jornalísticas)."""
    q = query.strip()
    clean = re.sub(r'["\']', '', q)
    clean = re.sub(r'^(?:pesquise|busque|procure|quem\s+[eé]|o\s+que\s+(?:aconteceu|houve)\s+(?:com|sobre)?)\s+', '', clean, flags=re.I).strip()

    candidates: list[str] = []
    has_news = bool(re.search(r'\bnot[ií]cias?\b', clean, re.I))

    if not has_news:
        candidates.append(f"{clean} noticias recentes")
        candidates.append(f"{clean} ultimas noticias")
        candidates.append(f"{clean} acontecimentos recentes")
    else:
        core = re.sub(r'\b(?:ultimas\s+)?not[ií]cias?\s*(?:sobre|do|da|de)?\b', '', clean, flags=re.I).strip()
        if core:
            candidates.append(f"{core} noticias recentes g1 uol")
            candidates.append(f"{core} ultimas novidades hoje")
            candidates.append(f"{core} o que aconteceu")
        else:
            candidates.append(f"{clean} g1 uol metropoles")

    seen = {q.lower()}
    unique_candidates: list[str] = []
    for cand in candidates:
        cand_l = cand.lower().strip()
        if cand_l not in seen:
            seen.add(cand_l)
            unique_candidates.append(cand.strip())

    return unique_candidates


def search_with_refinement(
    query: str,
    limit: int = 5,
    max_hops: int = 3,
) -> tuple[list[dict[str, str]], list[dict[str, str]], str]:
    """
    Executa busca multi-hop com refinamento iterativo.
    Se a busca inicial retornar apenas links genéricos (redes sociais, dicionários)
    ou 0 resultados, tenta termos refinados antes de desistir.
    Sabe quando parar assim que obtém resultados informativos suficientes.
    
    Retorna: (resultados, passos_executados, query_final_usada)
    """
    steps: list[dict[str, str]] = []

    # Hop 1: Busca inicial
    current_results = _search(query, limit)
    steps.append({
        "label": "Busca inicial",
        "status": "completed",
        "detail": f"{len(current_results)} resultados para '{query}'",
    })

    if not _needs_refinement(current_results):
        # Sabe quando parar: resultados satisfatórios obtidos de primeira
        return current_results, steps, query

    refinements = _generate_refinement_queries(query)
    effective_query = query
    best_results = current_results

    for hop_idx, ref_query in enumerate(refinements[: max_hops - 1], start=2):
        steps.append({
            "label": f"Refinamento iterativo (Hop {hop_idx})",
            "status": "running",
            "detail": f"Refinando busca com '{ref_query}'",
        })
        refined_results = _search(ref_query, limit)
        informative = [r for r in refined_results if _is_informative_result(r)]

        if informative:
            steps[-1]["status"] = "completed"
            steps[-1]["detail"] = f"{len(refined_results)} resultados ({len(informative)} informativos) para '{ref_query}'"
            best_results = refined_results
            effective_query = ref_query
            # Conclui com sucesso no refinamento ("saber quando parar")
            break
        else:
            steps[-1]["status"] = "completed"
            steps[-1]["detail"] = f"{len(refined_results)} resultados (nenhum informativo) para '{ref_query}'"
            if len(refined_results) > len(best_results):
                best_results = refined_results
                effective_query = ref_query

    return best_results, steps, effective_query


def _format_search_response(query: str, results: list[dict[str, Any]], refined_query: str | None = None) -> str:
    """Sintetiza os fatos encontrados de forma limpa e informativa, sem despejos de links brutos."""
    if not results:
        return f"Não foram encontradas notícias ou informações sobre '{query}' após pesquisa aprofundada."

    informative_items = [r for r in results if _is_informative_result(r)]
    items_to_use = informative_items if informative_items else results

    facts: list[str] = []
    sources: list[str] = []

    for r in items_to_use:
        title = r.get("title", "").strip()
        source = r.get("source", "").strip() or "web"
        url = r.get("url", "").strip()
        content = r.get("excerpt", "") or r.get("snippet", "") or ""
        clean_content = re.sub(r"\s+", " ", content).strip()

        if clean_content:
            facts.append(f"• [{source}] {clean_content}")
        elif title:
            facts.append(f"• [{source}] {title}")

        if title and url:
            sources.append(f"- {title} ({source}): {url}")

    refinement_info = f" (busca refinada com '{refined_query}')" if refined_query and refined_query.lower() != query.lower() else ""

    sections = [
        f"Síntese informativa sobre '{query}'{refinement_info}:",
        "\n".join(facts) if facts else "Nenhum detalhe informativo substantivo extraído.",
        "\nFontes consultadas:",
        "\n".join(sources),
    ]
    return "\n\n".join(sections)


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

    @tool(description="Pesquisa na web sem chave paga. Suporta busca rápida, pesquisa profunda e abertura de URLs.", category=TaskCategory.WEB_SEARCH, priority=1)
    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        action = str(args.get("action", "search"))
        query = str(args.get("query", "")).strip()
        try:
            limit = max(1, min(int(args.get("max_results") or 5), 8))
        except (TypeError, ValueError):
            limit = 5

        if not query:
            return ToolResult(ok=False, message="Nenhum termo ou URL fornecido.")

        # Roteamento exclusivo: web_search NUNCA deve sequestrar URLs do YouTube para abrir navegadores locais
        is_yt_url = "youtube.com" in query.lower() or "youtu.be" in query.lower()
        if is_yt_url:
            from .video_analyst_tool import VideoAnalystTool
            user_line = (context or {}).get("user_line", "")
            return VideoAnalystTool().execute(
                {"action": "analyze_youtube_video", "url": query, "prompt": user_line},
                context=context,
            )

        if action in {"search", "research"}:
            try:
                results, steps, effective_q = search_with_refinement(query, limit=limit)
                if not results:
                    return ToolResult(
                        ok=True,
                        message=f"Não foram encontradas notícias ou informações sobre '{query}' após pesquisa aprofundada.",
                        data={"query": query, "results": [], "steps": steps},
                    )

                if action == "research":
                    steps.append({"label": "Leitura das fontes", "status": "running", "detail": "Abrindo fontes relevantes"})
                    for result in results:
                        result["excerpt"] = _page_excerpt(result["url"])
                    steps[-1]["status"] = "completed"
                    steps[-1]["detail"] = f"{len(results)} fontes consultadas"

                refined_from = effective_q if effective_q.lower() != query.lower() else None
                synthesis_msg = _format_search_response(query, results, refined_query=refined_from)

                return ToolResult(
                    ok=True,
                    message=synthesis_msg,
                    data={"query": query, "effective_query": effective_q, "results": results, "steps": steps, "workflow": action},
                )
            except Exception as exc:
                return ToolResult(ok=False, message=f"Não foi possível pesquisar agora: {exc}")

        if action == "open_url":
            url = query if query.startswith(("http://", "https://")) else "https://" + query
            try:
                webbrowser.open(url)
                return ToolResult(ok=True, message=f"Navegador aberto na URL: {url}", data={"url": url})
            except Exception as exc:
                return ToolResult(ok=False, message=f"Erro ao abrir URL: {exc}")

        return ToolResult(ok=False, message=f"Ação desconhecida: {action}")
