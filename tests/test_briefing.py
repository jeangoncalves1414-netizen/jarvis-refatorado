"""Testes para o Serviço de Briefing Matinal, Debriefing Noturno e Templates de Rotina."""
from datetime import datetime
import pytest

from app.agent.personas import update_persona, reset_persona
from app.services.briefing import (
    generate_morning_briefing,
    generate_evening_debriefing,
    _format_date_pt,
)
from app.routines.templates import (
    list_routine_templates,
    get_routine_template,
    install_routine_template,
)


@pytest.fixture(autouse=True)
def isolated_briefing_dir(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("JARVIS_DATA_DIR", str(data_dir))
    reset_persona()
    yield data_dir


def test_format_date_pt():
    dt = datetime(2026, 11, 9, 8, 30)
    formatted = _format_date_pt(dt)
    assert "segunda-feira" in formatted
    assert "9 de novembro de 2026" in formatted


def test_morning_briefing_with_challenge():
    update_persona({
        "name": "Jarvis",
        "tone": "amigável",
        "morning_challenge": {
            "enabled": True,
            "text": "15 flexões e 20 polichinelos",
        },
    })
    dt = datetime(2026, 11, 9, 7, 0)
    text = generate_morning_briefing(now=dt)

    # 1. Saudação
    assert "Jarvis" in text
    assert "Bom dia" in text

    # 2. Data e Clima
    assert "segunda-feira" in text
    assert "novembro" in text
    assert "Clima" in text

    # 3. Hábitos / Tarefas
    assert "hábito" in text.lower() or "tarefa" in text.lower()

    # 4. Desafio matinal ativo
    assert "15 flexões e 20 polichinelos" in text

    # 5. Ação de despertar
    assert "despertar" in text.lower()


def test_morning_briefing_without_challenge():
    update_persona({
        "name": "Sexta-Feira",
        "tone": "militar",
        "morning_challenge": {
            "enabled": False,
            "text": "10 flexões",
        },
    })
    dt = datetime(2026, 11, 9, 6, 0)
    text = generate_morning_briefing(now=dt)

    assert "Sexta-Feira" in text
    assert "tático" in text.lower() or "reportando" in text.lower()
    # Desafio NÃO deve aparecer quando desativado
    assert "10 flexões" not in text


def test_morning_briefing_tones():
    tones = ["formal", "bem-humorado", "militar", "sarcástico leve"]
    for tone in tones:
        update_persona({"name": "TestBot", "tone": tone})
        text = generate_morning_briefing()
        assert "TestBot" in text
        assert len(text) > 50


def test_evening_debriefing():
    update_persona({"name": "Jarvis", "tone": "sarcástico leve"})
    dt = datetime(2026, 11, 9, 22, 0)
    text = generate_evening_debriefing(now=dt)

    # 1. Resumo de progresso
    assert "Fechamento do dia" in text or "balanço" in text.lower()
    # 2. Alarme proposto
    assert "alarme" in text.lower() or "despertador" in text.lower()


def test_routine_templates():
    templates = list_routine_templates()
    assert len(templates) >= 2

    ids = [t["id"] for t in templates]
    assert "morning_wake_up" in ids
    assert "evening_debrief" in ids

    morning = get_routine_template("morning_wake_up")
    assert morning is not None
    assert morning["name"] == "Despertar Matinal"
    assert any(tr["type"] == "daily" for tr in morning["triggers"])
    assert any(st["tool"] == "spotify" for st in morning["steps"])

    evening = get_routine_template("evening_debrief")
    assert evening is not None
    assert evening["name"] == "Encerramento do Dia"
    assert any(tr["type"] == "daily" for tr in evening["triggers"])


def test_install_routine_template():
    class MockRoutineService:
        def __init__(self):
            self.created = []

        def create(self, payload):
            self.created.append(payload)
            return {"id": "mock_123", **payload}

    svc = MockRoutineService()
    res = install_routine_template("morning_wake_up", service=svc)
    assert res["id"] == "mock_123"
    assert res["name"] == "Despertar Matinal"
    assert len(svc.created) == 1
