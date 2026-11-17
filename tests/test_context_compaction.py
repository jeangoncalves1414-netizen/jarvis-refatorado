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
    assert len(working) == 7 and working[-6:] == history[-6:]
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


def test_prepare_compacts_during_voice_and_preserves_transcript(history):
    compact.voice_started('test')
    calls = []
    model = SimpleNamespace(ask=lambda text, **kw: calls.append((text, kw)) or 'Objetivo ativo: terminar cadastro; pendente: validar voz.')
    working = compact.prepare_history('test', history, model)
    assert calls and 'Pendências' in calls[0][1]['system_instruction']
    assert 'terminar cadastro' in working[0]['content']
    assert working[-6:] == history[-6:]
    assert store.get_session_history('test') == history


def test_incremental_checkpoint_preserves_old_summary_and_new_corrections(history):
    compact.prepare_history('test', history, SimpleNamespace(ask=lambda *a, **k: 'Decisão: usar câmera USB.'))
    new = history + [{'role': 'user' if i % 2 == 0 else 'assistant', 'content': 'Correção: câmera IP. ' + 'y' * 900} for i in range(14)]
    store.save_session_history('test', new)
    requests = []
    result = compact.prepare_history('test', new, SimpleNamespace(ask=lambda text, **k: requests.append(text) or 'Decisão atual: câmera IP.'))
    assert 'câmera USB' in requests[0] and 'câmera IP' in requests[0]
    assert result[0]['content'].endswith('Decisão atual: câmera IP.')
    assert store.get_session_history('test') == new


def test_long_single_message_is_chunked_without_losing_tail(history):
    rows = [{'role': 'user', 'content': 'a' * 50000 + 'FINAL_IMPORTANTE'}] + history
    store.save_session_history('test', rows)
    calls = []
    compact.prepare_history('test', rows, SimpleNamespace(ask=lambda text, **k: calls.append(text) or 'Resumo'))
    assert len(calls) > 1 and any('FINAL_IMPORTANTE' in call for call in calls)
    assert max(map(len, calls)) < compact.MAX_INPUT_CHARS + compact.MAX_SUMMARY_CHARS + 200
    assert store.get_session_history('test') == rows


def test_private_checkpoint_never_used_in_public_scope(history):
    compact.prepare_history('test', history, SimpleNamespace(ask=lambda *a, **k: 'SEGREDO_DO_DONO'))
    store.save_turn('test', 'public', 'Olá', 'Oi', timestamp=1, access_scope='anonymous')
    public = store.get_context_history('test', 'anonymous')
    assert 'SEGREDO' not in str(compact.prepare_history('test', public, None, scope='anonymous'))


def test_mcp_structured_data_reaches_agent():
    from app.mcp.manager import _format_result
    result = _format_result(SimpleNamespace(isError=False, content=[], structuredContent={'latitude': -23.5, 'longitude': -46.6}))
    observation = result.model_observation()
    assert '"latitude": -23.5' in observation and '"longitude": -46.6' in observation
