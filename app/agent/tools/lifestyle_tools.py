"""Lifestyle AI Tools (HabitTool, TaskTool, FinanceTool).

Enables Jarvis AI (Orchestrator, Voice, Proactive Daemon) to query and update
habits, checklists, tasks, and personal finance via natural language commands.

Operações em lote (``create_many``, ``check_many``, ``add_many``) validam todos os
itens antes de gravar: um item inválido recusa o lote inteiro e nada é gravado.
"""
from __future__ import annotations

import unicodedata
import uuid
from datetime import date, timedelta
from typing import Any

from app.agent.tools.base import BaseTool, ToolResult
from app.services.habits import HabitService
from app.services.tasks import TaskService
from app.services.finance import FinanceService

MAX_HABITS_PER_CALL = 20
MAX_TASKS_PER_CALL = 20
MAX_ENTRIES_PER_CALL = 20
MAX_NAME = 120

ROUTINE_BLOCKS = ("morning", "afternoon", "evening", "anytime")
WEEK_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

DAY_MAP = {
    0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun",
    "0": "mon", "1": "tue", "2": "wed", "3": "thu", "4": "fri", "5": "sat", "6": "sun",
    "segunda": "mon", "segunda-feira": "mon", "seg": "mon", "mon": "mon", "monday": "mon",
    "terça": "tue", "terca": "tue", "terça-feira": "tue", "terca-feira": "tue", "ter": "tue", "tue": "tue", "tuesday": "tue",
    "quarta": "wed", "quarta-feira": "wed", "qua": "wed", "wed": "wed", "wednesday": "wed",
    "quinta": "thu", "quinta-feira": "thu", "qui": "thu", "thu": "thu", "thursday": "thu",
    "sexta": "fri", "sexta-feira": "fri", "sex": "fri", "fri": "fri", "friday": "fri",
    "sábado": "sat", "sabado": "sat", "sáb": "sat", "sab": "sat", "sat": "sat", "saturday": "sat",
    "domingo": "sun", "dom": "sun", "sun": "sun", "sunday": "sun",
}


def normalize_name(value: Any) -> str:
    """Nome para comparação: sem acento, minúsculo e com espaços simples."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.casefold().split())


def resolve_by_name(items: list[dict[str, Any]], query: str, field: str, *, kind: str, allow_partial: bool) -> dict[str, Any]:
    """Acha um item pelo nome exato (sem diferenciar acento/maiúscula).

    Sem nome exato e com ``allow_partial``, aceita um único nome que contenha o texto.
    Levanta ValueError (pt-BR) quando nada é achado ou quando há mais de um candidato.
    """
    wanted = normalize_name(query)
    if not wanted:
        raise ValueError(f"Informe o nome {kind}.")
    exact = [item for item in items if normalize_name(item.get(field)) == wanted]
    matches = exact
    if not exact and allow_partial:
        matches = [item for item in items if wanted in normalize_name(item.get(field))]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ValueError(f"Não encontrei {kind} chamado '{query}'.")
    names = ", ".join(f"'{item.get(field)}' ({item.get('id')})" for item in matches[:6])
    raise ValueError(f"Há mais de uma correspondência para '{query}': {names}. Diga qual, pelo nome exato ou id.")


def _norm_days(raw_list: Any) -> list[str]:
    if raw_list is None:
        return []
    if not isinstance(raw_list, (list, tuple)):
        raise ValueError("days_of_week deve ser uma lista de dias.")
    result: list[str] = []
    for item in raw_list:
        if isinstance(item, int):
            if 0 <= item <= 6:
                day = WEEK_DAYS[item]
            else:
                raise ValueError(f"Dia da semana inválido (índice 0-6): {item}.")
        else:
            clean = str(item).lower().strip()
            if clean.isdigit():
                idx = int(clean)
                if 0 <= idx <= 6:
                    day = WEEK_DAYS[idx]
                else:
                    raise ValueError(f"Dia da semana inválido (índice 0-6): '{item}'.")
            else:
                day = DAY_MAP.get(clean, clean)
                if day not in WEEK_DAYS:
                    raise ValueError(f"Dia da semana inválido: '{item}'.")
        if day not in result:
            result.append(day)
    return result


def _norm_time(time_str: Any) -> str:
    if not time_str:
        return "15:00"
    t = str(time_str).lower().strip()
    if "às " in t: t = t.replace("às ", "")
    if "as " in t: t = t.replace("as ", "")
    if "horas" in t: t = t.replace("horas", "").strip()
    if "hora" in t: t = t.replace("hora", "").strip()
    if "h" in t and ":" not in t: t = t.replace("h", "").strip()
    try:
        val = int(t)
        return f"{val:02d}:00"
    except ValueError:
        return str(time_str)


def _norm_exceptions(raw: Any) -> dict[str, str]:
    if not raw:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("time_exceptions deve ser um objeto dia → horário.")
    return {DAY_MAP.get(str(k).lower().strip(), str(k).lower().strip()): _norm_time(v) for k, v in raw.items()}


def _clean_text(value: Any, label: str, limit: int = MAX_NAME, *, required: bool = True) -> str:
    if value is None or value == "":
        if required:
            raise ValueError(f"{label} é obrigatório.")
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{label} deve ser texto.")
    cleaned = value.strip()
    if required and not cleaned:
        raise ValueError(f"{label} é obrigatório.")
    if len(cleaned) > limit:
        raise ValueError(f"{label} deve ter no máximo {limit} caracteres.")
    return cleaned


def _prepare_habit(spec: Any) -> dict[str, Any]:
    """Valida um hábito para criação. Levanta ValueError (pt-BR)."""
    if not isinstance(spec, dict):
        raise ValueError("Cada hábito deve ser um objeto com pelo menos 'name'.")
    name = _clean_text(spec.get("name"), "Nome do hábito")
    block = str(spec.get("routine_block") or "anytime").strip().lower()
    if block not in ROUTINE_BLOCKS:
        raise ValueError(f"Bloco de rotina inválido em '{name}': use " + ", ".join(ROUTINE_BLOCKS) + ".")
    items = spec.get("items_list") or []
    if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
        raise ValueError(f"items_list de '{name}' deve ser uma lista de textos.")
    return {
        "name": name,
        "category": _clean_text(spec.get("category"), "Categoria", 60, required=False) or "general",
        "routine_block": block,
        "days_of_week": _norm_days(spec.get("days_of_week")) or list(WEEK_DAYS),
        "start_time": _norm_time(spec.get("start_time")),
        "time_exceptions": _norm_exceptions(spec.get("time_exceptions")),
        "items_list": [item.strip() for item in items if item.strip()],
        "day_slots": spec.get("day_slots") or {},
    }


def _habit_brief(habit: dict[str, Any] | None) -> dict[str, Any]:
    habit = habit or {}
    return {key: habit.get(key) for key in ("id", "name", "category", "routine_block", "days_of_week", "start_time", "completed_today", "current_streak")}


class HabitTool(BaseTool):
    @property
    def name(self) -> str:
        return "habit_tool"

    @property
    def description(self) -> str:
        return (
            "Cadastro de hábitos e rotinas da usuária (lista de hábitos do Painel pessoal): listar, criar, renomear, "
            "mudar dias/horário/itens, marcar ou desmarcar como feito hoje e excluir. Para vários hábitos use UMA chamada "
            "com create_many (lista 'habits') ou check_many (lista 'names'). Use esta ferramenta para ADICIONAR hábitos. "
            "Não use para água, treino ou resumo do dia: isso é lifeos_tool. Hábitos podem ser indicados pelo nome."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        habit_fields = {
            "name": {"type": "string", "description": "Nome do hábito (ex.: 'Ler 20 minutos')."},
            "category": {"type": "string", "description": "Categoria (ex.: estudos, saúde, trabalho)."},
            "routine_block": {"type": "string", "enum": list(ROUTINE_BLOCKS), "description": "Período do dia: morning (manhã), afternoon (tarde), evening (noite), anytime (qualquer hora)."},
            "days_of_week": {"type": "array", "items": {"type": "string"}, "description": "Dias (ex.: ['mon','wed','fri'] ou ['segunda','quarta']). Vazio = todos os dias."},
            "start_time": {"type": "string", "description": "Horário de início HH:MM (ex.: '07:30')."},
            "items_list": {"type": "array", "items": {"type": "string"}, "description": "Sub-itens/matérias do hábito."},
            "day_slots": {"type": "object", "description": "Slots e substituições por dia da semana (ex.: {'mon': '20min inglês', 'tue': '30min xadrez'})."},
        }
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "create", "create_many", "update", "check", "check_many", "uncheck", "delete", "auto_check"],
                    "description": "list: lê; create: 1 hábito; create_many: vários de uma vez; update: altera; check/uncheck: marca/desmarca hoje; check_many: marca vários hoje; delete: exclui (pede aprovação); auto_check: marca hábitos por diálogo contextual.",
                },
                "habit_id": {"type": "string", "description": "Id do hábito, quando conhecido (ou o nome)."},
                **habit_fields,
                "new_name": {"type": "string", "description": "update: novo nome do hábito."},
                "time_exceptions": {"type": "object", "description": "Horário diferente em dias específicos (ex.: {'tue': '14:00'})."},
                "add_days": {"type": "array", "items": {"type": "string"}, "description": "update: dias a adicionar."},
                "remove_days": {"type": "array", "items": {"type": "string"}, "description": "update: dias a remover."},
                "add_items": {"type": "array", "items": {"type": "string"}, "description": "update: itens a adicionar."},
                "remove_items": {"type": "array", "items": {"type": "string"}, "description": "update: itens a remover."},
                "habits": {
                    "type": "array",
                    "maxItems": MAX_HABITS_PER_CALL,
                    "items": {"type": "object", "properties": habit_fields, "required": ["name"]},
                    "description": f"create_many: até {MAX_HABITS_PER_CALL} hábitos.",
                },
                "names": {"type": "array", "items": {"type": "string"}, "maxItems": MAX_HABITS_PER_CALL, "description": "check_many: nomes dos hábitos feitos hoje."},
                "only_today": {"type": "boolean", "description": "list: só os hábitos programados para hoje."},
            },
            "required": ["action"],
        }

    @staticmethod
    def _find(habit_id: str, name: str, *, allow_partial: bool) -> dict[str, Any]:
        if habit_id:
            found = HabitService.get_habit(habit_id)
            if found:
                return found
            name = name or habit_id
        return resolve_by_name(HabitService.list_habits(), name, "name", kind="o hábito", allow_partial=allow_partial)

    def run(
        self,
        action: str = "list",
        habit_id: str = "",
        name: str = "",
        category: str | None = None,
        routine_block: str | None = None,
        days_of_week: list[str] | None = None,
        start_time: str = "15:00",
        time_exceptions: dict[str, str] | None = None,
        items_list: list[str] | None = None,
        day_slots: dict[str, Any] | None = None,
        add_days: list[str] | None = None,
        remove_days: list[str] | None = None,
        add_items: list[str] | None = None,
        remove_items: list[str] | None = None,
        new_name: str = "",
        habits: list[dict[str, Any]] | None = None,
        names: list[str] | None = None,
        only_today: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        act = (action or "list").lower().strip()
        try:
            return self._dispatch(act, action, locals())
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

    def _dispatch(self, act: str, action: str, a: dict[str, Any]) -> dict[str, Any]:
        habit_id, name = str(a["habit_id"] or "").strip(), str(a["name"] or "").strip()

        if act == "list":
            habits = HabitService.list_habits()
            if a["only_today"]:
                today = WEEK_DAYS[date.today().weekday()]
                habits = [h for h in habits if today in (h.get("days_of_week") or WEEK_DAYS)]
                return {"ok": True, "message": f"{len(habits)} hábito(s) para hoje.", "habits": habits}
            return {"ok": True, "message": f"{len(habits)} hábito(s) cadastrado(s).", "habits": habits}

        if act == "create":
            spec = {
                "name": name, "category": a["category"], "routine_block": a["routine_block"],
                "days_of_week": a["days_of_week"], "start_time": a["start_time"],
                "time_exceptions": a["time_exceptions"], "items_list": a["items_list"],
                "day_slots": a.get("day_slots"),
            }
            prepared = _prepare_habit(spec)
            h_id = habit_id or f"habit_{uuid.uuid4().hex[:8]}"
            res = HabitService.create_habit(h_id, **prepared)
            items_desc = f" ({', '.join(prepared['items_list'])})" if prepared["items_list"] else ""
            days_desc = ", ".join(prepared["days_of_week"])
            return {
                "ok": True,
                "message": f"Hábito '{prepared['name']}'{items_desc} criado para [{days_desc}] às {prepared['start_time']}!",
                "habit": res, "habit_ids": [h_id], "habits": [_habit_brief(res)],
            }

        if act == "create_many":
            specs = a["habits"]
            if not isinstance(specs, list) or not specs:
                raise ValueError("Informe a lista 'habits' com pelo menos um hábito.")
            if len(specs) > MAX_HABITS_PER_CALL:
                raise ValueError(f"No máximo {MAX_HABITS_PER_CALL} hábitos por chamada; nada foi criado.")
            prepared_list = []
            for index, spec in enumerate(specs, 1):
                try:
                    prepared_list.append(_prepare_habit(spec))
                except ValueError as exc:
                    raise ValueError(f"Hábito {index}: {exc} Nada foi criado.") from None
            created = []
            for prepared in prepared_list:
                h_id = f"habit_{uuid.uuid4().hex[:8]}"
                created.append(HabitService.create_habit(h_id, **prepared))
            names_desc = ", ".join(item["name"] for item in prepared_list)
            return {
                "ok": True,
                "message": f"{len(created)} hábito(s) criado(s): {names_desc}.",
                "habit_ids": [item["id"] for item in created],
                "habits": [_habit_brief(item) for item in created],
            }

        if act == "update":
            target = self._find(habit_id, name, allow_partial=True)
            h_id = target["id"]
            current_days = list(target.get("days_of_week") or [])
            current_items = list(target.get("items_list") or [])
            current_exceptions = dict(target.get("time_exceptions") or {})

            if a["days_of_week"] is not None:
                current_days = _norm_days(a["days_of_week"])
            for d in _norm_days(a["add_days"]):
                if d not in current_days:
                    current_days.append(d)
            for d in _norm_days(a["remove_days"]):
                if d in current_days:
                    current_days.remove(d)

            if a["items_list"] is not None:
                current_items = list(a["items_list"])
            for item in a["add_items"] or []:
                if item not in current_items:
                    current_items.append(item)
            for item in a["remove_items"] or []:
                if item in current_items:
                    current_items.remove(item)

            start_time = a["start_time"]
            new_start = _norm_time(start_time) if start_time and start_time != "15:00" else target.get("start_time", "15:00")
            current_exceptions.update(_norm_exceptions(a["time_exceptions"]))

            changes: dict[str, Any] = {}
            if a["new_name"]:
                changes["name"] = _clean_text(a["new_name"], "Novo nome")
            if a["category"] is not None:
                changes["category"] = _clean_text(a["category"], "Categoria", 60)
            if a["routine_block"] is not None:
                block = str(a["routine_block"]).strip().lower()
                if block not in ROUTINE_BLOCKS:
                    raise ValueError("Bloco de rotina inválido: use " + ", ".join(ROUTINE_BLOCKS) + ".")
                changes["routine_block"] = block

            if a.get("day_slots") is not None:
                changes["day_slots"] = a["day_slots"]

            res = HabitService.update_habit(
                h_id,
                days_of_week=current_days,
                start_time=new_start,
                time_exceptions=current_exceptions,
                items_list=current_items,
                **changes,
            )
            return {"ok": True, "message": f"Hábito '{target['name']}' atualizado com sucesso!", "habit": res, "habit_ids": [h_id]}

        if act == "auto_check":
            text_query = name or a.get("new_name") or habit_id
            checked = HabitService.contextual_auto_check(text=text_query)
            names_desc = ", ".join(f"'{h['name']}'" for h in checked)
            msg = f"{len(checked)} hábito(s) marcado(s) automaticamente: {names_desc}." if checked else "Nenhum hábito elegível para auto-check."
            return {"ok": True, "message": msg, "checked_habits": checked, "habit_ids": [h["id"] for h in checked]}

        if act in ("check", "complete", "done"):
            target = self._find(habit_id, name, allow_partial=True)
            res = HabitService.check_in(target["id"])
            return {
                "ok": True,
                "message": f"Hábito '{target['name']}' concluído hoje! 🔥 Streak atual: {res.get('current_streak', 1)} dia(s).",
                "habit": res, "habit_ids": [target["id"]],
            }

        if act == "check_many":
            wanted = a["names"]
            if not isinstance(wanted, list) or not wanted:
                raise ValueError("Informe a lista 'names' com os hábitos feitos hoje.")
            if len(wanted) > MAX_HABITS_PER_CALL:
                raise ValueError(f"No máximo {MAX_HABITS_PER_CALL} hábitos por chamada; nada foi marcado.")
            all_habits = HabitService.list_habits()
            targets = []
            for item in wanted:
                found = resolve_by_name(all_habits, str(item), "name", kind="o hábito", allow_partial=True)
                if found["id"] not in {t["id"] for t in targets}:
                    targets.append(found)
            checked = [HabitService.check_in(t["id"]) for t in targets]
            return {
                "ok": True,
                "message": f"{len(targets)} hábito(s) marcado(s) hoje: " + ", ".join(t["name"] for t in targets) + ".",
                "habit_ids": [t["id"] for t in targets],
                "habits": [_habit_brief(item) for item in checked],
            }

        if act in ("uncheck", "undo"):
            target = self._find(habit_id, name, allow_partial=True)
            res = HabitService.uncheck_in(target["id"])
            return {"ok": True, "message": f"Check-in de hoje do hábito '{target['name']}' desfeito.", "habit": res, "habit_ids": [target["id"]]}

        if act == "delete":
            target = self._find(habit_id, name, allow_partial=False)
            ok = HabitService.delete_habit(target["id"])
            return {"ok": ok, "message": f"Hábito '{target['name']}' removido." if ok else "Hábito não encontrado.", "habit_ids": [target["id"]]}

        return {"ok": False, "error": f"Ação desconhecida: {action}"}


def _clean_priority(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("Prioridade deve ser um número de 1 a 4.")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError("Prioridade deve ser um número de 1 a 4.") from None
    if not 1 <= number <= 4:
        raise ValueError("Prioridade deve ser um número de 1 a 4.")
    return number


def _clean_due(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        raise ValueError("Data de vencimento inválida: use AAAA-MM-DD.") from None


def _prepare_task(spec: Any) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise ValueError("Cada tarefa deve ser um objeto com pelo menos 'title'.")
    return {
        "title": _clean_text(spec.get("title"), "Título da tarefa", 200),
        "priority": _clean_priority(spec.get("priority", 3)),
        "project": _clean_text(spec.get("project"), "Projeto", 60, required=False) or "Geral",
        "due_date": _clean_due(spec.get("due_date")),
    }


class TaskTool(BaseTool):
    @property
    def name(self) -> str:
        return "task_tool"

    @property
    def description(self) -> str:
        return (
            "Tarefas e pendências da usuária: listar, criar (prioridade 1=urgente a 4=baixa), editar, concluir/reabrir e "
            "excluir. Para várias tarefas use UMA chamada create_many (lista 'tasks'). Tarefas podem ser indicadas pelo título. "
            "Datas no formato AAAA-MM-DD. Compromisso com horário vai para calendar, não para cá."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        task_fields = {
            "title": {"type": "string", "description": "Título da tarefa."},
            "priority": {"type": "integer", "minimum": 1, "maximum": 4, "description": "1=P1 urgente, 2=alta, 3=média (padrão), 4=baixa."},
            "project": {"type": "string", "description": "Projeto ou categoria (padrão Geral)."},
            "due_date": {"type": "string", "description": "Vencimento AAAA-MM-DD (opcional)."},
        }
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "create", "create_many", "update", "toggle", "delete"],
                    "description": "list: lê; create: 1 tarefa; create_many: várias; update: edita; toggle: conclui ou reabre; delete: exclui (pede aprovação).",
                },
                "task_id": {"type": "string", "description": "Id da tarefa, quando conhecido."},
                **task_fields,
                "new_title": {"type": "string", "description": "update: novo título."},
                "tasks": {
                    "type": "array",
                    "maxItems": MAX_TASKS_PER_CALL,
                    "items": {"type": "object", "properties": task_fields, "required": ["title"]},
                    "description": f"create_many: até {MAX_TASKS_PER_CALL} tarefas.",
                },
                "include_completed": {"type": "boolean", "description": "list: inclui as tarefas concluídas."},
            },
            "required": ["action"],
        }

    @staticmethod
    def _find(task_id: str, title: str, *, allow_partial: bool) -> dict[str, Any]:
        if task_id:
            found = TaskService.get_task(task_id)
            if found:
                return found
            if not title:
                raise ValueError("Tarefa não encontrada.")
        return resolve_by_name(TaskService.list_tasks(completed=None), title, "title", kind="a tarefa", allow_partial=allow_partial)

    def run(
        self,
        action: str = "list",
        task_id: str = "",
        title: str = "",
        priority: int | None = None,
        project: str | None = None,
        due_date: str | None = None,
        new_title: str = "",
        tasks: list[dict[str, Any]] | None = None,
        include_completed: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        act = (action or "list").lower().strip()
        task_id, title = str(task_id or "").strip(), str(title or "").strip()
        try:
            if act == "list":
                listed = TaskService.list_tasks(completed=None if include_completed else False, project=project if project and project != "Geral" else "")
                label = "tarefa(s)" if include_completed else "tarefa(s) pendente(s)"
                return {"ok": True, "message": f"{len(listed)} {label}.", "tasks": listed}

            if act == "create":
                prepared = _prepare_task({"title": title, "priority": 3 if priority is None else priority, "project": project, "due_date": due_date})
                t_id = task_id or f"task_{uuid.uuid4().hex[:8]}"
                res = TaskService.create_task(t_id, **prepared)
                return {"ok": True, "message": f"Tarefa '{prepared['title']}' criada (P{prepared['priority']}).", "task": res, "task_ids": [t_id]}

            if act == "create_many":
                if not isinstance(tasks, list) or not tasks:
                    raise ValueError("Informe a lista 'tasks' com pelo menos uma tarefa.")
                if len(tasks) > MAX_TASKS_PER_CALL:
                    raise ValueError(f"No máximo {MAX_TASKS_PER_CALL} tarefas por chamada; nada foi criado.")
                prepared_list = []
                for index, spec in enumerate(tasks, 1):
                    try:
                        prepared_list.append(_prepare_task(spec))
                    except ValueError as exc:
                        raise ValueError(f"Tarefa {index}: {exc} Nada foi criado.") from None
                created = [TaskService.create_task(f"task_{uuid.uuid4().hex[:8]}", **item) for item in prepared_list]
                return {
                    "ok": True,
                    "message": f"{len(created)} tarefa(s) criada(s): " + ", ".join(item["title"] for item in prepared_list) + ".",
                    "task_ids": [item["id"] for item in created],
                    "tasks": created,
                }

            if act == "update":
                target = self._find(task_id, title, allow_partial=True)
                changes: dict[str, Any] = {}
                if new_title:
                    changes["title"] = _clean_text(new_title, "Novo título", 200)
                if priority is not None:
                    changes["priority"] = _clean_priority(priority)
                if project is not None:
                    changes["project"] = _clean_text(project, "Projeto", 60) or "Geral"
                if due_date is not None:
                    changes["due_date"] = _clean_due(due_date)
                if not changes:
                    raise ValueError("Nada para alterar: informe new_title, priority, project ou due_date.")
                res = TaskService.update_task(target["id"], **changes)
                return {"ok": res is not None, "message": f"Tarefa '{target['title']}' atualizada.", "task": res, "task_ids": [target["id"]]}

            if act in ("toggle", "complete", "done"):
                target = self._find(task_id, title, allow_partial=True)
                res = TaskService.toggle_task(target["id"])
                if not res:
                    return {"ok": False, "error": "Tarefa não encontrada."}
                status_str = "concluída" if res["completed"] == 1 else "reaberta"
                return {"ok": True, "message": f"Tarefa '{res['title']}' {status_str}.", "task": res, "task_ids": [res["id"]]}

            if act == "delete":
                target = self._find(task_id, title, allow_partial=False)
                ok = TaskService.delete_task(target["id"])
                return {"ok": ok, "message": f"Tarefa '{target['title']}' excluída." if ok else "Tarefa não encontrada.", "task_ids": [target["id"]]}
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        return {"ok": False, "error": f"Ação desconhecida: {action}"}


def _brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _period_start(period: str) -> str:
    today = date.today()
    if period == "week":
        return (today - timedelta(days=6)).isoformat()
    if period == "month":
        return today.replace(day=1).isoformat()
    if period in ("", "all"):
        return ""
    raise ValueError("Período inválido: use week, month ou all.")


class FinanceTool(BaseTool):
    @property
    def name(self) -> str:
        return "finance_tool"

    @property
    def description(self) -> str:
        return (
            "Finanças pessoais: resumo do mês e saldo, lançar receitas/despesas, listar lançamentos com filtro "
            "(período, tipo, categoria), corrigir e excluir lançamentos. Vários gastos de uma vez: UMA chamada add_many "
            "(lista 'entries'). Valores em reais; datas AAAA-MM-DD (padrão hoje). Para só abrir a tela de finanças, use open_window."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        entry_fields = {
            "type": {"type": "string", "enum": ["expense", "income"], "description": "expense = despesa (padrão); income = receita."},
            "amount": {"type": "number", "description": "Valor em reais, maior que zero."},
            "category": {"type": "string", "description": "Categoria (ex.: Alimentação, Moradia, Lazer, Salário)."},
            "description": {"type": "string", "description": "Descrição curta."},
            "date": {"type": "string", "description": "Data AAAA-MM-DD (padrão hoje)."},
        }
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["summary", "add", "add_many", "list", "update", "delete"],
                    "description": "summary: resumo; add: 1 lançamento; add_many: vários; list: lista com filtros; update: corrige; delete: exclui (pede aprovação).",
                },
                **entry_fields,
                "trans_id": {"type": "string", "description": "Id do lançamento (update e delete)."},
                "entries": {
                    "type": "array",
                    "maxItems": MAX_ENTRIES_PER_CALL,
                    "items": {"type": "object", "properties": entry_fields, "required": ["amount"]},
                    "description": f"add_many: até {MAX_ENTRIES_PER_CALL} lançamentos.",
                },
                "period": {"type": "string", "enum": ["week", "month", "all"], "description": "list: últimos 7 dias, mês atual ou tudo (padrão month)."},
            },
            "required": ["action"],
        }

    def run(
        self,
        action: str = "summary",
        type: str | None = None,
        amount: float | None = None,
        category: str | None = None,
        description: str | None = None,
        trans_id: str = "",
        entries: list[dict[str, Any]] | None = None,
        period: str = "month",
        date: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        act = (action or "summary").lower().strip()
        try:
            if act == "summary":
                summary = FinanceService.get_summary()
                return {
                    "ok": True,
                    "message": f"Saldo total: R$ {summary['total_balance']:.2f} | Mês atual: R$ {summary['income']:.2f} (entradas) / R$ {summary['expense']:.2f} (saídas).",
                    "summary": summary,
                }

            if act in ("add", "create"):
                if not isinstance(amount, (int, float)) or isinstance(amount, bool) or amount <= 0:
                    return {"ok": False, "error": "Informe um valor maior que zero."}
                t_id = trans_id or f"fin_{uuid.uuid4().hex[:8]}"
                t_type = "income" if str(type or "").lower() in ("income", "receita", "ganho") else "expense"
                label = category or "Outros"
                summary = FinanceService.add_transaction(t_id, t_type, amount, category=label, description=description or "", date_str=str(date or ""))
                type_label = "Receita" if t_type == "income" else "Despesa"
                return {"ok": True, "message": f"{type_label} de R$ {amount:.2f} lançada na categoria '{label}'.", "summary": summary, "trans_ids": [t_id]}

            if act == "add_many":
                if not isinstance(entries, list) or not entries:
                    raise ValueError("Informe a lista 'entries' com pelo menos um lançamento.")
                if len(entries) > MAX_ENTRIES_PER_CALL:
                    raise ValueError(f"No máximo {MAX_ENTRIES_PER_CALL} lançamentos por chamada; nada foi gravado.")
                prepared = []
                for index, spec in enumerate(entries, 1):
                    if not isinstance(spec, dict):
                        raise ValueError(f"Lançamento {index}: deve ser um objeto. Nada foi gravado.")
                    kind = str(spec.get("type") or "expense").strip().lower()
                    kind = "income" if kind in ("income", "receita", "ganho") else kind
                    kind = "expense" if kind in ("despesa", "gasto") else kind
                    try:
                        prepared.append(FinanceService.normalize_entry(kind, spec.get("amount"), spec.get("category"), spec.get("description"), spec.get("date")))
                    except ValueError as exc:
                        raise ValueError(f"Lançamento {index}: {exc} Nada foi gravado.") from None
                ids = []
                summary: dict[str, Any] = {}
                for entry in prepared:
                    t_id = f"fin_{uuid.uuid4().hex[:8]}"
                    summary = FinanceService.add_transaction(t_id, entry["type"], entry["amount"], category=entry["category"], description=entry["description"], date_str=entry["date_str"])
                    ids.append(t_id)
                total = round(sum(entry["amount"] for entry in prepared), 2)
                return {
                    "ok": True,
                    "message": f"{len(ids)} lançamento(s) gravado(s), total {_brl(total)}.",
                    "trans_ids": ids, "total": total, "summary": summary,
                }

            if act == "list":
                kind = str(type or "").strip().lower()
                if kind and kind not in ("expense", "income"):
                    raise ValueError("Tipo inválido: use expense ou income.")
                result = FinanceService.query_transactions(date_from=_period_start(str(period or "month").lower()), type_=kind, category=str(category or "").strip(), limit=50)
                totals = result["totals"]
                return {
                    "ok": True,
                    "message": f"{totals['count']} lançamento(s): entradas {_brl(totals['income'])}, saídas {_brl(totals['expense'])}.",
                    "transactions": result["transactions"], "totals": totals, "truncated": result["truncated"],
                }

            if act == "update":
                if not trans_id:
                    raise ValueError("Informe o id do lançamento (trans_id) a corrigir.")
                current = FinanceService.get_transaction(trans_id)
                if not current:
                    raise ValueError("Lançamento não encontrado.")
                updated = FinanceService.update_transaction(
                    trans_id,
                    type if type is not None else current["type"],
                    amount if amount is not None else current["amount"],
                    category if category is not None else current["category"],
                    description if description is not None else current["description"],
                    date if date is not None else current["date_str"],
                )
                if updated is None:
                    raise ValueError("Lançamento não encontrado.")
                return {"ok": True, "message": f"Lançamento atualizado: {_brl(float(updated['amount']))} em '{updated['category']}'.", "transaction": updated, "trans_ids": [trans_id]}

            if act == "delete":
                if not trans_id:
                    return {"ok": False, "error": "ID da transação é obrigatório."}
                summary = FinanceService.delete_transaction(trans_id)
                return {"ok": True, "message": "Transação removida.", "summary": summary, "trans_ids": [trans_id]}
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        return {"ok": False, "error": f"Ação desconhecida: {action}"}
