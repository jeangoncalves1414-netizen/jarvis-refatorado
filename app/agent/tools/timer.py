from __future__ import annotations

import re
import threading
import time
import winsound
from datetime import datetime, timedelta
from typing import Any
from .base import BaseTool, ToolResult


class _TimerManager:
    _instance: _TimerManager | None = None
    _lock = threading.Lock()

    def __new__(cls) -> _TimerManager:
        if cls._instance is None:
            obj = super().__new__(cls)
            obj._timers = []
            obj._thread = threading.Thread(target=obj._loop, daemon=True, name="TimerThread")
            obj._thread.start()
            cls._instance = obj
        return cls._instance

    def add(self, fire_at: datetime, label: str) -> None:
        with self._lock:
            self._timers.append({"fire_at": fire_at, "label": label, "fired": False})

    def list_active(self) -> list[dict[str, Any]]:
        with self._lock:
            now = datetime.now()
            return [t for t in self._timers if not t["fired"] and t["fire_at"] > now]

    def _loop(self) -> None:
        while True:
            now = datetime.now()
            with self._lock:
                timers_to_fire = [t for t in self._timers if not t["fired"] and now >= t["fire_at"]]
                for t in timers_to_fire:
                    t["fired"] = True
            for t in timers_to_fire:
                threading.Thread(target=self._fire, args=(t["label"],), daemon=True).start()
            time.sleep(1)

    @staticmethod
    def _fire(label: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        print(f"\n*** ALERTA TIMER: {label} ({stamp}) ***", flush=True)
        try:
            from app.core.logger import logger
            logger.warn("Timer", f"⏰ Timer disparado: {label}")
        except Exception:
            pass
        try:
            for _ in range(3):
                winsound.Beep(1000, 350)
                time.sleep(0.15)
        except Exception:
            pass


def list_active_timers() -> list[dict[str, str]]:
    """Expõe timers ativos para APIs do painel."""
    manager = _TimerManager()
    return [
        {
            "label": str(t.get("label", "Timer")),
            "fire_at": t["fire_at"].isoformat(),
        }
        for t in manager.list_active()
    ]


class TimerTool(BaseTool):
    def __init__(self) -> None:
        self.manager = _TimerManager()

    @property
    def name(self) -> str:
        return "timer"

    @property
    def description(self) -> str:
        return "Cria timers ou alarmes com aviso sonoro, ou lista os timers ativos."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["set_timer", "set_alarm", "list"],
                    "description": "Ação do timer: 'set_timer' para contagem regressiva, 'set_alarm' para horário fixo, 'list' para listar ativos."
                },
                "duration": {
                    "type": "string",
                    "description": "Duração para set_timer (ex: '5 minutos', '10s', '1h')."
                },
                "time": {
                    "type": "string",
                    "description": "Horário para set_alarm formato HH:MM (ex: '14:30')."
                },
                "label": {
                    "type": "string",
                    "description": "Descrição opcional para o timer/alarme."
                }
            },
            "required": ["action"]
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        action = args.get("action", "list")
        label = args.get("label", "").strip()

        if action == "list":
            active = self.manager.list_active()
            if not active:
                return ToolResult(ok=True, message="Nenhum timer ativo.")
            
            lines = []
            now = datetime.now()
            for t in active:
                rem = t["fire_at"] - now
                rem_seconds = int(rem.total_seconds())
                lines.append(f"- {t['label']} às {t['fire_at'].strftime('%H:%M:%S')} (faltam {self._fmt_duration(rem_seconds)})")
            return ToolResult(ok=True, message="Timers ativos:\n" + "\n".join(lines), data={"active": active})

        elif action == "set_timer":
            duration = args.get("duration", "").strip()
            if not duration:
                return ToolResult(ok=False, message="Parâmetro 'duration' é obrigatório para set_timer.")
            
            seconds = self._parse_duration(duration)
            if seconds is None or seconds <= 0:
                return ToolResult(ok=False, message=f"Duração não reconhecida: '{duration}'. Exemplos válidos: '5m', '1 hora', '30 segundos'.")
            
            fire_at = datetime.now() + timedelta(seconds=seconds)
            desc = label or f"Timer de {duration}"
            self.manager.add(fire_at, desc)
            return ToolResult(
                ok=True,
                message=f"Timer criado com sucesso: '{desc}' para disparar às {fire_at.strftime('%H:%M:%S')}.",
                data={"fire_at": fire_at.isoformat(), "label": desc}
            )

        elif action == "set_alarm":
            time_str = args.get("time", "").strip()
            if not time_str:
                return ToolResult(ok=False, message="Parâmetro 'time' é obrigatório para set_alarm.")
            
            try:
                target = datetime.strptime(time_str, "%H:%M")
            except ValueError:
                return ToolResult(ok=False, message=f"Horário inválido: '{time_str}'. Use o formato HH:MM.")
            
            now = datetime.now()
            fire_at = now.replace(hour=target.hour, minute=target.minute, second=0, microsecond=0)
            if fire_at <= now:
                fire_at += timedelta(days=1)
            
            desc = label or f"Alarme para {time_str}"
            self.manager.add(fire_at, desc)
            return ToolResult(
                ok=True,
                message=f"Alarme criado com sucesso: '{desc}' para às {fire_at.strftime('%H:%M')}.",
                data={"fire_at": fire_at.isoformat(), "label": desc}
            )

        return ToolResult(ok=False, message=f"Ação desconhecida: {action}")

    @staticmethod
    def _parse_duration(text: str) -> int | None:
        text = text.lower().strip()
        total = 0
        found = False
        for pattern, mult in [
            (r"(\d+)\s*h(?:ora)?s?", 3600),
            (r"(\d+)\s*min(?:uto)?s?", 60),
            (r"(\d+)\s*s(?:eg(?:undo)?)?s?\b", 1),
            (r"(\d+)\s*m\b", 60),
        ]:
            for m in re.finditer(pattern, text):
                total += int(m.group(1)) * mult
                found = True
        if found:
            return total
        
        # Se contiver apenas digitos, assume minutos
        digits = re.search(r"^(\d+)$", text)
        if digits:
            return int(digits.group(1)) * 60
        return None

    @staticmethod
    def _fmt_duration(seconds: int) -> str:
        if seconds < 60:
            return f"{seconds}s"
        if seconds < 3600:
            m, s = divmod(seconds, 60)
            return f"{m}m {s}s" if s else f"{m}m"
        h, rest = divmod(seconds, 3600)
        m = rest // 60
        return f"{h}h {m}m" if m else f"{h}h"
