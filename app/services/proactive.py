"""Serviço Proativo do Jarvis — Briefing matinal customizável e Lembretes temporizados por voz."""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

CONFIG_PATH = Path("data/proactive_config.json")


class ProactiveService:
    """
    Gerencia a configuração do assistente proativo, agendamento de lembretes e
    briefing matinal personalizável via linguagem natural.
    """

    def __init__(self, config_path: Path | str = CONFIG_PATH) -> None:
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()  # RLock = reentrante (evita deadlock entre _save/_load)
        self._config = self._load_config()

    def _default_config(self) -> dict[str, Any]:
        return {
            "briefing_enabled": True,
            "briefing_time": "08:00",
            "briefing_topics": ["weather", "news", "finance", "holidays"],
            "custom_instructions": "",
            "last_briefing_date": "",
            "reminders": [],
        }

    def _load_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            default = self._default_config()
            self._save_config(default)
            return default
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                merged = self._default_config()
                merged.update(data)
                return merged
        except Exception:
            return self._default_config()

    def _save_config(self, data: dict[str, Any] | None = None) -> None:
        with self._lock:
            to_save = data if data is not None else self._config
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(to_save, f, ensure_ascii=False, indent=2)

    def get_config(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._config)

    def update_briefing_config(
        self,
        enabled: bool | None = None,
        briefing_time: str | None = None,
        topics: list[str] | None = None,
        custom_instructions: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if enabled is not None:
                self._config["briefing_enabled"] = enabled
            if briefing_time:
                self._config["briefing_time"] = briefing_time.strip()
            if topics is not None:
                self._config["briefing_topics"] = topics
            if custom_instructions is not None:
                self._config["custom_instructions"] = custom_instructions.strip()
            self._save_config()
            return dict(self._config)

    def add_reminder(self, message: str, target_time_str: str) -> dict[str, Any]:
        """
        Adiciona um lembrete.
        *target_time_str* pode ser formato HH:MM (ex: "13:00") ou formato relativo em minutos (ex: "+30m").
        """
        now = datetime.now()
        target_dt = None

        target_str = target_time_str.strip().lower()
        if target_str.startswith("+") and target_str.endswith("m"):
            try:
                mins = int(target_str[1:-1])
                target_dt = now + timedelta(minutes=mins)
            except ValueError:
                pass
        elif target_str.startswith("+") and target_str.endswith("h"):
            try:
                hours = int(target_str[1:-1])
                target_dt = now + timedelta(hours=hours)
            except ValueError:
                pass
        else:
            try:
                t = datetime.strptime(target_str, "%H:%M").time()
                target_dt = datetime.combine(now.date(), t)
                if target_dt <= now:
                    target_dt += timedelta(days=1)
            except ValueError:
                pass

        if not target_dt:
            # Fallback: se não conseguiu converter, adiciona para 10 minutos no futuro
            target_dt = now + timedelta(minutes=10)

        reminder_id = f"rem_{os.urandom(4).hex()}"
        reminder = {
            "id": reminder_id,
            "message": message.strip(),
            "target_time": target_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "delivered": False,
            "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        }

        with self._lock:
            self._config["reminders"].append(reminder)
            self._save_config()

        return reminder

    def get_pending_reminders(self) -> list[dict[str, Any]]:
        with self._lock:
            return [r for r in self._config.get("reminders", []) if not r.get("delivered")]

    def check_due_reminders(self) -> list[dict[str, Any]]:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        due = []
        with self._lock:
            for r in self._config.get("reminders", []):
                if not r.get("delivered") and r.get("target_time", "") <= now_str:
                    r["delivered"] = True
                    due.append(r)
            if due:
                self._save_config()
        return due

    def check_briefing_due(self) -> bool:
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        current_time = now.time().replace(second=0, microsecond=0)

        with self._lock:
            if not self._config.get("briefing_enabled", True):
                return False
            if self._config.get("last_briefing_date") == today_str:
                return False
            try:
                briefing_time_obj = datetime.strptime(
                    self._config.get("briefing_time", "08:00"), "%H:%M"
                ).time()
            except ValueError:
                briefing_time_obj = datetime.strptime("08:00", "%H:%M").time()

            if current_time >= briefing_time_obj:
                self._config["last_briefing_date"] = today_str
                self._save_config()
                return True
        return False

    def generate_briefing_text(self) -> str:
        """Gera o texto completo do briefing matinal unindo os tópicos configurados."""
        from app.services.realtime import RealTimeService

        cfg = self.get_config()
        topics = cfg.get("briefing_topics", [])
        custom_instructions = cfg.get("custom_instructions", "")

        parts = ["Bom dia, Sir. Aqui está seu briefing matinal:"]

        if "weather" in topics:
            w = RealTimeService.get_weather()
            if w.get("ok"):
                parts.append(
                    f"O clima em {w['city']} é de {w['temp_c']}°C com {w['description']}. "
                    f"A máxima hoje será de {w['temp_max']}°C e a mínima de {w['temp_min']}°C."
                )

        if "news" in topics:
            n = RealTimeService.get_news(limit=3)
            if n.get("ok") and n.get("news"):
                headlines = "; ".join([item["title"] for item in n["news"][:3]])
                parts.append(f"As principais notícias de hoje são: {headlines}.")

        if "finance" in topics:
            fin_data = RealTimeService.get_finance()
            if fin_data.get("ok"):
                curr = fin_data.get("currencies", {})
                usd = curr.get("USD", {})
                btc = curr.get("BTC", {})
                if usd and btc:
                    parts.append(
                        f"No mercado financeiro, o Dólar está cotado a R$ {usd.get('bid', 0):.2f} "
                        f"e o Bitcoin a R$ {btc.get('bid', 0):.2f}."
                    )

        if "holidays" in topics:
            h = RealTimeService.get_holidays()
            if h.get("ok") and h.get("holidays"):
                today = datetime.now().strftime("%Y-%m-%d")
                upcoming = [item for item in h["holidays"] if item.get("date", "") >= today][:2]
                if upcoming:
                    next_h = upcoming[0]
                    parts.append(f"O próximo feriado nacional é {next_h['name']} no dia {next_h['date']}.")

        if custom_instructions:
            parts.append(f"Observação customizada: {custom_instructions}")

        parts.append("Tenho mais alguma instrução para hoje, Sir?")
        return "\n\n".join(parts)


class ProactiveDaemon(threading.Thread):
    """
    Thread em background que monitora agendamentos de briefing e lembretes.
    Usa threading.Event para parada instantânea em vez de time.sleep() bloqueante.
    """

    def __init__(
        self,
        proactive_service: ProactiveService,
        on_notify: Callable[[str, str], None] | None = None,
        interval_seconds: int = 15,
    ) -> None:
        super().__init__(daemon=True, name="ProactiveDaemon")
        self.service = proactive_service
        self.on_notify = on_notify
        self.interval = interval_seconds
        self._stop_event = threading.Event()

    def stop(self) -> None:
        """Para o daemon imediatamente (sem aguardar o próximo ciclo de sleep)."""
        self._stop_event.set()

    def run(self) -> None:
        print("[ProactiveDaemon] Iniciado servidor proativo em background.")
        while not self._stop_event.is_set():
            try:
                if self.service.check_briefing_due():
                    if self._stop_event.is_set():
                        break
                    briefing_text = self.service.generate_briefing_text()
                    print("[ProactiveDaemon] Disparando Briefing Matinal!")
                    if self.on_notify and not self._stop_event.is_set():
                        self.on_notify("Briefing Matinal", briefing_text)

                if self._stop_event.is_set():
                    break

                due_reminders = self.service.check_due_reminders()
                for r in due_reminders:
                    if self._stop_event.is_set():
                        break
                    msg = f"Sir, um lembrete: {r['message']}"
                    print(f"[ProactiveDaemon] Disparando Lembrete: {r['message']}")
                    if self.on_notify:
                        self.on_notify("Lembrete", msg)

            except Exception as e:
                print(f"[ProactiveDaemon] Erro na verificação: {e}")

            self._stop_event.wait(timeout=self.interval)

