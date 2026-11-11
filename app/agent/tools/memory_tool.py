"""Ferramenta ``memory``: memória durável sobre a usuária, oferecida ao modelo.

Roda dentro da ação do turno (``ActionExecutor``), então o recibo é a própria ação ``memory``;
a gravação usa ``memory_kernel.save_fact`` e não abre outra ação. ``memory_facts`` é a fonte de
verdade; o índice ``user_memory`` do Chroma (``context["semantic_memory"]``) é opcional.
"""
from __future__ import annotations

import logging
from typing import Any

from app.agent.tools.base import BaseTool, ToolResult
from app.services import memory_kernel
from app.storage import memory_facts

logger = logging.getLogger(__name__)

ACTIONS = ("save", "search", "list", "forget")
LIST_LIMIT = 30
SEARCH_LIMIT = 5
COLLECTION = "user_memory"


def _semantic(context: dict[str, Any] | None) -> Any:
    memory = (context or {}).get("semantic_memory")
    try:
        return memory if memory is not None and memory.is_available() else None
    except Exception:
        return None


def _public(fact: dict[str, Any]) -> dict[str, Any]:
    return {"id": fact.get("id"), "text": fact.get("text", ""), "pinned": bool(fact.get("pinned")),
            "updated_at": fact.get("updated_at")}


def _norm(text: str) -> str:
    return " ".join(memory_facts.memory_slots.normalize_aligned(text).split())


class MemoryTool(BaseTool):
    name = "memory"
    description = (
        "Memória durável sobre a usuária. save: fato duradouro que ela contou (nome, família, gostos); "
        "search: perguntas sobre ela; list: ver tudo; forget: apagar (pede aprovação). "
        "Notas e listas vão para o cofre."
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": list(ACTIONS), "description": "save, search, list ou forget."},
                "text": {"type": "string", "description": "save: o fato em 3ª pessoa (até 300 caracteres)."},
                "query": {"type": "string", "description": "search: o que procurar; forget: texto do fato a apagar."},
                "id": {"type": "string", "description": "forget: id do fato (veja search/list)."},
                "pinned": {"type": "boolean", "description": "save: fato central (nome, cidade, família)."},
            },
            "required": ["action"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        args = args or {}
        action = str(args.get("action") or "").strip().lower()
        if action not in ACTIONS:
            return ToolResult(False, "Ação inválida. Use save, search, list ou forget.")
        try:
            return getattr(self, f"_{action}")(args, context or {})
        except ValueError as exc:
            return ToolResult(False, str(exc))

    def _save(self, args: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        text = str(args.get("text") or "").strip()
        if not text:
            return ToolResult(False, "Informe em text o fato a lembrar.")
        pinned = args.get("pinned") if isinstance(args.get("pinned"), bool) else None
        fact = memory_kernel.save_fact(text, kind="manual", session_id=str(context.get("session_id") or ""),
                                       pinned=pinned)
        semantic = _semantic(context)
        if semantic is not None:
            try:
                semantic.add_memory(COLLECTION, fact["text"], metadata={
                    "fact_id": fact["id"], "session_id": str(context.get("session_id") or "")},
                    importance=float(fact.get("importance", 0.5)))
            except Exception as exc:
                logger.debug("Índice semântico indisponível ao salvar memória: %s", exc)
        return ToolResult(True, f"Memória salva: {fact['text'][:120]}",
                          data={"record": _public(fact), "record_id": fact["id"]})

    def _search(self, args: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        query = str(args.get("query") or args.get("text") or "").strip()
        if not query:
            return ToolResult(False, "Informe em query o que procurar.")
        found = memory_facts.relevant(query, SEARCH_LIMIT) or memory_facts.essential()
        results = [_public(fact) for fact in found]
        seen = {_norm(item["text"]) for item in results}
        semantic = _semantic(context)
        if semantic is not None:
            from app.storage.vector.semantic_memory import USER_MEMORY_MAX_DISTANCE
            try:
                hits = semantic.search_memories(COLLECTION, query, n_results=SEARCH_LIMIT,
                                                max_distance=USER_MEMORY_MAX_DISTANCE)
            except Exception as exc:
                logger.debug("Busca semântica falhou: %s", exc)
                hits = []
            for hit in hits or []:
                key = _norm(str(hit.get("text", "")))
                if key and key not in seen:
                    seen.add(key)
                    meta = hit.get("metadata") or {}
                    results.append({"id": meta.get("fact_id"), "text": hit.get("text", ""), "pinned": False,
                                    "semantic": True})
        if not results:
            return ToolResult(True, "Nenhuma memória salva sobre isso.", data={"results": []})
        return ToolResult(True, f"{len(results)} memória(s) encontrada(s).", data={"results": results})

    def _list(self, _args: dict[str, Any], _context: dict[str, Any]) -> ToolResult:
        facts = memory_facts.list_facts()
        results = [_public(fact) for fact in facts[:LIST_LIMIT]]
        if not results:
            return ToolResult(True, "Nenhuma memória salva ainda.", data={"results": []})
        extra = f" (mostrando {LIST_LIMIT} de {len(facts)})" if len(facts) > LIST_LIMIT else ""
        return ToolResult(True, f"{len(results)} memória(s) salva(s){extra}.", data={"results": results})

    def _forget(self, args: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        fact_id = str(args.get("id") or "").strip()
        if not fact_id:
            query = str(args.get("query") or args.get("text") or "").strip()
            if not query:
                return ToolResult(False, "Informe o id ou o texto (query) da memória a apagar.")
            key = _norm(query)
            matches = [fact for fact in memory_facts.list_facts() if _norm(fact.get("text", "")) == key]
            matches = matches or memory_facts.relevant(query, SEARCH_LIMIT)
            if len(matches) != 1:
                if not matches:
                    return ToolResult(False, "Nenhuma memória encontrada para apagar.")
                listed = "; ".join(f"{fact['id']}: {fact.get('text', '')[:60]}" for fact in matches)
                return ToolResult(False, f"Mais de uma memória combina. Escolha pelo id: {listed}",
                                  data={"results": [_public(fact) for fact in matches]})
            fact_id = matches[0]["id"]
        fact = memory_facts.delete(fact_id)
        semantic = _semantic(context)
        if semantic is not None and hasattr(semantic, "delete_where"):
            try:
                semantic.delete_where(COLLECTION, {"fact_id": fact_id})
            except Exception as exc:
                logger.debug("Falha ao remover memória do índice semântico: %s", exc)
        return ToolResult(True, f"Memória apagada: {fact.get('text', '')[:120]}",
                          data={"record": _public(fact), "record_id": fact_id})
