from types import SimpleNamespace

import pytest

from app.services.conversation_title import generate_title
from app.storage import session_store as store


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'SESSIONS_FILE', str(tmp_path / 'sessions.json'))
    store.add_session({'id': 's', 'title': 'Nova conversa', 'history': [
        {'role': 'user', 'content': 'Quero organizar meu treino semanal'},
        {'role': 'assistant', 'content': 'Vamos distribuir os exercícios por dia.'}], 'whiteboard': []})


def test_contextual_title_and_no_repeat():
    calls = []
    def generate(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(text='"Planejamento de treino semanal"')
    llm = SimpleNamespace(generate=generate)
    assert generate_title('s', llm)[1]['session']['title'] == 'Planejamento de treino semanal'
    assert 'distribuir os exercícios' in calls[0]['contents']
    assert 'tools' not in calls[0]
    assert generate_title('s', llm)[0] == 200
    assert len(calls) == 1
    assert len(store.get_session_history('s')) == 2


def test_manual_rename_during_generation_wins():
    def generate(**kwargs):
        store.update_session('s', {'title': 'Meu título'})
        return SimpleNamespace(text='Título automático')
    assert generate_title('s', SimpleNamespace(generate=generate))[1]['session']['title'] == 'Meu título'


def test_failure_can_retry_without_overwriting_history():
    assert generate_title('s', None)[0] == 503
    assert store.get_session('s')['title'] == 'Nova conversa'
    assert generate_title('s', SimpleNamespace(generate=lambda **kw: SimpleNamespace(text='Treinos da semana')))[0] == 200
    assert generate_title('missing', None)[0] == 404


def test_deleted_conversation_not_resurrected():
    def generate(**kwargs):
        store.delete_session('s')
        return SimpleNamespace(text='Treinos da semana')
    assert generate_title('s', SimpleNamespace(generate=generate))[0] == 404
    assert store.get_session('s') is None
