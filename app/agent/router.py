from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class AgentResponse:
    intent: str
    message: str


class AgentRouter:
    def __init__(
        self,
        task_store: Any | None = None,
        memory_store: Any | None = None,
    ) -> None:
        self.task_store = task_store
        self.memory_store = memory_store

    def handle_message(self, text: str) -> AgentResponse:
        normalized = (text or "").strip().lower()

        if "tarefa" in normalized or "task" in normalized:
            title = self._extract_task_title(normalized)
            if self.task_store is not None:
                self.task_store.add_task(title)
            return AgentResponse(intent="task", message=f"Tarefa criada: {title}")

        if "lembre" in normalized or "prefer" in normalized or "prefiro" in normalized:
            if self.memory_store is not None:
                self.memory_store.add_preference("preferred_response_style", "short")
            return AgentResponse(intent="memory", message="Preferência salva.")

        return AgentResponse(intent="general", message="Posso ajudar com tarefas, lembretes e contexto.")

    def _extract_task_title(self, normalized: str) -> str:
        if "de " in normalized:
            return normalized.split("de ", 1)[1].strip()
        return normalized.replace("crie", "").replace("uma", "").replace("tarefa", "").strip()
