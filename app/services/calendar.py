from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CalendarEvent:
    """Evento de calendário."""
    title: str
    start: datetime
    end: datetime | None = None
    description: str = ""
    location: str = ""
    reminder_minutes: int = 15
    reminder_policy: str = "once"  # once, until_confirmed, next_conversation
    reminder_at: datetime | None = None
    last_notified_at: datetime | None = None
    reminder_confirmed: bool = False
    reminder_instructions: str = ""
    reminder_status: str = "pending"  # pending, confirmed, missed
    reminder_history: list[dict] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def to_dict(self) -> dict[str, Any]:
        """Serializa o evento para JSON."""
        return {
            "id": self.id,
            "title": self.title,
            "start": self.start.isoformat(),
            "end": self.end.isoformat() if self.end else None,
            "description": self.description,
            "location": self.location,
            "reminder_minutes": self.reminder_minutes,
            "reminder_policy": self.reminder_policy,
            "reminder_at": self.reminder_at.isoformat() if self.reminder_at else None,
            "last_notified_at": self.last_notified_at.isoformat() if self.last_notified_at else None,
            "reminder_confirmed": self.reminder_confirmed,
            "reminder_instructions": self.reminder_instructions,
            "reminder_status": self.reminder_status,
            "reminder_history": self.reminder_history,
        }


class CalendarService:
    """Serviço de calendário simples (baseado em JSON)."""

    def __init__(self, storage_path: str = "data/calendar.json"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._events: list[CalendarEvent] = []
        self._load()

    def _load(self):
        """Carrega eventos do arquivo."""
        if not self.storage_path.exists():
            return

        try:
            import json
            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
            self._events = [
                CalendarEvent(
                    id=e.get("id") or uuid.uuid4().hex,
                    title=e["title"],
                    start=datetime.fromisoformat(e["start"]),
                    end=datetime.fromisoformat(e["end"]) if e.get("end") else None,
                    description=e.get("description", ""),
                    location=e.get("location", ""),
                    reminder_minutes=e.get("reminder_minutes", 15),
                    reminder_policy=e.get("reminder_policy", "once"),
                    reminder_at=datetime.fromisoformat(e["reminder_at"]) if e.get("reminder_at") else None,
                    last_notified_at=datetime.fromisoformat(e["last_notified_at"]) if e.get("last_notified_at") else None,
                    reminder_confirmed=e.get("reminder_confirmed", False),
                    reminder_instructions=e.get("reminder_instructions", ""),
                    reminder_status=e.get("reminder_status", "pending"),
                    reminder_history=e.get("reminder_history", []),
                )
                for e in data.get("events", [])
            ]
        except Exception as e:
            logger.error(f"Falha ao carregar calendário: {e}")
            self._events = []

    def _save(self):
        """Salva eventos no arquivo."""
        try:
            import json
            data = {"events": [e.to_dict() for e in self._events]}
            self.storage_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.error(f"Falha ao salvar calendário: {e}")

    def add_event(self, event: CalendarEvent) -> bool:
        """Adiciona evento."""
        try:
            self._events.append(event)
            self._save()
            return True
        except Exception as e:
            logger.error(f"Falha ao adicionar evento: {e}")
            return False

    def get_all_events(self) -> list[CalendarEvent]:
        """Retorna todos os eventos."""
        return list(self._events)

    def get_events(self, start: datetime | None = None, end: datetime | None = None) -> list[CalendarEvent]:
        """Retorna eventos em um período."""
        if start is None:
            start = datetime.now()
        if end is None:
            end = start + timedelta(days=7)

        return [
            e for e in self._events
            if start <= e.start <= end
        ]

    def get_upcoming_reminders(self, minutes_ahead: int = 30) -> list[CalendarEvent]:
        """Retorna eventos que precisam de lembrete."""
        now = datetime.now()
        cutoff = now + timedelta(minutes=minutes_ahead)

        return [
            e for e in self._events
            if now <= e.start <= cutoff
        ]

    def due_reminders(self, *, on_conversation: bool = False) -> list[CalendarEvent]:
        """Returns and records calendar notifications that are ready to be delivered.

        A one-time reminder is consumed after its first notification.  A repeating
        reminder waits 30 minutes between notices until the user confirms or cancels it.
        The next-conversation policy is intentionally held back from background alerts.
        """
        now = datetime.now()
        due: list[CalendarEvent] = []
        changed = False
        for event in self._events:
            if event.reminder_confirmed or event.reminder_status in {"cancelled", "confirmed"}:
                continue
            scheduled = event.reminder_at or (event.start - timedelta(minutes=max(0, event.reminder_minutes)))
            if now < scheduled:
                continue
            policy = event.reminder_policy or "once"
            if on_conversation and policy != "next_conversation":
                continue
            if policy == "next_conversation" and not on_conversation:
                continue
            if policy == "once" and event.last_notified_at:
                continue
            if policy == "until_confirmed" and event.last_notified_at and now - event.last_notified_at < timedelta(minutes=30):
                continue
            event.last_notified_at = now
            event.reminder_status = "waiting_confirmation" if policy == "until_confirmed" else "delivered"
            event.reminder_history.append({"timestamp": now.isoformat(), "action": "notified", "via": "conversation" if on_conversation else "notification"})
            due.append(event)
            changed = True
        if changed:
            self._save()
        return due

    def cancel_reminder(self, event_id: str) -> bool:
        for event in self._events:
            if event.id == event_id:
                event.reminder_status = "cancelled"
                event.reminder_confirmed = True
                event.reminder_history.append({"timestamp": datetime.now().isoformat(), "action": "cancelled"})
                self._save()
                return True
        return False

    def delete_event(self, title: str, start: datetime) -> bool:
        """Deleta evento por título e início (compat legado)."""
        try:
            original_len = len(self._events)
            self._events = [
                e for e in self._events
                if not (e.title == title and e.start == start)
            ]
            if len(self._events) < original_len:
                self._save()
                return True
            return False
        except Exception as e:
            logger.error(f"Falha ao deletar evento: {e}")
            return False

    def delete_event_by_id(self, event_id: str) -> bool:
        """Deleta evento por id estável."""
        try:
            original_len = len(self._events)
            self._events = [e for e in self._events if e.id != event_id]
            if len(self._events) < original_len:
                self._save()
                return True
            return False
        except Exception as e:
            logger.error(f"Falha ao deletar evento: {e}")
            return False

    def get_today_events(self) -> list[CalendarEvent]:
        """Retorna eventos de hoje."""
        now = datetime.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        return self.get_events(start_of_day, end_of_day)

    def confirm_reminder(self, event_id: str) -> bool:
        """Marca um lembrete como confirmado."""
        try:
            for event in self._events:
                if event.id == event_id:
                    event.reminder_confirmed = True
                    event.reminder_status = "confirmed"
                    event.reminder_history.append({
                        "timestamp": datetime.now().isoformat(),
                        "action": "confirmed"
                    })
                    self._save()
                    return True
            return False
        except Exception as e:
            logger.error(f"Falha ao confirmar lembrete: {e}")
            return False

    def get_pending_reminders(self) -> list[CalendarEvent]:
        """Retorna lembretes não confirmados."""
        return [e for e in self._events if not e.reminder_confirmed and e.reminder_status == "pending"]

    def update_reminder_status(self, event_id: str, status: str) -> bool:
        """Atualiza o status de um lembrete."""
        try:
            for event in self._events:
                if event.id == event_id:
                    event.reminder_status = status
                    event.reminder_history.append({
                        "timestamp": datetime.now().isoformat(),
                        "action": "status_updated",
                        "status": status
                    })
                    self._save()
                    return True
            return False
        except Exception as e:
            logger.error(f"Falha ao atualizar status do lembrete: {e}")
            return False
