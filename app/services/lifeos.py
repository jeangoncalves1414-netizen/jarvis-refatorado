"""Life OS (Evolute) Integration Service.

Gerencia a leitura, sincronização atômica e atualizações de dados do Life OS
(hábitos, hidratação, treinos, estudos e reflexões estóicas) para o ecossistema Jarvis.
"""
from __future__ import annotations

import json
import os
import random
import threading
from functools import wraps
from datetime import datetime, date
from pathlib import Path
from typing import Any

# Localização prioritária: pasta de documentos original do usuário
_DOCUMENTS_DB = Path(os.path.expanduser("~")) / "Documents" / "Evolute" / "data" / "lifeos_db.json"
_LOCAL_DB = Path(__file__).resolve().parents[2] / "data" / "lifeos_db.json"

_DB_LOCK = threading.RLock()
def _serialized(method):
    @wraps(method)
    def wrapped(*args, **kwargs):
        with _DB_LOCK:
            return method(*args, **kwargs)
    return wrapped


# Catálogo de citações e falas motivacionais do Jarvis (Estóica + Alta Performance + Stark)
MOTIVATIONAL_SPEECHES = [
    {
        "quote": "A disciplina é a distância exata entre os seus objetivos e a sua realidade. Não negocie com a fraqueza hoje.",
        "author": "Marco Aurélio",
        "action": "Ataque as tarefas mais difíceis logo no primeiro bloco da manhã."
    },
    {
        "quote": "Não é porque as coisas são difíceis que não ousamos; é porque não ousamos que elas se tornam difíceis.",
        "author": "Sêneca",
        "action": "Mantenha sua cadência e confie no processo que você desenhou."
    },
    {
        "quote": "Primeiro diga a si mesmo o que você deseja ser; em seguida, faça o que precisa ser feito.",
        "author": "Epicteto",
        "action": "Cada hábito marcado hoje é um voto na identidade de quem você escolheu ser."
    },
    {
        "quote": "A mente humana tem uma capacidade extraordinária de adaptação. Quando você acha que chegou ao seu limite, você usou apenas 40% do seu potencial.",
        "author": "Mentalidade Stark / Goggins",
        "action": "Dobre a aposta na sua hidratação e no foco hoje. Sem desculpas."
    },
    {
        "quote": "A constância não se mede nos dias em que você acorda inspirado, mas sim nos dias em que você age apesar da hesitação.",
        "author": "Filosofia Estóica",
        "action": "Execute o treino e a leitura programada como um compromisso inegociável."
    },
    {
        "quote": "Nós somos aquilo que fazemos repetidamente. A excelência, portanto, não é um ato isolado, mas um hábito.",
        "author": "Aristóteles",
        "action": "Proteja seus streaks no Life OS como se fossem sua armadura."
    },
    {
        "quote": "Você não pode controlar os ventos lá fora, Sir, mas tem controle absoluto sobre o leme da sua mente e suas ações hoje.",
        "author": "Jarvis",
        "action": "Mantenha o foco cirúrgico no que depende exclusivamente de você."
    }
]


class LifeOSService:
    @staticmethod
    def get_db_path() -> Path:
        """Retorna o caminho seguro do arquivo lifeos_db.json."""
        if _DOCUMENTS_DB.parent.exists():
            _DOCUMENTS_DB.parent.mkdir(parents=True, exist_ok=True)
            return _DOCUMENTS_DB
        _LOCAL_DB.parent.mkdir(parents=True, exist_ok=True)
        return _LOCAL_DB

    @classmethod
    def load_db(cls) -> dict[str, Any]:
        """Carrega os dados completos do lifeos_db.json com tolerância a falhas."""
        db_path = cls.get_db_path()
        with _DB_LOCK:
            if not db_path.exists():
                return {"data": {}, "updatedAt": 0}
            try:
                content = db_path.read_text(encoding="utf-8")
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    return parsed
                return {"data": {}, "updatedAt": 0}
            except Exception:
                return {"data": {}, "updatedAt": 0}

    @classmethod
    def save_db(cls, payload: dict[str, Any]) -> bool:
        """Salva os dados de forma atômica no banco."""
        db_path = cls.get_db_path()
        with _DB_LOCK:
            try:
                db_path.parent.mkdir(parents=True, exist_ok=True)
                temp_file = db_path.with_suffix(".tmp")
                content = json.dumps(payload, indent=2, ensure_ascii=False)
                temp_file.write_text(content, encoding="utf-8")
                # Substituição atômica no Windows
                if temp_file.exists():
                    temp_file.replace(db_path)
                return True
            except Exception:
                return False

    @classmethod
    def get_data_bucket(cls) -> dict[str, Any]:
        """Retorna apenas o dicionário 'data' do banco."""
        raw = cls.load_db()
        data = raw.get("data")
        if isinstance(data, dict):
            return data
        return {}

    @classmethod
    def save_data_bucket(cls, data_bucket: dict[str, Any]) -> bool:
        """Salva o dicionário 'data' atualizado com timestamp."""
        now_ms = max(int(datetime.now().timestamp() * 1000), int(cls.load_db().get("updatedAt") or 0) + 1)
        payload = {
            "data": data_bucket,
            "updatedAt": now_ms
        }
        return cls.save_db(payload)

    @classmethod
    def get_today_str(cls) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    @classmethod
    def get_daily_summary(cls, date_str: str | None = None) -> dict[str, Any]:
        """
        Retorna o resumo consolidado do dia para o briefing matinal e Live HUD:
        - Hábitos (total, concluídos hoje, taxa, streaks principais)
        - Água (consumo atual, meta diária, percentual)
        - Treino do dia (split da semana e se foi concluído)
        - Minutos de estudo registrados
        - Fala motivacional do Jarvis
        """
        today = date_str or cls.get_today_str()
        bucket = cls.get_data_bucket()

        # 1. Hábitos
        habits_list = bucket.get("lifeos_habits") or []
        hlog_key = f"lifeos_hlog_{today}"
        hlog = bucket.get(hlog_key) or {}

        from app.services.personal_habits import PersonalHabits
        rows = PersonalHabits.list_habits(day=today, scheduled=True)
        habits_summary = [
            {"id": h["id"], "title": h["name"], "streak": h["current_streak"], "bestStreak": h["best_streak"],
             "connectedTo": h.get("connectedTo"), "completed_today": h["completed_today"], "isPriority": h["isPriority"]}
            for h in rows
        ]
        completed_count = sum(h["completed_today"] for h in habits_summary)
        water_target = next((int(h["targetValue"]) for h in habits_list
                             if h.get("connectedTo") == "agua" and h.get("targetValue")), 3000)

        total_habits = len(habits_summary)
        habits_rate = round((completed_count / total_habits * 100) if total_habits > 0 else 0)
        priority_habits = [h for h in habits_summary if h.get("isPriority")]
        priority_completed = len([h for h in priority_habits if h.get("completed_today")])

        # 2. Água
        water_key = f"lifeos_water_{today}"
        water_ml = int(bucket.get(water_key) or 0)
        water_pct = round((water_ml / water_target * 100) if water_target > 0 else 0)

        # 3. Treino do dia
        weekday = datetime.strptime(today, "%Y-%m-%d").weekday() # 0 = Segunda, 6 = Domingo
        split_list = bucket.get("lifeos_workout_split") or [
            {"dayOfWeek": 1, "dayName": "Segunda-feira", "muscleGroups": "Peito, Ombros e Tríceps", "isRestDay": False},
            {"dayOfWeek": 2, "dayName": "Terça-feira", "muscleGroups": "Costas e Bíceps", "isRestDay": False},
            {"dayOfWeek": 3, "dayName": "Quarta-feira", "muscleGroups": "Pernas e Panturrilhas", "isRestDay": False},
            {"dayOfWeek": 4, "dayName": "Quinta-feira", "muscleGroups": "Ombros e Abdômen", "isRestDay": False},
            {"dayOfWeek": 5, "dayName": "Sexta-feira", "muscleGroups": "Braços e Cardio Intenso", "isRestDay": False},
            {"dayOfWeek": 6, "dayName": "Sábado", "muscleGroups": "Mobilidade e Força Funcional", "isRestDay": False},
            {"dayOfWeek": 0, "dayName": "Domingo", "muscleGroups": "Descanso Ativo / Recuperação", "isRestDay": True},
        ]
        # Converte weekday python (0=Seg) para split dayOfWeek (1=Seg, 0=Dom)
        split_day_num = (weekday + 1) % 7
        today_split = next((s for s in split_list if s.get("dayOfWeek") == split_day_num), None)

        workouts_all = bucket.get("lifeos_workouts") or []
        today_workouts = [w for w in workouts_all if w.get("date") == today]
        sessions = bucket.get('lifeos_workout_sessions') or []
        workout_done = any(w.get('completed', True) for w in today_workouts) or any(w.get('date') == today and w.get('completed') for w in sessions)

        # 4. Estudos
        study_logs = bucket.get("lifeos_study_logs") or []
        today_studies = [s for s in study_logs if s.get("date") == today]
        study_minutes = sum(int(s.get("minutes") or 0) for s in today_studies)

        # 5. Fala Motivacional
        motivational = cls.generate_motivational_speech({
            "habits_summary": habits_summary,
            "completed_count": completed_count,
            "total_habits": total_habits,
            "water_ml": water_ml,
            "water_target": water_target,
            "workout_done": workout_done
        })

        return {
            "ok": True,
            "date": today,
            "water": {
                "current_ml": water_ml,
                "target_ml": water_target,
                "percentage": water_pct
            },
            "habits": {
                "total": total_habits,
                "completed": completed_count,
                "rate_percentage": habits_rate,
                "items": habits_summary,
                "priority_total": len(priority_habits),
                "priority_completed": priority_completed
            },
            "workout": {
                "split_name": today_split.get("muscleGroups", "Treino Geral") if today_split else "Treino Geral",
                "is_rest_day": bool(today_split.get("isRestDay", False)) if today_split else False,
                "completed": workout_done
            },
            "study": {
                "minutes_today": study_minutes,
                "sessions_count": len(today_studies)
            },
            "motivational": motivational
        }

    @classmethod
    @_serialized
    def add_water(cls, amount_ml: int, date_str: str | None = None) -> dict[str, Any]:
        """Adiciona consumo de água ao dia de hoje e atualiza hábito correspondente."""
        today = date_str or cls.get_today_str()
        bucket = cls.get_data_bucket()

        water_key = f"lifeos_water_{today}"
        current = int(bucket.get(water_key) or 0)
        new_amount = max(0, current + amount_ml)
        bucket[water_key] = new_amount

        # Verifica hábito de água
        habits = bucket.get("lifeos_habits") or []
        water_habit = next((h for h in habits if h.get("connectedTo") == "agua"), None)
        target_ml = 3000
        habit_completed = False

        if water_habit:
            target_ml = int(water_habit.get("targetValue") or 3000)
            h_id = water_habit.get("id")
            if h_id:
                hlog_key = f"lifeos_hlog_{today}"
                hlog = bucket.get(hlog_key) or {}
                was_completed = bool(hlog.get(h_id, {}).get("completed", False))

                if new_amount >= target_ml:
                    hlog[h_id] = {"completed": True, "value": new_amount}
                    habit_completed = True
                    if not was_completed:
                        # Incrementa streak do hábito
                        water_habit["streak"] = int(water_habit.get("streak") or 0) + 1
                        if water_habit["streak"] > int(water_habit.get("bestStreak") or 0):
                            water_habit["bestStreak"] = water_habit["streak"]
                else:
                    hlog[h_id] = {"completed": False, "value": new_amount}

                bucket[hlog_key] = hlog

        cls.save_data_bucket(bucket)

        pct = round((new_amount / target_ml * 100) if target_ml > 0 else 0)
        return {
            "ok": True,
            "added_ml": amount_ml,
            "total_ml": new_amount,
            "target_ml": target_ml,
            "percentage": pct,
            "habit_completed": habit_completed
        }

    @classmethod
    @_serialized
    def set_water(cls, total_ml: int, date_str: str | None = None) -> dict[str, Any]:
        """Define o total de água do dia ("bebi 3 L hoje"); reutiliza ``add_water`` com a diferença."""
        today = date_str or cls.get_today_str()
        previous = int(cls.get_data_bucket().get(f"lifeos_water_{today}") or 0)
        result = cls.add_water(int(total_ml) - previous, date_str=today)
        result["previous_ml"] = previous
        return result

    @classmethod
    def toggle_habit(cls, habit_name_or_id: str, completed: bool = True, date_str: str | None = None) -> dict[str, Any]:
        """Marca ou desmarca um hábito pelo ID ou por busca de nome/termo."""
        today = date_str or cls.get_today_str()
        from app.services.personal_habits import PersonalHabits
        target = cls._resolve_habit(habit_name_or_id)
        if "error" in target:
            return target
        row = PersonalHabits.check_in(target["id"], today) if completed else PersonalHabits.uncheck_in(target["id"], today)
        return {"ok": True, "id": target["id"], "title": target["name"], "completed": completed,
                "changed": row["changed"], "streak": row["current_streak"], "bestStreak": row["best_streak"]}

    @classmethod
    def _resolve_habit(cls, reference: str) -> dict[str, Any]:
        from app.services.personal_habits import PersonalHabits, public_evolute_id
        from app.agent.tools.lifestyle_tools import resolve_by_name, normalize_name
        rows = PersonalHabits.list_habits()
        for key in (reference, public_evolute_id(reference)):
            direct = next((h for h in rows if h["id"] == key), None)
            if direct:
                return direct
        linked = [h for h in rows if h.get("connectedTo") and normalize_name(h["connectedTo"]) == normalize_name(reference)]
        if len(linked) == 1:
            return linked[0]
        try:
            return resolve_by_name(rows, reference, "name", kind="o hábito", allow_partial=True)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

    @classmethod
    @_serialized
    def toggle_habit_priority(cls, habit_name_or_id: str) -> dict[str, Any]:
        """Alterna o status de inegociável/prioridade de um hábito (ícone de coroa)."""
        from app.services.personal_habits import PersonalHabits
        target = cls._resolve_habit(habit_name_or_id)
        if "error" in target:
            return target
        row = PersonalHabits.update_habit(target["id"], isPriority=not target["isPriority"])
        return {"ok": True, "id": row["id"], "title": row["name"], "isPriority": row["isPriority"]}

    @classmethod
    @_serialized
    def log_workout(cls, workout_name: str, exercises: list | None = None, date_str: str | None = None) -> dict[str, Any]:
        """Registra uma sessão e aplica apenas relações explicitamente configuradas."""
        from app.services.personal_records import mutate
        result = mutate('workout', 'create', {'title': workout_name, 'exercises': exercises or [], 'date': date_str or cls.get_today_str()})
        return {'ok': result.ok, 'workout_id': result.data['record_id'], 'workout_name': workout_name, 'date': date_str or cls.get_today_str()}

    @classmethod
    def generate_motivational_speech(cls, context: dict[str, Any] | None = None) -> dict[str, str]:
        """
        Retorna uma fala motivacional de alto impacto formulada pelo Jarvis,
        combinando sabedoria estoica, disciplina implacável e foco nos objetivos.
        """
        item = random.choice(MOTIVATIONAL_SPEECHES)

        # Contextualização adicional com base em streaks do usuário
        extra_boost = ""
        if context:
            habits = context.get("habits_summary") or []
            high_streaks = [h for h in habits if h.get("streak", 0) >= 7]
            if high_streaks:
                top = max(high_streaks, key=lambda x: x.get("streak", 0))
                extra_boost = f" Você já construiu {top.get('streak')} dias consecutivos de disciplina em '{top.get('title')}'. Não quebre esse ritmo hoje."

        speech_text = (
            f"\"{item['quote']}\" — {item['author']}.{extra_boost} "
            f"Foco do dia: {item['action']}"
        )

        return {
            "quote": item["quote"],
            "author": item["author"],
            "action": item["action"],
            "speech": speech_text
        }
