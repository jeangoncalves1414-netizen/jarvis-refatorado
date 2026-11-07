from __future__ import annotations

from typing import Any


class ChatSession:
    """A lightweight chat session that routes user messages through the orchestrator."""

    def __init__(self, orchestrator: Any) -> None:
        self.orchestrator = orchestrator
        self._messages: list[dict[str, str]] = []

    def handle_message(self, text: str) -> dict[str, str]:
        normalized = (text or "").strip()
        if not normalized:
            return {"intent": "general", "message": "Digite algo para eu processar."}

        plan = self.orchestrator.handle_request(normalized)
        self._messages.append({"role": "user", "content": normalized})

        message = self._build_reply(plan)
        self._messages.append({"role": "assistant", "content": message})
        return {"intent": plan.intent, "message": message}

    def _build_reply(self, plan: Any) -> str:
        if isinstance(plan.summary, str) and plan.summary:
            return plan.summary
        if plan.intent == "file":
            return "Entendi. Posso listar o conteúdo do diretório ou ajudar a navegar por pastas."
        if plan.intent == "productivity":
            task_title = plan.context.get("task_title", "")
            if task_title:
                return f"Tarefa registrada: {task_title}."
            return "Tarefa registrada com sucesso."
        if plan.intent == "voice":
            return "Fluxo de voz ativado. Posso responder com fala em uma próxima etapa."
        return "Entendi. Vou usar o contexto atual para responder de forma útil."

    def get_messages(self) -> list[dict[str, str]]:
        return list(self._messages)
