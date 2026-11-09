"""Ferramenta notification: permite ao agente disparar notificações Toast nativas do Windows.

Suporta título, corpo de mensagem, nível de urgência e lista de botões/ações interativas
(deep-links) que executam ações locais ou abrem links sem exigir interação direta no chat.
"""
from __future__ import annotations

from typing import Any

from app.agent.tools.base import BaseTool
from app.services.windows_notifications import send_notification

MAX_TITLE = 100
MAX_MESSAGE = 300


class NotificationTool(BaseTool):
    @property
    def name(self) -> str:
        return "notification"

    @property
    def description(self) -> str:
        return (
            "Dispara uma notificação Toast nativa do Windows no desktop. Suporta título, mensagem, "
            "nível de urgência ('normal', 'low', 'high', 'critical') e botões interativos de ação rápida "
            "(ex.: 'Ouvir Briefing' [action=briefing], 'Ver Hábitos' [action=habits], "
            "'Beber Água' [action=water, amount=300], ou 'Abrir Link' [action=open_link, url=https://...]). "
            "Risco baixo (observe/low): gera apenas aviso nativo e botões na tela."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Título da notificação (até 100 caracteres).",
                },
                "message": {
                    "type": "string",
                    "description": "Mensagem ou resumo a exibir (até 300 caracteres).",
                },
                "urgency": {
                    "type": "string",
                    "enum": ["normal", "low", "high", "critical"],
                    "description": "Nível de urgência da notificação. Padrão: normal.",
                },
                "actions": {
                    "type": "array",
                    "description": (
                        "Lista de botões de ação rápida. Cada botão é um objeto com 'label' (texto visível) "
                        "e 'action' ('briefing', 'habits', 'water', 'open_link'). "
                        "Para 'open_link', informe 'url'. Para 'water', informe 'amount' em ml."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string", "description": "Texto exibido no botão."},
                            "action": {"type": "string", "description": "Identificador da ação."},
                            "url": {"type": "string", "description": "URL de destino para open_link."},
                            "amount": {"type": "number", "description": "Quantidade em ml para ação water."},
                        },
                        "required": ["label", "action"],
                    },
                },
            },
            "required": ["title", "message"],
        }

    def run(
        self,
        title: str = "",
        message: str = "",
        urgency: str = "normal",
        actions: list[dict[str, Any]] | None = None,
        command: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        t = (title or command or "Jarvis").strip()[:MAX_TITLE]
        m = (message or "").strip()[:MAX_MESSAGE]
        if not m and command:
            m = command.strip()[:MAX_MESSAGE]
        if not m:
            return {"ok": False, "error": "A mensagem da notificação é obrigatória."}

        urg = urgency.lower() if urgency in ("normal", "low", "high", "critical") else "normal"
        act_list = actions if isinstance(actions, list) else None

        sent = send_notification(
            title=t,
            message=m,
            actions=act_list,
            urgency=urg,
            sync=True,
        )

        return {
            "ok": True,
            "message": f"Notificação '{t}' enviada para o Windows.",
            "notification": {
                "title": t,
                "message": m,
                "urgency": urg,
                "actions": act_list or [],
                "dispatched": sent,
            },
        }

