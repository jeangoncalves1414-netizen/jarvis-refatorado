"""Ferramentas do Agente para o Memory Vault (ai-memory-vault).

Permite que o assistente consulte notas no Vault, registre diários automáticos,
atualize o perfil do usuário e recupere diretrizes de priming para tarefas.
"""
from __future__ import annotations

from typing import Any
from app.agent.tools.base import BaseTool
from app.services.memory_vault import memory_vault


class VaultSearchTool(BaseTool):
    name = "vault_search"
    description = "Pesquisa notas, diários e documentos salvos no Memory Vault Markdown por palavras-chave."

    def run(self, query: str = "", limit: int = 5, **kwargs: Any) -> dict[str, Any]:
        results = memory_vault.search_vault(query, limit=int(limit))
        return {
            "success": True,
            "query": query,
            "count": len(results),
            "results": results
        }


class VaultDailyNoteTool(BaseTool):
    name = "vault_daily_log"
    description = "Registra uma atividade, aprendizado ou tarefa no diário diário (Daily Note) do Memory Vault."

    def run(self, entry: str = "", category: str = "Atividade", **kwargs: Any) -> dict[str, Any]:
        ok = memory_vault.append_daily_log(entry, category=category)
        return {
            "success": ok,
            "entry": entry,
            "category": category
        }


class VaultSaveNoteTool(BaseTool):
    name = "vault_save_note"
    description = "Salva uma nova nota ou documento no Memory Vault (pasta 04-Projects ou personalizada)."

    def run(self, title: str = "", content: str = "", folder: str = "04-Projects", **kwargs: Any) -> dict[str, Any]:
        path = memory_vault.save_note(title, content, folder=folder)
        return {
            "success": True,
            "title": title,
            "path": path
        }


class VaultUserProfileTool(BaseTool):
    name = "vault_update_profile"
    description = "Adiciona um novo fato ou preferência descoberta sobre o usuário ao seu perfil em USER-PROFILE.md."

    def run(self, fact: str = "", **kwargs: Any) -> dict[str, Any]:
        ok = memory_vault.update_user_profile_fact(fact)
        return {
            "success": ok,
            "fact": fact
        }
