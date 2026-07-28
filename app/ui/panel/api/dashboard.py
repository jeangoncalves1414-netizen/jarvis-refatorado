from __future__ import annotations

import json
from typing import Any

from app.agent.tools.timer import list_active_timers
from app.services.system import SystemMetrics
from app.storage.activity_store import list_recent, log_activity
from app.storage.enem_store import EnemStore
from app.storage.session_store import list_sessions
from app.storage.task_store import add_task, delete_task, list_tasks, toggle_task
from app.storage.tutor_store import TutorStore


def build_dashboard_snapshot() -> dict[str, Any]:
    sessions = list_sessions()
    chat_sessions = [s for s in sessions if s.get("type", "chat") == "chat"]
    study_sessions = [s for s in sessions if s.get("type") == "study"]

    tutor = TutorStore().get_dashboard()
    progress = tutor.get("progress", {})
    stats = progress.get("stats", {})
    stage_id = progress.get("current_stage", "")
    stage_title = next(
        (s.get("title", stage_id) for s in progress.get("stages", []) if s.get("id") == stage_id),
        stage_id,
    )

    tasks = list_tasks(include_completed=False)
    all_tasks = list_tasks(include_completed=True)
    completed_tasks = sum(1 for t in all_tasks if t.get("completed"))

    return {
        "system": SystemMetrics.get_metrics(),
        "sessions": {
            "total": len(sessions),
            "chat": len(chat_sessions),
            "study": len(study_sessions),
        },
        "tutor": {
            "stage": stage_title,
            "stage_id": stage_id,
            "due_flashcards": tutor.get("due_flashcards", 0),
            "questions_solved": stats.get("questions_solved", 0),
            "sessions": stats.get("sessions", 0),
            "weak_spots": tutor.get("weak_spots", [])[:5],
        },
        "enem": {
            "questions": len(EnemStore().list_questions()),
        },
        "tasks": {
            "pending": len(tasks),
            "completed": completed_tasks,
            "items": tasks[:8],
        },
        "activity": list_recent(12),
        "timers": list_active_timers(),
    }


def handle_dashboard_get(parts: list[str], handler: Any) -> tuple[int, dict[str, Any]] | None:
    if len(parts) == 2 and parts[1] == "dashboard":
        return 200, build_dashboard_snapshot()
    return None


def handle_tasks_get(parts: list[str], handler: Any) -> tuple[int, dict[str, Any]] | None:
    if len(parts) == 2 and parts[1] == "tasks":
        include_completed = handler.path.endswith("?all=1")
        return 200, {"tasks": list_tasks(include_completed=include_completed)}
    return None


def handle_dashboard_post(path: str, body: bytes, handler: Any) -> tuple[int, dict[str, Any]] | None:
    if path != "/api/tasks":
        return None
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except Exception:
        return 400, {"ok": False, "error": "JSON inválido."}

    action = payload.get("action", "create")

    if action == "create":
        title = str(payload.get("title", "")).strip()
        if not title:
            return 400, {"ok": False, "error": "Título da tarefa é obrigatório."}
        try:
            task = add_task(title, priority=str(payload.get("priority", "normal")))
        except ValueError as exc:
            return 400, {"ok": False, "error": str(exc)}
        log_activity("task", f"Tarefa criada: {task['title']}", meta={"task_id": task["id"]})
        return 200, {"ok": True, "task": task}

    if action == "toggle":
        task_id = str(payload.get("task_id", "")).strip()
        if not task_id:
            return 400, {"ok": False, "error": "task_id é obrigatório."}
        task = toggle_task(task_id)
        if not task:
            return 404, {"ok": False, "error": "Tarefa não encontrada."}
        status = "concluída" if task.get("completed") else "reaberta"
        log_activity("task", f"Tarefa {status}: {task['title']}", meta={"task_id": task_id})
        return 200, {"ok": True, "task": task}

    if action == "delete":
        task_id = str(payload.get("task_id", "")).strip()
        if not task_id:
            return 400, {"ok": False, "error": "task_id é obrigatório."}
        if not delete_task(task_id):
            return 404, {"ok": False, "error": "Tarefa não encontrada."}
        log_activity("task", "Tarefa removida", meta={"task_id": task_id})
        return 200, {"ok": True}

    return 400, {"ok": False, "error": f"Ação desconhecida: {action}"}
