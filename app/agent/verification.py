"""Verificação seguida por regra, sem chamar o modelo (loop agêntico, lote 6).

Depois de uma escrita que deu certo, o loop relê o mesmo dado pela ferramenta de
leitura correspondente (operação ``observe``, registrada no mesmo pedido da Central)
e compara com o que a escrita devolveu. Falha na comparação vira uma nota no
histórico; o modelo decide se corrige ou encerra.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.agent.tools.base import ToolResult

Check = Callable[[ToolResult], tuple[bool, str]]


@dataclass(frozen=True)
class Verification:
    tool: str
    args: dict[str, Any]
    check: Check
    label: str


def _data(result: ToolResult | None) -> dict[str, Any]:
    data = getattr(result, "data", None)
    return data if isinstance(data, dict) else {}


def _ids(values: Any) -> list[str]:
    return [str(item) for item in values] if isinstance(values, list) else []


def _missing_note(missing: list[str], what: str) -> str:
    shown = ", ".join(missing[:5]) + ("…" if len(missing) > 5 else "")
    return f"verificação: {shown} não apareceu na leitura de {what}."


def _contains(expected: list[str], list_key: str, what: str, *, field: str = "id") -> Check:
    def check(read: ToolResult) -> tuple[bool, str]:
        if not read.ok:
            return False, f"verificação: a leitura de {what} falhou."
        items = _data(read).get(list_key)
        seen = {str(item.get(field)) for item in items if isinstance(item, dict)} if isinstance(items, list) else set()
        missing = [value for value in expected if value not in seen]
        return (not missing), ("" if not missing else _missing_note(missing, what))
    return check


def _habits_checked(expected: list[str]) -> Check:
    def check(read: ToolResult) -> tuple[bool, str]:
        if not read.ok:
            return False, "verificação: a leitura dos hábitos falhou."
        items = _data(read).get("habits")
        done = {str(item.get("id")) for item in items if isinstance(item, dict) and item.get("completed_today")} if isinstance(items, list) else set()
        missing = [value for value in expected if value not in done]
        return (not missing), ("" if not missing else _missing_note(missing, "hábitos concluídos hoje"))
    return check


def _water_total(expected: Any) -> Check:
    def check(read: ToolResult) -> tuple[bool, str]:
        if not read.ok:
            return False, "verificação: a leitura da água falhou."
        current = (_data(read).get("data") or {}).get("current_ml") if isinstance(_data(read).get("data"), dict) else None
        if current == expected:
            return True, ""
        return False, f"verificação: a água de hoje aparece como {current} ml, esperado {expected} ml."
    return check


def plan_verification(tool_name: str, args: dict[str, Any] | None, result: ToolResult | None) -> Verification | None:
    """Leitura que confirma a escrita ``tool_name``/``args``; ``None`` quando não há o que conferir."""
    if result is None or not result.ok:
        return None
    args = args or {}
    operation = str(args.get("action") or "").strip().lower()
    data = _data(result)

    if tool_name == "habit_tool":
        if operation in {"create", "create_many"}:
            names = [str(item.get("name")) for item in data.get("habits") or [] if isinstance(item, dict) and item.get("name")]
            if names:
                return Verification("habit_tool", {"action": "list"}, _contains(names, "habits", "hábitos", field="name"), "hábitos criados")
        if operation in {"check", "check_many", "complete", "done"}:
            ids = _ids(data.get("habit_ids"))
            if ids:
                return Verification("habit_tool", {"action": "list"}, _habits_checked(ids), "hábitos marcados hoje")
        return None
    if tool_name == "task_tool" and operation in {"create", "create_many"}:
        ids = _ids(data.get("task_ids"))
        if ids:
            return Verification("task_tool", {"action": "list", "include_completed": True}, _contains(ids, "tasks", "tarefas"), "tarefas criadas")
        return None
    if tool_name == "finance_tool" and operation in {"add", "create", "add_many"}:
        ids = _ids(data.get("trans_ids"))
        if ids:
            return Verification("finance_tool", {"action": "list", "period": "all"}, _contains(ids, "transactions", "lançamentos"), "lançamentos gravados")
        return None
    if tool_name == "lifeos_tool" and operation in {"add_water", "set_water"}:
        inner = data.get("data") if isinstance(data.get("data"), dict) else {}
        if "total_ml" in inner:
            return Verification("lifeos_tool", {"action": "get_water"}, _water_total(inner["total_ml"]), "água de hoje")
        return None
    if tool_name == "calendar" and operation in {"create_reminder", "create_many"}:
        ids = _ids(data.get("event_ids"))
        if ids:
            return Verification("calendar", {"action": "list"}, _contains(ids, "events", "lembretes"), "lembretes agendados")
        return None
    if tool_name == "vault_save_note":
        title, path = str(data.get("title") or ""), str(data.get("path") or "")
        if path and any(len(word) >= 3 for word in title.split()):
            return Verification("vault_search", {"query": title, "limit": 20}, _contains([path], "results", "notas do cofre", field="path"), "nota salva")
        return None
    return None
