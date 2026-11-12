"""Ferramenta nativa de Checklist Inteligente (Google Keep style).

Permite criar listas, adicionar itens com parsing de linguagem natural,
marcar/desmarcar itens (com afundamento dos concluídos) e gerenciar listas.
"""
from __future__ import annotations

import unicodedata
from typing import Any

from app.agent.tools.base import BaseTool
from app.storage.checklist_store import checklist_store, parse_spoken_items


def normalize_title(value: Any) -> str:
    """Normaliza título para comparação sem acento e minúsculo."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.casefold().split())


class ChecklistTool(BaseTool):
    @property
    def name(self) -> str:
        return "checklist_tool"

    @property
    def description(self) -> str:
        return (
            "Gerencia listas de checagem inteligentes (estilo Google Keep) com suporte a linguagem natural: "
            "criar listas, adicionar itens (extraindo quantidade e condição, ex.: '1 saco de arroz, 2 coca colas se abaixo de R$ 10'), "
            "marcar itens como concluídos (afundando para o rodapé), listar e excluir. Use para listas de compras, mercado, malas, tarefas diárias."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create_list", "add_items", "toggle_item", "get_list", "list_all", "list", "delete_list", "delete_item"],
                    "description": "create_list deve incluir text ou items quando o usuário pedir itens. Consultar não exclui: use delete_list para excluir.",
                },
                "title": {"type": "string", "description": "Título da lista (ex.: 'Mercado', 'Mala de Viagem')."},
                "list_id": {"type": "string", "description": "ID da lista de checagem."},
                "text": {"type": "string", "description": "Texto dos itens em linguagem natural ou texto do item específico."},
                "items": {
                    "type": "array",
                    "items": {"type": "object", "properties": {"text": {"type": "string"}, "completed": {"type": "boolean"}}, "required": ["text"]},
                    "description": "Lista de itens estruturados ou strings.",
                },
                "item_id": {"type": "string", "description": "ID do item específico a alternar ou excluir."},
                "completed": {"type": "boolean", "description": "Definir se o item está concluído (True) ou pendente (False)."},
            },
            "required": ["action"],
        }

    def _resolve_list(self, list_id: str, title: str) -> dict[str, Any] | None:
        if list_id:
            found = checklist_store.get_list(list_id)
            if found:
                return found
            return None
        if title:
            found = checklist_store.find_list_by_title(title)
            if found:
                return found
            # Fallback: normalização Unicode para títulos com acento
            norm = normalize_title(title)
            for l in checklist_store.list_all():
                if normalize_title(l.get("title", "")) == norm:
                    return checklist_store.get_list(l["id"])
            return None
        # Se nenhuma lista foi especificada e só existe uma ativa, pega ela
        all_lists = checklist_store.list_all()
        if len(all_lists) == 1:
            return checklist_store.get_list(all_lists[0]["id"])
        return None

    def run(
        self,
        action: str = "get_list",
        title: str = "",
        list_id: str = "",
        text: str = "",
        items: list[Any] | None = None,
        item_id: str = "",
        completed: bool | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        act = (action or "get_list").lower().strip()

        if act in ("list", "list_all"):
            lists = checklist_store.list_all()
            return {
                "ok": True,
                "message": f"{len(lists)} checklist(s) encontrada(s).",
                "checklists": lists,
            }

        if act == "create_list":
            if not title and not text:
                return {"ok": False, "error": "Informe o título ou os itens da lista."}
            list_title = title or "Nova Lista"
            raw_items = items or text or []
            created = checklist_store.create_list(list_title, items=raw_items, list_id=list_id or None)
            count = len(created.get("items", []))
            return {
                "ok": True,
                "message": f"Lista '{created['title']}' criada com {count} item(ns)!",
                "checklist": created,
                "list_id": created["id"],
            }

        if act == "add_items":
            target = self._resolve_list(list_id, title)
            if not target:
                if title or list_id:
                    # Cria a lista caso não exista
                    target = checklist_store.create_list(title or "Lista de Checagem", list_id=list_id or None)
                else:
                    return {"ok": False, "error": "Lista não encontrada. Especifique o título ou list_id."}

            payload_items: Any = items if items is not None else text
            added = checklist_store.add_items(target["id"], payload_items)
            updated_list = checklist_store.get_list(target["id"])
            return {
                "ok": True,
                "message": f"{len(added)} item(ns) adicionado(s) à lista '{target['title']}'.",
                "added_items": added,
                "checklist": updated_list,
            }

        if act == "toggle_item":
            if item_id:
                toggled = checklist_store.toggle_item(item_id, completed)
                if not toggled:
                    return {"ok": False, "error": f"Item '{item_id}' não encontrado."}
                updated_list = checklist_store.get_list(toggled["list_id"])
                status_txt = "concluído" if toggled["completed"] else "pendente"
                return {
                    "ok": True,
                    "message": f"Item '{toggled['text']}' marcado como {status_txt}.",
                    "item": toggled,
                    "checklist": updated_list,
                }
            # Se não passou item_id, tenta buscar pelo texto do item na lista
            target = self._resolve_list(list_id, title)
            if not target:
                return {"ok": False, "error": "Informe o item_id ou a lista e o texto do item."}
            wanted_text = normalize_title(text)
            match_item = None
            for it in target.get("items", []):
                if normalize_title(it.get("text")) == wanted_text:
                    match_item = it
                    break
            if not match_item:
                # busca parcial
                for it in target.get("items", []):
                    if wanted_text in normalize_title(it.get("text")):
                        match_item = it
                        break
            if not match_item:
                return {"ok": False, "error": f"Item '{text}' não encontrado na lista '{target['title']}'."}

            toggled = checklist_store.toggle_item(match_item["id"], completed)
            updated_list = checklist_store.get_list(target["id"])
            status_txt = "concluído" if toggled["completed"] else "pendente"
            return {
                "ok": True,
                "message": f"Item '{toggled['text']}' marcado como {status_txt}.",
                "item": toggled,
                "checklist": updated_list,
            }

        if act == "get_list":
            target = self._resolve_list(list_id, title)
            if not target:
                return {"ok": False, "error": f"Lista não encontrada para '{list_id or title}'."}
            return {
                "ok": True,
                "message": f"Lista '{target['title']}': {target['pending_count']} pendente(s), {target['completed_count']} concluído(s).",
                "checklist": target,
            }

        if act == "delete_item":
            if not item_id:
                return {"ok": False, "error": "Informe o item_id para exclusão."}
            success = checklist_store.delete_item(item_id)
            return {
                "ok": success,
                "message": "Item removido com sucesso." if success else "Item não encontrado.",
            }

        if act == "delete_list":
            target = self._resolve_list(list_id, title)
            if not target:
                return {"ok": False, "error": "Lista não encontrada para exclusão."}
            success = checklist_store.delete_list(target["id"])
            return {
                "ok": success,
                "message": f"Lista '{target['title']}' excluída com sucesso.",
            }

        return {"ok": False, "error": f"Ação desconhecida: '{action}'."}

