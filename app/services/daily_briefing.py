"""
Daily Briefing Service (inspired by Brahma AI Lite daily_briefing.py)
Generates a personalized morning/evening briefing with:
- Time-based greeting
- Real-time weather from wttr.in
- System metrics (CPU, RAM, disk)
- Today's calendar events
- Interruption support for TTS playback
"""
from __future__ import annotations

import json
import random
import urllib.request
from datetime import datetime
from typing import Any
import threading
import time

try:
    import psutil
    PSUTIL_OK = True
except ImportError:
    PSUTIL_OK = False


def get_time_greeting(name: str = "Senhor") -> str:
    hour = datetime.now().hour
    if 5 <= hour < 12:
        greeting = f"Bom dia, {name}."
    elif 12 <= hour < 18:
        greeting = f"Boa tarde, {name}."
    elif 18 <= hour < 23:
        greeting = f"Boa noite, {name}."
    else:
        greeting = f"Bem-vindo de volta, {name}."

    suffixes = [
        "Todos os sistemas estão online.",
        "Pronto para ajudar.",
        "Jarvis está operacional.",
        "Núcleo ativo e respondendo.",
    ]
    return f"{greeting} {random.choice(suffixes)}"


def fetch_weather(city: str = "São Paulo") -> str:
    """Busca clima atual via wttr.in (sem API key necessária)."""
    try:
        url = f"https://wttr.in/{city}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "JarvisCore/1.0"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        current = data.get("current_condition", [{}])[0]
        temp_c = current.get("temp_C", "?")
        weather_desc_list = current.get("weatherDesc", [])
        desc = weather_desc_list[0].get("value", "").lower() if weather_desc_list else ""

        chances = []
        for day in data.get("weather", [])[:1]:
            for h in day.get("hourly", []):
                v = h.get("chanceofrain")
                if v is not None:
                    try:
                        chances.append(int(v))
                    except ValueError:
                        pass

        rain = f", chance de {max(chances)}% de chuva" if chances and chances else ""
        return f"Clima em {city}: {temp_c}°C, {desc}{rain}."
    except Exception as exc:
        return f"Clima indisponível agora ({exc.__class__.__name__})."


def get_system_status() -> dict[str, Any]:
    """Coleta métricas do sistema atual (CPU, RAM, Disco)."""
    if not PSUTIL_OK:
        return {"cpu": None, "ram": None, "disk": None}

    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    # Usar path correto para cada OS
    import platform
    disk_path = "/" if platform.system() != "Windows" else "C:\\"
    disk = psutil.disk_usage(disk_path)

    return {
        "cpu_pct": round(cpu, 1),
        "ram_used_gb": round(ram.used / 1_073_741_824, 1),
        "ram_total_gb": round(ram.total / 1_073_741_824, 1),
        "ram_pct": round(ram.percent, 1),
        "disk_used_gb": round(disk.used / 1_073_741_824, 1),
        "disk_total_gb": round(disk.total / 1_073_741_824, 1),
        "disk_pct": round(disk.percent, 1),
    }


def format_system_status(status: dict[str, Any]) -> str:
    if not status.get("cpu_pct"):
        return "Métricas de sistema indisponíveis."
    return (
        f"CPU: {status['cpu_pct']}% | "
        f"RAM: {status['ram_used_gb']}/{status['ram_total_gb']} GB ({status['ram_pct']}%) | "
        f"Disco: {status['disk_used_gb']}/{status['disk_total_gb']} GB ({status['disk_pct']}%)"
    )


def get_today_calendar_summary() -> str:
    """Retorna um resumo rápido dos eventos de hoje do CalendarService."""
    try:
        from app.services.calendar import CalendarService
        events = CalendarService().get_today_events()
        if not events:
            return "Nenhum evento agendado para hoje."
        lines = []
        for ev in events[:5]:
            title = ev.get("title") or ev.get("name") or str(ev)
            time_str = ev.get("time") or ev.get("start_time") or ""
            lines.append(f"• {time_str} {title}".strip())
        return "Compromissos de hoje:\n" + "\n".join(lines)
    except Exception:
        return ""


def get_lifestyle_summary() -> str:
    parts = []
    try:
        from app.services.personal_habits import PersonalHabits as HabitService
        habits = HabitService.list_habits()
        completed = sum(1 for h in habits if h.get("completed_today"))
        if habits:
            parts.append(f"• Hábitos de hoje: {completed}/{len(habits)} concluídos.")
    except Exception:
        pass

    try:
        from app.services.tasks import TaskService
        tasks = TaskService.list_tasks(completed=False)
        p1_tasks = [t for t in tasks if t.get("priority") == 1]
        if tasks:
            msg = f"• Tarefas pendentes: {len(tasks)}"
            if p1_tasks:
                msg += f" ({len(p1_tasks)} urgentes P1)"
            parts.append(msg + ".")
    except Exception:
        pass

    return "\n".join(parts)


def generate_daily_briefing(name: str = "Senhor", city: str = "São Paulo") -> str:
    """Gera briefing diário completo (Brahma-inspired)."""
    sections = [
        get_time_greeting(name),
        fetch_weather(city),
        format_system_status(get_system_status()),
    ]

    lifestyle = get_lifestyle_summary()
    if lifestyle:
        sections.append(lifestyle)

    calendar = get_today_calendar_summary()
    if calendar:
        sections.append(calendar)

    return "\n\n".join(s for s in sections if s)


# ── Interruption Support ───────────────────────────────────────────────────────

_briefing_interrupted = False
_briefing_lock = threading.Lock()


def interrupt_briefing() -> None:
    """Sinaliza que o briefing deve ser interrompido."""
    global _briefing_interrupted
    with _briefing_lock:
        _briefing_interrupted = True


def reset_briefing_interrupt() -> None:
    """Reseta o sinal de interrupção."""
    global _briefing_interrupted
    with _briefing_lock:
        _briefing_interrupted = False


def is_briefing_interrupted() -> bool:
    """Verifica se o briefing foi interrompido."""
    with _briefing_lock:
        return _briefing_interrupted


def speak_briefing_with_interruption(
    text: str,
    speak_func,
    check_interval: float = 0.1
) -> bool:
    """
    Executa o TTS do briefing com suporte a interrupção.
    
    Args:
        text: Texto do briefing
        speak_func: Função de TTS que aceita texto como argumento
        check_interval: Intervalo de verificação de interrupção (segundos)
    
    Returns:
        True se completou com sucesso, False se foi interrompido
    """
    reset_briefing_interrupt()
    
    # Dividir em sentenças para permitir interrupção entre elas
    sentences = [s.strip() for s in text.split('.') if s.strip()]
    
    for sentence in sentences:
        if is_briefing_interrupted():
            print("[DailyBriefing] Playback interrompido pelo usuário")
            return False
        
        try:
            speak_func(sentence + ".")
            # Pequena pausa para verificar interrupção
            time.sleep(check_interval)
        except Exception as e:
            print(f"[DailyBriefing] Erro no TTS: {e}")
            continue
    
    return True
