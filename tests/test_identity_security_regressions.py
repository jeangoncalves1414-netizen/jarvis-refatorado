"""Cross-feature regressions: rejected chats, shared credentials and enrollment."""
import asyncio
import http.client
import json
import threading
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services import identity, identity_access, live_enrollment


@pytest.mark.parametrize('content', ['broken', '[]', 'null', '{}', '{"profiles": [null]}'])
def test_corrupt_identity_cannot_be_replaced_by_new_admin(content):
    identity.IDENTITY_FILE.write_text(content)
    assert identity_access.access(None) == (False, None)
    with pytest.raises(ValueError):
        identity.IdentityService.enroll_admin('Intruso', 'password123')
    assert identity.IDENTITY_FILE.read_text() == content


def test_orphan_profile_does_not_allow_new_admin():
    identity._write({'profiles': [{'id': 'user', 'name': 'Ana', 'role': 'user'}]})
    assert not identity.IdentityService.enroll_admin('Intruso', 'password123')['ok']


def test_password_limit_cannot_be_bypassed_by_switching_endpoints():
    admin = identity.IdentityService.enroll_admin('Jean', 'password123')['profile']
    from app.services.app_lock import app_lock
    app_lock.perform({'action': 'setup', 'password': 'unlock-password'})
    with pytest.raises(ValueError):
        identity.IdentityService.enroll_profile('Ana', 'user', 'wrong')
    with pytest.raises(ValueError):
        identity.IdentityService.authenticate(admin['id'], 'wrong')
    with pytest.raises(ValueError):
        identity.IdentityService.add_sample(admin['id'], 'wrong', 'face', '')
    with pytest.raises(ValueError):
        identity_access.set_permission({'admin_password': 'wrong'})
    with pytest.raises(ValueError):
        live_enrollment.authorize({'purpose': 'admin_reenroll', 'admin_password': 'wrong'})
    with pytest.raises(ValueError, match='30 segundos'):
        live_enrollment.authorize({'purpose': 'admin_reenroll', 'admin_password': 'unlock-password'})


def test_manual_enrollment_rejects_duplicate_name_and_face(monkeypatch):
    admin = identity.IdentityService.enroll_admin('Jean', 'password123')['profile']
    assert not identity.IdentityService.enroll_profile('jean', 'user', 'password123')['ok']
    other = identity.IdentityService.enroll_profile('Ana', 'user', 'password123')['profile']
    monkeypatch.setattr(identity, '_face_vector', lambda _: ([1., 0.], b'image'))
    args = ('password123', 'face', 'data:image/jpeg;base64,AA==')
    assert identity.IdentityService.add_sample(admin['id'], *args)['ok']
    before = identity.IDENTITY_FILE.read_bytes()
    assert not identity.IdentityService.add_sample(other['id'], *args)['ok']
    monkeypatch.setattr(identity, '_face_vector', lambda _: ([0., 1.], b'image'))
    assert not identity.IdentityService.add_sample(admin['id'], *args)['ok']
    assert identity.IDENTITY_FILE.read_bytes() == before


def test_guided_enrollment_rejects_face_of_existing_person(monkeypatch):
    identity.IdentityService.enroll_admin('Jean', 'password123')
    data = identity._read()
    data['profiles'][0]['face_embeddings_sface'] = [[1., 0.]]
    identity._write(data)
    before = identity.IDENTITY_FILE.read_bytes()
    monkeypatch.setattr(identity.voice_identity_engine, 'embed', lambda *a: [0., 1.])
    poses = iter([0., .2, -.2])
    monkeypatch.setattr(live_enrollment.faces, 'extract', lambda _: [{'embedding': [1., 0.], 'pose': next(poses)}])
    with pytest.raises(ValueError, match='outro perfil'):
        live_enrollment.enroll({'name': 'Ana', 'consent': True, 'admin_password': 'password123',
                                'audio': 'data:audio/wav;base64,AA==', 'images': ['data:image/jpeg;base64,AA=='] * 3})
    assert identity.IDENTITY_FILE.read_bytes() == before


@pytest.fixture
def restricted_server(monkeypatch, isolated_lote6_data):
    from app.agent.orchestrator import AgentPlan
    from app.config import Settings
    from app.ui.panel import server
    plan = AgentPlan(intent='general', summary='Identidade desconhecida.', actions=[], context={'identity_restricted': True})
    reminder = Mock(return_value='SEGREDO DA AGENDA')
    memory = Mock()
    monkeypatch.setattr(server, '_calendar_conversation_prefix', reminder)
    monkeypatch.setattr(server, '_orchestrator', SimpleNamespace(
        handle_request=lambda *a, **k: plan,
        handle_request_stream=lambda *a, **k: iter([{'status': 'complete', 'plan': plan}]),
        semantic_memory=SimpleNamespace(add_memory=memory)))
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), server.PanelHandler)
    monkeypatch.setattr(server.PanelHandler, 'settings', Settings(host='127.0.0.1', port=httpd.server_port))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    # Execute queued memory writes synchronously so an accidental write cannot race assertions.
    class ImmediateThread:
        def __init__(self, target, args=(), kwargs=None, **_):
            self.run = lambda: target(*args, **(kwargs or {}))
        def start(self):
            self.run()
    # Keep HTTP worker threads real; only intercept the memory scheduler.
    scheduler = Mock(side_effect=lambda target, **_: target)
    monkeypatch.setattr(server, 'in_background', scheduler)
    yield server, httpd.server_port, reminder, memory, ImmediateThread
    httpd.shutdown(); httpd.server_close(); thread.join(timeout=2)
    scheduler.assert_not_called()


@pytest.mark.parametrize('path', ['/api/chat', '/api/chat/stream'])
def test_restricted_http_chat_never_reads_reminders_or_saves_memory(restricted_server, monkeypatch, path):
    server, port, reminder, memory, immediate = restricted_server
    # Record thread creation without starting memory jobs; HTTP workers use the original module.
    monkeypatch.setattr(server, 'threading', SimpleNamespace(Thread=immediate))
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
    try:
        conn.request('POST', path, json.dumps({'message': 'guarde esta mentira'}), {'Content-Type': 'application/json'})
        response = conn.getresponse()
        body = response.read().decode()
        assert response.status == 200, body
        assert 'Identidade desconhecida' in body and 'SEGREDO' not in body
        reminder.assert_not_called()
        memory.assert_not_called()
    finally:
        conn.close()


def test_restricted_websocket_chat_never_reads_reminders_or_saves_memory(restricted_server, monkeypatch):
    server, _, reminder, memory, immediate = restricted_server
    sent = []
    class Socket:
        request_headers = {}
        async def __aiter__(self):
            yield '[]'
            yield json.dumps({'message': 'guarde esta mentira'})
        async def send(self, value):
            sent.append(json.loads(value))
    asyncio.run(server._ws_chat_handler(Socket()))
    reminder.assert_not_called()
    memory.assert_not_called()
    assert sent[0]['type'] == 'error'
    assert sent[-1]['type'] == 'complete' and 'SEGREDO' not in sent[-1]['summary']
