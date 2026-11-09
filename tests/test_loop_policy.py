import pytest

from app.agent.loop_policy import should_use_agent_loop

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
