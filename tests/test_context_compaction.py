import threading
import time
from types import SimpleNamespace

import pytest
from app.services import context_compaction as compact
from app.storage import session_store as store


@pytest.fixture
def history(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'SESSIONS_FILE', str(tmp_path / 'sessions.json'))
    compact._running.clear(); compact._voice.clear(); compact._models.clear()
    rows = [{'role': 'user' if i % 2 == 0 else 'assistant', 'content': f'{i} ' + 'x' * 900} for i in range(20)]
    store.save_session_history('test', rows)
    return rows


def wait():
    end = time.monotonic() + 3
    while compact.status('test')['running'] and time.monotonic() < end:
        time.sleep(.01)
    assert not compact.status('test')['running']


def test_compaction_only_after_voice_end_preserves_full_history(history):
    calls = []
    model = SimpleNamespace(ask=lambda *a, **k: calls.append(a) or 'Resumo confirmado')
    compact.voice_started('test')
    compact.schedule('test', model, voice=True)
    assert not calls and not compact.status('test')['running']
    compact.voice_ended('test'); wait()
    assert len(calls) == 1
    assert store.get_session_history('test') == history
    working = compact.working_history('test', history)
    assert len(working) == 8 and working[-6:] == history[-6:]
    compact.schedule('test', model); wait()
    assert len(calls) == 1  # Already small enough.


def test_stale_summary_never_overwrites_edited_history(history):
    entered, release = threading.Event(), threading.Event()
    def ask(*a, **k):
        entered.set(); release.wait(3); return 'Resumo antigo'
    compact.schedule('test', SimpleNamespace(ask=ask))
    assert entered.wait(2)
    assert compact.status('test') == {'running': True, 'cancellable': False, 'last': None}
    store.save_session_history('test', [{'role': 'user', 'content': 'Edição nova'}])
    release.set(); wait()
    assert 'compaction' not in store.get_session('test')
    assert compact.status('test')['last']['state'] == 'stale'


def test_failure_keeps_original_and_releases_status(history):
    from app.services.llm import ProviderErrorText
    compact.schedule('test', SimpleNamespace(ask=lambda *a, **k: ProviderErrorText('indisponível')))
    wait()
    assert compact.working_history('test', history) == history
    assert compact.status('test')['last']['state'] == 'failed'


def test_short_chat_no_model_call(history):
    store.save_session_history('test', history[:4])
    compact.schedule('test', SimpleNamespace(ask=lambda *a, **k: pytest.fail('Unnecessary compaction')))
    assert not compact.status('test')['running']


def test_mcp_structured_data_reaches_agent():
    from app.mcp.manager import _format_result
    result = _format_result(SimpleNamespace(isError=False, content=[], structuredContent={'latitude': -23.5, 'longitude': -46.6}))
    observation = result.model_observation()
    assert '"latitude": -23.5' in observation and '"longitude": -46.6' in observation
