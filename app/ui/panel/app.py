from __future__ import annotations

from typing import Any, Iterable


class PanelApp:
    """Simple panel renderer used by tests and by the runtime.

    Public API:
    - `render(status, task_count, memory_count, last_summary, messages)`
    """

    def __init__(self, settings: Any | None = None) -> None:
        self.settings = settings

    def render(
        self,
        status: str = "online",
        task_count: int = 0,
        memory_count: int = 0,
        last_summary: str = "Assistente pronto",
        messages: Iterable[dict[str, str]] | None = None,
    ) -> str:
        msgs = messages or []
        message_html = "".join(f"<div class='bubble {m.get('role','')}'>{m.get('content','')}</div>" for m in msgs)

        return (
            "<html>"
            "<head><meta charset='utf-8' /><title>Jarvis Panel</title>"
            "<style>body{font-family:Segoe UI,Arial,sans-serif;background:#090909;color:#f5f5f5;padding:20px;}"
            ".card{background:#151515;border:1px solid #2a2a2a;border-radius:12px;padding:16px;}"
            ".pill{display:inline-block;padding:6px 10px;border-radius:999px;background:#1f3c4a;color:#6fe7ff;}"
            ".bubble{padding:8px 10px;background:#1d1d1d;border-radius:8px;margin-top:8px;}"
            "</style></head><body>"
            "<div class='card'>"
            f"<h1>Jarvis</h1><p>Status: <span class='pill'>{status}</span></p>"
            f"<p>Tarefas: {task_count}</p><p>Memórias: {memory_count}</p>"
            f"<p>Última mensagem: {last_summary}</p>"
            f"<div>{message_html}</div>"
            "</div></body></html>"
        )


class PanelView(PanelApp):
    """Adapter used by older tests — keeps a `last_message` parameter name."""

    def render(
        self,
        status: str = "online",
        task_count: int = 0,
        memory_count: int = 0,
        last_message: str | None = None,
        messages: Iterable[dict[str, str]] | None = None,
    ) -> str:
        last_summary = last_message or "Assistente pronto"
        return super().render(
            status=status,
            task_count=task_count,
            memory_count=memory_count,
            last_summary=last_summary,
            messages=messages,
        )
