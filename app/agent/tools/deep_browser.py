"""Deep Browser & Search Intelligence Module.

Combina navegação profunda Playwright, snapshot interativo de elementos,
extração limpa de artigos e pesquisa multi-hop iterativa.
"""
from __future__ import annotations

from typing import Any

from app.agent.tools.browser_agent import BrowserAgentTool
from app.agent.tools.web_search import search_with_refinement, WebSearchTool
from app.services.browser import BrowserService, get_browser_service, extract_clean_text, get_interactive_snapshot

__all__ = [
    "BrowserAgentTool",
    "WebSearchTool",
    "search_with_refinement",
    "BrowserService",
    "get_browser_service",
    "extract_clean_text",
    "get_interactive_snapshot",
]
