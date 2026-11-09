import pytest

from app.agent.loop_policy import mentions_alarm, should_use_agent_loop, wait_intent

AUTO = {"mode": "auto"}


@pytest.mark.parametrize("text", [
    "abre o painel, adiciona ler e meditar nos hábitos, depois agenda dentista amanhã às 15h e depois coloca que bebi 3L de água hoje",
    "adiciona os hábitos ler e correr e marca meditar como feito",
    "registra que gastei 50 reais no mercado e depois abre as finanças",
    "cria um lembrete para amanhã às 9h e confere se ficou salvo",
    "anota comprar pão; depois agenda a reunião de sexta",
])
def test_multi_part_requests_use_the_loop(text):
    use, reason = should_use_agent_loop(text, "general", AUTO)
    assert use, reason


@pytest.mark.parametrize("text", [
    "oi tudo bem?",
    "abre minhas finanças",
    "qual é a capital da França?",
    "me explica como funciona a fotossíntese nas plantas",
    "adiciona ler nos meus hábitos de hoje",
    "",
    # MG7: perguntas e conversa não entram no loop, mesmo citando verbos de ação.
    "o que você acha de criar um app e abrir uma empresa",
    "meu pc está ligado mas a tela fica desligada, por que",
    "me explica como marcar consulta e registrar empresa",
    "como eu adiciono hábitos e depois agendo compromissos",
    "por que o app não consegue abrir e criar tarefas",
    "você acha melhor criar uma tarefa ou marcar um lembrete",
    "dá para adicionar ler nos hábitos e agendar dentista?",
    "explique como registrar uma despesa e depois abrir as finanças",
])
def test_greetings_questions_and_single_requests_stay_on_native_path(text):
    assert should_use_agent_loop(text, "general", AUTO)[0] is False


def test_settings_off_and_always():
    multi = "adiciona ler e meditar nos hábitos e depois agenda dentista"
    assert should_use_agent_loop(multi, "general", {"mode": "off"})[0] is False
    assert should_use_agent_loop("oi", "general", {"mode": "always"})[0] is True
    assert should_use_agent_loop("oi", "chat", {"mode": "always"})[0] is True
    # Sem configuração, vale o padrão automático.
    assert should_use_agent_loop(multi, "general", {})[0] is True


@pytest.mark.parametrize("mode", ["tutor", "planning", "research", "swarm", "vision"])
def test_excluded_modes_never_enter_the_loop(mode):
    multi = "adiciona ler e meditar nos hábitos e depois agenda dentista"
    assert should_use_agent_loop(multi, mode, {"mode": "auto"})[0] is False
    assert should_use_agent_loop(multi, mode, {"mode": "always"})[0] is False


def test_step_mode_always_uses_the_loop_even_when_off():
    assert should_use_agent_loop("faça", "react", {"mode": "off"}) == (True, "modo execução por etapas")


# ── rotinas, fase 1: espera real entre ações ────────────────────────────────
@pytest.mark.parametrize(("text", "seconds"), [
    ("Abra o spotify, aguarde 50 segundos e abra uma música no youtube", 50),
    ("abre o Spotify, espera 50 s e abre o YouTube", 50),
    ("abre o chrome, espere 2 minutos e depois abre o spotify", 120),
    ("abre o bloco de notas e após 1 hora abre o chrome", 3600),
])
def test_wait_requests_use_the_loop_with_the_wait_reason(text, seconds):
    assert wait_intent(text) == seconds
    assert should_use_agent_loop(text, "general", AUTO) == (True, "pedido com espera")


def test_wait_intent_and_alarm_detection():
    assert wait_intent("abre o spotify") is None
    assert wait_intent("me avisa em 10 minutos") is None
    assert mentions_alarm("me avisa em 10 minutos") and mentions_alarm("põe um timer de 5 min")
    assert not mentions_alarm("Abra o spotify, aguarde 50 segundos e abra uma música no youtube")
    # Pergunta e loop desligado continuam fora do loop.
    assert should_use_agent_loop("dá para abrir o spotify, esperar 5 s e abrir o youtube?", "general", AUTO)[0] is False
    assert should_use_agent_loop("abre o spotify, espera 50 s e abre o youtube", "general", {"mode": "off"})[0] is False
