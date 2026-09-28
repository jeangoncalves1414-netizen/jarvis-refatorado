"""
Composio Manager - Integração OAuth para Gmail, Google Calendar, Notion e outros serviços.
Baseado no padrão do Jarvis-astrokjoseph que usa Composio para managed auth.
"""

from __future__ import annotations

import os
import json
import requests
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse


class ServiceType(Enum):
    """Tipos de serviços suportados."""
    GMAIL = "gmail"
    GOOGLE_CALENDAR = "google_calendar"
    NOTION = "notion"
    SLACK = "slack"
    GITHUB = "github"
    JIRA = "jira"


@dataclass
class AuthConfig:
    """Configuração de autenticação para um serviço."""
    service: ServiceType
    enabled: bool = False
    auth_id: str | None = None
    connected_at: str | None = None
    scopes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ComposioManager:
    """
    Gerenciador de integrações Composio.
    Gerencia OAuth, tokens, e execuções de ferramentas.
    """

    def __init__(self, api_key: str | None = None, base_url: str = "https://api.composio.dev"):
        self.api_key = api_key or os.getenv("COMPOSIO_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.auth_configs: Dict[ServiceType, AuthConfig] = {}
        self._load_auth_configs()

    def _load_auth_configs(self) -> None:
        """Carrega configurações de autenticação do arquivo."""
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "composio_auth.json")
        try:
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for service_str, config_data in data.items():
                        try:
                            service = ServiceType(service_str)
                            self.auth_configs[service] = AuthConfig(
                                service=service,
                                enabled=config_data.get("enabled", False),
                                auth_id=config_data.get("auth_id"),
                                connected_at=config_data.get("connected_at"),
                                scopes=config_data.get("scopes", []),
                                metadata=config_data.get("metadata", {})
                            )
                        except ValueError:
                            print(f"[Composio] Serviço desconhecido: {service_str}")
        except Exception as e:
            print(f"[Composio] Erro ao carregar configs: {e}")

    def _save_auth_configs(self) -> None:
        """Salva configurações de autenticação no arquivo."""
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "composio_auth.json")
        try:
            config_dir = os.path.dirname(config_path)
            if config_dir:
                os.makedirs(config_dir, exist_ok=True)
            data = {}
            for service, config in self.auth_configs.items():
                data[service.value] = {
                    "enabled": config.enabled,
                    "auth_id": config.auth_id,
                    "connected_at": config.connected_at,
                    "scopes": config.scopes,
                    "metadata": config.metadata
                }
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[Composio] Erro ao salvar configs: {e}")

    def is_connected(self, service: ServiceType) -> bool:
        """Verifica se um serviço está conectado."""
        config = self.auth_configs.get(service)
        return config is not None and config.enabled and config.auth_id is not None

    def get_auth_url(self, service: ServiceType, redirect_uri: str) -> str:
        """
        Gera URL de autenticação OAuth para um serviço.
        Retorna a URL onde o usuário deve autorizar o acesso.
        """
        if not self.api_key:
            raise ValueError("COMPOSIO_API_KEY não configurada")
        
        # Validar redirect_uri para evitar open redirect
        try:
            parsed = urlparse(redirect_uri)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("redirect_uri inválido: deve ser uma URL válida")
        except Exception as e:
            raise ValueError(f"redirect_uri inválido: {e}")

        try:
            response = requests.post(
                f"{self.base_url}/oauth/connect",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "service": service.value,
                    "redirect_uri": redirect_uri,
                    "scopes": self._get_default_scopes(service)
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data.get("url", "")
        except Exception as e:
            print(f"[Composio] Erro ao gerar auth URL: {type(e).__name__}")
            raise

    def _get_default_scopes(self, service: ServiceType) -> List[str]:
        """Retorna escopos padrão para um serviço."""
        scopes_map = {
            ServiceType.GMAIL: [
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/gmail.send",
                "https://www.googleapis.com/auth/gmail.modify"
            ],
            ServiceType.GOOGLE_CALENDAR: [
                "https://www.googleapis.com/auth/calendar.readonly",
                "https://www.googleapis.com/auth/calendar.events"
            ],
            ServiceType.NOTION: [
                "read",
                "write"
            ],
            ServiceType.SLACK: [
                "chat:write",
                "channels:read",
                "channels:history"
            ],
            ServiceType.GITHUB: [
                "repo",
                "user"
            ],
            ServiceType.JIRA: [
                "read:jira-work",
                "write:jira-work"
            ]
        }
        return scopes_map.get(service, [])

    def complete_auth(self, service: ServiceType, code: str, redirect_uri: str) -> bool:
        """
        Completa o fluxo OAuth com o código recebido.
        Salva a configuração de autenticação.
        """
        if not self.api_key:
            raise ValueError("COMPOSIO_API_KEY não configurada")

        try:
            response = requests.post(
                f"{self.base_url}/oauth/callback",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "service": service.value,
                    "code": code,
                    "redirect_uri": redirect_uri
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            auth_id = data.get("auth_id")
            if not auth_id:
                raise ValueError("auth_id não recebido")

            from datetime import datetime
            self.auth_configs[service] = AuthConfig(
                service=service,
                enabled=True,
                auth_id=auth_id,
                connected_at=datetime.now().isoformat(),
                scopes=self._get_default_scopes(service),
                metadata=data.get("metadata", {})
            )
            self._save_auth_configs()
            return True

        except Exception as e:
            print(f"[Composio] Erro ao completar auth: {type(e).__name__}")
            return False

    def disconnect(self, service: ServiceType) -> bool:
        """Desconecta um serviço."""
        if service in self.auth_configs:
            config = self.auth_configs[service]
            if config.auth_id:
                try:
                    requests.delete(
                        f"{self.base_url}/auth/{config.auth_id}",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        timeout=30
                    )
                except Exception as e:
                    print(f"[Composio] Erro ao desconectar na API: {type(e).__name__}")

            del self.auth_configs[service]
            self._save_auth_configs()
            return True
        return False

    def execute_tool(self, service: ServiceType, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executa uma ferramenta através do Composio.
        Usa a autenticação configurada para o serviço.
        """
        config = self.auth_configs.get(service)
        if not config or not config.auth_id:
            raise ValueError(f"Serviço {service.value} não está conectado")

        try:
            response = requests.post(
                f"{self.base_url}/tools/execute",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "auth_id": config.auth_id,
                    "service": service.value,
                    "tool": tool_name,
                    "params": params
                },
                timeout=60
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[Composio] Erro ao executar tool: {e}")
            raise

    # ── Gmail ───────────────────────────────────────────────────────────────
    def gmail_list_emails(self, max_results: int = 10, query: str = "") -> List[Dict[str, Any]]:
        """Lista emails do Gmail."""
        if not self.is_connected(ServiceType.GMAIL):
            raise ValueError("Gmail não está conectado")

        params = {"maxResults": max_results}
        if query:
            params["q"] = query

        result = self.execute_tool(ServiceType.GMAIL, "list_emails", params)
        return result.get("data", result.get("emails", []))

    def gmail_send_email(self, to: str, subject: str, body: str) -> bool:
        """Envia um email via Gmail."""
        if not self.is_connected(ServiceType.GMAIL):
            raise ValueError("Gmail não está conectado")

        params = {
            "to": to,
            "subject": subject,
            "body": body
        }
        result = self.execute_tool(ServiceType.GMAIL, "send_email", params)
        return result.get("success", False)

    # ── Google Calendar ───────────────────────────────────────────────────────
    def calendar_list_events(self, max_results: int = 10, time_min: str | None = None) -> List[Dict[str, Any]]:
        """Lista eventos do Google Calendar."""
        if not self.is_connected(ServiceType.GOOGLE_CALENDAR):
            raise ValueError("Google Calendar não está conectado")

        params = {"maxResults": max_results}
        if time_min:
            params["timeMin"] = time_min

        result = self.execute_tool(ServiceType.GOOGLE_CALENDAR, "list_events", params)
        return result.get("data", result.get("events", []))

    def calendar_create_event(self, summary: str, start: str, end: str, description: str = "") -> bool:
        """Cria um evento no Google Calendar."""
        if not self.is_connected(ServiceType.GOOGLE_CALENDAR):
            raise ValueError("Google Calendar não está conectado")

        params = {
            "summary": summary,
            "start": start,
            "end": end,
            "description": description
        }
        result = self.execute_tool(ServiceType.GOOGLE_CALENDAR, "create_event", params)
        return result.get("success", False)

    # ── Notion ─────────────────────────────────────────────────────────────────
    def notion_list_pages(self, page_size: int = 10) -> List[Dict[str, Any]]:
        """Lista páginas do Notion."""
        if not self.is_connected(ServiceType.NOTION):
            raise ValueError("Notion não está conectado")

        params = {"pageSize": page_size}
        result = self.execute_tool(ServiceType.NOTION, "list_pages", params)
        return result.get("data", result.get("pages", []))

    def notion_create_page(self, parent_id: str, title: str, content: str = "") -> Dict[str, Any]:
        """Cria uma página no Notion."""
        if not self.is_connected(ServiceType.NOTION):
            raise ValueError("Notion não está conectado")

        params = {
            "parentId": parent_id,
            "title": title,
            "content": content
        }
        result = self.execute_tool(ServiceType.NOTION, "create_page", params)
        return result.get("data", result)

    def list_connected_services(self) -> List[ServiceType]:
        """Lista todos os serviços conectados."""
        return [service for service, config in self.auth_configs.items() if config.enabled]


# Singleton global
_manager_instance: Optional[ComposioManager] = None


def get_manager() -> ComposioManager:
    """Retorna instância singleton do ComposioManager."""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = ComposioManager()
    return _manager_instance
