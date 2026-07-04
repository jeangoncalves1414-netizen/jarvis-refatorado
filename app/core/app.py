from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class AppRuntime:
    name: str
    version: str = "0.1.0"
    state: str = "idle"


class ApplicationCore:
    def __init__(self, settings: Any | None = None) -> None:
        self.settings = settings
        self.runtime = AppRuntime(name="Jarvis Rebuild")

    def start(self) -> None:
        self.runtime.state = "running"

    def stop(self) -> None:
        self.runtime.state = "stopped"

    def get_status(self) -> dict[str, str]:
        return {
            "name": self.runtime.name,
            "version": self.runtime.version,
            "state": self.runtime.state,
        }
