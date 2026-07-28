from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class ToolResult:
    ok: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)


class Tool(Protocol):
    name: str
    description: str
    critical: bool

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        ...


class BaseTool:
    @property
    def name(self) -> str:
        raise NotImplementedError

    @property
    def description(self) -> str:
        return ""

    @property
    def critical(self) -> bool:
        return False

    @property
    def parameters(self) -> dict[str, Any]:
        return {}

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        raise NotImplementedError
