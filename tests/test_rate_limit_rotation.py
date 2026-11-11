from types import SimpleNamespace
import sys
import pytest
from app.services.rate_limits import retry_seconds, is_rate_limit, ProviderRateLimit
from app.services import llm


def error(message='429 tokens per day. Please try again in 10m3.072s.', headers=None):
    e = RuntimeError(message)
    e.response = SimpleNamespace(headers=headers or {})
    return e


def test_retry_hint_and_classification():
    assert retry_seconds(error()) == 605
    assert retry_seconds(error(headers={'retry-after': '900'})) == 901
    assert retry_seconds(error('429 retryDelay: "32476s"')) == 32477
    assert retry_seconds(error('429', {'retry-after': 'NaN'})) == 60
    assert retry_seconds(error('429', {'retry-after': 'invalid'})) == 60
    assert not is_rate_limit(error('400 context length limit exceeded'))


def test_cooldown_keeps_longest_and_only_blocks_failed_key(monkeypatch):
    monkeypatch.setattr(llm.time, 'time', lambda: 1000)
    r = llm.KeyRotator()
    settings = SimpleNamespace(groq_api_keys=['one', 'two', 'three', 'four'])
    r.mark_rate_limit('one', error())
    r.mark_cooldown('one', 60)
    assert r.cooldowns['one'] == 1605
    assert r.get_key('groq', settings) == 'two'
    assert '1 de 4' in r.wait_message('groq', settings)
    for key in settings.groq_api_keys[1:]:
        r.mark_rate_limit(key, error())
    assert r.get_key('groq', settings) == ''
    assert '4 de 4' in r.wait_message('groq', settings)
    assert 'cota diária' in r.wait_message('groq', settings)
    monkeypatch.setattr(llm.time, 'time', lambda: 1606)
    assert r.get_key('groq', settings)


@pytest.mark.parametrize('all_blocked', [False, True])
def test_generate_rotates_without_retrying_blocked_keys(monkeypatch, all_blocked):
    r = llm.KeyRotator()
    monkeypatch.setattr(llm, '_key_rotator', r)
    settings = SimpleNamespace(groq_api_keys=['one', 'two', 'three', 'four'])
    calls = []
    class FakeGroq:
        def __init__(self, api_key, **kwargs):
            def create(**kwargs):
                calls.append(api_key)
                if all_blocked or api_key != 'two':
                    raise error()
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='ok', tool_calls=[]))])
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))
    monkeypatch.setitem(sys.modules, 'groq', SimpleNamespace(Groq=FakeGroq))
    monkeypatch.setattr(llm.LLMService, '_effective_chat_model', lambda *args: 'fake')
    service = llm.LLMService(settings)
    if all_blocked:
        with pytest.raises(ProviderRateLimit, match='4 de 4'):
            service._generate_groq('hello', None, None, 'one')
        assert calls == settings.groq_api_keys
    else:
        assert service._generate_groq('hello', None, None, 'one').text == 'ok'
        assert calls == ['one', 'two']
