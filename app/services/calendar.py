from __future__ import annotations

import logging
from dataclasses import dataclass
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
                    title=e["title"],
                    start=datetime.fromisoformat(e["start"]),
                    end=datetime.fromisoformat(e["end"]) if e.get("end") else None,
                    description=e.get("description", ""),
                    location=e.get("location", ""),
                    reminder_minutes=e.get("reminder_minutes", 15)
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
            data = {
                "events": [
                    {
                        "title": e.title,
                        "start": e.start.isoformat(),
                        "end": e.end.isoformat() if e.end else None,
                        "description": e.description,
                        "location": e.location,
                        "reminder_minutes": e.reminder_minutes
                    }
                    for e in self._events
                ]
            }
            self.storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
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
    
    def delete_event(self, title: str, start: datetime) -> bool:
        """Deleta evento por título e início."""
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
    
    def get_today_events(self) -> list[CalendarEvent]:
        """Retorna eventos de hoje."""
        now = datetime.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        
        return self.get_events(start_of_day, end_of_day)
