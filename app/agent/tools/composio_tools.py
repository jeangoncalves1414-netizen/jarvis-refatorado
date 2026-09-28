"""
Composio Tools - Ferramentas para integração com serviços OAuth via Composio.
Gmail, Google Calendar, Notion, etc.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from .base import BaseTool, ToolResult
from ..integrations.composio_manager import ComposioManager, ServiceType, get_manager


class ComposioGmailTool(BaseTool):
    @property
    def name(self) -> str:
        return "composio_gmail"

    @property
    def description(self) -> str:
        return (
            "Gerencia emails via Gmail usando autenticação OAuth. "
            "Use action='list' para listar emails, action='send' para enviar. "
            "Requer que o Gmail esteja conectado via Composio."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "send", "check_connection"],
                    "description": "list: listar emails; send: enviar email; check_connection: verificar se está conectado.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Quantidade de emails para listar (padrão: 10).",
                    "default": 10,
                },
                "query": {
                    "type": "string",
                    "description": "Query de busca do Gmail (ex: 'is:unread', 'from:example@gmail.com').",
                },
                "to": {
                    "type": "string",
                    "description": "Destinatário do email (para action='send').",
                },
                "subject": {
                    "type": "string",
                    "description": "Assunto do email (para action='send').",
                },
                "body": {
                    "type": "string",
                    "description": "Corpo do email (para action='send').",
                },
            },
            "required": ["action"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        manager = get_manager()
        action = str(args.get("action", "list"))

        if action == "check_connection":
            is_connected = manager.is_connected(ServiceType.GMAIL)
            return ToolResult(
                ok=True,
                message=f"Gmail {'conectado' if is_connected else 'não conectado'}.",
                data={"connected": is_connected}
            )

        if action == "list":
            if not manager.is_connected(ServiceType.GMAIL):
                return ToolResult(
                    ok=False,
                    message="Gmail não está conectado. Use o painel de configurações para conectar.",
                    data={"connected": False}
                )

            try:
                max_results = int(args.get("max_results", 10))
                query = str(args.get("query", "")).strip()
                emails = manager.gmail_list_emails(max_results=max_results, query=query)

                if not emails:
                    return ToolResult(
                        ok=True,
                        message="Nenhum email encontrado.",
                        data={"emails": [], "count": 0}
                    )

                lines = [f"Encontrados {len(emails)} emails:"]
                for i, email in enumerate(emails[:max_results], 1):
                    subject = email.get("subject", "Sem assunto")
                    sender = email.get("sender", "Desconhecido")
                    date = email.get("date", "")
                    lines.append(f"{i}. {subject}\n   De: {sender}\n   Data: {date}")

                return ToolResult(
                    ok=True,
                    message="\n".join(lines),
                    data={"emails": emails, "count": len(emails)}
                )
            except Exception as e:
                return ToolResult(ok=False, message=f"Erro ao listar emails: {e}")

        if action == "send":
            if not manager.is_connected(ServiceType.GMAIL):
                return ToolResult(
                    ok=False,
                    message="Gmail não está conectado. Use o painel de configurações para conectar.",
                    data={"connected": False}
                )

            to = str(args.get("to", "")).strip()
            subject = str(args.get("subject", "")).strip()
            body = str(args.get("body", "")).strip()

            if not to or not subject:
                return ToolResult(ok=False, message="Destinatário e assunto são obrigatórios.")
            
            # Validar formato de email básico
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, to):
                return ToolResult(ok=False, message="Formato de email inválido.")

            try:
                success = manager.gmail_send_email(to=to, subject=subject, body=body)
                if success:
                    return ToolResult(
                        ok=True,
                        message=f"Email enviado para {to}.",
                        data={"to": to, "subject": subject}
                    )
                else:
                    return ToolResult(ok=False, message="Falha ao enviar email.")
            except Exception as e:
                return ToolResult(ok=False, message=f"Erro ao enviar email: {e}")

        return ToolResult(ok=False, message=f"Ação desconhecida: {action}")


class ComposioCalendarTool(BaseTool):
    @property
    def name(self) -> str:
        return "composio_calendar"

    @property
    def description(self) -> str:
        return (
            "Gerencia eventos do Google Calendar usando autenticação OAuth. "
            "Use action='list' para listar eventos, action='create' para criar. "
            "Requer que o Google Calendar esteja conectado via Composio."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "create", "check_connection"],
                    "description": "list: listar eventos; create: criar evento; check_connection: verificar conexão.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Quantidade de eventos (padrão: 10).",
                    "default": 10,
                },
                "time_min": {
                    "type": "string",
                    "description": "Data mínima em formato ISO (ex: 2024-01-01T00:00:00Z).",
                },
                "summary": {
                    "type": "string",
                    "description": "Título do evento (para action='create').",
                },
                "start": {
                    "type": "string",
                    "description": "Data/hora início em ISO (para action='create').",
                },
                "end": {
                    "type": "string",
                    "description": "Data/hora fim em ISO (para action='create').",
                },
                "description": {
                    "type": "string",
                    "description": "Descrição do evento (para action='create').",
                },
            },
            "required": ["action"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        manager = get_manager()
        action = str(args.get("action", "list"))

        if action == "check_connection":
            is_connected = manager.is_connected(ServiceType.GOOGLE_CALENDAR)
            return ToolResult(
                ok=True,
                message=f"Google Calendar {'conectado' if is_connected else 'não conectado'}.",
                data={"connected": is_connected}
            )

        if action == "list":
            if not manager.is_connected(ServiceType.GOOGLE_CALENDAR):
                return ToolResult(
                    ok=False,
                    message="Google Calendar não está conectado.",
                    data={"connected": False}
                )

            try:
                max_results = int(args.get("max_results", 10))
                time_min = args.get("time_min")
                events = manager.calendar_list_events(max_results=max_results, time_min=time_min)

                if not events:
                    return ToolResult(
                        ok=True,
                        message="Nenhum evento encontrado.",
                        data={"events": [], "count": 0}
                    )

                lines = [f"Encontrados {len(events)} eventos:"]
                for i, event in enumerate(events[:max_results], 1):
                    summary = event.get("summary", "Sem título")
                    start = event.get("start", "")
                    lines.append(f"{i}. {summary}\n   Início: {start}")

                return ToolResult(
                    ok=True,
                    message="\n".join(lines),
                    data={"events": events, "count": len(events)}
                )
            except Exception as e:
                return ToolResult(ok=False, message=f"Erro ao listar eventos: {e}")

        if action == "create":
            if not manager.is_connected(ServiceType.GOOGLE_CALENDAR):
                return ToolResult(
                    ok=False,
                    message="Google Calendar não está conectado.",
                    data={"connected": False}
                )

            summary = str(args.get("summary", "")).strip()
            start = str(args.get("start", "")).strip()
            end = str(args.get("end", "")).strip()
            description = str(args.get("description", "")).strip()

            if not summary or not start or not end:
                return ToolResult(ok=False, message="Título, início e fim são obrigatórios.")
            
            # Validar formato ISO datetime
            try:
                datetime.fromisoformat(start.replace('Z', '+00:00'))
                datetime.fromisoformat(end.replace('Z', '+00:00'))
            except ValueError:
                return ToolResult(ok=False, message="Formato de data/hora inválido. Use formato ISO (ex: 2024-01-01T10:00:00Z).")

            try:
                success = manager.calendar_create_event(
                    summary=summary,
                    start=start,
                    end=end,
                    description=description
                )
                if success:
                    return ToolResult(
                        ok=True,
                        message=f"Evento criado: {summary}",
                        data={"summary": summary, "start": start, "end": end}
                    )
                else:
                    return ToolResult(ok=False, message="Falha ao criar evento.")
            except Exception as e:
                return ToolResult(ok=False, message=f"Erro ao criar evento: {e}")

        return ToolResult(ok=False, message=f"Ação desconhecida: {action}")


class ComposioNotionTool(BaseTool):
    @property
    def name(self) -> str:
        return "composio_notion"

    @property
    def description(self) -> str:
        return (
            "Gerencia páginas do Notion usando autenticação OAuth. "
            "Use action='list' para listar páginas, action='create' para criar. "
            "Requer que o Notion esteja conectado via Composio."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "create", "check_connection"],
                    "description": "list: listar páginas; create: criar página; check_connection: verificar conexão.",
                },
                "page_size": {
                    "type": "integer",
                    "description": "Quantidade de páginas (padrão: 10).",
                    "default": 10,
                },
                "parent_id": {
                    "type": "string",
                    "description": "ID da página pai (para action='create').",
                },
                "title": {
                    "type": "string",
                    "description": "Título da página (para action='create').",
                },
                "content": {
                    "type": "string",
                    "description": "Conteúdo da página (para action='create').",
                },
            },
            "required": ["action"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        manager = get_manager()
        action = str(args.get("action", "list"))

        if action == "check_connection":
            is_connected = manager.is_connected(ServiceType.NOTION)
            return ToolResult(
                ok=True,
                message=f"Notion {'conectado' if is_connected else 'não conectado'}.",
                data={"connected": is_connected}
            )

        if action == "list":
            if not manager.is_connected(ServiceType.NOTION):
                return ToolResult(
                    ok=False,
                    message="Notion não está conectado.",
                    data={"connected": False}
                )

            try:
                page_size = int(args.get("page_size", 10))
                pages = manager.notion_list_pages(page_size=page_size)

                if not pages:
                    return ToolResult(
                        ok=True,
                        message="Nenhuma página encontrada.",
                        data={"pages": [], "count": 0}
                    )

                lines = [f"Encontradas {len(pages)} páginas:"]
                for i, page in enumerate(pages[:page_size], 1):
                    title = page.get("title", "Sem título")
                    lines.append(f"{i}. {title}")

                return ToolResult(
                    ok=True,
                    message="\n".join(lines),
                    data={"pages": pages, "count": len(pages)}
                )
            except Exception as e:
                return ToolResult(ok=False, message=f"Erro ao listar páginas: {e}")

        if action == "create":
            if not manager.is_connected(ServiceType.NOTION):
                return ToolResult(
                    ok=False,
                    message="Notion não está conectado.",
                    data={"connected": False}
                )

            parent_id = str(args.get("parent_id", "")).strip()
            title = str(args.get("title", "")).strip()
            content = str(args.get("content", "")).strip()

            if not parent_id or not title:
                return ToolResult(ok=False, message="ID da página pai e título são obrigatórios.")

            try:
                result = manager.notion_create_page(
                    parent_id=parent_id,
                    title=title,
                    content=content
                )
                return ToolResult(
                    ok=True,
                    message=f"Página criada: {title}",
                    data=result
                )
            except Exception as e:
                return ToolResult(ok=False, message=f"Erro ao criar página: {e}")

        return ToolResult(ok=False, message=f"Ação desconhecida: {action}")
