"""Rotas de API do Painel para Checklists Inteligentes (estilo Google Keep)."""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlsplit

from app.storage.checklist_store import checklist_store
from app.services.habits import HabitService

_NOT_FOUND = (404, {"ok": False, "error": "Checklist não encontrada."})
_ITEM_NOT_FOUND = (404, {"ok": False, "error": "Item da checklist não encontrado."})
_HABIT_NOT_FOUND = (404, {"ok": False, "error": "Hábito não encontrado."})


def handle_checklists_get(parts: list[str], _handler: Any) -> tuple[int, dict] | None:
    # Suporte a /api/checklists e /api/lifeos/habits
    if parts[:2] == ["api", "lifeos"] and len(parts) >= 3 and parts[2] == "habits":
        try:
            if len(parts) == 3:
                return 200, {"ok": True, "habits": HabitService.list_habits()}
            if len(parts) == 4:
                habit = HabitService.get_habit(parts[3])
                return (200, {"ok": True, "habit": habit}) if habit else _HABIT_NOT_FOUND
        except Exception as exc:
            return 500, {"ok": False, "error": str(exc)}

    if parts[:2] != ["api", "checklists"]:
        return None
    try:
        # GET /api/checklists
        if len(parts) == 2:
            return 200, {"ok": True, "checklists": checklist_store.list_all()}
        # GET /api/checklists/{list_id}
        if len(parts) == 3:
            list_id = parts[2]
            found = checklist_store.get_list(list_id)
            if not found:
                return _NOT_FOUND
            return 200, {"ok": True, "checklist": found}
    except Exception as exc:
        return 500, {"ok": False, "error": str(exc)}
    return None


def handle_checklists_post(path: str, body: bytes, _handler: Any) -> tuple[int, dict] | None:
    parts = [part for part in urlsplit(path).path.split("/") if part]

    # Endpoints de hábitos modulares: /api/lifeos/habits
    if parts[:2] == ["api", "lifeos"] and len(parts) >= 3 and parts[2] == "habits":
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, ValueError):
            return 400, {"ok": False, "error": "JSON inválido."}

        try:
            # POST /api/lifeos/habits/auto-check
            if len(parts) == 4 and parts[3] == "auto-check":
                text = str(payload.get("text") or "").strip()
                event_type = str(payload.get("event_type") or "dialogue").strip()
                checked = HabitService.contextual_auto_check(text=text, event_type=event_type)
                return 200, {"ok": True, "checked": checked, "count": len(checked)}

            # POST /api/lifeos/habits -> criar hábito
            if len(parts) == 3:
                name = str(payload.get("name") or "").strip()
                if not name:
                    return 400, {"ok": False, "error": "Informe o nome do hábito."}
                import uuid
                habit_id = payload.get("id") or f"habit_{uuid.uuid4().hex[:8]}"
                created = HabitService.create_habit(
                    habit_id=habit_id,
                    name=name,
                    category=payload.get("category", "general"),
                    routine_block=payload.get("routine_block", "anytime"),
                    days_of_week=payload.get("days_of_week"),
                    start_time=payload.get("start_time", "15:00"),
                    day_slots=payload.get("day_slots"),
                    items_list=payload.get("items_list"),
                )
                return 201, {"ok": True, "habit": created}

            habit_id = parts[3]
            # POST /api/lifeos/habits/{id}/toggle
            if len(parts) == 5 and parts[4] == "toggle":
                completed = payload.get("completed")
                habit = HabitService.get_habit(habit_id)
                if not habit:
                    return _HABIT_NOT_FOUND
                if completed is False or (completed is None and habit.get("completed_today")):
                    res = HabitService.uncheck_in(habit_id)
                else:
                    res = HabitService.check_in(habit_id, notes=payload.get("notes", ""))
                return 200, {"ok": True, "habit": res}

            # POST /api/lifeos/habits/{id}/slot
            if len(parts) == 5 and parts[4] == "slot":
                day = payload.get("day")
                slot_data = payload.get("slot") or payload.get("data")
                res = HabitService.set_day_slot(habit_id, day, slot_data)
                return (200, {"ok": True, "habit": res}) if res else _HABIT_NOT_FOUND

            # POST /api/lifeos/habits/{id}/delete
            if len(parts) == 5 and parts[4] == "delete":
                success = HabitService.delete_habit(habit_id)
                return (200, {"ok": True}) if success else _HABIT_NOT_FOUND

            # POST /api/lifeos/habits/{id} -> update
            if len(parts) == 4:
                updated = HabitService.update_habit(habit_id, **payload)
                return (200, {"ok": True, "habit": updated}) if updated else _HABIT_NOT_FOUND
        except Exception as exc:
            return 500, {"ok": False, "error": str(exc)}

    if parts[:2] != ["api", "checklists"]:
        return None
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
        if not isinstance(payload, dict):
            return 400, {"ok": False, "error": "JSON inválido."}
    except (UnicodeDecodeError, ValueError):
        return 400, {"ok": False, "error": "JSON inválido."}

    try:
        # POST /api/checklists -> cria lista
        if len(parts) == 2:
            title = str(payload.get("title") or "Nova Lista").strip()
            items = payload.get("items") or payload.get("text")
            list_id = payload.get("id") or payload.get("list_id")
            created = checklist_store.create_list(title, items=items, list_id=list_id)
            return 201, {"ok": True, "checklist": created}

        # POST /api/checklists/items/{item_id}/toggle
        if len(parts) == 5 and parts[2] == "items" and parts[4] == "toggle":
            item_id = parts[3]
            completed = payload.get("completed")
            toggled = checklist_store.toggle_item(item_id, completed=completed)
            if not toggled:
                return _ITEM_NOT_FOUND
            return 200, {"ok": True, "item": toggled}

        # POST /api/checklists/items/{item_id}/delete
        if len(parts) == 5 and parts[2] == "items" and parts[4] == "delete":
            item_id = parts[3]
            success = checklist_store.delete_item(item_id)
            return (200, {"ok": True}) if success else _ITEM_NOT_FOUND

        # POST /api/checklists/items/{item_id}/update
        if len(parts) == 5 and parts[2] == "items" and parts[4] == "update":
            item_id = parts[3]
            updated = checklist_store.update_item(item_id, **payload)
            if not updated:
                return _ITEM_NOT_FOUND
            return 200, {"ok": True, "item": updated}

        list_id = parts[2]
        # POST /api/checklists/{list_id}/items -> adiciona itens
        if len(parts) == 4 and parts[3] == "items":
            items = payload.get("items") if "items" in payload else payload.get("text")
            if not items:
                return 400, {"ok": False, "error": "Informe os itens a adicionar."}
            added = checklist_store.add_items(list_id, items)
            checklist = checklist_store.get_list(list_id)
            return 200, {"ok": True, "added": added, "checklist": checklist}

        # POST /api/checklists/{list_id}/toggle -> alterna item
        if len(parts) == 4 and parts[3] == "toggle":
            item_id = str(payload.get("item_id") or "").strip()
            if not item_id:
                return 400, {"ok": False, "error": "Informe o item_id."}
            completed = payload.get("completed")
            toggled = checklist_store.toggle_item(item_id, completed=completed)
            if not toggled:
                return _ITEM_NOT_FOUND
            checklist = checklist_store.get_list(list_id)
            return 200, {"ok": True, "item": toggled, "checklist": checklist}

        # POST /api/checklists/{list_id}/delete -> exclui lista
        if len(parts) == 4 and parts[3] == "delete":
            success = checklist_store.delete_list(list_id)
            return (200, {"ok": True}) if success else _NOT_FOUND

    except Exception as exc:
        return 500, {"ok": False, "error": str(exc)}

    return None
