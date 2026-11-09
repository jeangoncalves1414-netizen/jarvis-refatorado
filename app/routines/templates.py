"""Templates de rotinas pré-configuradas (Despertar Matinal e Encerramento do Dia)."""
from __future__ import annotations

from typing import Any

ROUTINE_TEMPLATES: dict[str, dict[str, Any]] = {
    "morning_wake_up": {
        "id": "morning_wake_up",
        "name": "Despertar Matinal",
        "description": "Dispara às 07:00, por comando de voz ('bom dia jarvis') ou /acordar para iniciar o dia com música e revisão de hábitos.",
        "triggers": [
            {"type": "daily", "time": "07:00"},
            {"type": "voice", "phrase": "bom dia jarvis"},
            {"type": "command", "slash": "acordar"},
        ],
        "steps": [
            {
                "tool": "spotify",
                "operation": "search_play",
                "params": {"query": "Wake Up Happy"},
                "label": "Tocar música de despertar",
                "delay_before": 0,
                "on_failure": "continue",
            },
            {
                "tool": "habit_tool",
                "operation": "list",
                "params": {},
                "label": "Verificar hábitos do dia",
                "delay_before": 5,
                "on_failure": "continue",
            },
        ],
        "catch_up_minutes": 30,
    },
    "evening_debrief": {
        "id": "evening_debrief",
        "name": "Encerramento do Dia",
        "description": "Dispara às 22:30, por comando de voz ('boa noite jarvis') ou /dormir para balanço diário e fechamento.",
        "triggers": [
            {"type": "daily", "time": "22:30"},
            {"type": "voice", "phrase": "boa noite jarvis"},
            {"type": "command", "slash": "dormir"},
        ],
        "steps": [
            {
                "tool": "habit_tool",
                "operation": "list",
                "params": {},
                "label": "Balanço de hábitos do dia",
                "delay_before": 0,
                "on_failure": "continue",
            },
            {
                "tool": "task_tool",
                "operation": "list",
                "params": {},
                "label": "Conferir pendências de tarefas",
                "delay_before": 2,
                "on_failure": "continue",
            },
        ],
        "catch_up_minutes": 15,
    },
}


def list_routine_templates() -> list[dict[str, Any]]:
    """Retorna a lista de templates de rotinas disponíveis para instalação."""
    return [dict(t) for t in ROUTINE_TEMPLATES.values()]


def get_routine_template(template_id: str) -> dict[str, Any] | None:
    """Retorna um template específico pelo identificador."""
    t = ROUTINE_TEMPLATES.get(template_id)
    return dict(t) if t else None


def install_routine_template(template_id: str, service: Any = None) -> dict[str, Any]:
    """Cria uma rotina ativa a partir do template especificado."""
    template = get_routine_template(template_id)
    if not template:
        raise ValueError(f"Template '{template_id}' não encontrado.")

    if service is None:
        from app.routines.service import routine_service
        service = routine_service

    payload = {
        "name": template["name"],
        "triggers": template["triggers"],
        "steps": template["steps"],
        "catch_up_minutes": template.get("catch_up_minutes", 15),
    }

    return service.create(payload)
