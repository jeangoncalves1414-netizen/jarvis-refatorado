"""
System & Intelligence Domain REST Endpoints (LLM Route, Command Inspect, Diagram Generator)
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import date
from typing import Any, Callable

_FINANCE_ID_RE = re.compile(r"[A-Za-z0-9_.:-]{1,64}")


def handle_system_routes(path: str, body: bytes, send_json_fn: Callable[[int, dict[str, Any]], None]) -> bool:
    """Processa requisições REST para o domínio de Inteligência do Sistema e Segurança."""
    if path == "/api/llm/route":
        try:
            from app.services.llm_router import SmartLLMRouter
            payload = json.loads(body.decode("utf-8") or "{}")
            prompt = str(payload.get("prompt") or "")
            has_image = bool(payload.get("has_image", False))
            req_prov = payload.get("provider")
            router = SmartLLMRouter()
            decision = router.route(prompt, has_image=has_image, requested_provider=req_prov)
            send_json_fn(200, decision.to_dict())
        except Exception as exc:
            send_json_fn(500, {"ok": False, "error": str(exc)})
        return True

    if path == "/api/diagram/generate":
        try:
            from app.services.diagram_copilot import DiagramCopilotService
            payload = json.loads(body.decode("utf-8") or "{}")
            title = str(payload.get("title", "Diagrama"))
            steps = payload.get("steps") or []
            if steps:
                res = DiagramCopilotService.generate_flowchart(title, steps)
            else:
                raw_code = str(payload.get("mermaid_code") or payload.get("code") or "")
                res = DiagramCopilotService.from_text_prompt(title, raw_code)
            send_json_fn(200 if res.ok else 400, res.to_dict())
        except Exception as exc:
            send_json_fn(500, {"ok": False, "error": str(exc)})
        return True

    if path == "/api/command/inspect":
        try:
            from app.services.command_inspector import CommandInspector
            payload = json.loads(body.decode("utf-8") or "{}")
            cmd = str(payload.get("command") or payload.get("cmd") or "").strip()
            inspector = CommandInspector()
            audit = inspector.inspect(cmd)
            preview = inspector.generate_dry_run_preview(cmd)
            data = audit.to_dict()
            data["dry_run_markdown"] = preview
            send_json_fn(200, data)
        except Exception as exc:
            send_json_fn(500, {"ok": False, "error": str(exc)})
        return True

    if path == "/api/briefing/daily":
        try:
            from app.services.daily_briefing import generate_daily_briefing
            payload = json.loads(body.decode("utf-8") or "{}")
            name = str(payload.get("name") or "Senhor")
            city = str(payload.get("city") or "São Paulo")
            briefing = generate_daily_briefing(name=name, city=city)
            send_json_fn(200, {"ok": True, "briefing": briefing})
        except Exception as exc:
            send_json_fn(500, {"ok": False, "error": str(exc)})
        return True

    if path == "/api/meeting/start":
        try:
            from app.services.meeting_assistant import start_meeting
            payload = json.loads(body.decode("utf-8") or "{}")
            title = str(payload.get("title") or "")
            res = start_meeting(title=title)
            send_json_fn(200 if res.get("ok") else 400, res)
        except Exception as exc:
            send_json_fn(500, {"ok": False, "error": str(exc)})
        return True

    if path == "/api/meeting/stop":
        try:
            from app.services.meeting_assistant import stop_meeting
            res = stop_meeting()
            send_json_fn(200 if res.get("ok") else 400, res)
        except Exception as exc:
            send_json_fn(500, {"ok": False, "error": str(exc)})
        return True

    if path == "/api/meeting/minutes":
        try:
            from app.services.meeting_assistant import get_meeting_minutes
            payload = json.loads(body.decode("utf-8") or "{}")
            hint = str(payload.get("transcript_hint") or "")
            res = get_meeting_minutes(transcript_hint=hint)
            send_json_fn(200 if res.get("ok") else 400, res)
        except Exception as exc:
            send_json_fn(500, {"ok": False, "error": str(exc)})
        return True

    if path == "/api/meeting/status":
        try:
            from app.services.meeting_assistant import get_meeting_status
            send_json_fn(200, get_meeting_status())
        except Exception as exc:
            send_json_fn(500, {"ok": False, "error": str(exc)})
        return True

    # ── Lifestyle Endpoints (Hábitos, Tarefas & Finanças) ────────────────────

    if path in ("/api/habits", "/api/habits/list"):
        try:
            from app.services.habits import HabitService
            payload = {}
            if body and body.strip():
                try:
                    payload = json.loads(body.decode("utf-8"))
                except Exception:
                    payload = {}
            action = payload.get("action", "list")
            if action == "create":
                h = HabitService.create_habit(
                    habit_id=payload.get("id") or f"habit_{uuid.uuid4().hex[:8]}",
                    name=str(payload.get("name") or "Novo Hábito"),
                    category=str(payload.get("category", "general")),
                    routine_block=str(payload.get("routine_block", "anytime")),
                    days_of_week=payload.get("days_of_week"),
                    start_time=str(payload.get("start_time", "15:00")),
                    time_exceptions=payload.get("time_exceptions"),
                    items_list=payload.get("items_list"),
                )
                send_json_fn(200, {"ok": True, "habit": h})
            elif action == "update":
                h = HabitService.update_habit(
                    habit_id=str(payload.get("id") or payload.get("habit_id")),
                    name=payload.get("name"),
                    category=payload.get("category"),
                    routine_block=payload.get("routine_block"),
                    days_of_week=payload.get("days_of_week"),
                    start_time=payload.get("start_time"),
                    time_exceptions=payload.get("time_exceptions"),
                    items_list=payload.get("items_list"),
                )
                send_json_fn(200, {"ok": True, "habit": h})
            elif action in ("check", "complete"):
                h = HabitService.check_in(str(payload.get("id") or payload.get("habit_id")))
                send_json_fn(200, {"ok": True, "habit": h})
            elif action in ("uncheck", "undo"):
                h = HabitService.uncheck_in(str(payload.get("id") or payload.get("habit_id")))
                send_json_fn(200, {"ok": True, "habit": h})
            elif action == "delete":
                ok = HabitService.delete_habit(str(payload.get("id") or payload.get("habit_id")))
                send_json_fn(200, {"ok": ok})
            else:
                habits = HabitService.list_habits()
                send_json_fn(200, {"ok": True, "habits": habits})
        except Exception as exc:
            send_json_fn(500, {"ok": False, "error": str(exc)})
        return True

    if path in ("/api/tasks", "/api/tasks/list"):
        try:
            from app.services.tasks import TaskService
            import uuid
            payload = json.loads(body.decode("utf-8") or "{}") if body else {}
            action = payload.get("action", "list")
            if action == "create":
                t = TaskService.create_task(
                    task_id=payload.get("id") or f"task_{uuid.uuid4().hex[:8]}",
                    title=str(payload.get("title") or "Nova Tarefa"),
                    priority=int(payload.get("priority", 3)),
                    project=str(payload.get("project", "Geral")),
                    due_date=str(payload.get("due_date", "")),
                )
                send_json_fn(200, {"ok": True, "task": t})
            elif action in ("toggle", "complete"):
                t = TaskService.toggle_task(str(payload.get("id") or payload.get("task_id")))
                send_json_fn(200, {"ok": True, "task": t})
            elif action == "delete":
                ok = TaskService.delete_task(str(payload.get("id") or payload.get("task_id")))
                send_json_fn(200, {"ok": ok})
            else:
                tasks = TaskService.list_tasks(completed=False)
                send_json_fn(200, {"ok": True, "tasks": tasks})
        except Exception as exc:
            send_json_fn(500, {"ok": False, "error": str(exc)})
        return True

    if path in ("/api/finance", "/api/finance/summary"):
        try:
            from app.services.finance import FinanceService
            import uuid
            payload = json.loads(body.decode("utf-8") or "{}") if body else {}
            action = payload.get("action", "summary")
            trans_id = str(payload.get("id") or payload.get("trans_id") or "")
            if action in ("add", "create", "update") and trans_id and not _FINANCE_ID_RE.fullmatch(trans_id):
                send_json_fn(400, {"ok": False, "error": "Identificador do lançamento inválido."})
                return True
            if action in ("add", "create"):
                # Registro manual: nunca chama o modelo. O id enviado pelo cliente torna o reenvio idempotente.
                entry = FinanceService.normalize_entry(
                    payload.get("type", "expense"), payload.get("amount"), payload.get("category", ""),
                    payload.get("description", ""), payload.get("date") or payload.get("date_str") or "",
                )
                summary = FinanceService.add_transaction(
                    trans_id=trans_id or f"fin_{uuid.uuid4().hex[:8]}",
                    type_=entry["type"], amount=entry["amount"], category=entry["category"],
                    description=entry["description"], date_str=entry["date_str"],
                )
                send_json_fn(200, {"ok": True, "summary": summary, "transaction": FinanceService.get_transaction(trans_id) if trans_id else None})
            elif action == "update":
                tx = FinanceService.update_transaction(
                    trans_id, payload.get("type"), payload.get("amount"), payload.get("category", ""),
                    payload.get("description", ""), payload.get("date") or payload.get("date_str") or "",
                ) if trans_id else None
                if tx is None:
                    send_json_fn(404, {"ok": False, "error": "Lançamento não encontrado."})
                else:
                    send_json_fn(200, {"ok": True, "transaction": tx, "summary": FinanceService.get_summary()})
            elif action == "delete":
                summary = FinanceService.delete_transaction(trans_id)
                send_json_fn(200, {"ok": True, "summary": summary})
            elif action == "list":
                date_from = str(payload.get("date_from") or "")
                date_to = str(payload.get("date_to") or "")
                kind = str(payload.get("type") or "")
                for label, value in (("inicial", date_from), ("final", date_to)):
                    if value:
                        try:
                            date.fromisoformat(value)
                        except ValueError:
                            send_json_fn(400, {"ok": False, "error": f"Data {label} inválida: use AAAA-MM-DD."})
                            return True
                if kind and kind not in ("expense", "income"):
                    send_json_fn(400, {"ok": False, "error": "Tipo inválido: use 'expense' ou 'income'."})
                    return True
                result = FinanceService.query_transactions(
                    date_from=date_from, date_to=date_to, type_=kind,
                    category=str(payload.get("category") or ""), limit=int(payload.get("limit") or 200),
                )
                send_json_fn(200, {"ok": True, **result, "summary": FinanceService.get_summary()})
            else:
                summary = FinanceService.get_summary()
                txs = FinanceService.list_transactions(limit=30)
                send_json_fn(200, {"ok": True, "summary": summary, "transactions": txs})
        except ValueError as exc:
            send_json_fn(400, {"ok": False, "error": str(exc)})
        except Exception as exc:
            send_json_fn(500, {"ok": False, "error": str(exc)})
        return True

    # --- Heatmap (30-day consistency matrix) ---
    if path == "/api/habits/heatmap":
        try:
            from app.services.habits import HabitService
            matrix = HabitService.get_heatmap_30_days()
            send_json_fn(200, {"ok": True, "heatmap": matrix})
        except Exception as exc:
            send_json_fn(500, {"ok": False, "error": str(exc)})
        return True

    # --- Mobile Sync Export ---
    if path == "/api/sync/export":
        try:
            from app.services.habits import HabitService
            from app.services.tasks import TaskService
            from app.services.finance import FinanceService
            payload = {
                "ok": True,
                "version": 1,
                "exported_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
                "habits": HabitService.list_habits(include_archived=True),
                "tasks": TaskService.list_tasks(completed=None),
                "finance": {
                    "summary": FinanceService.get_summary(),
                    "transactions": FinanceService.list_transactions(limit=500),
                },
            }
            send_json_fn(200, payload)
        except Exception as exc:
            send_json_fn(500, {"ok": False, "error": str(exc)})
        return True

    # --- Mobile Sync Import (delta upsert) ---
    if path == "/api/sync/import":
        try:
            from app.services.habits import HabitService
            from app.services.tasks import TaskService
            from app.services.finance import FinanceService
            payload = json.loads(body.decode("utf-8") or "{}") if body else {}
            imported = {"habits": 0, "tasks": 0, "transactions": 0}

            for h in payload.get("habits") or []:
                HabitService.create_habit(
                    habit_id=h["id"], name=h["name"],
                    category=h.get("category", "general"),
                    days_of_week=h.get("days_of_week"),
                    start_time=h.get("start_time", "15:00"),
                    time_exceptions=h.get("time_exceptions"),
                    items_list=h.get("items_list"),
                )
                imported["habits"] += 1

            for t in payload.get("tasks") or []:
                TaskService.create_task(
                    task_id=t["id"], title=t["title"],
                    priority=t.get("priority", 3),
                    project=t.get("project", "Geral"),
                )
                imported["tasks"] += 1

            for tx in (payload.get("finance") or {}).get("transactions") or []:
                FinanceService.add_transaction(
                    trans_id=tx["id"],
                    type_=tx.get("type", "expense"),
                    amount=float(tx.get("amount", 0)),
                    category=tx.get("category", "Outros"),
                    description=tx.get("description", ""),
                )
                imported["transactions"] += 1

            send_json_fn(200, {"ok": True, "imported": imported})
        except Exception as exc:
            send_json_fn(500, {"ok": False, "error": str(exc)})
        return True

    return False
