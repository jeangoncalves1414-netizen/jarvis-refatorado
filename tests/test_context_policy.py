import pytest

from app.agent.context_policy import chat_history_reply, context_preferences, explicit_preference, is_chat_history_request, requests_saved_memory


@pytest.mark.parametrize("text", [
    "Olá quero que você abra", "quero que você abra Spotify", "quero que você abra um vídeo curto",
    "me lembre de abrir o Spotify amanhã", "quero que você fale um texto grande agora", "qual a minha preferência?",
])
def test_commands_and_questions_are_not_durable_preferences(text):
    assert explicit_preference(text) is None


@pytest.mark.parametrize("text,expected", [
    ("Me lembre que eu prefiro respostas curtas", ("preferred_response_style", "short")),
    ("Prefiro respostas informais", ("preferred_response_style", "informal")),
    ("Quero que você sempre responda de forma informal", ("preferred_response_style", "informal")),
    ("prefiro usar o navegador Firefox", ("general_preference", "prefiro usar o navegador Firefox")),
])
def test_explicit_preferences_are_preserved(text, expected):
    assert explicit_preference(text) == expected


def test_legacy_commands_are_filtered_without_mutating_saved_preferences():
    prefs = [{"key": "general_preference", "value": "Olá quero que você abra"},
             {"key": "general_preference", "value": "prefiro usar Firefox"},
             {"key": "preferred_response_style", "value": "short"}]
    notes = context_preferences(prefs)
    assert len(prefs) == 3 and len(notes) == 2
    assert "Olá quero" not in str(notes) and "Firefox" in str(notes)


@pytest.mark.parametrize("text", [
    "qual é a primeira mensagem que enviei nesse chat", "Qual foi a minha primeira mensagem?",
    "Você lembra o que conversamos neste chat?", "Resuma essa conversa", "qual foi minha mensagem anterior?",
])
def test_current_chat_never_requests_global_memory(text):
    assert is_chat_history_request(text)
    assert not requests_saved_memory(text)


@pytest.mark.parametrize("text", [
    "Procure na memória o que conversamos sobre Roblox", "Você lembra do meu projeto?",
    "Qual foi a primeira mensagem de outro chat?", "Consulte nossas conversas anteriores sobre o projeto",
    "Qual foi a primeira mensagem de conversas anteriores?",
])
def test_explicit_recall_can_use_saved_memory(text):
    assert not is_chat_history_request(text)
    assert requests_saved_memory(text)


@pytest.mark.parametrize("text", [
    "Salve isso na memória", "Não consulte a memória para responder", "Responda sem usar outras conversas",
    "Não pesquise no cofre", "Olá, tudo bem?",
])
def test_writes_negation_and_small_talk_do_not_trigger_recall(text):
    assert not requests_saved_memory(text)


def test_first_previous_and_empty_history_are_grounded_in_messages():
    rows = [{"role": "assistant", "content": "Olá"}, {"role": "user", "content": "teste"},
            {"role": "assistant", "content": "A primeira mensagem foi outra coisa"},
            {"role": "user", "content": "Teve interação sim"}]
    assert "“teste”" in chat_history_reply("qual a minha primeira mensagem?", rows)
    assert "“Teve interação sim”" in chat_history_reply("qual foi minha mensagem anterior?", rows)
    assert "Não há mensagens" in chat_history_reply("qual a primeira mensagem nesse chat?", [])
    assert chat_history_reply("Qual a primeira mensagem de outro chat?", rows) is None
    assert chat_history_reply("Explique a primeira mensagem desse chat", rows) is None
