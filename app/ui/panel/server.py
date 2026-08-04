from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from app.ui.panel.api.dashboard import (
    handle_dashboard_get,
    handle_dashboard_post,
    handle_tasks_get,
)
from app.ui.panel.api.enem import handle_enem_get, handle_enem_post
from app.ui.panel.api.settings import handle_settings_get, handle_settings_post
from app.ui.panel.api.tutor import handle_tutor_get, handle_tutor_post
from app.ui.panel.api.voice import handle_voice_post
from app.storage.vector.semantic_memory import is_technical_error_memory

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_STATIC_DIR   = Path(__file__).parent / "static"
_REACT_DIST_DIR = Path(__file__).resolve().parents[3] / "frontend" / "dist"

_orchestrator: Any = None
_wake_word_enabled: bool = True
_wake_word_detector: Any = None  # WakeWordDetector instance
_ws_loop: asyncio.AbstractEventLoop | None = None  # asyncio loop do WS para broadcast
_ws_clients: set = set()  # connected WebSocket clients for broadcast


def _calendar_conversation_prefix() -> str:
    """Consumes calendar reminders deliberately configured for the next chat."""
    try:
        from app.services.calendar import CalendarService
        due = CalendarService().due_reminders(on_conversation=True)
        if not due:
            return ""
        lines = [f"Sir, antes de continuarmos: lembrete — {event.title}." for event in due]
        return "\n".join(lines) + "\n\n"
    except Exception:
        return ""

# ──────────────────────────────────────────────────────────── HTTP handler ──

class PanelHandler(BaseHTTPRequestHandler):
    settings: Any = None

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A002
        # Suprimir 426 (WS upgrade) e 404 de favicon — apenas erros reais
        if args and str(args[1]) in ("200", "304", "204", "426", "404"):
            return
        super().log_message(fmt, *args)

    # ── helpers ─────────────────────────────────────────────────────────────

    def _send_json(self, status: int, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        mime, _ = mimetypes.guess_type(str(path))
        mime = mime or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_404(self) -> None:
        self.send_response(404)
        self.end_headers()

    # ── WebSocket upgrade detection ─────────────────────────────────────────

    def _is_websocket_upgrade(self) -> bool:
        return (
            self.headers.get("Upgrade", "").lower() == "websocket"
            and self.headers.get("Connection", "").lower().find("upgrade") != -1
        )

    # ── GET ──────────────────────────────────────────────────────────────────

    def do_GET(self) -> None:
        path = self.path.split("?")[0]

        # ── WebSocket upgrade (hand off to asyncio WS server on same port) ──
        if self._is_websocket_upgrade():
            # The websockets server handles /ws/chat — proxy the raw socket.
            # Since both servers share the same port via _HybridServer, the
            # HybridHTTPServer.get_request intercepts WS before reaching here.
            # This branch is a safety fallback that just returns 426.
            self.send_response(426, "Upgrade Required")
            self.send_header("Upgrade", "websocket")
            self.end_headers()
            return

        # ── HTML pages ───────────────────────────────────────────────────────
        if path in ("/", "/index.html"):
            f = _REACT_DIST_DIR / "index.html"
            self._send_html(
                f.read_text(encoding="utf-8")
                if f.exists()
                else "<h1>Interface React nao compilada. Execute npm run build em frontend.</h1>"
            )
            return

        if path in ("/legacy", "/legacy/"):
            f = _TEMPLATE_DIR / "index.html"
            self._send_html(f.read_text(encoding="utf-8") if f.exists() else "<h1>index.html não encontrado</h1>")
            return

        if path in ("/app", "/app/"):
            self.send_response(301)
            self.send_header("Location", "/")
            self.end_headers()
            return

        if path.startswith("/assets/"):
            try:
                asset = (_REACT_DIST_DIR / path.removeprefix("/")).resolve()
                asset.relative_to(_REACT_DIST_DIR.resolve())
            except ValueError:
                self._send_404()
                return
            if asset.is_file():
                self._send_file(asset)
            else:
                self._send_404()
            return

        # Compatibilidade com builds antigos servidos em /app/assets/
        if path.startswith("/app/assets/"):
            try:
                asset = (_REACT_DIST_DIR / path.removeprefix("/app/")).resolve()
                asset.relative_to(_REACT_DIST_DIR.resolve())
            except ValueError:
                self._send_404()
                return
            if asset.is_file():
                self._send_file(asset)
            else:
                self._send_404()
            return

        if path == "/spotlight":
            f = _TEMPLATE_DIR / "spotlight.html"
            (self._send_html(f.read_text(encoding="utf-8")) if f.exists() else self._send_404())
            return

        if path == "/camera-modal":
            f = _TEMPLATE_DIR / "camera-modal.html"
            (self._send_html(f.read_text(encoding="utf-8")) if f.exists() else self._send_404())
            return

        # Página mínima para testar a ponte em outro dispositivo da mesma LAN.
        # O app móvel definitivo será construído depois, usando o mesmo contrato.
        if path in ("/bridge", "/bridge/"):
            f = _TEMPLATE_DIR / "bridge.html"
            (self._send_html(f.read_text(encoding="utf-8")) if f.exists() else self._send_404())
            return

        if path == "/favicon.ico":
            self._send_404()
            return

        # ── Static assets ────────────────────────────────────────────────────
        if path.startswith("/static/"):
            rel = path[len("/static/"):]
            static_path = _STATIC_DIR / rel
            if static_path.is_file():
                self._send_file(static_path)
            else:
                self._send_404()
            return

        # ── API GET ──────────────────────────────────────────────────────────
        if path.startswith("/api/"):
            parts = [p for p in path.split("/") if p]

            # /api/sessions (list)
            if len(parts) == 2 and parts[1] == "sessions":
                try:
                    from app.storage.session_store import list_sessions
                    self._send_json(200, {"sessions": list_sessions()})
                except Exception:
                    self._send_json(200, {"sessions": []})
                return

            # Study workspace metadata (categories are persisted alongside sessions).
            if len(parts) == 3 and parts[1] == "study" and parts[2] == "categories":
                try:
                    from app.storage.session_store import list_categories
                    self._send_json(200, {"categories": list_categories()})
                except Exception as exc:
                    self._send_json(500, {"error": str(exc)})
                return

            if len(parts) == 3 and parts[1] == "study" and parts[2] == "trash":
                try:
                    from app.storage.session_store import list_trash
                    self._send_json(200, {"sessions": list_trash("tutor")})
                except Exception as exc:
                    self._send_json(500, {"error": str(exc)})
                return

            # /api/sessions/<id> or sub-routes (/history, /whiteboard)
            if len(parts) >= 3 and parts[1] == "sessions":
                session_id = parts[2]
                sub = parts[3] if len(parts) >= 4 else ""
                try:
                    from app.storage.session_store import get_session, get_session_history, get_whiteboard
                    if sub == "history":
                        self._send_json(200, {"history": get_session_history(session_id)})
                    elif sub == "whiteboard":
                        self._send_json(200, {"whiteboard": get_whiteboard(session_id)})
                    else:
                        session = get_session(session_id)
                        if session:
                            self._send_json(200, {"session": session})
                        else:
                            self._send_json(404, {"error": "Sessão não encontrada."})
                except Exception as exc:
                    self._send_json(500, {"error": str(exc)})
                return

            if len(parts) == 2 and parts[1] == "wake-word":
                try:
                    from app.services.voice.wake_word import VOSK_AVAILABLE, PYAUDIO_AVAILABLE
                    self._send_json(200, {
                        "enabled": _wake_word_enabled,
                        "available": VOSK_AVAILABLE and PYAUDIO_AVAILABLE,
                    })
                except Exception as exc:
                    self._send_json(200, {"enabled": False, "available": False, "error": str(exc)})
                return

            if len(parts) == 2 and parts[1] == "memories":
                try:
                    import urllib.parse
                    query = urllib.parse.urlparse(self.path).query
                    parsed = urllib.parse.parse_qs(query)
                    collection = parsed.get("collection", ["conversations"])[0]
                    limit = int(parsed.get("limit", [20])[0])
                    if _orchestrator and hasattr(_orchestrator, "semantic_memory") and _orchestrator.semantic_memory:
                        sm = _orchestrator.semantic_memory
                        col = sm.get_or_create_collection(collection)
                        if col:
                            results = col.get(limit=limit)
                            memories = []
                            for i, doc in enumerate(results.get("documents") or []):
                                meta = (results.get("metadatas") or [{}])[i] or {}
                                memories.append({"text": doc, "metadata": meta, "id": (results.get("ids") or [""])[i]})
                            self._send_json(200, {"memories": memories, "collection": collection})
                        else:
                            self._send_json(200, {"memories": [], "collection": collection})
                    else:
                        self._send_json(200, {"memories": [], "error": "Memória semântica não disponível."})
                except Exception as exc:
                    self._send_json(500, {"error": str(exc)})
                return

            if len(parts) == 2 and parts[1] == "metrics":
                try:
                    import urllib.parse
                    from app.services.system import SystemMetrics
                    from app.core.logger import logger
                    data = SystemMetrics.get_metrics()
                    data.update(logger.get_metrics_summary())
                    if _orchestrator and hasattr(_orchestrator, "llm_service") and _orchestrator.llm_service:
                        provider = _orchestrator.llm_service.get_active_provider()
                        data["provider"] = provider
                    self._send_json(200, data)
                except Exception as exc:
                    self._send_json(200, {"cpu": 0, "ram": 0, "error": str(exc)})
                return

            if len(parts) == 2 and parts[1] == "logs":
                try:
                    import urllib.parse
                    from app.core.logger import logger
                    query = urllib.parse.urlparse(self.path).query
                    parsed = urllib.parse.parse_qs(query)
                    level = parsed.get("level", [None])[0]
                    self._send_json(200, {"logs": logger.get_logs(level=level)})
                except Exception as exc:
                    self._send_json(500, {"error": str(exc)})
                return

            # /api/realtime -> clima e cotações
            if len(parts) == 2 and parts[1] == "realtime":
                try:
                    from app.services.realtime import RealTimeService
                    weather = RealTimeService.get_weather()
                    finance = RealTimeService.get_finance()
                    self._send_json(200, {"weather": weather, "finance": finance})
                except Exception as exc:
                    self._send_json(200, {"weather": {"ok": False}, "finance": {"ok": False}, "error": str(exc)})
                return

            if len(parts) == 2 and parts[1] == "climate":
                from app.services.climate_control import ClimateControlService
                self._send_json(200, ClimateControlService().get_state())
                return

            # /api/bridge -> registry, conexões e eventos da ponte local
            if len(parts) == 2 and parts[1] == "bridge":
                try:
                    from app.services.device_bridge import DeviceBridgeService
                    self._send_json(200, DeviceBridgeService().get_status())
                except Exception as exc:
                    self._send_json(500, {"ok": False, "error": str(exc)})
                return

            # /api/proactive -> status do briefing e lembretes
            if len(parts) == 2 and parts[1] == "proactive":
                try:
                    from app.services.proactive import ProactiveService
                    srv = ProactiveService()
                    config = srv.get_config()
                    reminders = srv.get_pending_reminders()
                    self._send_json(200, {"config": config, "reminders": reminders})
                except Exception as exc:
                    self._send_json(200, {"config": {}, "reminders": [], "error": str(exc)})
                return

            # /api/calendar -> eventos do calendário (filtro opcional ?start=&end=)
            if len(parts) == 2 and parts[1] == "calendar":
                try:
                    import urllib.parse
                    from datetime import datetime
                    from app.services.calendar import CalendarService
                    query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                    srv = CalendarService()
                    start_s = (query.get("start") or [""])[0]
                    end_s = (query.get("end") or [""])[0]
                    if start_s or end_s:
                        start = datetime.fromisoformat(start_s) if start_s else None
                        end = datetime.fromisoformat(end_s) if end_s else None
                        events = srv.get_events(start, end)
                    else:
                        events = srv.get_all_events()
                    self._send_json(200, {"events": [e.to_dict() for e in events]})
                except ValueError as exc:
                    self._send_json(400, {"error": f"Datas inválidas: {exc}"})
                except Exception as exc:
                    self._send_json(500, {"error": str(exc)})
                return

            # /api/tray -> status do boot automático
            if len(parts) == 2 and parts[1] == "tray":
                try:
                    from app.services.tray import BootService
                    self._send_json(200, {"boot_enabled": BootService.is_enabled()})
                except Exception as exc:
                    self._send_json(200, {"boot_enabled": False, "error": str(exc)})
                return

            # /api/cinema/search?q={query}
            if len(parts) >= 3 and parts[1] == "cinema" and parts[2] == "library":
                from app.services.cinema_library import CinemaLibraryService
                self._send_json(200, CinemaLibraryService().list_items())
                return

            if len(parts) >= 4 and parts[1] == "cinema" and parts[2] == "discovery" and parts[3] == "search":
                try:
                    import urllib.parse
                    query = urllib.parse.urlparse(self.path).query
                    q = urllib.parse.parse_qs(query).get("q", [""])[0]
                    from app.services.cinema_discovery import CinemaDiscoveryService
                    result = CinemaDiscoveryService().search(q)
                    self._send_json(200 if result.get("ok") else 400, result)
                except Exception as exc:
                    self._send_json(500, {"ok": False, "error": str(exc)})
                return

            if len(parts) >= 3 and parts[1] == "cinema" and parts[2] == "search":
                try:
                    import urllib.parse
                    query = urllib.parse.urlparse(self.path).query
                    parsed = urllib.parse.parse_qs(query)
                    q = parsed.get("q", [""])[0]
                    mtype = parsed.get("type", ["auto"])[0]
                    from app.services.cinema import CinemaService
                    res = CinemaService.search_media(q, media_type=mtype)
                    self._send_json(200, res)
                except Exception as exc:
                    self._send_json(500, {"ok": False, "error": str(exc)})
                return

            # /api/vision/file/<filename> -> serve captured screenshots/photos
            if len(parts) >= 3 and parts[1] == "vision" and parts[2] == "file":
                filename = parts[3] if len(parts) >= 4 else ""
                capture_file = Path("data/captures") / filename
                if capture_file.is_file():
                    self._send_file(capture_file)
                else:
                    self._send_404()
                return


            for handler_fn in (
                handle_dashboard_get,
                handle_tasks_get,
                handle_tutor_get,
                handle_enem_get,
                handle_settings_get,
            ):
                result = handler_fn(parts, self)
                if result:
                    self._send_json(*result)
                    return

            # /api/chat GET → list sessions (legacy compat)
            if len(parts) == 2 and parts[1] == "chat" and _orchestrator is not None:
                try:
                    from app.storage.session_store import list_sessions
                    self._send_json(200, {"sessions": list_sessions()})
                except Exception as exc:
                    self._send_json(500, {"error": str(exc)})
                return

            self._send_json(404, {"error": "Endpoint não encontrado."})
            return

        self._send_404()

    # ── OPTIONS (CORS) ───────────────────────────────────────────────────────

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_DELETE(self) -> None:
        import urllib.parse
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        if path.startswith("/api/study/categories/"):
            try:
                from app.storage.session_store import delete_category
                category_id = path.rsplit("/", 1)[-1]
                deleted = delete_category(category_id)
                self._send_json(200, {"ok": deleted})
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return

        if path.startswith("/api/sessions/") and path.endswith("/restore"):
            try:
                from app.storage.session_store import restore_session
                parts_restore = [p for p in path.split("/") if p]
                session_id = parts_restore[2] if len(parts_restore) >= 4 else ""
                restored = restore_session(session_id)
                self._send_json(200, {"ok": restored})
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return
        if path.startswith("/api/sessions/"):
            parts = [p for p in path.split("/") if p]
            if len(parts) == 3 and parts[1] == "sessions":
                session_id = parts[2]
                try:
                    from app.storage.session_store import delete_session, trash_session
                    permanent = (urllib.parse.parse_qs(parsed_path.query).get("permanent", ["0"])[0] == "1")
                    deleted = delete_session(session_id) if permanent else trash_session(session_id)
                    self._send_json(200, {"ok": deleted})
                except Exception as exc:
                    self._send_json(500, {"error": str(exc)})
                return
        if path == "/api/calendar":
            import urllib.parse
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            event_id = (query.get("id") or [""])[0]
            if not event_id:
                self._send_json(400, {"ok": False, "error": "Parâmetro 'id' obrigatório."})
                return
            try:
                from app.services.calendar import CalendarService
                deleted = CalendarService().delete_event_by_id(event_id)
                self._send_json(200, {"ok": deleted})
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return
        self._send_404()

    # ── POST ─────────────────────────────────────────────────────────────────

    def do_POST(self) -> None:
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b""

        if not path.startswith("/api/"):
            self._send_404()
            return

        if path == "/api/automation":
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
                if payload.get("action") != "set_temperature" or payload.get("device") != "climate":
                    self._send_json(400, {"ok": False, "error": "Ação de automação inválida."})
                    return
                from app.services.climate_control import ClimateControlService
                result = ClimateControlService().set_target(payload.get("value"))
                self._send_json(200 if result.get("ok") else 400, result)
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send_json(400, {"ok": False, "error": "JSON inválido."})
            return

        # Contrato da ponte: o celular e o desktop usam as mesmas operações,
        # independentemente do adaptador físico (Tuya, BLE, Matter etc.).
        if path == "/api/bridge":
            try:
                from app.services.device_bridge import DeviceBridgeService
                payload = json.loads(body.decode("utf-8") or "{}")
                action = str(payload.get("action") or "").strip()
                service = DeviceBridgeService()
                if action in {"pair", "register"}:
                    result = service.register_device(
                        payload.get("device_id"), payload.get("name"), payload.get("kind", "client"),
                        payload.get("platform", "unknown"), payload.get("transport", "lan"), payload.get("pairing_code"),
                    )
                elif action == "heartbeat":
                    result = service.heartbeat(payload.get("device_id"))
                elif action == "command":
                    result = service.command(payload.get("target_id"), payload.get("command"), payload.get("payload"), payload.get("source", "desktop"))
                elif action == "remove":
                    result = {"ok": service.remove_device(payload.get("device_id"))}
                else:
                    result = {"ok": False, "error": "Ação de ponte inválida."}
                self._send_json(200 if result.get("ok") else 400, result)
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send_json(400, {"ok": False, "error": "JSON inválido."})
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        if path == "/api/memories/cleanup":
            try:
                if not _orchestrator or not getattr(_orchestrator, "semantic_memory", None):
                    self._send_json(200, {"ok": True, "removed": 0})
                    return
                removed = _orchestrator.semantic_memory.cleanup_technical_error_memories()
                self._send_json(200, {"ok": True, "removed": removed})
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        # /api/proactive -> atualiza briefing ou adiciona lembrete
        if path == "/api/proactive":
            try:
                from app.services.proactive import ProactiveService
                payload = json.loads(body.decode("utf-8") or "{}")
                action = payload.get("action")
                srv = ProactiveService()
                if action == "configure_briefing":
                    res = srv.update_briefing_config(
                        enabled=payload.get("enabled"),
                        briefing_time=payload.get("briefing_time"),
                        topics=payload.get("topics"),
                        custom_instructions=payload.get("custom_instructions"),
                    )
                    self._send_json(200, {"ok": True, "config": res})
                elif action == "add_reminder":
                    msg = payload.get("reminder_message", "")
                    target_time = payload.get("reminder_time", "+10m")
                    rem = srv.add_reminder(msg, target_time)
                    self._send_json(200, {"ok": True, "reminder": rem})
                elif action == "trigger_briefing":
                    text = srv.generate_briefing_text()
                    self._send_json(200, {"ok": True, "briefing_text": text})
                else:
                    self._send_json(400, {"error": "Ação inválida."})
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return

        # /api/tray -> altera boot automático
        if path == "/api/tray":
            try:
                from app.services.tray import BootService
                payload = json.loads(body.decode("utf-8") or "{}")
                action = payload.get("action")
                if action == "enable_boot":
                    ok = BootService.enable()
                    self._send_json(200, {"ok": ok, "boot_enabled": BootService.is_enabled()})
                elif action == "disable_boot":
                    ok = BootService.disable()
                    self._send_json(200, {"ok": ok, "boot_enabled": BootService.is_enabled()})
                else:
                    self._send_json(400, {"error": "Ação inválida."})
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return

        # /api/calendar -> cria evento
        if path == "/api/calendar":
            try:
                from datetime import datetime, timedelta
                from app.services.calendar import CalendarService, CalendarEvent
                payload = json.loads(body.decode("utf-8") or "{}")
                if payload.get("action") == "cancel_reminder":
                    event_id = str(payload.get("id") or "")
                    ok = CalendarService().cancel_reminder(event_id)
                    self._send_json(200 if ok else 404, {"ok": ok, "error": "Lembrete não encontrado." if not ok else ""})
                    return
                title = (payload.get("title") or "").strip()
                start_s = (payload.get("start") or "").strip()
                if not title or not start_s:
                    self._send_json(400, {"error": "Campos 'title' e 'start' são obrigatórios."})
                    return
                start = datetime.fromisoformat(start_s)
                end = None
                if payload.get("end"):
                    end = datetime.fromisoformat(str(payload["end"]))
                reminder_at = datetime.fromisoformat(str(payload["reminder_at"])) if payload.get("reminder_at") else None
                event = CalendarEvent(
                    title=title,
                    start=start,
                    end=end,
                    description=payload.get("description") or "",
                    location=payload.get("location") or "",
                    reminder_minutes=int(payload.get("reminder_minutes") or 15),
                    reminder_policy=str(payload.get("reminder_policy") or "once"),
                    reminder_at=reminder_at,
                    reminder_instructions=payload.get("reminder_instructions") or "",
                )
                ok = CalendarService().add_event(event)
                self._send_json(200 if ok else 500, {"ok": ok, "event": event.to_dict()})
            except ValueError as exc:
                self._send_json(400, {"error": f"Dados inválidos: {exc}"})
            except (TypeError, json.JSONDecodeError):
                self._send_json(400, {"error": "JSON ou payload inválido."})
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return

        # /api/chat → call orchestrator

        if path == "/api/chat":
            if _orchestrator is None:
                self._send_json(503, {"error": "Orquestrador não disponível."})
                return
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
                message = payload.get("message", "").strip()
                session_id = payload.get("session_id")
                mode = payload.get("mode", "general")
                if not message:
                    self._send_json(400, {"error": "Mensagem não pode ser vazia."})
                    return
                plan = _orchestrator.handle_request(message, session_id=session_id, mode=mode)
                prefix = _calendar_conversation_prefix()
                if prefix:
                    plan.summary = prefix + getattr(plan, "summary", str(plan))
                self._send_json(200, {
                    "ok": True,
                    "status": "complete",
                    "reply":   getattr(plan, "summary", str(plan)),
                    "summary": getattr(plan, "summary", str(plan)),
                    "intent":  getattr(plan, "intent", ""),
                    "actions": getattr(plan, "actions", []),
                    "context": getattr(plan, "context", {}) or {},
                })
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return

        # /api/script/run → executa script com timeout 30s (aprovado pelo usuário no modal)
        if path == "/api/script/run":
            try:
                import subprocess, sys, tempfile
                payload = json.loads(body.decode("utf-8") or "{}")
                language = payload.get("language", "python").lower()
                code = payload.get("code", "").strip()
                if not code:
                    self._send_json(400, {"error": "Código vazio."})
                    return
                if language == "python":
                    with tempfile.NamedTemporaryFile(
                        suffix=".py", delete=False, mode="w", encoding="utf-8"
                    ) as f:
                        f.write(code)
                        tmp_path = f.name
                    try:
                        result = subprocess.run(
                            [sys.executable, tmp_path],
                            capture_output=True, text=True, timeout=30,
                            encoding="utf-8", errors="replace"
                        )
                    finally:
                        import os as _os; _os.unlink(tmp_path)
                elif language == "powershell":
                    result = subprocess.run(
                        ["powershell", "-NoProfile", "-NonInteractive", "-Command", code],
                        capture_output=True, text=True, timeout=30,
                        encoding="utf-8", errors="replace"
                    )
                else:
                    self._send_json(400, {"error": f"Linguagem '{language}' não suportada."})
                    return
                self._send_json(200, {
                    "ok": result.returncode == 0,
                    "returncode": result.returncode,
                    "stdout": result.stdout.strip(),
                    "stderr": result.stderr.strip(),
                })
            except subprocess.TimeoutExpired:
                self._send_json(200, {"ok": False, "error": "Script excedeu o limite de 30 segundos e foi cancelado."})
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return

        # /api/vision/capture (POST — captura e analisa tela ou webcam)
        if path == "/api/vision/capture":
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
                action = payload.get("action", "analyze_screen")
                prompt = payload.get("prompt", "Analise em detalhes o conteúdo visual.").strip()
                api_key = ""
                provider = "gemini"
                if _orchestrator and hasattr(_orchestrator, "settings"):
                    st = _orchestrator.settings
                    provider = getattr(st, "llm_provider", "gemini")
                    api_key = getattr(st, "groq_api_key", "") if provider == "groq" else getattr(st, "gemini_api_key", "")

                from app.services.vision import VisionService
                vs = VisionService(api_key=api_key, provider=provider)
                img = vs.capture_camera() if action == "analyze_camera" else vs.capture_pil()
                if img is None:
                    self._send_json(400, {"error": "Não foi possível capturar a imagem da câmera ou tela."})
                    return

                res = vs.analyze(prompt=prompt, image=img, api_key=api_key, provider=provider)
                fn = res.get("capture_filename", "")
                self._send_json(200, {
                    "ok": True,
                    "reply": res.get("reply", ""),
                    "filename": fn,
                    "capture_url": f"/api/vision/file/{fn}" if fn else None,
                })
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return

        # A imagem chega aqui somente após uma ação explícita no espaço de câmeras.
        if path == "/api/vision/analyze-frame":
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
                image_data = str(payload.get("image", ""))
                prompt = str(payload.get("prompt", "Descreva a imagem."))[:4000].strip()
                camera_name = str(payload.get("camera_name", "Câmera"))[:120].strip() or "Câmera"
                if not image_data.startswith("data:image/") or "," not in image_data or len(image_data) > 12_000_000:
                    self._send_json(400, {"ok": False, "error": "Frame de câmera inválido."})
                    return

                import base64
                from io import BytesIO
                from PIL import Image
                encoded_image = image_data.split(",", 1)[1]
                image = Image.open(BytesIO(base64.b64decode(encoded_image))).convert("RGB")

                api_key = ""
                provider = "gemini"
                if _orchestrator and hasattr(_orchestrator, "settings"):
                    st = _orchestrator.settings
                    provider = getattr(st, "llm_provider", "gemini")
                    api_key = getattr(st, "groq_api_key", "") if provider == "groq" else getattr(st, "gemini_api_key", "")

                from app.services.vision import VisionService
                result = VisionService(api_key=api_key, provider=provider).analyze(
                    prompt=f"A imagem veio da câmera chamada '{camera_name}'. {prompt}",
                    image=image,
                    api_key=api_key,
                    provider=provider,
                )
                filename = result.get("capture_filename", "")
                self._send_json(200, {
                    "ok": True,
                    "reply": result.get("reply", "Análise concluída."),
                    "capture_url": f"/api/vision/file/{filename}" if filename else None,
                })
            except Exception as exc:
                self._send_json(400, {"ok": False, "error": f"Não foi possível analisar o frame: {exc}"})
            return

        # /api/cinema/play (POST)
        if path == "/api/cinema/library":
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
                from app.services.cinema_library import CinemaLibraryService
                result = CinemaLibraryService().upsert_source(payload)
                self._send_json(200 if result.get("ok") else 400, result)
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send_json(400, {"ok": False, "error": "JSON inválido."})
            return

        if path == "/api/cinema/discovery/probe":
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
                from app.services.cinema_discovery import CinemaDiscoveryService
                result = CinemaDiscoveryService().probe(payload.get("url", ""))
                self._send_json(200 if result.get("ok") else 400, result)
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send_json(400, {"ok": False, "error": "JSON inválido."})
            return

        if path == "/api/cinema/play":
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
                imdb_id = str(payload.get("imdb_id", "") or "").strip()
                title = str(payload.get("title", "") or "").strip()
                media_type = str(payload.get("type", "movie") or "movie").strip()
                poster = str(payload.get("poster", "") or "").strip()
                season = int(payload.get("season", 1) or 1)
                episode = int(payload.get("episode", 1) or 1)
                from app.services.cinema import CinemaService
                player_data = CinemaService.get_player_data(
                    imdb_id=imdb_id,
                    media_type=media_type,
                    title=title,
                    poster=poster,
                    season=season,
                    episode=episode,
                )
                self._send_json(200, player_data)
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        # /api/browser/run (POST — aciona automação autônoma de navegador)
        if path == "/api/browser/run":
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
                goal = payload.get("goal", "").strip()
                start_url = payload.get("start_url", "").strip()
                if not goal:
                    self._send_json(400, {"error": "Objetivo (goal) não pode ser vazio."})
                    return
                
                if _orchestrator is None or not hasattr(_orchestrator, "registry"):
                    self._send_json(503, {"error": "Orquestrador não disponível."})
                    return

                tool = _orchestrator.registry.get_tool("browser_agent")
                if not tool:
                    self._send_json(503, {"error": "Ferramenta browser_agent não cadastrada."})
                    return

                ctx = {
                    "vision": getattr(_orchestrator, "vision_service", None),
                    "browser": getattr(_orchestrator, "browser_agent", None),
                    "settings": getattr(_orchestrator, "settings", None)
                }
                res = tool.execute({"goal": goal, "start_url": start_url}, context=ctx)
                self._send_json(200, {
                    "ok": res.ok,
                    "message": res.message,
                    "data": res.data
                })
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return

        # /api/wake-word (POST — toggle)
        if path == "/api/wake-word":
            global _wake_word_enabled
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
                _wake_word_enabled = bool(payload.get("enabled", not _wake_word_enabled))
                # Propagate to running detector
                if _wake_word_detector:
                    _wake_word_detector.set_enabled(_wake_word_enabled)
                self._send_json(200, {"ok": True, "enabled": _wake_word_enabled})
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return

        # Study categories and session metadata
        if path == "/api/study/categories":
            try:
                import uuid
                from app.storage.session_store import add_category
                payload = json.loads(body.decode("utf-8") or "{}")
                name = str(payload.get("name", "Nova categoria") or "Nova categoria").strip()[:60]
                color = str(payload.get("color", "#00daf8") or "#00daf8")[:20]
                category = add_category({"id": str(uuid.uuid4()), "name": name, "color": color})
                self._send_json(200, {"ok": True, "category": category})
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return

        if path.startswith("/api/study/categories/"):
            try:
                import uuid
                from app.storage.session_store import update_category
                category_id = path.rsplit("/", 1)[-1]
                payload = json.loads(body.decode("utf-8") or "{}")
                category = update_category(category_id, payload)
                self._send_json(200 if category else 404, {"ok": bool(category), "category": category})
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return

        # Update persisted title/category without replacing history or whiteboard.
        if path.startswith("/api/sessions/") and len([p for p in path.split("/") if p]) == 3:
            try:
                from app.storage.session_store import update_session
                session_id = [p for p in path.split("/") if p][2]
                payload = json.loads(body.decode("utf-8") or "{}")
                session = update_session(session_id, payload)
                self._send_json(200 if session else 404, {"ok": bool(session), "session": session})
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return

        # /api/sessions (POST — create session)
        if path == "/api/sessions":
            try:
                import uuid
                from app.storage.session_store import add_session
                payload = json.loads(body.decode("utf-8") or "{}")
                session_id = str(uuid.uuid4())
                session_data = {
                    "id": session_id,
                    "title": payload.get("title", "Nova sessão"),
                    "type": payload.get("type", "chat"),
                    "history": [],
                    "whiteboard": [],
                }
                add_session(session_data)
                self._send_json(200, {"ok": True, "id": session_id, "session": session_data})
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return

        # /api/sessions/<id>/history  (POST — save history)
        if path.endswith("/history"):
            try:
                from app.storage.session_store import save_session_history
                parts_p = [p for p in path.split("/") if p]
                session_id = parts_p[2] if len(parts_p) >= 4 else None
                if session_id:
                    payload = json.loads(body.decode("utf-8") or "{}")
                    save_session_history(session_id, payload.get("history", []))
                self._send_json(200, {"ok": True})
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return

        # /api/sessions/<id>/whiteboard (POST — save whiteboard)
        if path.endswith("/whiteboard"):
            try:
                from app.storage.session_store import save_whiteboard
                parts_p = [p for p in path.split("/") if p]
                session_id = parts_p[2] if len(parts_p) >= 4 else None
                if session_id:
                    payload = json.loads(body.decode("utf-8") or "{}")
                    save_whiteboard(session_id, payload.get("whiteboard", payload.get("elements", [])))
                self._send_json(200, {"ok": True})
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return

        for handler_fn in (
            handle_dashboard_post,
            handle_tutor_post,
            handle_enem_post,
            handle_settings_post,
            handle_voice_post,
        ):
            result = handler_fn(path, body, self)
            if result:
                status_code, data = result
                if isinstance(data, bytes):
                    self.send_response(status_code)
                    self.send_header("Content-Type", "audio/mpeg")
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(data)
                else:
                    self._send_json(status_code, data)
                return

        self._send_json(404, {"error": "Endpoint não encontrado."})


# ──────────────────────────────────────── WebSocket handler (asyncio) ────────

async def _ws_chat_handler(websocket) -> None:
    """Handle /ws/chat — streams Jarvis responses as JSON messages."""
    _ws_clients.add(websocket)
    try:
        async for raw in websocket:
            try:
                data = json.loads(raw)
            except Exception:
                await websocket.send(json.dumps({"type": "error", "message": "JSON inválido."}))
                continue

            message = str(data.get("message", "")).strip()
            if not message:
                continue

            if _orchestrator is None:
                await websocket.send(json.dumps({"type": "error", "message": "Orquestrador não disponível."}))
                continue

            # Signal thinking
            await websocket.send(json.dumps({"type": "status", "status": "thinking"}))

            try:
                session_id = data.get("session_id")
                mode = data.get("mode", "general")
                loop = asyncio.get_running_loop()

                def on_chunk(chunk_text: str) -> None:
                    if chunk_text:
                        try:
                            asyncio.run_coroutine_threadsafe(
                                websocket.send(json.dumps({"type": "chunk", "text": chunk_text})),
                                loop
                            )
                        except Exception:
                            pass

                def on_reasoning(reason_text: str) -> None:
                    if reason_text:
                        try:
                            asyncio.run_coroutine_threadsafe(
                                websocket.send(json.dumps({"type": "reasoning", "text": reason_text})),
                                loop
                            )
                        except Exception:
                            pass

                def on_search(payload: dict) -> None:
                    try:
                        asyncio.run_coroutine_threadsafe(
                            websocket.send(json.dumps({"type": "search", "payload": payload}, ensure_ascii=False)),
                            loop,
                        )
                    except Exception:
                        pass

                # Run the blocking orchestrator call in a thread
                plan = await loop.run_in_executor(
                    None, lambda: _orchestrator.handle_request(message, session_id=session_id, mode=mode, on_chunk=on_chunk, on_reasoning=on_reasoning, on_search=on_search)
                )
                prefix = _calendar_conversation_prefix()
                if prefix:
                    plan.summary = prefix + getattr(plan, "summary", str(plan))
                await websocket.send(json.dumps({
                    "type":    "complete",
                    "summary": getattr(plan, "summary", str(plan)),
                    "intent":  getattr(plan, "intent", ""),
                    "actions": getattr(plan, "actions", []),
                    "context": getattr(plan, "context", {}) or {},
                }))

                # Fase 7: salvar conversa na memória semântica em background
                if (
                    _orchestrator
                    and hasattr(_orchestrator, "semantic_memory")
                    and _orchestrator.semantic_memory
                    and getattr(plan, "intent", "") != "error"
                    and not is_technical_error_memory(getattr(plan, "summary", ""))
                ):
                    try:
                        convo_text = f"Usuário: {message}\nJarvis: {getattr(plan, 'summary', '')}"
                        import threading as _t
                        _t.Thread(
                            target=_orchestrator.semantic_memory.add_memory,
                            args=("conversations", convo_text),
                            kwargs={"metadata": {"session_id": session_id or ""}},
                            daemon=True
                        ).start()
                    except Exception:
                        pass

            except Exception as exc:
                await websocket.send(json.dumps({"type": "error", "message": str(exc)}))
    except Exception:
        pass
    finally:
        _ws_clients.discard(websocket)


async def _broadcast_wake_word() -> None:
    """Envia evento de wake word para todos os clientes WebSocket conectados."""
    msg = json.dumps({"type": "wake_word", "phrase": "ei jarvis"})
    dead = set()
    for ws in list(_ws_clients):
        try:
            await ws.send(msg)
        except Exception:
            dead.add(ws)
    _ws_clients.difference_update(dead)



async def _run_ws_server(host: str, port: int) -> None:
    try:
        import websockets
        async with websockets.serve(_ws_chat_handler, host, port):
            await asyncio.Future()  # run forever
    except Exception as exc:
        print(f"[WS] Falha ao iniciar servidor WebSocket: {exc}")


# ──────────────────────────────────────────────────────── PanelServer ────────

class PanelServer:
    def __init__(self, settings: Any) -> None:
        self.settings = settings
        self.http_server: HTTPServer | None = None
        self._http_thread: threading.Thread | None = None
        self._ws_thread: threading.Thread | None = None

    def set_orchestrator(self, orchestrator: Any) -> None:
        global _orchestrator
        _orchestrator = orchestrator

    def set_voice_pipeline(self, pipeline: Any) -> None:
        PanelHandler.voice_pipeline = pipeline

    def _run_http(self) -> None:
        PanelHandler.settings = self.settings
        address = (self.settings.host, self.settings.port)
        self.http_server = HTTPServer(address, PanelHandler)
        self.http_server.serve_forever()

    def _run_ws(self) -> None:
        """Run the asyncio WebSocket server in a dedicated thread on port+1."""
        global _ws_loop
        ws_port = self.settings.port + 1
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _ws_loop = loop
        try:
            loop.run_until_complete(_run_ws_server(self.settings.host, ws_port))
        finally:
            loop.close()
            _ws_loop = None

    def start(self) -> None:
        if self._http_thread and self._http_thread.is_alive():
            return

        self._http_thread = threading.Thread(
            target=self._run_http, daemon=True, name="PanelHTTP"
        )
        self._http_thread.start()

        self._ws_thread = threading.Thread(
            target=self._run_ws, daemon=True, name="PanelWS"
        )
        self._ws_thread.start()

    def start_wake_word(self) -> None:
        """Inicia o detector de wake word (Vosk PT-BR, sem API key)."""
        global _wake_word_detector
        try:
            from app.services.voice.wake_word import WakeWordDetector
            def on_wake():
                loop = _ws_loop
                if loop and loop.is_running():
                    asyncio.run_coroutine_threadsafe(_broadcast_wake_word(), loop)
            _wake_word_detector = WakeWordDetector(on_wake=on_wake)
            _wake_word_detector.start()
            print("[Jarvis] Wake word detector iniciado. Diga 'Ei Jarvis' para ativar.")
        except Exception as e:
            print(f"[Jarvis] Wake word desativado: {e}")

    def stop(self) -> None:
        if self.http_server:
            self.http_server.shutdown()
