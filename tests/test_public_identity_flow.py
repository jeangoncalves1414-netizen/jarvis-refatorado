from types import SimpleNamespace

import pytest

from app.services import identity, live_enrollment, public_conversation
from app.services.app_lock import app_lock
from app.services.llm import LLMService


@pytest.mark.parametrize('origin', ['voice'])
def test_public_conversation_isolated_from_owner_context(origin, monkeypatch, isolated_lote6_data):
    from app.agent import orchestrator
    from app.storage import session_store
    identity.IdentityService.enroll_admin('Jean', 'profile-password')
    monkeypatch.setattr(orchestrator, 'get_session_history', lambda *a: pytest.fail('Owner history read'))
    session_store.save_session_history('public-test', [{'role': 'user', 'content': 'OWNER_SECRET'}])
    calls, chunks = [], []
    def generate(contents, **kwargs):
        calls.append((contents, kwargs))
        return SimpleNamespace(text='Olá! Como posso ajudar?')
    agent = orchestrator.AgentOrchestrator.__new__(orchestrator.AgentOrchestrator)
    agent.llm_service = SimpleNamespace(build_contents=LLMService.build_contents, generate=generate)
    agent._dispatch_request = lambda *a, **k: pytest.fail('Private tools reached')
    for text in ['Olá', 'Como você se chama?']:
        plan = agent.handle_request(text, session_id='public-test', origin=origin, on_chunk=chunks.append,
                                    history=[{'role': 'user', 'content': 'OWNER_SECRET'}])
        assert plan.intent == 'general' and plan.summary == 'Olá! Como posso ajudar?'
        assert plan.context['identity_restricted'] and plan.context['access_mode'] == 'public'
        assert plan.actions == []
    assert len(calls[1][0]) == 3
    assert 'OWNER_SECRET' not in str(calls)
    assert all(kwargs['tools'] is None for _, kwargs in calls)
    assert len(chunks) == 2
    assert len(session_store.get_context_history('public-test', 'anonymous')) == 4


def test_public_registration_needs_no_admin_and_ignores_privileges(monkeypatch):
    identity.IdentityService.enroll_admin('Jean', 'profile-password')
    ticket = live_enrollment.authorize({'name': 'Jamille', 'role': 'admin', 'permissions': ['assistant_private']})['ticket']
    monkeypatch.setattr(live_enrollment, 'transcribe_reading', lambda *a: live_enrollment.READING)
    monkeypatch.setattr(identity.voice_identity_engine, 'embed', lambda *a: [1., 0.])
    live_enrollment.validate_voice({'ticket': ticket, 'consent': True, 'audio': 'data:audio/wav;base64,AA=='})
    profile = live_enrollment.enroll({'ticket': ticket, 'consent': True, 'role': 'admin', 'images': []})['profile']
    assert profile['role'] == 'user' and profile['permissions'] == []


@pytest.mark.parametrize('cancelled', [False, True])
def test_failed_public_turn_never_writes_owner_history(cancelled, monkeypatch, isolated_lote6_data):
    from app.agent import orchestrator
    from app.core.runs import RunCancelled
    from app.storage import session_store
    identity.IdentityService.enroll_admin('Jean', 'profile-password')
    monkeypatch.setattr(session_store, 'save_turn', lambda *a, **k: pytest.fail('Owner history modified'))
    def fail(*a, **k):
        raise RunCancelled() if cancelled else ValueError('provider unavailable')
    agent = orchestrator.AgentOrchestrator.__new__(orchestrator.AgentOrchestrator)
    agent.llm_service = SimpleNamespace(build_contents=LLMService.build_contents, generate=fail)
    plan = agent.handle_request('Olá', session_id='public-failed', origin='voice')
    assert plan.intent == ('cancelled' if cancelled else 'error')
    assert plan.context['identity_restricted'] and plan.context['access_mode'] == 'public'


def test_admin_reenrollment_requires_unlock_password_not_legacy_password():
    identity.IdentityService.enroll_admin('Jean', 'profile-password')
    app_lock.perform({'action': 'setup', 'password': 'unlock-password'})
    with pytest.raises(ValueError):
        live_enrollment.authorize({'purpose': 'admin_reenroll', 'admin_password': 'profile-password'})
    assert live_enrollment.authorize({'purpose': 'admin_reenroll', 'admin_password': 'unlock-password'})['ok']


def test_admin_creation_and_password_change_revoke_pending_authorization(monkeypatch):
    app_lock.perform({'action': 'setup', 'password': 'unlock-password'})
    payload = {'purpose': 'admin_reenroll', 'admin_password': 'unlock-password', 'name': 'Jean'}
    ticket = live_enrollment.authorize(payload)['ticket']
    live_enrollment._pending[ticket]['voice'] = [1., 0.]
    app_lock._save({'enabled': True, 'password': identity._hash_password('changed-password')})
    with pytest.raises(ValueError, match='revogada'):
        live_enrollment.enroll({'ticket': ticket, 'consent': True, 'images': []})
    assert identity._read()['profiles'] == []
    ticket = live_enrollment.authorize({**payload, 'admin_password': 'changed-password'})['ticket']
    live_enrollment._pending[ticket]['voice'] = [1., 0.]
    profile = live_enrollment.enroll({'ticket': ticket, 'consent': True, 'images': []})['profile']
    assert profile['name'] == 'Jean' and profile['role'] == 'admin'


def test_password_check_keeps_unlock_session_and_old_password_cannot_modify_admin(monkeypatch):
    admin = identity.IdentityService.enroll_admin('Jean', 'profile-password')['profile']
    _, session = app_lock.perform({'action': 'setup', 'password': 'unlock-password'})
    before = dict(app_lock.sessions)
    assert app_lock.perform({'action': 'verify_password', 'password': 'unlock-password'}) == ({'ok': True}, None)
    assert app_lock.sessions == before and session in app_lock.sessions
    with pytest.raises(ValueError):
        identity.IdentityService.add_sample(admin['id'], 'profile-password', 'face', 'data:image/jpeg;base64,AA==')
    monkeypatch.setattr(identity, '_face_vector', lambda *a: ([1., 0.], b''))
    assert identity.IdentityService.add_sample(admin['id'], 'unlock-password', 'face', 'data:image/jpeg;base64,AA==')['ok']
