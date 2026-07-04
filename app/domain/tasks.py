from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Task:
    title: str
    completed: bool = False


class TaskStore:
    def __init__(self) -> None:
        self._tasks: list[Task] = []

    def add_task(self, title: str) -> Task:
        cleaned = title.strip()
        if not cleaned:
            raise ValueError("O título da tarefa não pode ficar vazio.")
        task = Task(title=cleaned)
        self._tasks.append(task)
        return task

    def list_tasks(self) -> list[Task]:
        return list(self._tasks)
