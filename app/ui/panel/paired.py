"""Opt-in HTTPS listener for the Android app paired over USB."""
import hmac
import json
import os
import ssl
from dataclasses import replace
from http.cookies import CookieError, SimpleCookie
from http.server import ThreadingHTTPServer
from ipaddress import IPv4Address
from pathlib import Path
from threading import Thread
from app.core.control_plane import ControlPlanePolicy

DIRECTORY = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Jarvis" / "routine-wifi"
PORT = 48732
COOKIE = "__Host-jarvis_panel"


class PairedPanel:
    def __init__(self, settings, directory):
        self.host = str(IPv4Address(json.loads((directory / "config.json").read_text())["address"]))
        self.origin = f"https://{self.host}:{PORT}"
        self.token = (directory / "panel-token").read_text().strip()
        if len(self.token) < 40:
            raise ValueError("Credencial de pareamento inválida.")
        self.policy = ControlPlanePolicy(replace(settings, host=self.host, port=PORT, access_mode="lan",
                                                 lan_enabled=True, control_token=self.token, trusted_origins=[self.origin]))
        self.tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.tls.load_cert_chain(directory / "tls.pem")
        self.http = None

    def authorized(self, headers, port):
        if headers.get("Host") != f"{self.host}:{port}":
            return False
        if headers.get("Origin", self.origin) != self.origin or headers.get("Sec-Fetch-Site") == "cross-site":
            return False
        cookies = SimpleCookie()
        try:
            cookies.load(headers.get("Cookie", ""))
            value = cookies[COOKIE].value
            return hmac.compare_digest(value.encode(), self.token.encode())
        except (CookieError, KeyError):
            return False

    def start_http(self, base_handler):
        panel = self

        class Server(ThreadingHTTPServer):
            paired_panel = panel

            def finish_request(self, sock, addr):
                sock.settimeout(15)
                try:
                    with panel.tls.wrap_socket(sock, server_side=True) as stream:
                        super().finish_request(stream, addr)
                except (ssl.SSLError, ConnectionError, TimeoutError):
                    pass

        self.http = Server((self.host, PORT), base_handler)
        Thread(target=self.http.serve_forever, name="PairedPanelHTTPS", daemon=True).start()

    async def serve_chat(self, handler):
        import asyncio
        import websockets

        async def chat(socket):
            headers = socket.request.headers if hasattr(socket, "request") else socket.request_headers
            if not self.authorized(headers, PORT + 1) or headers.get("Origin") != self.origin:
                await socket.close(code=1008, reason="Pareamento necessário")
                return
            await handler(socket, allowed_origins={self.origin})

        try:
            async with websockets.serve(chat, self.host, PORT + 1, ssl=self.tls, origins=[self.origin]):
                await asyncio.Future()
        except OSError as error:
            import logging
            logging.getLogger(__name__).warning("Chat ao vivo no Android indisponível: %s", error)
