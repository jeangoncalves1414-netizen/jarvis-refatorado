"""Research Subagent: Especialista em Pesquisa Científica, Síntese de Conteúdo e Análise."""
from __future__ import annotations

from typing import Any


class ResearchSubagent:
    """Sub-agente especializado em síntese de informações e pesquisa multi-fonte."""

    name = "research_agent"
    description = "Pesquisa na web e fontes acadêmicas para compilar relatórios ricos e estruturados."

    def __init__(self, llm_service: Any = None) -> None:
        self.llm_service = llm_service

    def execute_task(self, query: str, **kwargs: Any) -> dict[str, Any]:
        """Realiza uma pesquisa estruturada."""
        if not query:
            return {"ok": False, "error": "Query de pesquisa não fornecida."}

        try:
            from app.agent.tools.web_search import _search
            raw_results = _search(query, limit=5)
        except Exception:
            raw_results = [{"title": query, "url": "https://duckduckgo.com", "snippet": f"Pesquisa sobre {query}"}]

        snippets = [f"- {item.get('title', '')}: {item.get('snippet', '')}" for item in raw_results]
        combined_text = "\n".join(snippets)

        if self.llm_service:
            prompt = (
                f"Sintetize os seguintes resultados de pesquisa para a pergunta '{query}':\n"
                f"{combined_text}\n\n"
                "Gere um resumo executivo claro com tópicos."
            )
            synthesis = self.llm_service.ask(prompt)
        else:
            synthesis = f"Resultados para '{query}':\n" + combined_text

        return {
            "ok": True,
            "agent": self.name,
            "query": query,
            "synthesis": synthesis,
            "sources_count": len(raw_results)
        }
