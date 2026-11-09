"""Calendar actions exposed to the conversational agent."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from app.services.calendar import CalendarEvent, CalendarService
from .base import BaseTool, ToolResult

MAX_REMINDERS_PER_CALL = 10
REMINDER_POLICIES = ("once", "until_confirmed", "next_conversation")
_REMINDER_FIELDS = {
    "title": {"type": "string", "description": "Nome curto do compromisso (ex.: 'Dentista')."},
    "start": {"type": "string", "description": "Data e hora do compromisso em ISO local AAAA-MM-DDTHH:MM (ex.: 2026-08-04T15:00)."},
    "reminder_minutes": {"type": "integer", "minimum": 0, "description": "Quantos minutos antes avisar (padrão 15)."},
    "reminder_at": {"type": "string", "description": "Horário exato do aviso em ISO local, se a usuária pedir."},
    "reminder_policy": {"type": "string", "enum": list(REMINDER_POLICIES), "description": "once: avisa uma vez; until_confirmed: repete até confirmar; next_conversation: avisa na próxima conversa."},
}


def _build_event(spec: dict[str, Any]) -> CalendarEvent:
    """Valida os campos de um lembrete. Levanta ValueError (pt-BR)."""
    title = str(spec.get("title") or "").strip()
    start_value = str(spec.get("start") or "").strip()
    if not title or not start_value:
        raise ValueError("Preciso do assunto e da data/hora para criar o lembrete.")
    if len(title) > 120:
        raise ValueError("O título do lembrete deve ter no máximo 120 caracteres.")
    try:
        start = datetime.fromisoformat(start_value)
        reminder_at_value = str(spec.get("reminder_at") or "").strip()
        reminder_at = datetime.fromisoformat(reminder_at_value) if reminder_at_value else None
        policy = str(spec.get("reminder_policy") or "once")
        if policy not in REMINDER_POLICIES:
            policy = "once"
        minutes = max(0, int(spec.get("reminder_minutes", 15)))
    except (TypeError, ValueError):
        raise ValueError("A data ou o horario do lembrete esta invalido.") from None
    return CalendarEvent(title=title, start=start, reminder_minutes=minutes, reminder_at=reminder_at, reminder_policy=policy)


class CalendarTool(BaseTool):
    @property
    def name(self) -> str:
        return "calendar"

    @property
    def description(self) -> str:
        return (
            "Agenda/calendário local: listar compromissos (de um dia ou dos próximos dias), criar lembrete com data e hora "
            "e parar os avisos de um lembrete. Vários compromissos de uma vez: UMA chamada create_many (lista 'reminders'). "
            "Datas e horas em ISO local (AAAA-MM-DDTHH:MM); calcule 'amanhã às 15h' a partir da data atual. "
            "Tudo criado aqui aparece na tela Calendário."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "create_reminder", "create_many", "cancel_reminder"],
                    "description": "list: lê; create_reminder: 1 lembrete; create_many: vários; cancel_reminder: para os avisos.",
                },
                "query": {"type": "string", "description": "cancel_reminder: parte distintiva do título do lembrete."},
                **_REMINDER_FIELDS,
                "reminders": {
                    "type": "array",
                    "maxItems": MAX_REMINDERS_PER_CALL,
                    "items": {"type": "object", "properties": _REMINDER_FIELDS, "required": ["title", "start"]},
                    "description": f"create_many: até {MAX_REMINDERS_PER_CALL} lembretes.",
                },
                "day": {"type": "string", "description": "list: só os compromissos deste dia (AAAA-MM-DD)."},
                "upcoming_days": {"type": "integer", "minimum": 1, "maximum": 31, "description": "list: só os próximos N dias (1 a 31)."},
            },
            "required": ["action"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        service = CalendarService()
        action = str(args.get("action") or "")
        if action == "list":
            return self._list(service, args)
        if action == "create_reminder":
            try:
                event = _build_event(args)
            except ValueError as exc:
                return ToolResult(ok=False, message=str(exc))
            if not service.add_event(event):
                return ToolResult(ok=False, message="Nao foi possivel salvar o lembrete no calendario.")
            return ToolResult(ok=True, message=f"Lembrete '{event.title}' agendado para {event.start.strftime('%d/%m as %H:%M')} e sincronizado com o calendario, Sir.", data={"event": event.to_dict(), "event_ids": [event.id]})
        if action == "create_many":
            specs = args.get("reminders")
            if not isinstance(specs, list) or not specs:
                return ToolResult(ok=False, message="Informe a lista 'reminders' com pelo menos um lembrete.")
            if len(specs) > MAX_REMINDERS_PER_CALL:
                return ToolResult(ok=False, message=f"No máximo {MAX_REMINDERS_PER_CALL} lembretes por chamada; nada foi criado.")
            events = []
            for index, spec in enumerate(specs, 1):
                try:
                    if not isinstance(spec, dict):
                        raise ValueError("deve ser um objeto com title e start.")
                    events.append(_build_event(spec))
                except ValueError as exc:
                    return ToolResult(ok=False, message=f"Lembrete {index}: {exc} Nada foi criado.")
            saved = [event for event in events if service.add_event(event)]
            if len(saved) != len(events):
                return ToolResult(ok=False, message=f"Só {len(saved)} de {len(events)} lembretes foram salvos no calendário.", data={"events": [e.to_dict() for e in saved], "event_ids": [e.id for e in saved]})
            listed = "; ".join(f"{e.title} ({e.start.strftime('%d/%m %H:%M')})" for e in saved)
            return ToolResult(ok=True, message=f"{len(saved)} lembrete(s) agendado(s): {listed}.", data={"events": [e.to_dict() for e in saved], "event_ids": [e.id for e in saved]})
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

    @staticmethod
    def _list(service: CalendarService, args: dict[str, Any]) -> ToolResult:
        events = [event for event in service.get_all_events() if event.reminder_status != "cancelled"]
        day_value, upcoming = args.get("day"), args.get("upcoming_days")
        scope = ""
        if day_value not in (None, ""):
            try:
                day = date.fromisoformat(str(day_value).strip())
            except ValueError:
                return ToolResult(ok=False, message="Dia inválido: use AAAA-MM-DD.")
            events = [event for event in events if event.start.date() == day]
            scope = f" em {day.strftime('%d/%m')}"
        elif upcoming not in (None, ""):
            if isinstance(upcoming, bool) or not isinstance(upcoming, int) or not 1 <= upcoming <= 31:
                return ToolResult(ok=False, message="upcoming_days deve ser um número de 1 a 31.")
            now = datetime.now()
            events = [event for event in events if now <= event.start <= now + timedelta(days=upcoming)]
            scope = f" nos próximos {upcoming} dia(s)"
        events.sort(key=lambda event: event.start)
        data = [event.to_dict() for event in events]
        if not data:
            return ToolResult(ok=True, message=f"Nao ha lembretes ativos no calendario{scope}.", data={"events": []})
        return ToolResult(ok=True, message=f"Lembretes ativos{scope}: " + "; ".join(f"{e.title} ({e.start.strftime('%d/%m %H:%M')})" for e in events[:8]), data={"events": data})
