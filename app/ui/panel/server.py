from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


class PanelHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/":
            content = (
                "<html><head><title>Jarvis Rebuild</title></head>"
                "<body style='background:#111;color:#eee;font-family:Segoe UI,Arial,sans-serif;'>"
                "<h1>Jarvis Rebuild</h1>"
                "<p>Interface inicial do painel modular.</p>"
                "</body></html>"
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content.encode("utf-8"))))
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()


class PanelServer:
    def __init__(self, settings: Any) -> None:
        self.settings = settings
        self.server: HTTPServer | None = None
        self.thread: threading.Thread | None = None

    def _run(self) -> None:
        address = (self.settings.host, self.settings.port)
        self.server = HTTPServer(address, PanelHandler)
        self.server.serve_forever()

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self._run, daemon=True, name="PanelServer")
        self.thread.start()
