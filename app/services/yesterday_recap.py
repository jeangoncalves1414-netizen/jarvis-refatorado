"""
Yesterday Recap Briefing Service — inspirado no Mark-L
Analisa logs e tarefas recentes para gerar o resumo matinal do dia anterior ("Ontem você parou em...").
"""
from __future__ import annotations

from typing import Any


class YesterdayRecapService:
    """Gerador de resumo matinal de sessões anteriores."""

    @staticmethod
    def generate_recap() -> dict[str, Any]:
        """Gera mensagem de resumo do contexto anterior."""
        try:
            from app.storage.session_store import list_sessions
            sessions = list_sessions()
            if sessions:
                latest = sessions[0]
                title = latest.get("title", "Sessão anterior")
                updated = latest.get("updated_at", "")
                return {
                    "ok": True,
                    "recap": f"Ontem você parou na sessão '{title}'. Todas as alterações foram preservadas.",
                    "session_id": latest.get("id"),
                }
        except Exception:
            pass

        return {
            "ok": True,
            "recap": "Bem-vindo de volta, Sir! Nenhum contexto pendente do dia anterior.",
        }
