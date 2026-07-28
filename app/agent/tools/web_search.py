from __future__ import annotations

import webbrowser
from urllib.parse import quote_plus
from typing import Any
from .base import BaseTool, ToolResult

class WebSearchTool(BaseTool):
    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Pesquisa na web por informações atualizadas ou abre o navegador em uma URL."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["search", "open_url"],
                    "description": "Ação a ser executada: 'search' para pesquisar ou 'open_url' para abrir site."
                },
                "query": {
                    "type": "string",
                    "description": "Termo de pesquisa ou URL a abrir."
                }
            },
            "required": ["action", "query"]
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        action = args.get("action", "search")
        query = args.get("query", "").strip()

        if not query:
            return ToolResult(ok=False, message="Nenhum termo ou URL fornecido.")

        if action == "search":
            try:
                # Tentativa de busca com DuckDuckGo Search
                from duckduckgo_search import DDGS
                with DDGS() as ddgs:
                    results = list(ddgs.text(query, max_results=3))
                if not results:
                    return ToolResult(ok=True, message=f"Nenhum resultado encontrado para '{query}'.")
                
                lines = []
                for i, r in enumerate(results, 1):
                    lines.append(f"{i}. {r.get('title')}\n   {r.get('body')}\n   Link: {r.get('href')}")
                return ToolResult(ok=True, message=f"Resultados para '{query}':\n\n" + "\n\n".join(lines))
            except Exception as e:
                # Fallback: abrir a pesquisa no navegador padrão do usuário
                print(f"[WebSearch] Erro ao buscar via API: {e}. Abrindo navegador.")
                try:
                    url = f"https://www.google.com/search?q={quote_plus(query)}"
                    webbrowser.open(url)
                    return ToolResult(ok=True, message=f"Erro ao buscar na API. Abri o navegador com a pesquisa: '{query}'.")
                except Exception as inner_e:
                    return ToolResult(ok=False, message=f"Falha ao abrir navegador: {inner_e}")

        elif action == "open_url":
            url = query
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            try:
                webbrowser.open(url)
                return ToolResult(ok=True, message=f"Navegador aberto na URL: {url}")
            except Exception as e:
                return ToolResult(ok=False, message=f"Erro ao abrir URL: {e}")

        return ToolResult(ok=False, message=f"Ação desconhecida: {action}")
