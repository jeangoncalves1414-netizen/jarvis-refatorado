"""Horários das rotinas no fuso de São Paulo: gatilhos do APScheduler, próximas e perdidas, silêncio e textos.

O APScheduler só calcula datas aqui (``get_next_fire_time``); o agendador de verdade fica em
``app.routines.service``. Assim "próximas execuções" funciona mesmo sem o agendador ligado.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.routines.models import TIME_TRIGGERS, WEEK_DAYS, time_trigger

TZ = ZoneInfo("America/Sao_Paulo")
_DAY_LABELS = {"mon": "seg", "tue": "ter", "wed": "qua", "thu": "qui", "fri": "sex", "sat": "sáb", "sun": "dom"}
_MAX_ITERATIONS = 5000
_TICK = timedelta(microseconds=1)


def _local(moment: datetime) -> datetime:
    return moment.replace(tzinfo=TZ) if moment.tzinfo is None else moment.astimezone(TZ)


def from_timestamp(value: float) -> datetime:
    return datetime.fromtimestamp(value, TZ)


def _hour_minute(text: str) -> tuple[int, int]:
    hour, minute = text.split(":")
    return int(hour), int(minute)


def build_aps_trigger(trigger: dict[str, Any], *, anchor: datetime | None = None) -> Any:
    """Gatilho do APScheduler equivalente; None para voz/comando. ``anchor`` fixa o início do intervalo."""
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.date import DateTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    kind = trigger.get("type")
    if kind == "at":
        return DateTrigger(run_date=_local(datetime.fromisoformat(trigger["datetime"])), timezone=TZ)
    if kind in ("daily", "weekdays", "weekly"):
        hour, minute = _hour_minute(trigger["time"])
        days = {"daily": None, "weekdays": "mon-fri"}.get(kind, ",".join(trigger.get("days") or ()))
        return CronTrigger(day_of_week=days, hour=hour, minute=minute, timezone=TZ)
    if kind == "interval":
        start = _local(anchor) if anchor else None
        return IntervalTrigger(minutes=int(trigger["minutes"]), start_date=start, timezone=TZ)
    return None


def _anchor(routine: dict[str, Any]) -> datetime | None:
    stamp = routine.get("updated_at") or routine.get("created_at")
    return from_timestamp(float(stamp)) if stamp else None


def _fires_after(routine: dict[str, Any], start: datetime, *, until: datetime | None = None, count: int | None = None) -> list[datetime]:
    """Datas previstas depois de ``start`` (exclusivo), até ``until`` (inclusivo) ou ``count`` datas."""
    trigger = time_trigger(routine)
    if trigger is None:
        return []
    start = _local(start)
    if trigger["type"] == "at":
        moment = _local(datetime.fromisoformat(trigger["datetime"]))
        return [moment] if moment > start and (until is None or moment <= _local(until)) else []
    aps = build_aps_trigger(trigger, anchor=_anchor(routine))
    found: list[datetime] = []
    previous = None
    cursor = start + _TICK
    for _ in range(_MAX_ITERATIONS):
        moment = aps.get_next_fire_time(previous, cursor)
        if moment is None or (until is not None and moment > _local(until)):
            break
        if moment > start:
            found.append(moment)
            if count is not None and len(found) >= count:
                break
        previous, cursor = moment, moment + _TICK
    return found


def next_runs(routine: dict[str, Any], now: datetime | None = None, count: int = 1) -> list[datetime]:
    """Próximas execuções previstas de uma rotina ativa (vazio se não tem horário ou já passou)."""
    if not routine.get("enabled", True):
        return []
    return _fires_after(routine, now or datetime.now(TZ), count=max(1, count))


def next_run(routine: dict[str, Any], now: datetime | None = None) -> datetime | None:
    found = next_runs(routine, now, 1)
    return found[0] if found else None


def missed_fires(routine: dict[str, Any], since: datetime, now: datetime) -> list[datetime]:
    """Datas previstas entre ``since`` (exclusivo) e ``now`` (inclusivo): o que não rodou com o PC desligado."""
    return _fires_after(routine, since, until=now)


def in_quiet_hours(quiet: dict[str, str] | None, now: datetime | None = None) -> bool:
    """Dentro do horário de silêncio; o intervalo pode atravessar a meia-noite (22:00-07:00)."""
    if not quiet:
        return False
    moment = _local(now or datetime.now(TZ))
    start, end = (_hour_minute(quiet["start"]), _hour_minute(quiet["end"]))
    current = moment.hour * 60 + moment.minute
    low, high = start[0] * 60 + start[1], end[0] * 60 + end[1]
    return low <= current < high if low < high else current >= low or current < high


def describe_trigger(trigger: dict[str, Any]) -> str:
    kind = trigger.get("type")
    if kind == "daily":
        return f"Todo dia às {trigger['time']}"
    if kind == "weekdays":
        return f"Dias úteis às {trigger['time']}"
    if kind == "weekly":
        names = [_DAY_LABELS[day].capitalize() if index == 0 else _DAY_LABELS[day] for index, day in enumerate(trigger.get("days") or [])]
        joined = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " e " + names[-1]
        return f"{joined} às {trigger['time']}"
    if kind == "interval":
        return f"A cada {trigger['minutes']} min"
    if kind == "at":
        moment = datetime.fromisoformat(trigger["datetime"])
        return f"Em {moment:%d/%m} às {moment:%H:%M}"
    if kind == "voice":
        return f"Voz: {trigger['phrase']}"
    if kind == "command":
        return f"/{trigger['slash']}"
    if kind == "event":
        ev = trigger.get("event")
        params = trigger.get("params") or {}
        if ev == "calendar_before":
            return f"Compromisso em {params.get('minutes', 15)} min"
        if ev == "app_started":
            return f"Programa abriu: {params.get('app_name', '')}"
        if ev == "app_closed":
            return f"Programa fechou: {params.get('app_name', '')}"
        if ev == "resource":
            metric = str(params.get("metric") or "cpu").upper()
            return f"Recurso: {metric} > {params.get('threshold', 90)}%"
        if ev == "idle":
            return f"Ausente por {params.get('minutes', 15)} min"
        if ev == "returned":
            return "Voltou ao PC"
        return f"Evento: {ev}"
    return str(kind or "")


def describe_triggers(routine: dict[str, Any]) -> str:
    texts = [describe_trigger(item) for item in routine.get("triggers") or []]
    return " · ".join(texts) if texts else "Só manual"


def describe_when(moment: datetime | None, now: datetime | None = None) -> str:
    """"hoje 08:00", "amanhã 08:00" ou "seg 10/11 08:00"."""
    if moment is None:
        return "sem próxima execução"
    moment, today = _local(moment), _local(now or datetime.now(TZ)).date()
    if moment.date() == today:
        return f"hoje {moment:%H:%M}"
    if moment.date() == today + timedelta(days=1):
        return f"amanhã {moment:%H:%M}"
    return f"{_DAY_LABELS[WEEK_DAYS[moment.weekday()]]} {moment:%d/%m %H:%M}"


def is_scheduled(routine: dict[str, Any]) -> bool:
    return any(item.get("type") in TIME_TRIGGERS for item in routine.get("triggers") or [])
