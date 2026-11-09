"""Contexto situacional do turno (fase 1): código puro, sem chamada ao modelo.

Cada fonte é um provedor com cache curto. Toda falha de uma fonte vira "fonte ausente";
o bloco nunca quebra o turno. O bloco inteiro cabe em 600 caracteres, cabeçalho incluído;
quando passa, as linhas de menor prioridade saem primeiro.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Protocol

from app.storage.contexto_settings import SOURCE_LABELS, get_context_settings

TZ_NAME = "America/Sao_Paulo"
HEADER = "Situação agora (use só se for relevante ao pedido):"
MAX_CHARS = 600
LINE_CHARS = 120
TITLE_CHARS = 60
_WEEKDAYS = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")
_PAUSED_MEDIA_TITLES = {"spotify", "spotify free", "spotify premium"}


def _tz():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(TZ_NAME)
    except Exception:
        # Sem base de fusos: o Brasil não tem horário de verão desde 2019.
        return timezone(timedelta(hours=-3), TZ_NAME)


def local_now() -> datetime:
    return datetime.now(_tz())


def period_of(hour: int) -> str:
    if 5 <= hour < 12:
        return "manhã"
    if 12 <= hour < 18:
        return "tarde"
    return "noite"


def _short(text: str, limit: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


class ContextProvider(Protocol):
    key: str
    label: str
    ttl: float

    def read(self, now: datetime, settings: dict[str, Any]) -> str | None: ...


@dataclass
class ContextBlock:
    text: str = ""
    sources: list[dict[str, str]] = field(default_factory=list)
    chars: int = 0
    show_in_chat: bool = False


class SituationalContext:
    def __init__(
        self,
        providers: list[ContextProvider],
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = local_now,
        settings: Callable[[], dict[str, Any]] = get_context_settings,
    ):
        self.providers = list(providers)
        self.clock = clock
        self.now = now
        self.settings = settings
        self._cache: dict[tuple[str, bool], tuple[str | None, float]] = {}
        self._lock = threading.Lock()

    def _read(self, provider: ContextProvider, now: datetime, settings: dict[str, Any]) -> str | None:
        # O título da janela entra na chave do cache: desligar a privacidade vale na hora.
        cache_key = (provider.key, bool(settings.get("send_window_titles")))
        moment = self.clock()
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached is not None and provider.ttl > 0 and moment - cached[1] < provider.ttl:
                return cached[0]
        try:
            value = provider.read(now, settings)
            value = _short(value, LINE_CHARS - 2) if isinstance(value, str) and value.strip() else None
        except Exception:
            value = None
        with self._lock:
            self._cache[cache_key] = (value, moment)
        return value

    def build(self) -> ContextBlock:
        try:
            settings = self.settings()
        except Exception:
            return ContextBlock()
        if not settings.get("enabled", True):
            return ContextBlock()
        enabled_sources = settings.get("sources") or {}
        try:
            now = self.now()
        except Exception:
            now = datetime.now()
        lines: list[tuple[dict[str, str], str]] = []
        for provider in self.providers:
            if not enabled_sources.get(provider.key, True):
                continue
            value = self._read(provider, now, settings)
            if value:
                lines.append(({"key": provider.key, "label": provider.label}, f"- {value}"))
        while lines and len(HEADER) + sum(1 + len(line) for _, line in lines) > MAX_CHARS:
            lines.pop()
        if not lines:
            return ContextBlock(show_in_chat=bool(settings.get("show_in_chat", True)))
        text = "\n".join([HEADER, *(line for _, line in lines)])
        return ContextBlock(
            text=text, sources=[source for source, _ in lines], chars=len(text),
            show_in_chat=bool(settings.get("show_in_chat", True)),
        )


# ---------------------------------------------------------------- fontes reais

@dataclass
class _Provider:
    key: str
    ttl: float
    reader: Callable[[datetime, dict[str, Any]], str | None]

    @property
    def label(self) -> str:
        return SOURCE_LABELS.get(self.key, self.key)

    def read(self, now: datetime, settings: dict[str, Any]) -> str | None:
        return self.reader(now, settings)


def read_datetime(now: datetime, _settings: dict[str, Any]) -> str:
    return f"Agora: {_WEEKDAYS[now.weekday()]}, {now:%d/%m/%Y %H:%M} ({TZ_NAME}), {period_of(now.hour)}"


def read_calendar(now: datetime, _settings: dict[str, Any]) -> str | None:
    # Só lê arquivo existente: CalendarService criaria a pasta data/.
    if not Path("data/calendar.json").exists():
        return None
    from app.services.calendar import CalendarService

    naive_now = now.replace(tzinfo=None)
    upcoming = sorted(
        (event for event in CalendarService().get_today_events() if event.start.replace(tzinfo=None) > naive_now),
        key=lambda event: event.start.replace(tzinfo=None),
    )
    if not upcoming:
        return None
    event = upcoming[0]
    return f"Próximo compromisso hoje: {event.start:%H:%M} {_short(event.title, 70)}"


def _foreground_window() -> tuple[str, str]:
    """(nome do processo, título) da janela em primeiro plano; vazio fora do Windows."""
    if os.name != "nt":
        return "", ""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return "", ""
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    name = ""
    try:
        import psutil
        name = psutil.Process(pid.value).name()
    except Exception:
        pass
    return name, buffer.value


def _app_name(process_name: str) -> str:
    name = (process_name or "").strip()
    if name.lower().endswith(".exe"):
        name = name[:-4]
    return name[:1].upper() + name[1:]


def make_window_reader(foreground: Callable[[], tuple[str, str]] = _foreground_window):
    def read_window(_now: datetime, settings: dict[str, Any]) -> str | None:
        process_name, title = foreground()
        app = _app_name(process_name)
        title = _short(title, TITLE_CHARS)
        send_title = bool(settings.get("send_window_titles"))
        if not app:
            # Sem o nome do processo, o título só sai com a permissão de privacidade.
            return f"Em primeiro plano: {title}" if send_title and title else None
        return f"Em primeiro plano: {app}" + (f" — {title}" if send_title and title else "")
    return read_window


def _spotify_title() -> str:
    """Título da janela principal do Spotify ("Artista - Música" quando toca)."""
    if os.name != "nt":
        return ""
    import ctypes
    from ctypes import wintypes

    import psutil

    pids = {p.info["pid"] for p in psutil.process_iter(["pid", "name"]) if (p.info.get("name") or "").lower() == "spotify.exe"}
    if not pids:
        return ""
    user32 = ctypes.windll.user32
    titles: list[str] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                titles.append(buffer.value)
        return True

    user32.EnumWindows(callback, 0)
    return next((t for t in titles if " - " in t), "")


def make_media_reader(title_reader: Callable[[], str] = _spotify_title):
    def read_media(_now: datetime, _settings: dict[str, Any]) -> str | None:
        title = (title_reader() or "").strip()
        if not title or title.lower() in _PAUSED_MEDIA_TITLES or " - " not in title:
            return None
        return f"Tocando no Spotify: {_short(title, 90)}"
    return read_media


def _habits_db_exists() -> bool:
    from app.services import habits
    return Path(habits.DB_PATH).exists()


def read_lifeos(_now: datetime, _settings: dict[str, Any]) -> str | None:
    parts: list[str] = []
    try:
        from app.services import lifeos
        if lifeos._DOCUMENTS_DB.exists() or lifeos._LOCAL_DB.exists():
            water = lifeos.LifeOSService.get_daily_summary().get("water") or {}
            parts.append(f"Água: {int(water.get('current_ml') or 0)}/{int(water.get('target_ml') or 0)} ml")
    except Exception:
        pass
    try:
        if _habits_db_exists():
            from app.services.habits import HabitService
            items = HabitService.list_habits()
            if items:
                done = sum(1 for item in items if item.get("completed_today"))
                parts.append(f"hábitos feitos hoje: {done} de {len(items)}")
    except Exception:
        pass
    if not parts:
        return None
    text = "; ".join(parts)
    return text[:1].upper() + text[1:]


def read_tasks(_now: datetime, _settings: dict[str, Any]) -> str | None:
    if not _habits_db_exists():
        return None
    from app.services.tasks import TaskService

    count = len(TaskService.list_tasks(completed=False))
    return f"Tarefas pendentes: {count}" if count else None


def read_routines(_now: datetime, _settings: dict[str, Any]) -> str | None:
    # Rotinas são do Workflow A (feat/rotinas): só leitura, e só se o módulo existir.
    import importlib

    try:
        module = importlib.import_module("app.services.routines")
    except Exception:
        return None
    list_running = getattr(module, "list_running", None)
    if not callable(list_running):
        return None
    names = []
    for item in list_running() or []:
        name = (item.get("name") or item.get("title")) if isinstance(item, dict) else item
        if name:
            names.append(str(name))
    return f"Rotinas em andamento: {', '.join(names[:3])}" if names else None


def make_pc_reader(battery: Callable[[], Any] | None = None, cpu: Callable[[], float] | None = None):
    def read_pc(_now: datetime, _settings: dict[str, Any]) -> str | None:
        import psutil

        parts: list[str] = []
        try:
            info = battery() if battery else psutil.sensors_battery()
            if info is not None and info.percent is not None and info.percent < 30 and not info.power_plugged:
                parts.append(f"bateria {round(info.percent)}% (sem carregar)")
        except Exception:
            pass
        try:
            usage = cpu() if cpu else psutil.cpu_percent(interval=None)
            if usage is not None and usage >= 85:
                parts.append(f"CPU {round(usage)}%")
        except Exception:
            pass
        return "PC: " + "; ".join(parts) if parts else None
    return read_pc


def default_providers() -> list[ContextProvider]:
    return [
        _Provider("datetime", 0, read_datetime),
        _Provider("calendar", 30, read_calendar),
        _Provider("window", 3, make_window_reader()),
        _Provider("media", 5, make_media_reader()),
        _Provider("lifeos", 15, read_lifeos),
        _Provider("tasks", 15, read_tasks),
        _Provider("routines", 10, read_routines),
        _Provider("pc", 5, make_pc_reader()),
    ]


situational_context: SituationalContext | None = None
_instance_lock = threading.Lock()


def get_situational_context() -> SituationalContext:
    global situational_context
    with _instance_lock:
        if situational_context is None:
            situational_context = SituationalContext(default_providers())
        return situational_context
