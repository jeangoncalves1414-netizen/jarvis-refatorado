"""Authentication and origin policy for the local HTTP control plane."""
from __future__ import annotations

import hmac
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from app.core.diagnostics import record


@dataclass(frozen=True)
class RequestPrincipal:
    id: str
    mode: str


class ControlPlanePolicy:
    def __init__(self, settings: Any) -> None:
        self.settings = settings
        settings.validate_control_plane()

    @property
    def is_lan(self) -> bool:
        return self.settings.access_mode == "lan"

    @staticmethod
    def _origin(value: str) -> str | None:
        try:
            parsed = urlsplit(value.strip())
        except (AttributeError, ValueError):
            return None
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            return None
        return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"

    def allowed_origins(self, runtime_port: int | None = None) -> set[str]:
        """Return origins derived only from trusted application configuration."""
        configured_port = int(getattr(self.settings, "port", 8000))
        ports = {configured_port}
        if runtime_port:
            ports.add(runtime_port)
        configured_host = str(getattr(self.settings, "host", "")).strip().lower()
        hosts = {"127.0.0.1", "localhost", "[::1]"}
        if configured_host and configured_host not in {"0.0.0.0", "::", "[::]"}:
            hosts.add(configured_host if ":" not in configured_host or configured_host.startswith("[") else f"[{configured_host}]")
        configured = {f"http://{host}:{p}" for host in hosts for p in ports if p > 0}
        trusted = {self._origin(str(origin)) for origin in self.settings.trusted_origins}
        return {origin for origin in configured | trusted if origin}

    def trusted_hosts(self, runtime_port: int | None = None) -> set[str]:
        return {urlsplit(origin).netloc.lower() for origin in self.allowed_origins(runtime_port)}

    def is_trusted_host(self, host: str, runtime_port: int | None = None) -> bool:
        candidate = str(host or "").strip().lower()
        if not candidate or any(char in candidate for char in "/\\, \t\r\n"):
            return False
        return hmac.compare_digest(candidate, next((item for item in self.trusted_hosts(runtime_port) if hmac.compare_digest(candidate, item)), ""))

    def authorize(self, handler: Any, path: str, method: str) -> tuple[bool, int, str, RequestPrincipal | None]:
        runtime_port = None
        server = getattr(handler, "server", None)
        if server:
            addr = getattr(server, "server_address", None)
            if isinstance(addr, tuple) and len(addr) > 1 and isinstance(addr[1], int):
                runtime_port = addr[1]
            elif hasattr(server, "server_port") and isinstance(server.server_port, int):
                runtime_port = server.server_port

        origin = handler.headers.get("Origin", "").rstrip("/").lower()
        host = handler.headers.get("Host", "")
        if not self.is_trusted_host(host, runtime_port=runtime_port):
            self._denied("host", path, method)
            return False, 403, "Host não confiável.", None
        if origin and origin not in self.allowed_origins(runtime_port=runtime_port):
            self._denied("origin", path, method)
            return False, 403, "Origem não confiável.", None
        if self.is_lan:
            supplied = handler.headers.get("Authorization", "")
            if supplied.lower().startswith("bearer "):
                supplied = supplied[7:]
            if not supplied or not hmac.compare_digest(supplied, self.settings.control_token):
                self._denied("authentication", path, method)
                return False, 401, "Autenticação obrigatória.", None
            return True, 200, "", RequestPrincipal("lan-control", "lan")
        client = handler.client_address[0] if handler.client_address else ""
        if client not in {"127.0.0.1", "::1"}:
            self._denied("non_loopback", path, method)
            return False, 403, "Acesso permitido apenas em loopback.", None
        return True, 200, "", RequestPrincipal("local-desktop", "loopback")

    def _denied(self, reason: str, path: str, method: str) -> None:
        record("control_plane", "request_denied", correlation_id=uuid.uuid4().hex, reason=reason, path=path, method=method)
