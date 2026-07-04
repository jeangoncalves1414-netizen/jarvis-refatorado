from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(slots=True)
class Task:
    title: str
    completed: bool = False


class ProductivityService:
    def __init__(self) -> None:
        self.tasks: List[Task] = []

    def add_task(self, title: str) -> Task:
        task = Task(title=title.strip())
        self.tasks.append(task)
        return task

    def list_tasks(self) -> List[Task]:
        return list(self.tasks)

    def complete_task(self, title: str) -> bool:
        normalized = title.strip().lower()
        for task in self.tasks:
            if task.title.lower() == normalized:
                task.completed = True
                return True
        return False
