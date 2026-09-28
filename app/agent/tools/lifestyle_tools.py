"""Lifestyle AI Tools (HabitTool, TaskTool, FinanceTool).

Enables Jarvis AI (Orchestrator, Voice, Proactive Daemon) to query and update
habits, checklists, tasks, and personal finance via natural language commands.
"""
from __future__ import annotations

import uuid
from typing import Any

from app.agent.tools.base import BaseTool, ToolResult
from app.services.habits import HabitService
from app.services.tasks import TaskService
from app.services.finance import FinanceService


class HabitTool(BaseTool):
    @property
    def name(self) -> str:
        return "habit_tool"

    @property
    def description(self) -> str:
        return "Gerencia hábitos e rotinas (listar, criar, atualizar dias/horários/matérias, marcar como concluído ou desmarcar)."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "create", "update", "check", "uncheck", "delete"],
                    "description": "Ação a realizar nos hábitos.",
                },
                "habit_id": {"type": "string", "description": "ID do hábito (ou nome para busca)."},
                "name": {"type": "string", "description": "Nome do hábito."},
                "category": {"type": "string", "description": "Categoria do hábito (ex: estudos, saúde, trabalho)."},
                "routine_block": {"type": "string", "enum": ["morning", "afternoon", "evening", "anytime"]},
                "days_of_week": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista dos dias da semana (ex: ['mon', 'wed', 'fri'] ou ['segunda', 'quarta', 'sexta']).",
                },
                "start_time": {"type": "string", "description": "Horário padrão de início (ex: '15:00' ou '3 horas')."},
                "time_exceptions": {
                    "type": "object",
                    "description": "Exceção de horário por dia específico (ex: {'tue': '14:00', 'terça': '14:00'}).",
                },
                "items_list": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de matérias, assuntos ou sub-itens do hábito (ex: ['História', 'Matemática', 'Geografia']).",
                },
                "add_days": {"type": "array", "items": {"type": "string"}, "description": "Dias a adicionar ao hábito."},
                "remove_days": {"type": "array", "items": {"type": "string"}, "description": "Dias a remover do hábito."},
                "add_items": {"type": "array", "items": {"type": "string"}, "description": "Matérias/itens a adicionar ao hábito."},
                "remove_items": {"type": "array", "items": {"type": "string"}, "description": "Matérias/itens a remover do hábito."},
            },
            "required": ["action"],
        }

    def run(
        self,
        action: str = "list",
        habit_id: str = "",
        name: str = "",
        category: str = "general",
        routine_block: str = "anytime",
        days_of_week: list[str] | None = None,
        start_time: str = "15:00",
        time_exceptions: dict[str, str] | None = None,
        items_list: list[str] | None = None,
        add_days: list[str] | None = None,
        remove_days: list[str] | None = None,
        add_items: list[str] | None = None,
        remove_items: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        act = (action or "list").lower().strip()

        # Helper to normalize day names to ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
        day_map = {
            "segunda": "mon", "segunda-feira": "mon", "seg": "mon", "mon": "mon", "monday": "mon",
            "terça": "tue", "terca": "tue", "terça-feira": "tue", "ter": "tue", "tue": "tue", "tuesday": "tue",
            "quarta": "wed", "quarta-feira": "wed", "qua": "wed", "wed": "wed", "wednesday": "wed",
            "quinta": "thu", "quinta-feira": "thu", "qui": "thu", "thu": "thu", "thursday": "thu",
            "sexta": "fri", "sexta-feira": "fri", "sex": "fri", "fri": "fri", "friday": "fri",
            "sábado": "sat", "sabado": "sat", "sáb": "sat", "sab": "sat", "sat": "sat", "saturday": "sat",
            "domingo": "sun", "dom": "sun", "sun": "sun", "sunday": "sun",
        }

        def norm_days(raw_list: list[str] | None) -> list[str]:
            if not raw_list:
                return []
            res = []
            for d in raw_list:
                clean = str(d).lower().strip()
                res.append(day_map.get(clean, clean))
            return res

        def norm_time(time_str: str) -> str:
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
                return time_str

        if act == "list":
            habits = HabitService.list_habits()
            return {"ok": True, "message": f"{len(habits)} hábito(s) cadastrado(s).", "habits": habits}

        if act == "create":
            if not name:
                return {"ok": False, "error": "Nome do hábito é obrigatório para criação."}
            h_id = habit_id or f"habit_{uuid.uuid4().hex[:8]}"
            norm_days_list = norm_days(days_of_week) or ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
            norm_start = norm_time(start_time)
            
            norm_exceptions = {}
            if time_exceptions:
                for k, v in time_exceptions.items():
                    norm_k = day_map.get(str(k).lower().strip(), str(k).lower().strip())
                    norm_exceptions[norm_k] = norm_time(v)

            res = HabitService.create_habit(
                h_id,
                name,
                category=category,
                routine_block=routine_block,
                days_of_week=norm_days_list,
                start_time=norm_start,
                time_exceptions=norm_exceptions,
                items_list=items_list or [],
            )
            items_desc = f" ({', '.join(items_list)})" if items_list else ""
            days_desc = ", ".join(norm_days_list)
            return {"ok": True, "message": f"Hábito '{name}'{items_desc} criado para [{days_desc}] às {norm_start}!", "habit": res}

        if act == "update":
            # Find target habit by ID or by matching name/items
            target = None
            if habit_id:
                target = HabitService.get_habit(habit_id)
            if not target and name:
                for h in HabitService.list_habits():
                    if name.lower() in h["name"].lower() or any(name.lower() in item.lower() for item in h.get("items_list", [])):
                        target = h
                        break
            if not target:
                return {"ok": False, "error": "Hábito não encontrado para atualização."}

            h_id = target["id"]
            current_days = list(target.get("days_of_week") or [])
            current_items = list(target.get("items_list") or [])
            current_exceptions = dict(target.get("time_exceptions") or {})

            if days_of_week is not None:
                current_days = norm_days(days_of_week)
            if add_days:
                for d in norm_days(add_days):
                    if d not in current_days:
                        current_days.append(d)
            if remove_days:
                for d in norm_days(remove_days):
                    if d in current_days:
                        current_days.remove(d)

            if items_list is not None:
                current_items = items_list
            if add_items:
                for item in add_items:
                    if item not in current_items:
                        current_items.append(item)
            if remove_items:
                for item in remove_items:
                    if item in current_items:
                        current_items.remove(item)

            new_start = norm_time(start_time) if start_time and start_time != "15:00" else target.get("start_time", "15:00")

            if time_exceptions:
                for k, v in time_exceptions.items():
                    norm_k = day_map.get(str(k).lower().strip(), str(k).lower().strip())
                    current_exceptions[norm_k] = norm_time(v)

            res = HabitService.update_habit(
                h_id,
                days_of_week=current_days,
                start_time=new_start,
                time_exceptions=current_exceptions,
                items_list=current_items,
            )
            return {"ok": True, "message": f"Hábito '{target['name']}' atualizado com sucesso!", "habit": res}

        if act in ("check", "complete", "done"):
            if not habit_id and name:
                for h in HabitService.list_habits():
                    if name.lower() in h["name"].lower():
                        habit_id = h["id"]
                        break
            if not habit_id:
                return {"ok": False, "error": "Informe o ID ou nome do hábito."}
            res = HabitService.check_in(habit_id)
            return {"ok": True, "message": f"Hábito concluído hoje! 🔥 Streak atual: {res.get('current_streak', 1)} dia(s).", "habit": res}

        if act in ("uncheck", "undo"):
            if not habit_id and name:
                for h in HabitService.list_habits():
                    if name.lower() in h["name"].lower():
                        habit_id = h["id"]
                        break
            if not habit_id:
                return {"ok": False, "error": "ID do hábito é obrigatório."}
            res = HabitService.uncheck_in(habit_id)
            return {"ok": True, "message": "Check-in do hábito desfeito.", "habit": res}

        if act == "delete":
            if not habit_id:
                return {"ok": False, "error": "ID do hábito é obrigatório."}
            ok = HabitService.delete_habit(habit_id)
            return {"ok": ok, "message": "Hábito removido." if ok else "Hábito não encontrado."}

        return {"ok": False, "error": f"Ação desconhecida: {action}"}


class TaskTool(BaseTool):
    @property
    def name(self) -> str:
        return "task_tool"

    @property
    def description(self) -> str:
        return "Gerencia tarefas e checklists (listar tarefas pendentes, criar tarefa com prioridade P1-P4, alternar conclusão)."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "create", "toggle", "delete"],
                    "description": "Ação a realizar nas tarefas.",
                },
                "task_id": {"type": "string", "description": "ID da tarefa."},
                "title": {"type": "string", "description": "Título da tarefa."},
                "priority": {"type": "integer", "description": "Prioridade 1=P1 Urgente a 4=P4 Baixa."},
                "project": {"type": "string", "description": "Projeto ou categoria da tarefa."},
                "due_date": {"type": "string", "description": "Data de vencimento (YYYY-MM-DD)."},
            },
            "required": ["action"],
        }

    def run(self, action: str = "list", task_id: str = "", title: str = "", priority: int = 3, project: str = "Geral", due_date: str = "", **kwargs: Any) -> dict[str, Any]:
        act = (action or "list").lower().strip()

        if act == "list":
            tasks = TaskService.list_tasks(completed=False, project=project if project != "Geral" else "")
            return {"ok": True, "message": f"{len(tasks)} tarefa(s) pendente(s).", "tasks": tasks}

        if act == "create":
            if not title:
                return {"ok": False, "error": "Título da tarefa é obrigatório."}
            t_id = task_id or f"task_{uuid.uuid4().hex[:8]}"
            res = TaskService.create_task(t_id, title, priority=priority, project=project, due_date=due_date)
            return {"ok": True, "message": f"Tarefa '{title}' criada (P{priority}).", "task": res}

        if act in ("toggle", "complete", "done"):
            if not task_id and title:
                for t in TaskService.list_tasks(completed=None):
                    if title.lower() in t["title"].lower():
                        task_id = t["id"]
                        break
            if not task_id:
                return {"ok": False, "error": "Informe o ID ou título da tarefa."}
            res = TaskService.toggle_task(task_id)
            if not res:
                return {"ok": False, "error": "Tarefa não encontrada."}
            status_str = "concluída" if res["completed"] == 1 else "reaberta"
            return {"ok": True, "message": f"Tarefa '{res['title']}' {status_str}.", "task": res}

        if act == "delete":
            if not task_id:
                return {"ok": False, "error": "ID da tarefa é obrigatório."}
            ok = TaskService.delete_task(task_id)
            return {"ok": ok, "message": "Tarefa excluída." if ok else "Tarefa não encontrada."}

        return {"ok": False, "error": f"Ação desconhecida: {action}"}


class FinanceTool(BaseTool):
    @property
    def name(self) -> str:
        return "finance_tool"

    @property
    def description(self) -> str:
        return "Gerencia finanças pessoais (resumo mensal, lançamento de receitas/despesas, saldo acumulado)."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["summary", "add", "list", "delete"],
                    "description": "Ação financeira a realizar.",
                },
                "type": {"type": "string", "enum": ["expense", "income"], "description": "Tipo de transação: receita ou despesa."},
                "amount": {"type": "number", "description": "Valor monetário da transação."},
                "category": {"type": "string", "description": "Categoria (ex: Alimentação, Moradia, Lazer, Salário)."},
                "description": {"type": "string", "description": "Descrição detalhada do lançamento."},
                "trans_id": {"type": "string", "description": "ID da transação para exclusão."},
            },
            "required": ["action"],
        }

    def run(self, action: str = "summary", type: str = "expense", amount: float = 0.0, category: str = "Outros", description: str = "", trans_id: str = "", **kwargs: Any) -> dict[str, Any]:
        act = (action or "summary").lower().strip()

        if act == "summary":
            summary = FinanceService.get_summary()
            return {
                "ok": True,
                "message": f"Saldo total: R$ {summary['total_balance']:.2f} | Mês atual: R$ {summary['income']:.2f} (entradas) / R$ {summary['expense']:.2f} (saídas).",
                "summary": summary,
            }

        if act in ("add", "create"):
            if amount <= 0:
                return {"ok": False, "error": "Informe um valor maior que zero."}
            t_id = trans_id or f"fin_{uuid.uuid4().hex[:8]}"
            t_type = "income" if type in ("income", "receita", "ganho") else "expense"
            summary = FinanceService.add_transaction(t_id, t_type, amount, category=category, description=description)
            type_label = "Receita" if t_type == "income" else "Despesa"
            return {"ok": True, "message": f"{type_label} de R$ {amount:.2f} lançada na categoria '{category}'.", "summary": summary}

        if act == "list":
            txs = FinanceService.list_transactions(limit=30)
            return {"ok": True, "message": f"{len(txs)} transação(ões) recente(s).", "transactions": txs}

        if act == "delete":
            if not trans_id:
                return {"ok": False, "error": "ID da transação é obrigatório."}
            summary = FinanceService.delete_transaction(trans_id)
            return {"ok": True, "message": "Transação removida.", "summary": summary}

        return {"ok": False, "error": f"Ação desconhecida: {action}"}
