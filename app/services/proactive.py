"""Serviço Proativo do Jarvis — Briefing matinal customizável e Lembretes temporizados por voz."""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

try:
    from app.services.calendar import CalendarService as _CalendarService
except Exception:
    _CalendarService = None  # type: ignore[assignment,misc]

CONFIG_PATH = Path("data/proactive_config.json")


SESSION_MEMORY_PATH = Path("data/session_memory.json")


class ProactiveService:
    """
    Gerencia a configuração do assistente proativo, agendamento de lembretes,
    Session Memory (continuidade do dia anterior) e monitoramento de tópicos.
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
            "briefing_topics": ["weather", "news", "finance", "holidays", "lifeos"],
            "custom_instructions": "",
            "last_briefing_date": "",
            "reminders": [],
            "monitored_topics": [],
            "seen_headlines": [],
            "cooldown_minutes": 20,
            "last_interaction_timestamp": 0,
        }

    def save_session_summary(self, summary: str) -> None:
        """Salva um resumo da sessão ativa para inclusão no briefing do dia seguinte (Session Memory)."""
        summary = (summary or "").strip()
        if not summary:
            return
        try:
            SESSION_MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(SESSION_MEMORY_PATH, "w", encoding="utf-8") as f:
                json.dump({
                    "summary": summary,
                    "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "consumed": False,
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ProactiveService] Erro ao salvar Session Memory: {e}")

    def get_yesterday_summary(self, consume: bool = True) -> str:
        """Obtém o resumo da sessão anterior para ser mencionado no briefing matinal."""
        if not SESSION_MEMORY_PATH.exists():
            return ""
        try:
            with open(SESSION_MEMORY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("consumed") and consume:
                return ""
            summary = data.get("summary", "")
            if consume and summary:
                data["consumed"] = True
                with open(SESSION_MEMORY_PATH, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            return summary
        except Exception:
            return ""

    def add_monitored_topic(self, topic: str) -> bool:
        """Adiciona um tópico para monitoramento em segundo plano (Watchdog)."""
        topic = (topic or "").strip()
        if not topic:
            return False
        with self._lock:
            topics = self._config.setdefault("monitored_topics", [])
            if topic not in topics:
                topics.append(topic)
                self._save_config()
                return True
        return False

    def remove_monitored_topic(self, topic: str) -> bool:
        with self._lock:
            topics = self._config.get("monitored_topics", [])
            if topic in topics:
                topics.remove(topic)
                self._save_config()
                return True
        return False

    def check_monitored_topics_updates(self) -> list[str]:
        """Verifica se há novidades sobre os tópicos monitorados em segundo plano."""
        with self._lock:
            topics = self._config.get("monitored_topics", [])
            seen = set(self._config.get("seen_headlines", []))

        if not topics:
            return []

        updates = []
        from app.agent.tools.web_search import WebSearchTool
        search_tool = WebSearchTool()

        for topic in topics:
            try:
                res = search_tool.execute({"query": topic, "max_results": 2})
                if res.ok and res.data and "results" in res.data:
                    for item in res.data["results"]:
                        title = item.get("title", "")
                        if title and title not in seen:
                            seen.add(title)
                            updates.append(f"Tópico [{topic}]: {title}")
            except Exception:
                pass

        if updates:
            with self._lock:
                self._config["seen_headlines"] = list(seen)[-100:]  # Mantém as últimas 100
                self._save_config()

        return updates

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

    def check_uncompleted_habits(self) -> str | None:
        """Verifica hábitos pendentes no período noturno (após 20h) e retorna alerta, uma vez por dia."""
        now = datetime.now()
        if now.hour < 20:
            return None
        today_str = now.strftime("%Y-%m-%d")
        with self._lock:
            last_check = self._config.get("last_habit_alert_date", "")
            if last_check == today_str:
                return None
        try:
            from app.services.habits import HabitService
            habits = HabitService.list_habits()
            pending = [h["name"] for h in habits if not h.get("completed_today")]
            if pending:
                with self._lock:
                    self._config["last_habit_alert_date"] = today_str
                    self._save_config()
                names = ", ".join(pending[:3])
                extra = f" e mais {len(pending) - 3}" if len(pending) > 3 else ""
                return f"Sir, você ainda tem {len(pending)} hábito(s) pendente(s) hoje: {names}{extra}. Deseja concluí-los agora?"
        except Exception:
            pass
        return None

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

            # Limite de horário: briefing só dispara até as 9AM
            briefing_cutoff = datetime.strptime("09:00", "%H:%M").time()

            # Só dispara se estiver no horário válido (de briefing_time até 9AM)
            if briefing_time_obj <= current_time <= briefing_cutoff:
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

        # Session Memory: Recao do dia anterior (Mark-L)
        yesterday_summary = self.get_yesterday_summary(consume=True)
        if yesterday_summary:
            parts.append(f"🗓️ Resumo do seu progresso anterior: {yesterday_summary}")

        # Updates dos tópicos monitorados em segundo plano
        topic_updates = self.check_monitored_topics_updates()
        if topic_updates:
            parts.append("👁️ Novidades nos tópicos monitorados em segundo plano:\n" + "\n".join(f"- {up}" for up in topic_updates))

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

        # Life OS (Evolute): Hábitos, Sequências, Hidratação, Treino e Fala Motivacional
        try:
            from app.services.lifeos import LifeOSService
            if "lifeos" in topics or LifeOSService.get_db_path().exists():
                lifeos_summary = LifeOSService.get_daily_summary()
                if lifeos_summary.get("ok"):
                    habits = lifeos_summary.get("habits", {})
                    water = lifeos_summary.get("water", {})
                    workout = lifeos_summary.get("workout", {})
                    motivational = lifeos_summary.get("motivational", {})

                    lifeos_lines = ["⚡ Life OS & Disciplina:"]
                    
                    # Streaks destacados
                    top_streaks = [h for h in habits.get("items", []) if h.get("streak", 0) > 0]
                    if top_streaks:
                        top_streaks_sorted = sorted(top_streaks, key=lambda x: x.get("streak", 0), reverse=True)[:3]
                        streak_strs = [f"{h['title']} ({h['streak']} dias seguidos)" for h in top_streaks_sorted]
                        lifeos_lines.append(f"- Seus streaks em alta: {', '.join(streak_strs)}.")
                    
                    # Hidratação
                    lifeos_lines.append(f"- Meta de hidratação: {water.get('current_ml', 0)}ml de {water.get('target_ml', 3000)}ml programados.")
                    
                    # Treino
                    if workout.get("is_rest_day"):
                        lifeos_lines.append("- Treino de hoje: Dia de descanso ativo / recuperação.")
                    else:
                        lifeos_lines.append(f"- Treino programado: {workout.get('split_name', 'Treino Geral')}.")

                    parts.append("\n".join(lifeos_lines))

                    # Fala Motivacional do Jarvis
                    if motivational and motivational.get("speech"):
                        parts.append(f"💡 Mensagem Inspiradora do Dia:\n{motivational['speech']}")
        except Exception:
            pass

        if custom_instructions:
            parts.append(f"Observação customizada: {custom_instructions}")

        parts.append("Tenho mais alguma instrução para hoje, Sir?")
        full_text = "\n\n".join(parts)

        # Truncar para limite do Windows System Tray (256 caracteres)
        # Mantém título e parte do corpo
        max_length = 256
        if len(full_text) > max_length:
            full_text = full_text[:max_length - 3] + "..."
        
        return full_text


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

                if self._stop_event.is_set():
                    break

                # Proactive habit check
                habit_msg = self.service.check_uncompleted_habits()
                if habit_msg and not self._stop_event.is_set():
                    print(f"[ProactiveDaemon] Disparando Alerta de Hábitos: {habit_msg}")
                    if self.on_notify:
                        self.on_notify("Lembrete de Hábitos", habit_msg)

                # Calendar reminders — use pre-imported service to avoid import delay
                if _CalendarService is not None:
                    for event in _CalendarService().due_reminders():
                        if self._stop_event.is_set():
                            break
                        msg = f"Sir, lembrete: {event.title}."
                        if event.reminder_policy == "until_confirmed":
                            msg += " Quando puder, confirme ou peça para eu parar de lembrar."
                        if self.on_notify:
                            self.on_notify("Calendário Jarvis", msg)

            except Exception as e:
                print(f"[ProactiveDaemon] Erro na verificação: {e}")

            self._stop_event.wait(timeout=self.interval)
