from __future__ import annotations

import asyncio
from itertools import chain
import json
import mimetypes
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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
from app.ui.panel.api.voice import handle_voice_post, handle_voice_stream, handle_voice_realtime_stream
from app.ui.panel.api.planning import handle_planning_get, handle_planning_post
from app.ui.panel.api.actions import handle_actions_get, handle_actions_post
from app.ui.panel.api.runs import handle_runs_get, handle_runs_post
from app.ui.panel.api.controls import handle_controls_post
from app.ui.panel.api.mission_control import handle_mission_control_get
from app.ui.panel.api.goals import handle_goals_get, handle_goals_post
from app.storage.vector.semantic_memory import is_technical_error_memory
from app.core.control_plane import ControlPlanePolicy, RequestPrincipal
from app.core.execution_receipts import receipts

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_STATIC_DIR   = Path(__file__).parent / "static"
_REACT_DIST_DIR = Path(__file__).resolve().parents[3] / "frontend" / "dist"
_EVOLUTE_DIST_DIR = Path(__file__).resolve().parents[3] / "evolute" / "dist"

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
    voice_pipeline: Any = None
    _pipeline_lock = threading.Lock()
    protocol_version = "HTTP/1.1"
    timeout = 30

    def _policy(self) -> ControlPlanePolicy:
        return ControlPlanePolicy(self.settings)

    def _authorize_api(self, path: str, method: str) -> RequestPrincipal | None:
        try:
            ok, status, error, principal = self._policy().authorize(self, path, method)
        except ValueError as exc:
            self._send_json(503, {"ok": False, "error": str(exc)})
            return None
        if not ok:
            self._send_json(status, {"ok": False, "error": error})
            return None
        return principal

    def _send_cors(self) -> None:
        origin = self.headers.get("Origin", "").rstrip("/")
        if not origin:
            return
        try:
            if origin in self._policy().allowed_origins():
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
        except ValueError:
            return

    def log_error(self, fmt: str, *args: Any) -> None:
        # Suprimir logs de erro causados por timeouts normais de sockets HTTP/1.1 ociosos (keep-alive)
        try:
            msg = (fmt % args) if args else fmt
            if "timed out" in msg.lower():
                return
        except Exception:
            pass
        super().log_error(fmt, *args)

    def handle(self) -> None:
        # Silencia erros de conexão abortada (ex: barge-in cancela o fetch no navegador)
        try:
            super().handle()
        except (ConnectionAbortedError, BrokenPipeError, ConnectionResetError, OSError):
            pass  # cliente desconectou antes do servidor terminar — comportamento normal

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A002
        try:
            # Suprimir 200, 304, 204, 426 (WS upgrade) e 404
            if len(args) >= 2 and str(args[1]) in ("200", "304", "204", "426", "404"):
                return
            msg = (fmt % args) if args else fmt
            if "timed out" in msg.lower():
                return
            super().log_message(fmt, *args)
        except Exception:
            pass


    # ── helpers ─────────────────────────────────────────────────────────────

    def _send_json(self, status: int, data: dict) -> None:
        try:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._send_cors()
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass

    def _send_html(self, html: str) -> None:
        try:
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            # Disable caching for HTML to prevent stale index.html references
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass

    def _send_file(self, path: Path) -> None:
        try:
            mime, _ = mimetypes.guess_type(str(path))
            mime = mime or "application/octet-stream"
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            # Disable caching for all static files to prevent stale JavaScript
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass

    def _send_404(self) -> None:
        try:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass

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
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        # ── HTML pages ───────────────────────────────────────────────────────
        if path in ("/", "/index.html", "/app", "/app/"):
            f = _REACT_DIST_DIR / "index.html"
            self._send_html(
                f.read_text(encoding="utf-8")
                if f.exists()
                else "<h1>Interface React nao compilada. Execute npm run build em frontend.</h1>"
            )
            return

        # Arquivos de raiz da PWA precisam ser acessíveis para que o navegador
        # consiga atualizar o Service Worker e não retenha uma interface antiga.
        if path in ("/sw.js", "/manifest.webmanifest", "/icon.svg"):
            asset = _REACT_DIST_DIR / path.lstrip("/")
            if asset.is_file():
                self._send_file(asset)
            else:
                self._send_404()
            return

        if path == "/evolute":
            self.send_response(301)
            self.send_header("Location", "/evolute/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if path == "/evolute/":
            f = _EVOLUTE_DIST_DIR / "index.html"
            if f.exists():
                self._send_html(f.read_text(encoding="utf-8"))
            else:
                self._send_html("<h1>Interface do Evolute não encontrada em evolute/dist.</h1>")
            return

        if path in ("/legacy", "/legacy/"):
            self.send_response(301)
            self.send_header("Location", "/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if path.startswith("/evolute/assets/"):
            try:
                rel = path.removeprefix("/evolute/assets/")
                asset = (_EVOLUTE_DIST_DIR / "assets" / rel).resolve()
                asset.relative_to((_EVOLUTE_DIST_DIR / "assets").resolve())
                if asset.is_file():
                    self._send_file(asset)
                    return
            except Exception:
                pass
            self._send_404()
            return

        if path.startswith("/assets/"):
            try:
                asset = (_REACT_DIST_DIR / path.removeprefix("/")).resolve()
                asset.relative_to(_REACT_DIST_DIR.resolve())
                if asset.is_file():
                    self._send_file(asset)
                    return
            except ValueError:
                pass

            # Fallback para assets do Evolute
            try:
                asset = (_EVOLUTE_DIST_DIR / path.removeprefix("/")).resolve()
                asset.relative_to(_EVOLUTE_DIST_DIR.resolve())
                if asset.is_file():
                    self._send_file(asset)
                    return
            except Exception:
                pass

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
            try:
                rel = path[len("/static/"):]
                static_path = (_STATIC_DIR / rel).resolve()
                static_path.relative_to(_STATIC_DIR.resolve())
            except Exception:
                self._send_404()
                return
            if static_path.is_file():
                self._send_file(static_path)
            else:
                self._send_404()
            return

        # ── API GET ──────────────────────────────────────────────────────────
        if path.startswith("/api/"):
            if self._authorize_api(path, "GET") is None:
                return
            parts = [p for p in path.split("/") if p]

            if path in ("/api/sync", "/api/evolute/sync"):
                from app.ui.panel.api.evolute import handle_evolute_sync_get
                status, data = handle_evolute_sync_get()
                self._send_json(status, data)
                return

            if path == "/api/evolute/status":
                from app.ui.panel.api.evolute import handle_evolute_status_get
                status, data = handle_evolute_status_get()
                self._send_json(status, data)
                return

            if path == "/api/evolute/summary":
                try:
                    from app.services.lifeos import LifeOSService
                    summary_data = LifeOSService.get_daily_summary()
                    self._send_json(200, summary_data)
                except Exception as exc:
                    self._send_json(500, {"ok": False, "error": str(exc)})
                return

            if path == "/api/system/backup":
                import zipfile
                import io
                import datetime
                try:
                    data_dir = Path(__file__).resolve().parents[3] / "data"
                    snapshots_dir = data_dir / "snapshots"
                    snapshots_dir.mkdir(parents=True, exist_ok=True)
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                        for f in data_dir.glob("*.json"):
                            zf.write(f, arcname=f"data/{f.name}")
                        for f in data_dir.glob("*.jsonl"):
                            zf.write(f, arcname=f"data/{f.name}")
                        evolute_db = Path(os.path.expanduser("~")) / "Documents" / "Evolute" / "data" / "lifeos_db.json"
                        if evolute_db.exists():
                            zf.write(evolute_db, arcname="evolute/lifeos_db.json")
                    zip_data = zip_buffer.getvalue()
                    snapshot_file = snapshots_dir / f"jarvis_backup_{timestamp}.zip"
                    snapshot_file.write_bytes(zip_data)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/zip")
                    self.send_header("Content-Disposition", f'attachment; filename="jarvis_backup_{timestamp}.zip"')
                    self.send_header("Content-Length", str(len(zip_data)))
                    self.end_headers()
                    self.wfile.write(zip_data)
                except Exception as exc:
                    self._send_json(500, {"ok": False, "error": str(exc)})
                return


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

            # /api/identity -> perfis locais e estado da verificação
            if len(parts) == 2 and parts[1] == "identity":
                try:
                    from app.services.identity import IdentityService
                    self._send_json(200, IdentityService.status())
                except Exception as exc:
                    self._send_json(500, {"ok": False, "error": str(exc)})
                return

            if len(parts) == 2 and parts[1] == "profile-memory":
                try:
                    import urllib.parse
                    from app.services.identity import IdentityService
                    from app.services.profile_memory import ProfileMemoryStore
                    query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                    profile_id = (query.get("profile_id") or [""])[0]
                    if not IdentityService.profile_exists(profile_id):
                        self._send_json(400, {"ok": False, "error": "Perfil não encontrado."})
                        return
                    store = ProfileMemoryStore()
                    memories = store.list(profile_id, query=(query.get("q") or [""])[0], limit=int((query.get("limit") or [50])[0]))
                    self._send_json(200, {"ok": True, "profile_id": profile_id, "count": store.count(profile_id), "memories": memories})
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

            # /api/tool-forge -> lista ferramentas forjadas
            if len(parts) >= 2 and parts[1] == "tool-forge":
                try:
                    from app.services.tool_forge import tool_forge
                    self._send_json(200, {"tools": tool_forge.list_custom_tools()})
                except Exception as exc:
                    self._send_json(500, {"error": str(exc)})
                return


            # /api/vault (Memory Vault Markdown)
            if len(parts) >= 2 and parts[1] == "vault":
                try:
                    import urllib.parse
                    from app.services.memory_vault import memory_vault
                    sub = parts[2] if len(parts) >= 3 else ""
                    if sub == "daily":
                        self._send_json(200, {"ok": True, "content": memory_vault.get_or_create_daily_note(), "path": str(memory_vault.get_today_note_path())})
                    elif sub == "profile":
                        self._send_json(200, {"ok": True, "content": memory_vault.get_user_profile()})
                    elif sub == "search":
                        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                        q = (query.get("q") or [""])[0]
                        self._send_json(200, {"ok": True, "results": memory_vault.search_vault(q)})
                    else:
                        self._send_json(200, {"ok": True, "daily": memory_vault.get_or_create_daily_note(), "profile": memory_vault.get_user_profile()})
                except Exception as exc:
                    self._send_json(500, {"ok": False, "error": str(exc)})
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
                handle_planning_get,
                handle_actions_get,
                handle_runs_get,
                handle_mission_control_get,
                handle_goals_get,
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
        path = self.path.split("?")[0]
        if not path.startswith("/api/"):
            self._send_json(404, {"ok": False, "error": "Endpoint não encontrado."})
            return
        origin = self.headers.get("Origin", "").rstrip("/")
        if not self._policy().is_trusted_host(self.headers.get("Host", "")):
            self._send_json(403, {"ok": False, "error": "Host não confiável."})
            return
        if origin and origin not in self._policy().allowed_origins():
            self._send_json(403, {"ok": False, "error": "Origem não confiável."})
            return
        self.send_response(204)
        self._send_cors()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_DELETE(self) -> None:
        import urllib.parse
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        if path.startswith("/api/") and self._authorize_api(path, "DELETE") is None:
            return
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
        if path.startswith("/api/"):
            from app.ui.panel.api.routes.system_routes import handle_system_routes
            if handle_system_routes(path, b"", self._send_json):
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
        principal = self._authorize_api(path, self.command)
        if principal is None:
            return

        if path in ("/api/sync", "/api/evolute/sync"):
            try:
                payload = json.loads(body.decode("utf-8")) if body else {}
                from app.ui.panel.api.evolute import handle_evolute_sync_post
                status, data = handle_evolute_sync_post(payload)
                self._send_json(status, data)
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return

        if path in ("/api/ai/chat", "/api/evolute/ai/chat"):
            try:
                payload = json.loads(body.decode("utf-8")) if body else {}
                from app.ui.panel.api.evolute import handle_evolute_ai_chat
                status, data = handle_evolute_ai_chat(payload, _orchestrator)
                self._send_json(status, data)
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return

        if path == "/api/evolute/water/add":
            try:
                payload = json.loads(body.decode("utf-8")) if body else {}
                amount_ml = int(payload.get("amount_ml") or 250)
                from app.services.lifeos import LifeOSService
                res = LifeOSService.add_water(amount_ml)
                self._send_json(200, res)
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        if path == "/api/evolute/habit/toggle":
            try:
                payload = json.loads(body.decode("utf-8")) if body else {}
                habit_ref = str(payload.get("habit_name_or_id") or "")
                completed = payload.get("completed", True)
                from app.services.lifeos import LifeOSService
                res = LifeOSService.toggle_habit(habit_ref, completed=completed)
                self._send_json(200, res)
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        if path == "/api/evolute/habit/priority":
            try:
                payload = json.loads(body.decode("utf-8")) if body else {}
                habit_ref = str(payload.get("habit_name_or_id") or "")
                from app.services.lifeos import LifeOSService
                res = LifeOSService.toggle_habit_priority(habit_ref)
                self._send_json(200, res)
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        if path == "/api/voice/tts/stream":
            stream = handle_voice_stream(path, body, self)
            if stream is None:
                self._send_json(503, {"ok": False, "error": "Streaming Fish indisponível."})
                return
            try:
                first = next(stream)
            except StopIteration:
                self._send_json(502, {"ok": False, "error": "Fish não retornou áudio."})
                return
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Transfer-Encoding", "chunked")
            self.send_header("Cache-Control", "no-store")
            self._send_cors()
            self.end_headers()
            try:
                for chunk in chain((first,), stream):
                    if chunk:
                        self.wfile.write(f"{len(chunk):X}\r\n".encode("ascii"))
                        self.wfile.write(chunk)
                        self.wfile.write(b"\r\n")
                        self.wfile.flush()
            except Exception:
                pass
            self.wfile.write(b"0\r\n\r\n")
            return

        if path == "/api/voice/realtime/stream":
            result = handle_voice_realtime_stream(path, body, self)
            if result is None:
                self._send_json(400, {"ok": False, "error": "Requisição inválida."})
                return
            status, data = result
            self._send_json(status, data)
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

        if path == "/api/qr/read":
            try:
                from app.services.qr_reader import QRReaderService
                payload = json.loads(body.decode("utf-8") or "{}")
                source = str(payload.get("source", "screen")).lower()
                svc = QRReaderService()
                if source == "screen":
                    mon = int(payload.get("monitor", 0))
                    res = svc.read_from_screen(monitor=mon)
                elif source == "camera":
                    cam_idx = int(payload.get("camera_index", 0))
                    timeout = float(payload.get("timeout", 5.0))
                    res = svc.read_from_camera(camera_index=cam_idx, timeout_s=timeout)
                elif source == "image_b64" or "image" in payload:
                    img_data = payload.get("image") or payload.get("image_b64") or ""
                    res = svc.read_from_base64(img_data, source_label="web_camera")
                else:
                    self._send_json(400, {"ok": False, "error": f"Fonte inválida: {source}"})
                    return
                self._send_json(200 if res.ok else 400, res.to_dict())
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        # Delegate to modular domain sub-routers
        from app.ui.panel.api.routes.code_routes import handle_code_routes
        from app.ui.panel.api.routes.system_routes import handle_system_routes

        if handle_code_routes(path, body, self._send_json):
            return

        if handle_system_routes(path, body, self._send_json):
            return

        # Contrato da ponte: o celular e o desktop usam as mesmas operações,
        # independentemente do adaptador físico (Tuya, BLE, Matter etc.).
        if path == "/api/bridge":
            try:
                from app.services.device_bridge import DeviceBridgeService
                payload = json.loads(body.decode("utf-8") or "{}")
                action = str(payload.get("action") or "").strip()
                service = DeviceBridgeService()
                if action == "pairing_code":
                    if principal.mode != "loopback":
                        self._send_json(403, {"ok": False, "error": "O código de pareamento só é exibido no controle local."})
                        return
                    result = {"ok": True, "pairing_code": service.get_pairing_code()}
                elif action in {"pair", "register"}:
                    result = service.register_device(
                        payload.get("device_id"), payload.get("name"), payload.get("kind", "client"),
                        payload.get("platform", "unknown"), payload.get("transport", "lan"), payload.get("pairing_code"),
                    )
                elif action == "heartbeat":
                    result = service.heartbeat(payload.get("device_id"), payload.get("device_token"))
                elif action == "command":
                    result = service.command(payload.get("target_id"), payload.get("command"), payload.get("payload"), payload.get("source", "desktop"), payload.get("device_token"))
                elif action == "remove":
                    # Revogar reduz privilégio. Sem a credencial do próprio
                    # dispositivo, só o controle local remove, pela mesma regra
                    # que protege o código de pareamento.
                    result = service.remove_device(payload.get("device_id"), payload.get("device_token"), local_owner=principal.mode == "loopback")
                else:
                    result = {"ok": False, "error": "Ação de ponte inválida."}
                self._send_json(200 if result.get("ok") else 400, result)
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send_json(400, {"ok": False, "error": "JSON inválido."})
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        # Cadastro/verificação biométrica local. O payload é JSON com data URL;
        # as amostras são reduzidas a vetores no backend e não ficam no navegador.
        if path == "/api/identity":
            try:
                from app.services.identity import IdentityService
                payload = json.loads(body.decode("utf-8") or "{}")
                action = str(payload.get("action") or "").strip()
                if action == "enroll_admin":
                    result = IdentityService.enroll_admin(payload.get("name", ""), payload.get("password", ""))
                elif action == "enroll_profile":
                    result = IdentityService.enroll_profile(payload.get("name", ""), payload.get("role", "user"), payload.get("admin_password", ""))
                elif action == "add_sample":
                    result = IdentityService.add_sample(payload.get("profile_id", ""), payload.get("password", ""), payload.get("kind", ""), payload.get("sample", ""), payload.get("content_type", ""))
                elif action == "verify":
                    result = IdentityService.verify(payload.get("kind", ""), payload.get("sample", ""), payload.get("content_type", ""))
                else:
                    result = {"ok": False, "error": "Ação de identidade inválida."}
                self._send_json(200 if result.get("ok") else 400, result)
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send_json(400, {"ok": False, "error": "JSON inválido."})
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        if path == "/api/profile-memory":
            try:
                from app.services.identity import IdentityService
                from app.services.profile_memory import ProfileMemoryStore
                payload = json.loads(body.decode("utf-8") or "{}")
                profile_id = str(payload.get("profile_id") or "")
                action = str(payload.get("action") or "").strip()
                if not IdentityService.profile_exists(profile_id):
                    self._send_json(400, {"ok": False, "error": "Perfil não encontrado."})
                    return
                if action in {"add", "delete", "clear"} and not IdentityService.authenticate(profile_id, payload.get("password", "")):
                    self._send_json(403, {"ok": False, "error": "Senha do perfil inválida."})
                    return
                store = ProfileMemoryStore()
                if action == "add":
                    memory = store.add(profile_id, payload.get("text", ""), kind=payload.get("kind", "note"), importance=payload.get("importance", 0.5), source="panel")
                    result = {"ok": bool(memory), "memory": memory}
                elif action == "delete":
                    result = {"ok": store.delete(profile_id, str(payload.get("memory_id") or ""))}
                elif action == "clear":
                    result = {"ok": True, "removed": store.clear(profile_id)}
                else:
                    result = {"ok": False, "error": "Ação de memória inválida."}
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

        # /api/vault POST → Memory Vault (daily log, profile fact, save note)
        if path.startswith("/api/vault"):
            try:
                from app.services.memory_vault import memory_vault
                payload = json.loads(body.decode("utf-8") or "{}")
                sub = path.removeprefix("/api/vault").lstrip("/")
                if sub == "daily/log":
                    entry = payload.get("entry", "").strip()
                    category = payload.get("category", "Atividade")
                    ok = memory_vault.append_daily_log(entry, category)
                    self._send_json(200, {"ok": ok})
                elif sub == "profile/fact":
                    fact = payload.get("fact", "").strip()
                    ok = memory_vault.update_user_profile_fact(fact)
                    self._send_json(200, {"ok": ok})
                elif sub == "notes":
                    title = payload.get("title", "nota")
                    content = payload.get("content", "")
                    folder = payload.get("folder", "04-Projects")
                    path_saved = memory_vault.save_note(title, content, folder)
                    self._send_json(200, {"ok": True, "path": path_saved})
                else:
                    self._send_json(400, {"ok": False, "error": f"Sub-rota '{sub}' não reconhecida."})
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        # /api/swarm → Swarm Manager routing
        if path == "/api/swarm":
            try:
                from app.agent.swarm import agent_swarm
                payload = json.loads(body.decode("utf-8") or "{}")
                task = payload.get("task", "")
                t_type = payload.get("type", "auto")
                res = agent_swarm.route_and_execute(task, task_type=t_type)
                self._send_json(200, res)
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        # /api/react → ReAct Loop execution
        if path == "/api/react":
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
                if not isinstance(payload, dict):
                    self._send_json(400, {"ok": False, "error": "Envie um objeto JSON."})
                    return
                goal = payload.get("goal", "")
                max_steps = payload.get("max_steps", 8)
                session_id = payload.get("session_id")
                if not isinstance(goal, str) or not goal.strip() or type(max_steps) is not int or not 1 <= max_steps <= 20 or (session_id is not None and (not isinstance(session_id, str) or len(session_id) > 200)):
                    self._send_json(400, {"ok": False, "error": "Informe um objetivo, um limite inteiro entre 1 e 20 e uma sessão válida."})
                    return
                if _orchestrator is None:
                    self._send_json(503, {"ok": False, "error": "O agente não está disponível."})
                    return
                plan = _orchestrator.handle_request(goal, mode="react", session_id=session_id, react_max_steps=max_steps)
                self._send_json(200, {
                    "ok": plan.context.get("success", False),
                    "goal": goal,
                    "final_output": plan.summary,
                    "steps_count": plan.context.get("steps_count", 0),
                    "total_elapsed_sec": plan.context.get("elapsed_sec", 0),
                    "run_id": plan.context.get("run_id"),
                    "pending_action_id": plan.context.get("pending_action_id"),
                    "cancelled": plan.intent == "cancelled",
                })
            except (ValueError, TypeError):
                self._send_json(400, {"ok": False, "error": "Pedido ReAct inválido."})
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        # /api/ambient/alerts → Ambient Monitor status & alerts
        if path == "/api/ambient/alerts":
            try:
                from app.services.ambient_monitor import ambient_monitor
                # Verifica a área de transferência ao consultar
                ambient_monitor.inspect_clipboard_for_errors()
                alerts = ambient_monitor.get_alerts()
                self._send_json(200, {"ok": True, "count": len(alerts), "alerts": alerts})
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        # /api/reflexion → Evaluator-Optimizer Engine
        if path == "/api/reflexion":
            try:
                from app.services.reflexion import reflexion_engine
                payload = json.loads(body.decode("utf-8") or "{}")
                prompt = payload.get("prompt", "")
                candidate = payload.get("response", "")
                res = reflexion_engine.process_with_reflexion(prompt, candidate)
                self._send_json(200, res)
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        # /api/skills/distill → Skill Distiller
        if path == "/api/skills/distill":
            try:
                from app.services.skill_distiller import skill_distiller
                payload = json.loads(body.decode("utf-8") or "{}")
                skill_name = payload.get("skill_name", "")
                description = payload.get("description", "")
                steps = payload.get("steps", [])
                ok, msg = skill_distiller.distill_trajectory_to_skill(skill_name, description, steps)
                self._send_json(200 if ok else 400, {"ok": ok, "message": msg})
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        # /api/hacker → Hacker AI Remote Terminal & Permissões
        if path.startswith("/api/hacker"):
            try:
                from app.services.hacker_terminal import hacker_terminal
                sub = path.removeprefix("/api/hacker").lstrip("/")
                if sub == "policy" and self.command == "GET":
                    self._send_json(200, {"ok": True, "policy_mode": hacker_terminal.policy_mode, "whitelist": list(hacker_terminal.allowed_whitelist)})
                    return

                payload = json.loads(body.decode("utf-8") or "{}") if body else {}
                if sub == "policy":
                    mode = payload.get("mode", "")
                    ok = hacker_terminal.set_policy_mode(mode, actor=principal.id)
                    self._send_json(200 if ok else 400, {"ok": ok, "policy_mode": hacker_terminal.policy_mode})
                elif sub == "execute":
                    cmd = payload.get("command", "")
                    receipt = str(payload.get("receipt", ""))
                    if receipt:
                        if not receipts.consume(receipt, principal.id, "hacker:command", cmd):
                            self._send_json(403, {"ok": False, "error": "Recibo de autorização ausente, expirado ou inválido."})
                            return
                        analysis = hacker_terminal.analyze_command(cmd)
                        res = hacker_terminal._run_command_subprocess(cmd.strip(), analysis.get("risk_level", "high"), approved=True)
                    else:
                        res = hacker_terminal.prepare_for_approval(cmd)
                    self._send_json(200 if res.get("ok") else 400, res)
                elif sub == "approve":
                    cmd_id = payload.get("cmd_id", "")
                    approved = hacker_terminal.approve_pending(cmd_id)
                    res = ({"ok": True, "receipt": receipts.issue(principal.id, "hacker:command", approved["command"])}
                           if approved.get("ok") else approved)
                    self._send_json(200 if res.get("ok") else 400, res)
                elif sub == "reject":
                    cmd_id = payload.get("cmd_id", "")
                    res = hacker_terminal.reject_pending(cmd_id)
                    self._send_json(200 if res.get("ok") else 400, res)
                elif sub == "history":
                    logs = hacker_terminal.get_audit_logs()
                    self._send_json(200, {"ok": True, "count": len(logs), "logs": logs})
                else:
                    self._send_json(400, {"ok": False, "error": f"Sub-rota hacker '{sub}' inválida."})
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        # /api/call → Voice Call Session RTC Engine (TEN-Framework Architecture)
        if path.startswith("/api/call"):
            try:
                from app.services.voice_call import voice_call_engine
                sub = path.removeprefix("/api/call").lstrip("/")
                payload = json.loads(body.decode("utf-8") or "{}") if body else {}
                if sub == "start":
                    session = voice_call_engine.start_call(payload.get("session_id", ""))
                    self._send_json(200, {"ok": True, "session_id": session.session_id, "state": session.state.value})
                elif sub == "interrupt":
                    res = voice_call_engine.interrupt_call(payload.get("session_id", ""))
                    self._send_json(200 if res.get("ok") else 400, res)
                elif sub == "mute":
                    res = voice_call_engine.toggle_mute(payload.get("session_id", ""))
                    self._send_json(200 if res.get("ok") else 400, res)
                elif sub == "end":
                    res = voice_call_engine.end_call(payload.get("session_id", ""))
                    self._send_json(200 if res.get("ok") else 400, res)
                elif sub == "status":
                    res = voice_call_engine.get_session_status(payload.get("session_id", ""))
                    self._send_json(200 if res.get("ok") else 400, res)
                else:
                    self._send_json(400, {"ok": False, "error": f"Sub-rota call '{sub}' inválida."})
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        # /api/deobfuscate → JS/AST Deobfuscator (reverse-skill)
        if path == "/api/deobfuscate":
            try:
                from app.services.js_deobfuscator import js_deobfuscator
                payload = json.loads(body.decode("utf-8") or "{}")
                res = js_deobfuscator.deobfuscate(payload.get("code", ""))
                self._send_json(200 if res.get("ok") else 400, res)
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        # /api/llm-security → LLM Security Auditor (reverse-skill)
        if path == "/api/llm-security":
            try:
                from app.services.llm_security_auditor import llm_security_auditor
                payload = json.loads(body.decode("utf-8") or "{}")
                res = llm_security_auditor.audit_prompt(payload.get("prompt_text", ""))
                self._send_json(200, res)
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        # /api/skills/import → Security Skill Importer (reverse-skill)
        if path.startswith("/api/skills/import"):
            try:
                from app.services.skill_importer import skill_importer
                if self.command == "GET":
                    skills = skill_importer.list_available_source_skills()
                    self._send_json(200, {"ok": True, "count": len(skills), "available_skills": skills})
                    return
                payload = json.loads(body.decode("utf-8") or "{}")
                res = skill_importer.import_skill(payload.get("skill_name", ""))
                self._send_json(200 if res.get("ok") else 400, res)
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        # /api/tool-forge POST → generate or install custom tool
        if path.startswith("/api/tool-forge"):
            try:
                from app.services.tool_forge import tool_forge
                payload = json.loads(body.decode("utf-8") or "{}")
                sub = path.removeprefix("/api/tool-forge").lstrip("/")
                if sub == "install":
                    tool_name = payload.get("tool_name", "")
                    code = payload.get("code", "")
                    success, message = tool_forge.save_and_register_tool(tool_name, code)
                    self._send_json(200 if success else 400, {"ok": success, "message": message})
                elif sub == "validate":
                    code = payload.get("code", "")
                    valid, msg = tool_forge.validate_code_ast(code)
                    self._send_json(200, {"ok": True, "valid": valid, "message": msg})
                else:
                    self._send_json(400, {"ok": False, "error": f"Sub-rota tool-forge '{sub}' não reconhecida."})
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        # /api/chat → call orchestrator

        if path == "/api/chat/stream":
            if _orchestrator is None:
                self._send_json(503, {"error": "Orquestrador não disponível."})
                return
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
                message = payload.get("message", "").strip()
                session_id = payload.get("session_id")
                mode = payload.get("mode", "general")
                profile_id = payload.get("profile_id")
                if not message:
                    self._send_json(400, {"error": "Mensagem não pode ser vazia."})
                    return

                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.close_connection = True
                self._send_cors()
                self.end_headers()

                full_summary = ""
                for item in _orchestrator.handle_request_stream(message, session_id=session_id, mode=mode, profile_id=profile_id):
                    plan = item.get("plan")
                    if plan is not None:
                        if item.get("status") == "complete" and plan.intent != "cancelled" and plan.context.get("success") is not False:
                            full_summary = plan.summary
                        item = {**item, "plan": {"intent": plan.intent, "summary": plan.summary, "actions": plan.actions,
                                                 "context": plan.context, "whiteboard_updated": plan.whiteboard_updated}}
                        if item["status"] == "error":
                            item["error"] = plan.summary
                    line = f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
                    self.wfile.write(line.encode("utf-8"))
                    self.wfile.flush()

                # Salvar conversa na memória semântica em background
                if (
                    full_summary
                    and _orchestrator
                    and getattr(_orchestrator, "semantic_memory", None)
                    and not is_technical_error_memory(full_summary)
                ):
                    try:
                        convo_text = f"Usuário: {message}\nJarvis: {full_summary}"
                        threading.Thread(
                            target=_orchestrator.semantic_memory.add_memory,
                            args=("conversations", convo_text),
                            kwargs={"metadata": {"session_id": session_id or ""}},
                            daemon=True,
                        ).start()
                    except Exception:
                        pass
            except (ConnectionAbortedError, BrokenPipeError, ConnectionResetError, OSError):
                return
            except Exception as exc:
                try:
                    line = f"data: {json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=False)}\n\n"
                    self.wfile.write(line.encode("utf-8"))
                    self.wfile.flush()
                except Exception:
                    pass
            return

        if path == "/api/chat":
            if _orchestrator is None:
                self._send_json(503, {"error": "Orquestrador não disponível."})
                return
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
                message = payload.get("message", "").strip()
                session_id = payload.get("session_id")
                mode = payload.get("mode", "general")
                profile_id = payload.get("profile_id")
                racing_mode = bool(payload.get("racing", False))
                if profile_id:
                    from app.services.identity import IdentityService
                    if not IdentityService.profile_exists(str(profile_id)):
                        profile_id = None
                if not message:
                    self._send_json(400, {"error": "Mensagem não pode ser vazia."})
                    return
                plan = _orchestrator.handle_request(message, session_id=session_id, mode=mode, profile_id=profile_id, racing_mode=racing_mode)
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

        if path == "/api/script/authorize":
            payload = json.loads(body.decode("utf-8") or "{}")
            language = str(payload.get("language", "")).lower()
            code = str(payload.get("code", "")).strip()
            if language not in {"python", "powershell"} or not code or not payload.get("confirmed"):
                self._send_json(400, {"ok": False, "error": "Confirmação e script válido são obrigatórios."})
                return
            self._send_json(200, {"ok": True, "receipt": receipts.issue(principal.id, f"script:{language}", code)})
            return

        # /api/script/run → privileged local execution with a single-use receipt.
        if path == "/api/script/run":
            try:
                import subprocess, sys, tempfile, ast, re, logging
                logger = logging.getLogger(__name__)
                
                payload = json.loads(body.decode("utf-8") or "{}")
                language = payload.get("language", "python").lower()
                code = payload.get("code", "").strip()
                receipt = str(payload.get("receipt", ""))
                
                if not code:
                    self._send_json(400, {"error": "Código vazio."})
                    return
                
                if not receipts.consume(receipt, principal.id, f"script:{language}", code):
                    self._send_json(403, {"ok": False, "error": "Recibo de autorização ausente, expirado ou inválido."})
                    return
                
                # Security validation for Python code
                if language == "python":
                    # Check code length
                    if len(code) > 10000:
                        self._send_json(400, {"error": "Código muito longo (máximo 10000 caracteres)."})
                        return
                    
                    # Basic syntax validation
                    try:
                        ast.parse(code)
                    except SyntaxError as e:
                        self._send_json(400, {"error": f"Erro de sintaxe Python: {e}"})
                        return
                    
                    # Security checks for dangerous patterns
                    dangerous_patterns = [
                        r'__import__\s*\(',
                        r'eval\s*\(',
                        r'exec\s*\(',
                        r'compile\s*\(',
                        r'open\s*\(',
                        r'\.__class__',
                        r'\.__bases__',
                        r'\.__subclasses__',
                        r'\.__globals__',
                        r'\.__code__',
                        r'\.__func__',
                        r'os\.system',
                        r'subprocess\.',
                        r'globals\s*\(\)',
                        r'locals\s*\(\)',
                        r'getattr\s*\(',
                        r'setattr\s*\(',
                        r'delattr\s*\(',
                        r'__builtins__',
                    ]
                    
                    for pattern in dangerous_patterns:
                        if re.search(pattern, code, re.IGNORECASE):
                            logger.warning(f"Blocked dangerous Python pattern: {pattern}")
                            self._send_json(403, {"error": f"Código contém padrão perigoso não permitido: {pattern}"})
                            return
                    
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
                    # Check code length
                    if len(code) > 10000:
                        self._send_json(400, {"error": "Código muito longo (máximo 10000 caracteres)."})
                        return
                    
                    # Security checks for dangerous PowerShell patterns
                    dangerous_patterns = [
                        r'Invoke-Expression',
                        r'iex\s+',
                        r'Invoke-Command',
                        r'icm\s+',
                        r'Start-Process',
                        r'WScript\.Shell',
                        r'New-Object\s+System\.Diagnostics\.Process',
                        r'\[System\.Reflection\.Assembly\]',
                        r'Add-Type',
                        r'Invoke-WebRequest',
                        r'Invoke-RestMethod',
                        r'Out-File',
                        r'Set-Content',
                        r'Add-Content',
                        r'Remove-Item',
                        r'Remove-ItemProperty',
                        r'Registry::',
                        r'HKEY_',
                        r'HKLM:',
                        r'HKCU:',
                        r'HKCR:',
                        r'Get-Credential',
                        r'Get-Process',
                        r'Stop-Process',
                        r'Kill-Process',
                    ]
                    
                    for pattern in dangerous_patterns:
                        if re.search(pattern, code, re.IGNORECASE):
                            logger.warning(f"Blocked dangerous PowerShell pattern: {pattern}")
                            self._send_json(403, {"error": f"Código contém padrão perigoso não permitido: {pattern}"})
                            return
                    
                    result = subprocess.run(
                        ["powershell", "-NoProfile", "-NonInteractive", "-Command", code],
                        capture_output=True, text=True, timeout=30,
                        encoding="utf-8", errors="replace"
                    )
                else:
                    self._send_json(400, {"error": f"Linguagem '{language}' não suportada."})
                    return
                    
                logger.info(f"Script executed successfully: language={language}, returncode={result.returncode}")
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
            handle_planning_post,
            handle_actions_post,
            handle_runs_post,
            handle_controls_post,
            handle_goals_post,
        ):
            result = handler_fn(path, body, self)
            if result:
                status_code, data = result
                if isinstance(data, bytes):
                    self.send_response(status_code)
                    # Fish/Edge retornam MP3; Gemini pode retornar WAV.
                    audio_type = "audio/wav" if data[:4] == b"RIFF" else "audio/mpeg"
                    self.send_header("Content-Type", audio_type)
                    self.send_header("Content-Length", str(len(data)))
                    self._send_cors()
                    self.end_headers()
                    self.wfile.write(data)
                else:
                    self._send_json(status_code, data)
                return

        self._send_json(404, {"error": "Endpoint não encontrado."})

    def do_PATCH(self) -> None:
        self.do_POST()

    def do_PUT(self) -> None:
        self.do_POST()


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
                profile_id = data.get("profile_id")
                if profile_id:
                    from app.services.identity import IdentityService
                    if not IdentityService.profile_exists(str(profile_id)):
                        profile_id = None
                loop = asyncio.get_running_loop()

                def on_chunk(chunk_text: str) -> None:
                    if chunk_text:
                        try:
                            asyncio.run_coroutine_threadsafe(
                                websocket.send(json.dumps({"type": "chunk", "text": chunk_text, "session_id": session_id})),
                                loop
                            )
                        except Exception:
                            pass

                def on_reasoning(reason_text: str) -> None:
                    if reason_text:
                        try:
                            asyncio.run_coroutine_threadsafe(
                                websocket.send(json.dumps({"type": "reasoning", "text": reason_text, "session_id": session_id})),
                                loop
                            )
                        except Exception:
                            pass

                def on_search(payload: dict) -> None:
                    try:
                        asyncio.run_coroutine_threadsafe(
                            websocket.send(json.dumps({"type": "search", "payload": payload, "session_id": session_id}, ensure_ascii=False)),
                            loop,
                        )
                    except Exception:
                        pass

                # Run the blocking orchestrator call in a thread
                plan = await loop.run_in_executor(
                    None, lambda: _orchestrator.handle_request(message, session_id=session_id, mode=mode, on_chunk=on_chunk, on_reasoning=on_reasoning, on_search=on_search, profile_id=profile_id)
                )
                prefix = _calendar_conversation_prefix()
                if prefix:
                    plan.summary = prefix + getattr(plan, "summary", str(plan))
                await websocket.send(json.dumps({
                    "type":    "complete",
                    "session_id": session_id,
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
                    and plan.intent not in {"error", "cancelled"}
                    and plan.context.get("success") is not False
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
    from app.storage.runtime_settings import get_agent_profile
    msg = json.dumps({"type": "wake_word", "phrase": get_agent_profile()["wake_phrase"]})
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
        with PanelHandler._pipeline_lock:
            PanelHandler.voice_pipeline = pipeline

    def _run_http(self) -> None:
        PanelHandler.settings = self.settings
        address = (self.settings.host, self.settings.port)
        self.http_server = ThreadingHTTPServer(address, PanelHandler)
        self.http_server.daemon_threads = True
        self.http_server.serve_forever()

    def _run_ws(self) -> None:
        """Run legacy streaming only on a real loopback desktop listener."""
        if not self._websocket_enabled():
            return
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

    def _websocket_enabled(self) -> bool:
        """Never expose the unauthenticated legacy WebSocket outside loopback."""
        host = str(getattr(self.settings, "host", "")).strip().lower()
        return self.settings.access_mode == "loopback" and host in {"127.0.0.1", "localhost", "::1", "[::1]"}

    def start(self) -> None:
        if self._http_thread and self._http_thread.is_alive():
            return
        self.settings.validate_control_plane()
        from app.storage.action_store import action_store
        action_store.start_runtime()

        self._http_thread = threading.Thread(
            target=self._run_http, daemon=True, name="PanelHTTP"
        )
        self._http_thread.start()

        if self._websocket_enabled():
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
            phrase = next(iter(_wake_word_detector.wake_words), "")
            print(f"[Jarvis] Wake word detector iniciado. Diga '{phrase}' para ativar.")
        except Exception as e:
            print(f"[Jarvis] Wake word desativado: {e}")

    def stop(self) -> None:
        if self.http_server:
            self.http_server.shutdown()
