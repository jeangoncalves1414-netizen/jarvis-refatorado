"""Testes de Hábitos Modulares por Dia da Semana e Auto-Check Contextual.

100% isolado de data/ real, utilizando tmp_path.
"""
from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

import pytest

from app.agent.tools.lifestyle_tools import HabitTool
from app.services import habits
from app.services.habits import (
    CANONICAL_WEEK_DAYS,
    HabitService,
    normalize_day,
    normalize_days_list,
)


@pytest.fixture
def isolated_lifestyle_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, isolated_lote6_data):
    """Garante que habits use um banco SQLite em tmp_path."""
    db_file = tmp_path / "lifestyle.db"
    monkeypatch.setattr(habits, "DB_PATH", db_file)
    habits.init_db()
    return db_file


def test_days_of_week_normalization():
    """Testa normalização flexível de dias da semana (inteiros, pt-BR e inglês)."""
    # Inteiros 0, 2, 4 -> mon, wed, fri
    assert normalize_days_list([0, 2, 4]) == ["mon", "wed", "fri"]

    # Abreviações em português: seg, qua, sex
    assert normalize_days_list(["seg", "qua", "sex"]) == ["mon", "wed", "fri"]

    # Nomes completos em português
    assert normalize_days_list(["segunda-feira", "quarta-feira", "sexta-feira"]) == ["mon", "wed", "fri"]

    # Nomes em inglês
    assert normalize_days_list(["mon", "wed", "fri"]) == ["mon", "wed", "fri"]

    # Valores mistos e índices
    assert normalize_days_list(["ter", 5, "domingo"]) == ["tue", "sat", "sun"]


def test_create_habit_with_modular_days_and_slots(isolated_lifestyle_db: Path):
    """Testa criação de hábito com dias em português/inteiros e slots modulares de substituição."""
    # 1. Hábito de Estudo com slots diferentes por dia
    # Segunda: 20min de inglês; Terça: 30min de xadrez
    study_habit = HabitService.create_habit(
        habit_id="habit_study",
        name="Estudo Focado",
        category="estudos",
        routine_block="morning",
        days_of_week=["seg", "ter", "qua"],  # aceita português
        day_slots={
            "mon": "20min de inglês",
            "tue": "30min de xadrez",
            "wed": {"title": "Revisão Feynman", "notes": "Física e Matemática"},
        },
    )

    assert study_habit is not None
    assert study_habit["days_of_week"] == ["mon", "tue", "wed"]
    assert "mon" in study_habit["day_slots"]
    assert study_habit["day_slots"]["mon"] == "20min de inglês"
    assert study_habit["day_slots"]["tue"] == "30min de xadrez"

    # Slot por método
    slot_seg = HabitService.get_slot_for_day("habit_study", "seg")
    assert slot_seg == "20min de inglês"
    slot_ter = HabitService.get_slot_for_day("habit_study", 1)  # 1 = terça = tue
    assert slot_ter == "30min de xadrez"

    # 2. Hábito de Treino Dinâmico com grupos musculares por dia
    workout_habit = HabitService.create_habit(
        habit_id="habit_workout",
        name="Musculação",
        category="saúde",
        routine_block="afternoon",
        days_of_week=[0, 2, 4],  # aceita inteiros (Seg, Qua, Sex)
        day_slots={
            "mon": {"title": "Treino A", "muscle_group": "Peito e Tríceps"},
            "wed": {"title": "Treino B", "muscle_group": "Costas e Bíceps"},
            "fri": {"title": "Treino C", "muscle_group": "Pernas e Ombros"},
        },
    )

    assert workout_habit["days_of_week"] == ["mon", "wed", "fri"]
    wed_slot = HabitService.get_slot_for_day("habit_workout", "qua")
    assert isinstance(wed_slot, dict)
    assert wed_slot["muscle_group"] == "Costas e Bíceps"

    # Atualiza slot de sexta
    HabitService.set_day_slot("habit_workout", "sex", {"title": "Treino Full Body", "muscle_group": "Corpo Inteiro"})
    updated_workout = HabitService.get_habit("habit_workout")
    assert updated_workout["day_slots"]["fri"]["muscle_group"] == "Corpo Inteiro"


def test_contextual_auto_check(isolated_lifestyle_db: Path, monkeypatch: pytest.MonkeyPatch):
    """Testa o auto-check contextual (saudação matinal, água, treino)."""
    # Força a data do sistema para uma data fixa (segunda-feira)
    fixed_monday = datetime.date(2026, 11, 9)  # 2026-11-09 é Segunda-feira (weekday == 0, 'mon')
    class FakeDate(datetime.date):
        @classmethod
        def today(cls):
            return fixed_monday

    monkeypatch.setattr(datetime, "date", FakeDate)
    monkeypatch.setattr("app.services.habits.date", FakeDate)

    # Cria hábitos programados para segunda-feira
    HabitService.create_habit(
        habit_id="habit_wake",
        name="Acordar cedo",
        routine_block="morning",
        days_of_week=["mon", "tue", "wed", "thu", "fri"],
    )
    HabitService.create_habit(
        habit_id="habit_water",
        name="Beber água (3L)",
        category="saúde",
        days_of_week=["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
    )
    HabitService.create_habit(
        habit_id="habit_reading",
        name="Leitura noturna",
        routine_block="evening",
        days_of_week=["mon", "wed", "fri"],
    )

    # Verifica que nenhum está concluído ainda hoje
    assert HabitService.is_completed_today("habit_wake") is False
    assert HabitService.is_completed_today("habit_water") is False

    # 1. Simula saudação matinal do usuário
    checked = HabitService.contextual_auto_check(text="Bom dia, Jarvis! Acabei de acordar.")
    assert len(checked) == 1
    assert checked[0]["id"] == "habit_wake"
    assert HabitService.is_completed_today("habit_wake") is True
    # Hábito de leitura não deve ter sido afetado
    assert HabitService.is_completed_today("habit_reading") is False

    # Segunda saudação não deve re-marcar (já concluído)
    checked_again = HabitService.contextual_auto_check(text="Bom dia!")
    assert len(checked_again) == 0

    # 2. Simula ingestão de água
    checked_water = HabitService.contextual_auto_check(text="Bebi água agora, mais um copo.")
    assert len(checked_water) == 1
    assert checked_water[0]["id"] == "habit_water"
    assert HabitService.is_completed_today("habit_water") is True


def test_habit_tool_modular_and_auto_check(isolated_lifestyle_db: Path, monkeypatch: pytest.MonkeyPatch):
    """Testa HabitTool com dias em português, slots e ação auto_check."""
    fixed_monday = datetime.date(2026, 11, 9)
    class FakeDate(datetime.date):
        @classmethod
        def today(cls):
            return fixed_monday

    monkeypatch.setattr(datetime, "date", FakeDate)
    monkeypatch.setattr("app.services.habits.date", FakeDate)

    tool = HabitTool()

    # Cria hábito via tool passando dias em pt-BR
    res_create = tool.run(
        action="create",
        name="Acordar às 06h",
        category="rotina",
        routine_block="morning",
        days_of_week=["seg", "qua", "sex"],
        day_slots={"mon": "Alongamento matinal", "wed": "Respiração guiada"},
    )
    assert res_create["ok"] is True
    habit = res_create["habit"]
    assert habit["days_of_week"] == ["mon", "wed", "fri"]
    assert habit["day_slots"]["mon"] == "Alongamento matinal"

    # Executa auto_check via HabitTool
    res_auto = tool.run(action="auto_check", name="Bom dia Jarvis")
    assert res_auto["ok"] is True
    assert len(res_auto["checked_habits"]) == 1
    assert res_auto["checked_habits"][0]["id"] == habit["id"]

