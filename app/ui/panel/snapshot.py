from __future__ import annotations

from typing import Any

from app.domain.chat import ChatSession
from app.ui.panel.app import PanelApp


class PanelSnapshot:
    """A small helper that prepares the panel state from the current runtime."""

    def __init__(self, orchestrator: Any, chat_session: ChatSession | None = None) -> None:
        self.orchestrator = orchestrator
        self.chat_session = chat_session
        self.panel = PanelApp()

    def render(self) -> str:
        messages = self.chat_session.get_messages() if self.chat_session else []
        task_count = 0
        if hasattr(self.orchestrator, "productivity_service"):
            from app.storage import task_store
            from app.services.tasks import TaskService
            service = self.orchestrator.productivity_service
            task_count = len(TaskService.list_tasks(completed=None) if service is task_store else service.list_tasks())

        memory_count = 0
        if hasattr(self.orchestrator, "memory_store") and self.orchestrator.memory_store is not None:
            memory_count = len(self.orchestrator.memory_store.get_preferences()) + len(self.orchestrator.memory_store.get_facts())

        last_summary = "Assistente pronto"
        if hasattr(self.orchestrator, "last_plan"):
            last_summary = self.orchestrator.last_plan.summary

        return self.panel.render(
            status="online",
            task_count=task_count,
            memory_count=memory_count,
            last_summary=last_summary,
            messages=messages,
        )
