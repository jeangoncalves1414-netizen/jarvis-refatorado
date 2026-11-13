import pytest

from app.services.app_lock import AppLock


def test_password_lifecycle_and_restart(tmp_path):
    lock = AppLock(tmp_path / 'lock.json')
    assert not lock.status()['configured']
    _, token = lock.perform({'action': 'setup', 'password': 'test-password'})
    cookie = f'jarvis_unlock={token}'
    assert lock.authenticated(cookie)
    assert not lock.authenticated('')
    assert not AppLock(lock.path).authenticated(cookie)
    assert 'test-password' not in lock.path.read_text()
    with pytest.raises(ValueError):
        lock.perform({'action': 'disable', 'password': 'wrong'}, cookie)
    _, next_token = lock.perform({'action': 'change', 'password': 'test-password', 'new_password': 'new-password'}, cookie)
    assert not lock.authenticated(cookie)
    cookie = f'jarvis_unlock={next_token}'
    lock.perform({'action': 'lock'}, cookie)
    assert lock.locked()
    with pytest.raises(ValueError):
        lock.perform({'action': 'unlock', 'password': 'test-password'})
    _, token = lock.perform({'action': 'unlock', 'password': 'new-password'})
    lock.perform({'action': 'disable', 'password': 'new-password'}, f'jarvis_unlock={token}')
    assert not lock.enabled()
    assert 'password' not in lock.path.read_text()


def test_rate_limit_and_corrupt_file_fail_closed(tmp_path):
    lock = AppLock(tmp_path / 'lock.json')
    lock.perform({'action': 'setup', 'password': 'test-password'})
    for _ in range(5):
        with pytest.raises(ValueError):
            lock.perform({'action': 'unlock', 'password': 'wrong'})
    with pytest.raises(ValueError, match='30 segundos'):
        lock.perform({'action': 'unlock', 'password': 'test-password'})
    lock.path.write_text('invalid')
    assert lock.enabled()
    assert not lock.authenticated()


def test_biometrics_require_password_consent_and_matching_sample(tmp_path, monkeypatch):
    lock = AppLock(tmp_path / 'lock.json')
    _, token = lock.perform({'action': 'setup', 'password': 'test-password'})
    cookie = f'jarvis_unlock={token}'
    monkeypatch.setattr(lock, '_vector', lambda *args: [1.0, 0.0])
    with pytest.raises(ValueError):
        lock.perform({'action': 'enroll', 'kind': 'face', 'password': 'test-password'}, cookie)
    _, token = lock.perform({'action': 'enroll', 'kind': 'face', 'password': 'test-password', 'consent': True}, cookie)
    lock.perform({'action': 'lock'}, f'jarvis_unlock={token}')
    monkeypatch.setattr(lock, '_vector', lambda *args: [0.0, 1.0])
    with pytest.raises(ValueError):
        lock.perform({'action': 'biometric', 'kind': 'face'})
    assert lock.locked()
    monkeypatch.setattr(lock, '_vector', lambda *args: [1.0, 0.0])
    _, token = lock.perform({'action': 'biometric', 'kind': 'face'})
    assert lock.authenticated(f'jarvis_unlock={token}')


def test_deferred_setup_can_be_enabled(tmp_path):
    lock = AppLock(tmp_path / 'lock.json')
    lock.perform({'action': 'skip'})
    lock.perform({'action': 'change', 'new_password': 'test-password'})
    assert lock.enabled()
    with pytest.raises(ValueError):
        lock.perform({'action': 'skip'})


def test_http_gate_and_cookie(tmp_path, monkeypatch):
    import http.client
    import json
    import threading
    from http.server import ThreadingHTTPServer
    from app.config import Settings
    from app.ui.panel import server
    lock = AppLock(tmp_path / 'lock.json')
    monkeypatch.setattr(server, 'app_lock', lock)
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), server.PanelHandler)
    monkeypatch.setattr(server.PanelHandler, 'settings', Settings(host='127.0.0.1', port=httpd.server_port))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    def call(method, path, data=None, cookie=''):
        connection = http.client.HTTPConnection('127.0.0.1', httpd.server_port, timeout=10)
        connection.request(method, path, json.dumps(data) if data else None, {'Content-Type': 'application/json', 'Cookie': cookie})
        response = connection.getresponse()
        result = response.status, response.getheader('Set-Cookie'), json.loads(response.read())
        connection.close()
        return result
    try:
        code, cookie, _ = call('POST', '/api/app-lock', {'action': 'setup', 'password': 'test-password'})
        assert code == 200 and 'HttpOnly' in cookie and 'SameSite=Strict' in cookie
        assert call('GET', '/api/sessions')[0] == 423
        assert call('POST', '/api/chat', {'message': 'hello'})[0] == 423
        assert call('GET', '/api/app-lock', cookie=cookie)[2]['unlocked']
        call('POST', '/api/app-lock', {'action': 'lock'}, cookie)
        assert call('GET', '/api/sessions', cookie=cookie)[0] == 423
        assert call('POST', '/api/app-lock', {'action': 'unlock', 'password': 'wrong'})[0] == 400
    finally:
        httpd.shutdown(); httpd.server_close(); thread.join(timeout=2)


def test_websocket_rejects_locked_client(tmp_path, monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from app.ui.panel import server
    lock = AppLock(tmp_path / 'lock.json')
    lock.perform({'action': 'setup', 'password': 'test-password'})
    monkeypatch.setattr(server, 'app_lock', lock)
    closed = []
    async def close(**kwargs):
        closed.append(kwargs)
    ws = SimpleNamespace(request_headers={}, close=close)
    asyncio.run(server._ws_chat_handler(ws))
    assert closed[0]['code'] == 1008

def test_websocket_revokes_inflight_response(tmp_path, monkeypatch):
    import asyncio
    import json
    from types import SimpleNamespace
    from app.ui.panel import server
    lock = AppLock(tmp_path / 'lock.json')
    _, token = lock.perform({'action': 'setup', 'password': 'test-password'})
    monkeypatch.setattr(server, 'app_lock', lock)
    sent, closed = [], []
    class Socket:
        request_headers = {'Cookie': f'jarvis_unlock={token}'}
        async def close(self, **kwargs):
            closed.append(kwargs)
        async def send(self, message):
            sent.append(json.loads(message))
        async def __aiter__(self):
            yield json.dumps({'message': 'test'})
    def handle(*args, **kwargs):
        lock.lock()
        kwargs['on_chunk']('private result')
        return SimpleNamespace(summary='private result', intent='answer', actions=[], context={})
    monkeypatch.setattr(server, '_orchestrator', SimpleNamespace(handle_request=handle))
    monkeypatch.setattr(server, '_calendar_conversation_prefix', lambda: '')
    asyncio.run(server._ws_chat_handler(Socket()))
    assert closed and closed[0]['code'] == 1008
    assert all(event['type'] == 'status' for event in sent)
