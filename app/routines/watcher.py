"""Observador de eventos do sistema e regras de alerta em segundo plano (Fase 3).

Executa em thread daemon ('routine-events') com baixo overhead: só chama sondas de
hardware/processos/agenda se alguma regra ativa exigir. Não faz chamadas a modelos de IA.
"""
from __future__ import annotations

import ctypes
import re
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Callable

import psutil

from app.agent import popups
from app.core import ui_events
from app.routines import triggers as trig
from app.storage import routine_store as routine_store_module
from app.storage import runtime_settings


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def _default_idle_seconds() -> float:
    try:
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
            return max(0.0, millis / 1000.0)
    except Exception:
        pass
    return 0.0


def _default_processes() -> set[str]:
    names: set[str] = set()
    try:
        for p in psutil.process_iter(["name"]):
            name = p.info.get("name")
            if name:
                names.add(str(name).lower())
    except Exception:
        pass
    return names


def _default_calendar_events(start: datetime, end: datetime) -> list[Any]:
    try:
        from app.services.calendar import CalendarService
        return CalendarService().get_events(start, end)
    except Exception:
        return []


def _in_window(window: dict[str, str] | None, now: datetime) -> bool:
    if not window or not window.get("start") or not window.get("end"):
        return True
    try:
        sh, sm = (int(v) for v in window["start"].split(":"))
        eh, em = (int(v) for v in window["end"].split(":"))
        curr = now.hour * 60 + now.minute
        s = sh * 60 + sm
        e = eh * 60 + em
        if s <= e:
            return s <= curr < e
        return curr >= s or curr < e
    except Exception:
        return True


class EventWatcher:
    def __init__(self, runner: Any = None) -> None:
        self.runner = runner
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._running = False
        self._paused = False
        self._reload_needed = False

        # Sondas injetáveis para testes
        self.probe_cpu: Callable[[], float] = lambda: float(psutil.cpu_percent(None))
        self.probe_ram: Callable[[], float] = lambda: float(psutil.virtual_memory().percent)
        self.probe_disk: Callable[[str], float] = lambda path: float(psutil.disk_usage(path).percent)
        self.probe_processes: Callable[[], set[str]] = _default_processes
        self.probe_idle_seconds: Callable[[], float] = _default_idle_seconds
        self.probe_calendar_events: Callable[[datetime, datetime], list[Any]] = _default_calendar_events

        # Estado de rastreamento
        self._last_processes: set[str] | None = None
        self._resource_high_since: dict[str, float] = {}
        self._resource_triggered: set[str] = set()
        self._last_fired: dict[str, float] = {}
        self._fired_calendar_events: set[str] = set()
        self._was_idle = False

    @staticmethod
    def store() -> Any:
        return routine_store_module.routine_store

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._running = True
            self._paused = False
            self._thread = threading.Thread(target=self._loop, name="routine-events", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            self._thread = None

    def pause(self) -> None:
        with self._lock:
            self._paused = True

    def resume(self) -> None:
        with self._lock:
            self._paused = False

    def reload(self) -> None:
        with self._lock:
            self._reload_needed = True

    def _loop(self) -> None:
        while self._running:
            try:
                settings = runtime_settings.get_event_settings()
                interval = max(5, int(settings.get("interval_seconds") or 15))
            except Exception:
                interval = 15

            start_time = time.time()
            if not self._paused:
                try:
                    self.tick()
                except Exception:
                    pass

            elapsed = time.time() - start_time
            sleep_time = max(0.5, interval - elapsed)
            time.sleep(sleep_time)

    def tick(self, now: datetime | None = None) -> list[dict[str, Any]]:
        """Ciclo único de checagem. Público para testes e acionamento direto."""
        with self._lock:
            if self._paused:
                return []

            now_dt = now or datetime.now(trig.TZ)
            now_ts = now_dt.timestamp()

            # 1. Carrega configurações globais e rotinas ativas
            settings = runtime_settings.get_event_settings()
            global_enabled = bool(settings.get("enabled", True))
            disk_path = str(settings.get("disk_path") or "C:\\")
            global_cooldown = int(settings.get("cooldown_minutes") or 30)

            routines = self.store().list()
            active_event_routines: list[tuple[dict[str, Any], dict[str, Any]]] = []
            for r in routines:
                if not r.get("enabled"):
                    continue
                for t in r.get("triggers") or []:
                    if t.get("type") == "event":
                        active_event_routines.append((r, t))

            # Determina o que precisa ser coletado
            need_cpu = False
            need_ram = False
            need_disk = False
            need_procs = False
            need_idle = False
            need_cal = False

            if global_enabled:
                if settings.get("cpu", {}).get("enabled"):
                    need_cpu = True
                if settings.get("ram", {}).get("enabled"):
                    need_ram = True
                if settings.get("disk", {}).get("enabled"):
                    need_disk = True

            for _r, trig_def in active_event_routines:
                ev_type = trig_def.get("event")
                if ev_type == "resource":
                    m = str((trig_def.get("params") or {}).get("metric") or "cpu").lower()
                    if m == "cpu":
                        need_cpu = True
                    elif m == "ram":
                        need_ram = True
                    elif m == "disk":
                        need_disk = True
                elif ev_type in ("app_started", "app_closed"):
                    need_procs = True
                elif ev_type in ("idle", "returned"):
                    need_idle = True
                elif ev_type == "calendar_before":
                    need_cal = True

            # Se nenhuma regra precisa de nada, encerra sem sondar
            if not any((need_cpu, need_ram, need_disk, need_procs, need_idle, need_cal)):
                return []

            # 2. Coleta das sondas necessárias
            cpu_val: float | None = self.probe_cpu() if need_cpu else None
            ram_val: float | None = self.probe_ram() if need_ram else None
            disk_val: float | None = self.probe_disk(disk_path) if need_disk else None
            procs_val: set[str] | None = self.probe_processes() if need_procs else None
            idle_val: float | None = self.probe_idle_seconds() if need_idle else None
            cal_events: list[Any] | None = (
                self.probe_calendar_events(now_dt, now_dt + timedelta(days=1)) if need_cal else None
            )

            dispatched: list[dict[str, Any]] = []

            # 3. Avaliação dos alertas globais de recurso
            if global_enabled:
                res_checks = [
                    ("global:cpu", "cpu", cpu_val, settings.get("cpu") or {}),
                    ("global:ram", "ram", ram_val, settings.get("ram") or {}),
                    ("global:disk", "disk", disk_val, settings.get("disk") or {}),
                ]
                for key, metric_name, val, cfg in res_checks:
                    if not cfg.get("enabled") or val is None:
                        continue
                    thresh = int(cfg.get("threshold") or 90)
                    for_sec = int(cfg.get("for_seconds") or 0)
                    last_fired = self._last_fired.get(key, 0)
                    in_cooldown = (now_ts - last_fired) < (global_cooldown * 60)

                    if val >= thresh:
                        if key not in self._resource_high_since:
                            self._resource_high_since[key] = now_ts
                        duration = now_ts - self._resource_high_since[key]
                        if duration >= for_sec and key not in self._resource_triggered and not in_cooldown:
                            # Dispara alerta
                            summary = f"Uso de {metric_name.upper()} em {val:.1f}% (limiar: {thresh}% por {for_sec}s)."
                            res_actions = [
                                {"label": "Ver Hábitos", "action": "habits"},
                                {"label": "Ouvir Briefing", "action": "briefing"},
                            ]
                            self._fire_alert(
                                routine_id=None,
                                title=f"Alerta de Sistema: {metric_name.upper()}",
                                lines=[summary],
                                summary=summary,
                                actions=res_actions,
                                urgency="high" if val >= 90 else "normal",
                            )
                            self._resource_triggered.add(key)
                            self._last_fired[key] = now_ts
                            dispatched.append({"kind": "global_resource", "metric": metric_name, "value": val})
                    elif val < thresh - 5:
                        self._resource_triggered.discard(key)
                        self._resource_high_since.pop(key, None)
                    else:
                        self._resource_high_since.pop(key, None)

            # 4. Avaliação das rotinas ativas
            for routine, trig_def in active_event_routines:
                routine_id = routine["id"]
                ev_type = trig_def.get("event")
                params = trig_def.get("params") or {}
                mode = trig_def.get("mode") or "alert"
                cooldown_min = int(trig_def.get("cooldown_minutes") or 30)
                window = trig_def.get("window")

                # Checa horário de silêncio e janela permitida
                if trig.in_quiet_hours(routine.get("quiet"), now_dt):
                    continue
                if not _in_window(window, now_dt):
                    continue

                last_fired = self._last_fired.get(routine_id, 0)
                if (now_ts - last_fired) < (cooldown_min * 60):
                    continue

                should_fire = False
                summary = ""
                routine_actions: list[dict[str, Any]] | None = None

                if ev_type == "resource":
                    metric_name = str(params.get("metric") or "cpu").lower()
                    val = cpu_val if metric_name == "cpu" else ram_val if metric_name == "ram" else disk_val
                    if val is not None:
                        thresh = int(params.get("threshold") or 90)
                        for_sec = int(params.get("for_seconds") or 0)
                        key = f"routine:{routine_id}:{metric_name}"
                        if val >= thresh:
                            if key not in self._resource_high_since:
                                self._resource_high_since[key] = now_ts
                            duration = now_ts - self._resource_high_since[key]
                            if duration >= for_sec and key not in self._resource_triggered:
                                should_fire = True
                                summary = f"Uso de {metric_name.upper()} em {val:.1f}% (limiar: {thresh}% por {for_sec}s)."
                                self._resource_triggered.add(key)
                        elif val < thresh - 5:
                            self._resource_triggered.discard(key)
                            self._resource_high_since.pop(key, None)
                        else:
                            self._resource_high_since.pop(key, None)

                elif ev_type == "app_started" and procs_val is not None:
                    target = str(params.get("app_name") or "").strip().lower()
                    if self._last_processes is not None:
                        if not any(target in p for p in self._last_processes) and any(target in p for p in procs_val):
                            should_fire = True
                            summary = f"Programa '{target}' foi aberto."

                elif ev_type == "app_closed" and procs_val is not None:
                    target = str(params.get("app_name") or "").strip().lower()
                    if self._last_processes is not None:
                        if any(target in p for p in self._last_processes) and not any(target in p for p in procs_val):
                            should_fire = True
                            summary = f"Programa '{target}' foi fechado."

                elif ev_type == "calendar_before" and cal_events is not None:
                    mins_before = int(params.get("minutes") or 15)
                    for event in cal_events:
                        event_id = getattr(event, "id", None) or str(event)
                        if event_id in self._fired_calendar_events:
                            continue
                        event_start = getattr(event, "start", None)
                        if not event_start:
                            continue
                        # Normaliza para comparação
                        diff_sec = (event_start.replace(tzinfo=None) - now_dt.replace(tzinfo=None)).total_seconds()
                        diff_min = diff_sec / 60.0
                        if 0 <= diff_min <= mins_before:
                            should_fire = True
                            title = getattr(event, "title", "Compromisso")
                            summary = f"Compromisso '{title}' em {int(diff_min)} min."
                            event_url = getattr(event, "url", None) or getattr(event, "link", None) or getattr(event, "location", None)
                            cal_acts: list[dict[str, Any]] = []
                            if event_url and (str(event_url).startswith("http://") or str(event_url).startswith("https://")):
                                cal_acts.append({"label": "Abrir Reunião", "action": "open_link", "url": str(event_url)})
                            cal_acts.append({"label": "Ouvir Briefing", "action": "briefing"})
                            routine_actions = cal_acts
                            self._fired_calendar_events.add(event_id)
                            break

                elif ev_type == "idle" and idle_val is not None:
                    mins_idle = int(params.get("minutes") or 15)
                    if idle_val >= mins_idle * 60:
                        should_fire = True
                        summary = f"Inatividade detectada por {int(idle_val / 60)} min."

                elif ev_type == "returned" and idle_val is not None:
                    if self._was_idle and idle_val < 10:
                        should_fire = True
                        summary = "Retorno ao PC detectado."

                if should_fire:
                    self._last_fired[routine_id] = now_ts
                    if mode == "alert":
                        self._fire_alert(
                            routine_id=routine_id,
                            title=f"Rotina: {routine['name']}",
                            lines=[summary],
                            summary=summary,
                            actions=routine_actions,
                        )
                        dispatched.append({"kind": "routine_alert", "routine_id": routine_id, "summary": summary})
                    else:
                        if self.runner is not None:
                            run_id = self.runner.start(routine, f"event:{ev_type}")
                            dispatched.append({"kind": "routine_run", "routine_id": routine_id, "run_id": run_id})

            # Atualiza estados anteriores
            if procs_val is not None:
                self._last_processes = procs_val
            if idle_val is not None:
                self._was_idle = idle_val >= 60

            return dispatched

    def _fire_alert(
        self,
        routine_id: str | None,
        title: str,
        lines: list[str],
        summary: str,
        actions: list[dict[str, Any]] | None = None,
        urgency: str = "normal",
    ) -> None:
        """Gera o popup de aviso, grava no histórico, publica o evento e emite notificação nativa do Windows."""
        try:
            popup = popups.build_popup("info", {"title": title, "lines": lines, "tone": "warn"}, origin="chat")
            popups.emit(popup)
        except Exception:
            pass

        try:
            from app.services.windows_notifications import send_notification
            send_notification(
                title=title,
                message=summary or ("\n".join(lines)),
                actions=actions,
                urgency=urgency,
            )
        except Exception:
            pass

        if routine_id:
            try:
                self.store().add_run(routine_id, "event", status="alert", summary=summary)
            except Exception:
                pass

        try:
            ui_events.publish({"type": "routine_alert", "routine_id": routine_id, "summary": summary})
        except Exception:
            pass

