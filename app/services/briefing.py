"""Serviço de Briefing Matinal e Debriefing Noturno do Jarvis."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.agent.personas import get_persona


DIAS_SEMANA = [
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
]

MESES = [
    "",
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]


def _format_date_pt(dt: datetime | None = None) -> str:
    now = dt or datetime.now()
    dia_semana = DIAS_SEMANA[now.weekday()]
    mes = MESES[now.month]
    return f"Hoje é {dia_semana}, {now.day} de {mes} de {now.year}."


def _get_weather(city: str = "São Paulo") -> str:
    try:
        from app.services.daily_briefing import fetch_weather
        return fetch_weather(city)
    except Exception:
        return f"Clima em {city}: Céu claro e temperatura agradável."


def _get_lifestyle_summary() -> tuple[str, int, int, int]:
    """Retorna (texto_resumo, total_habitos, habitos_concluidos, tarefas_pendentes)."""
    total_habits = 0
    completed_habits = 0
    pending_tasks = 0
    parts = []

    try:
        from app.services.habits import HabitService
        habits = HabitService.list_habits()
        total_habits = len(habits)
        completed_habits = sum(1 for h in habits if h.get("completed_today"))
        if habits:
            parts.append(f"Hábitos do dia: {completed_habits} de {total_habits} concluídos.")
        else:
            parts.append("Nenhum hábito específico agendado para hoje.")
    except Exception:
        parts.append("Hábitos: registro disponível no painel.")

    try:
        from app.services.tasks import TaskService
        tasks = TaskService.list_tasks(completed=False)
        pending_tasks = len(tasks)
        p1 = sum(1 for t in tasks if t.get("priority") == 1)
        if pending_tasks > 0:
            msg = f"Tarefas pendentes: {pending_tasks}"
            if p1 > 0:
                msg += f" (sendo {p1} de prioridade urgente P1)"
            parts.append(msg + ".")
        else:
            parts.append("Todas as tarefas principais estão em dia.")
    except Exception:
        pass

    return " ".join(parts), total_habits, completed_habits, pending_tasks


def generate_morning_briefing(city: str = "São Paulo", now: datetime | None = None) -> str:
    """Gera o texto falado do início do dia estruturado:
    1. Saudação personalizada com base na persona ativa.
    2. Data, dia da semana e clima atual.
    3. Resumo dos hábitos/tarefas do dia.
    4. O desafio matinal configurado (se ativado).
    5. Ação de despertar (ex: playlist de despertar).
    """
    persona = get_persona()
    name = persona.get("name", "Jarvis")
    tone = persona.get("tone", "amigável")
    challenge = persona.get("morning_challenge", {})

    dt = now or datetime.now()
    hour = dt.hour

    # 1. Saudação personalizada por tom
    if tone == "formal":
        greeting = f"Bom dia. Aqui é {name}. Apresento o briefing operacional para o início deste dia."
    elif tone == "militar":
        greeting = f"Atenção. {name} reportando às {hour:02d}:{dt.minute:02d}. Briefing tático matinal pronto para execução."
    elif tone == "bem-humorado":
        greeting = f"Bom dia! {name} na área. Hora de despertar, tomar aquele café turbinado e conquistar o dia!"
    elif tone == "sarcástico leve":
        greeting = f"Bom dia. {name} online e operando em plena capacidade, para variar. Vamos ver o que nos espera."
    else:  # amigável
        greeting = f"Bom dia! Sou {name}, seu assistente pessoal. Que você tenha um início de dia excelente e produtivo."

    # 2. Data, dia da semana e clima
    date_info = _format_date_pt(dt)
    weather_info = _get_weather(city)

    # 3. Resumo de hábitos e tarefas
    lifestyle_text, total_h, comp_h, pend_t = _get_lifestyle_summary()

    # 4. Desafio matinal (se ativado)
    challenge_part = ""
    if challenge.get("enabled"):
        ch_text = challenge.get("text", "10 polichinelos e 10 flexões")
        if tone == "militar":
            challenge_part = f"Diretriz de condicionamento físico: {ch_text}. Sem desculpas, execução imediata!"
        elif tone == "bem-humorado":
            challenge_part = f"Desafio matinal na mesa: {ch_text}. Seus músculos vão agradecer depois!"
        elif tone == "sarcástico leve":
            challenge_part = f"Quase esqueci do seu desafio físico: {ch_text}. Nada como um pouco de esforço para despertar."
        elif tone == "formal":
            challenge_part = f"Desafio matinal estabelecido para cumprimento: {ch_text}."
        else:
            challenge_part = f"Seu desafio matinal de hoje é: {ch_text}. Vamos lá, comece com toda disposição!"

    # 5. Ação de despertar
    if tone == "militar":
        wakeup_action = "Iniciando frequência sonora e sistemas táticos de prontidão."
    elif tone == "sarcástico leve":
        wakeup_action = "Playlist de despertar pronta no Spotify. Recomendo começar antes que a preguiça vença."
    elif tone == "bem-humorado":
        wakeup_action = "Soltando a trilha sonora de despertar para energizar a manhã!"
    elif tone == "formal":
        wakeup_action = "Playlist de despertar programada. Todos os subsistemas encontram-se operacionais."
    else:
        wakeup_action = "Preparando sua playlist de despertar no Spotify para dar o ritmo certo ao dia."

    sections = [greeting, f"{date_info} {weather_info}", lifestyle_text]
    if challenge_part:
        sections.append(challenge_part)
    sections.append(wakeup_action)

    return "\n\n".join(s for s in sections if s)


def generate_evening_debriefing(now: datetime | None = None) -> str:
    """Gera o fechamento do dia:
    1. Resumo do progresso de hábitos cumpridos e pendentes.
    2. Parabenização ou incentivo com base na persona ativa.
    3. Proposta de horário do alarme do dia seguinte.
    """
    persona = get_persona()
    name = persona.get("name", "Jarvis")
    tone = persona.get("tone", "amigável")

    lifestyle_text, total_h, comp_h, pend_t = _get_lifestyle_summary()

    # 1. Resumo do progresso
    if total_h > 0:
        progress_summary = f"No balanço de hoje, você concluiu {comp_h} de {total_h} hábitos planejados."
        if pend_t > 0:
            progress_summary += f" Restaram {pend_t} pendências de tarefas na sua fila de trabalho."
        else:
            progress_summary += " Nenhuma tarefa prioritária ficou pendente."
    else:
        progress_summary = "Fechamento do dia: todas as rotinas registradas foram concluídas."

    # 2. Parabenização ou incentivo
    high_success = (total_h > 0 and comp_h >= (total_h * 0.7)) or (total_h == 0 and pend_t == 0)

    if high_success:
        if tone == "militar":
            feedback = "Excelente disciplina tática. Objetivos cumpridos conforme o planejamento."
        elif tone == "bem-humorado":
            feedback = "Show de bola! O dia rendeu demais, mandou muito bem!"
        elif tone == "sarcástico leve":
            feedback = "Impressionante. Nem eu teria feito melhor hoje. Você merece uma pausa."
        elif tone == "formal":
            feedback = "Desempenho satisfatório nas atividades registradas. Encerramento de expediente recomendado."
        else:
            feedback = "Parabéns pela dedicação hoje! Você manteve uma ótima constância."
    else:
        if tone == "militar":
            feedback = "Houve pendências não sanadas. Reajuste de estratégia para o próximo ciclo."
        elif tone == "bem-humorado":
            feedback = "Nem todo dia é perfeito, mas amanhã a gente corre atrás e recupera com facilidade!"
        elif tone == "sarcástico leve":
            feedback = "Ficaram algumas coisas para trás, mas nada que comprometa a sobrevivência da espécie."
        elif tone == "formal":
            feedback = "Recomenda-se reagendamento dos itens pendentes para o início do próximo expediente."
        else:
            feedback = "Cada passo conta. O importante é manter o foco e descansar para recomeçar com calma amanhã."

    # 3. Proposta de alarme do dia seguinte
    if tone == "militar":
        alarm_proposal = "Sugestão tática de repouso: alarme para amanhã programado para as 06:30. Descanso autorizado."
    elif tone == "formal":
        alarm_proposal = "Proposta de alarme para amanhã às 07:00, assegurando intervalo adequado de descanso."
    elif tone == "bem-humorado":
        alarm_proposal = "Sugiro colocar o despertador para as 07:00 amanhã para acordar 100% renovado. Boa noite!"
    elif tone == "sarcástico leve":
        alarm_proposal = "Proponho alarme para as 07:00. Dormir também é necessário, até para humanos brilhantes."
    else:
        alarm_proposal = "Sugiro programar seu alarme para amanhã às 07:00 para manter sua rotina de sono equilibrada. Tenha uma ótima noite de descanso!"

    sections = [
        f"Fechamento do dia com {name}:",
        progress_summary,
        feedback,
        alarm_proposal,
    ]

    return "\n\n".join(sections)
