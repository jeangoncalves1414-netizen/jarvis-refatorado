"""Calendar actions exposed to the conversational agent."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services.calendar import CalendarEvent, CalendarService
from .base import BaseTool, ToolResult


class CalendarTool(BaseTool):
    @property
    def name(self) -> str:
        return "calendar"

    @property
    def description(self) -> str:
        return "Cria, consulta e interrompe lembretes do calendario. Tudo criado aqui aparece no painel Calendario."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list", "create_reminder", "cancel_reminder"]},
                "query": {"type": "string", "description": "Parte distintiva do titulo do evento."},
                "title": {"type": "string", "description": "Nome curto do lembrete."},
                "start": {"type": "string", "description": "Data e hora do compromisso no formato ISO local, por exemplo 2026-08-04T18:30."},
                "reminder_minutes": {"type": "integer", "description": "Quantos minutos antes avisar. Padrao 15."},
                "reminder_at": {"type": "string", "description": "Horario exato do aviso em ISO local, se solicitado."},
                "reminder_policy": {"type": "string", "enum": ["once", "until_confirmed", "next_conversation"]},
            },
            "required": ["action"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        service = CalendarService()
        action = str(args.get("action") or "")
        if action == "list":
            events = [event.to_dict() for event in service.get_all_events() if event.reminder_status != "cancelled"]
            if not events:
                return ToolResult(ok=True, message="Nao ha lembretes ativos no calendario.", data={"events": []})
            return ToolResult(ok=True, message="Lembretes ativos: " + "; ".join(event["title"] for event in events[:8]), data={"events": events})
        if action == "create_reminder":
            title = str(args.get("title") or "").strip()
            start_value = str(args.get("start") or "").strip()
            if not title or not start_value:
                return ToolResult(ok=False, message="Preciso do assunto e da data/hora para criar o lembrete.")
            try:
                start = datetime.fromisoformat(start_value)
                reminder_at_value = str(args.get("reminder_at") or "").strip()
                reminder_at = datetime.fromisoformat(reminder_at_value) if reminder_at_value else None
                policy = str(args.get("reminder_policy") or "once")
                if policy not in {"once", "until_confirmed", "next_conversation"}:
                    policy = "once"
                minutes = max(0, int(args.get("reminder_minutes", 15)))
            except (TypeError, ValueError):
                return ToolResult(ok=False, message="A data ou o horario do lembrete esta invalido.")
            event = CalendarEvent(title=title, start=start, reminder_minutes=minutes, reminder_at=reminder_at, reminder_policy=policy)
            if not service.add_event(event):
                return ToolResult(ok=False, message="Nao foi possivel salvar o lembrete no calendario.")
            return ToolResult(ok=True, message=f"Lembrete '{title}' agendado para {start.strftime('%d/%m as %H:%M')} e sincronizado com o calendario, Sir.", data={"event": event.to_dict()})
        if action == "cancel_reminder":
            query = str(args.get("query") or "").strip().casefold()
            if not query:
                return ToolResult(ok=False, message="Informe qual lembrete deve ser interrompido.")
            matches = [event for event in service.get_all_events() if query in event.title.casefold() and event.reminder_status != "cancelled"]
            if not matches:
                return ToolResult(ok=False, message=f"Nao encontrei um lembrete ativo relacionado a '{args.get('query')}'.")
            if len(matches) > 1:
                return ToolResult(ok=False, message="Encontrei mais de um lembrete: " + ", ".join(event.title for event in matches[:4]) + ". Diga qual deles devo parar.")
            service.cancel_reminder(matches[0].id)
            return ToolResult(ok=True, message=f"Parei os avisos sobre '{matches[0].title}', Sir.", data={"event_id": matches[0].id})
        return ToolResult(ok=False, message="Acao de calendario desconhecida.")
