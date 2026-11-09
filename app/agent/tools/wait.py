from __future__ import annotations

from typing import Any

from app.core import waits
from .base import BaseTool, ToolResult

TOO_LONG_TEXT = "Espera maior que 1 hora: crie uma rotina com horário (ferramenta routine)."


class WaitTool(BaseTool):
    """Pausa real entre ações do mesmo pedido; cancela com "Parar pedido"."""

    @property
    def name(self) -> str:
        return "wait"

    @property
    def description(self) -> str:
        return (
            "Espera N segundos ANTES da próxima ação deste pedido (ex.: 'espere 50 s'). "
            "Cancela com 'Parar pedido'. Para alarme sonoro use timer."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "seconds": {"type": "integer", "description": f"Segundos de espera (1 a {waits.MAX_INLINE_WAIT})."},
                "reason": {"type": "string", "description": "Motivo curto (ex.: 'antes de abrir o YouTube')."},
            },
            "required": ["seconds"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        raw = (args or {}).get("seconds")
        try:
            seconds = int(raw) if not isinstance(raw, bool) else None
        except (TypeError, ValueError):
            seconds = None
        if seconds is None or (isinstance(raw, float) and raw != int(raw)):
            return ToolResult(False, "Informe a espera em segundos inteiros (ex.: 50).")
        if seconds > waits.MAX_INLINE_WAIT:
            return ToolResult(False, TOO_LONG_TEXT)
        if seconds < 1:
            return ToolResult(False, "A espera precisa ter pelo menos 1 segundo.")
        reason = " ".join(str((args or {}).get("reason") or "").split())[:80]
        waits.wait_seconds(seconds, label=reason)
        return ToolResult(True, f"Esperei {seconds} s" + (f" ({reason})." if reason else "."), data={"waited_seconds": seconds})
