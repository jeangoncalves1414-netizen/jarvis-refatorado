"""Ferramentas do Agente para o Memory Vault (ai-memory-vault).

Permite que o assistente consulte notas no Vault, registre diários automáticos,
atualize o perfil do usuário e salve anotações. Toda gravação passa pelo Action
Kernel (catálogo em ``catalog.py``); aqui só ficam a validação e o despacho.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.agent.tools.base import BaseTool
from app.services import memory_vault as vault_module
from app.services.memory_vault import memory_vault

# Pastas em que o agente pode salvar notas (decisão 13 do lote 6). Qualquer outra
# pasta, inclusive caminhos com ".." ou absolutos, é recusada.
NOTE_FOLDERS = ("01-Daily-Notes", "03-Priming-Notes", "04-Projects", "05-Notas")
MAX_TITLE = 120
MAX_CONTENT = 20_000
MAX_ENTRY = 2_000


def _relative_to_vault(path: str) -> str:
    try:
        return Path(path).resolve().relative_to(Path(vault_module.VAULT_DIR).resolve()).as_posix()
    except (OSError, ValueError):
        return Path(path).name


class VaultSearchTool(BaseTool):
    name = "vault_search"
    description = (
        "Pesquisa por palavras-chave nas notas, diários e anotações salvos no cofre de memória (Markdown). "
        "Use para lembrar algo que a usuária anotou ou para conferir se uma nota foi salva. Só lê; nada é alterado."
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Palavras-chave (pelo menos uma com 3 letras ou mais)."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20, "description": "Máximo de resultados (padrão 5)."},
            },
            "required": ["query"],
        }

    def run(self, query: str = "", limit: int = 5, **kwargs: Any) -> dict[str, Any]:
        if not isinstance(query, str) or not query.strip():
            return {"ok": False, "error": "Informe o que procurar no cofre."}
        try:
            size = max(1, min(int(limit), 20))
        except (TypeError, ValueError):
            size = 5
        results = memory_vault.search_vault(query, limit=size)
        for item in results:
            item["path"] = _relative_to_vault(item.get("path", ""))
        return {
            "success": True,
            "message": f"{len(results)} nota(s) encontrada(s) para '{query.strip()}'.",
            "query": query,
            "count": len(results),
            "results": results,
        }


class VaultDailyNoteTool(BaseTool):
    name = "vault_daily_log"
    description = (
        "Acrescenta uma linha com horário ao diário de hoje (Daily Note) do cofre: atividade feita, aprendizado ou pendência. "
        "Para anotação com título próprio (lista, ideias, ata), use vault_save_note."
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "entry": {"type": "string", "description": f"Texto da entrada (até {MAX_ENTRY} caracteres)."},
                "category": {"type": "string", "description": "Rótulo curto da entrada (ex.: Atividade, Aprendizado, Pendência)."},
            },
            "required": ["entry"],
        }

    def run(self, entry: str = "", category: str = "Atividade", **kwargs: Any) -> dict[str, Any]:
        if not isinstance(entry, str) or not entry.strip():
            return {"ok": False, "error": "Informe o texto da entrada do diário."}
        if len(entry) > MAX_ENTRY:
            return {"ok": False, "error": f"A entrada do diário deve ter no máximo {MAX_ENTRY} caracteres."}
        label = (category if isinstance(category, str) else "").strip()[:40] or "Atividade"
        ok = memory_vault.append_daily_log(entry, category=label)
        return {
            "success": ok,
            "message": "Entrada registrada no diário de hoje." if ok else "Não foi possível registrar no diário.",
            "entry": entry,
            "category": label,
            "path": _relative_to_vault(str(memory_vault.get_today_note_path())) if ok else "",
        }


class VaultSaveNoteTool(BaseTool):
    name = "vault_save_note"
    description = (
        "Salva uma anotação em Markdown no cofre com título próprio. Use para listas, ideias, ditados e resumos que a "
        "usuária pede para anotar. Pasta padrão 05-Notas (anotações); 04-Projects para notas de projeto. Salvar de novo "
        "com o mesmo título substitui o conteúdo da nota."
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": f"Título da nota (1 a {MAX_TITLE} caracteres)."},
                "content": {
                    "type": "string",
                    "description": f"Conteúdo em Markdown (até {MAX_CONTENT} caracteres). Lista: '- item' por linha; checklist: '- [ ] item'.",
                },
                "folder": {"type": "string", "enum": list(NOTE_FOLDERS), "description": "Pasta do cofre (padrão 05-Notas)."},
            },
            "required": ["title", "content"],
        }

    def run(self, title: str = "", content: str = "", folder: str = "05-Notas", **kwargs: Any) -> dict[str, Any]:
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > MAX_TITLE:
            return {"ok": False, "error": f"O título da nota deve ter de 1 a {MAX_TITLE} caracteres."}
        if not isinstance(content, str):
            return {"ok": False, "error": "O conteúdo da nota deve ser texto."}
        if len(content) > MAX_CONTENT:
            return {"ok": False, "error": f"O conteúdo da nota deve ter no máximo {MAX_CONTENT} caracteres."}
        folder = folder if isinstance(folder, str) and folder.strip() else "05-Notas"
        if folder.strip() not in NOTE_FOLDERS:
            return {"ok": False, "error": "Pasta inválida. Use uma de: " + ", ".join(NOTE_FOLDERS) + "."}
        path = memory_vault.save_note(title.strip(), content, folder=folder.strip())
        relative = _relative_to_vault(path)
        return {
            "success": True,
            "message": f"Nota '{title.strip()}' salva no cofre ({relative}).",
            "title": title.strip(),
            "folder": folder.strip(),
            "path": relative,
        }


class VaultUserProfileTool(BaseTool):
    name = "vault_update_profile"
    description = (
        "Acrescenta ao perfil da usuária (USER-PROFILE.md) um fato ou preferência duradoura que ela contou. "
        "Não use para tarefas, lembretes ou anotações do dia."
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"fact": {"type": "string", "description": "Fato ou preferência em uma frase (até 300 caracteres)."}},
            "required": ["fact"],
        }

    def run(self, fact: str = "", **kwargs: Any) -> dict[str, Any]:
        if not isinstance(fact, str) or not fact.strip():
            return {"ok": False, "error": "Informe o fato ou preferência a registrar."}
        if len(fact) > 300:
            return {"ok": False, "error": "O fato deve ter no máximo 300 caracteres."}
        ok = memory_vault.update_user_profile_fact(fact)
        return {
            "success": ok,
            "message": "Perfil atualizado." if ok else "Não foi possível atualizar o perfil.",
            "fact": fact,
        }
