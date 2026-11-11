"""Real Chromium regressions using synthetic local media, never third-party sites."""
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event, Thread
from time import monotonic, sleep

import pytest

from app.services.cinema_page import inspect_dynamic, player_reports_unavailable, response_media
from app.services.cinema_discovery import CinemaDiscoveryService
from app.services.cinema_session import CinemaSessions


@pytest.fixture
def media_site():
    clip = (Path(__file__).parents[1] / 'frontend/tests/fixtures/cinema/clip.mp4').read_bytes()
    played = Event()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            kind, status, cookie = 'text/html', 200, False
            if self.path.endswith('.mp4'):
                kind = 'video/mp4'
                status = 200 if self.path != '/session.mp4' or 'fixture=1' in self.headers.get('Cookie', '') else 403
                body = clip if status == 200 else b'No session'
                if self.path == '/session.mp4' and status == 200:
                    played.set()
            elif self.path == '/late':
                body = b'<body><script>setTimeout(()=>{document.body.innerHTML=\'<video src="/clip.mp4"></video>\'},3500)</script></body>'
            elif self.path == '/known-player':
                body = b'<button class="vjs-big-play-button" onclick="this.outerHTML=\'<video src=/clip.mp4></video>\'">Play</button>'
            elif self.path == '/unknown-player':
                body = b'<button onclick="this.outerHTML=\'<video src=/clip.mp4></video>\'">Pay or play</button>'
            elif self.path == '/blocked':
                status, body = 403, b'Access denied'
            elif self.path == '/session':
                cookie = True
                body = b'<video autoplay muted src="/session.mp4"></video>'
            elif self.path == '/embedded':
                body = b'<iframe src="/session"></iframe>'
            elif self.path == '/dom-embedded':
                body = b'<iframe src="/dom-only"></iframe>'
            elif self.path == '/dom-only':
                body = b'<video preload="none" src="/clip.mp4"></video>'
            elif self.path == '/landing':
                body = b'<a href="/session">Assistir Filme</a>'
            elif self.path == '/alternatives':
                body = b'''<button onclick="document.querySelector('#player').innerHTML='Video unavailable'">Player 1</button>
                <button onclick="document.querySelector('#player').innerHTML='<video src=/clip.mp4></video>'">Player 2 Dublado</button><div id=player></div>'''
            elif self.path == '/unsafe-controls':
                body = b'''<form action=/session><button>Assistir</button></form>
                <a href="https://other.example/player">Assistir Filme</a><button onclick="location='/session'">Download</button>'''
            elif self.path == '/blank-player':
                body = b'<script>location.replace("about:blank")</script>'
            elif self.path == '/slow-page':
                body = b'<video autoplay muted src="/clip.mp4"></video><script defer src="/slow.js"></script>'
            elif self.path == '/slow.js':
                sleep(4)
                kind, body = 'application/javascript', b'void 0'
            else:
                body = b'<video src="/clip.mp4"></video>'
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            if cookie:
                self.send_header('Set-Cookie', 'fixture=1; Path=/; HttpOnly; SameSite=Lax')
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    Thread(target=server.serve_forever, daemon=True).start()
    yield f'http://127.0.0.1:{server.server_port}', played
    server.shutdown()
    server.server_close()


@pytest.mark.parametrize('path', ['/late', '/known-player', '/alternatives'])
def test_detector_observes_late_video_and_known_play_control(media_site, path):
    base, _ = media_site
    result = inspect_dynamic(base + path, lambda url: url.startswith(base + '/'), observation_seconds=4.5)
    assert result['status'] == 'detected'
    assert any(item['url'] == base + '/clip.mp4' and item.get('evidence') == 'network' for item in result['media'])


def test_detector_does_not_click_arbitrary_buttons_and_reports_blocked(media_site):
    base, _ = media_site
    for path, status in [('/unknown-player', 'unconfirmed'), ('/unsafe-controls', 'unconfirmed'), ('/blocked', 'blocked'), ('/blank-player', 'interaction_required')]:
        result = inspect_dynamic(base + path, lambda url: url.startswith(base + '/'), observation_seconds=.5)
        assert result['status'] == status and not result['media']


def test_fragments_are_not_independent_movies():
    assert not response_media('https://example.org/a.ts', 'video/mp2t')
    assert not response_media('https://example.org/a.m4s?token=1', 'video/mp4')
    assert not response_media('https://example.org/fragment', 'video/mp2t')
    assert response_media('https://example.org/master', 'application/vnd.apple.mpegurl')


def test_response_without_a_frame_does_not_interrupt_capture():
    from types import SimpleNamespace
    from app.services.cinema_page import response_belongs_to_page
    class EarlyRequest:
        @property
        def frame(self):
            raise RuntimeError('Frame for this navigation request is not available')
    page = object()
    assert not response_belongs_to_page(SimpleNamespace(request=EarlyRequest()), page)
    assert response_belongs_to_page(SimpleNamespace(request=SimpleNamespace(frame=SimpleNamespace(page=page))), page)


@pytest.mark.parametrize('path', ['/session', '/embedded', '/landing'])
@pytest.mark.parametrize('fast', [False, True])
def test_full_probe_captures_cookie_media_even_when_html_has_a_source(media_site, monkeypatch, path, fast):
    from app.services.cinema_relay import get_probe_relay
    base, _ = media_site
    monkeypatch.setattr(CinemaDiscoveryService, '_is_public_http_url', staticmethod(lambda url: url.startswith(base + '/')))
    result = CinemaDiscoveryService().probe(base + path, fast=fast)
    media = next(item for item in result['media'] if item['url'] == base + '/session.mp4')
    if not fast or path == '/embedded':
        assert media['evidence'] == 'network'
    relay = get_probe_relay(media['session_id'])
    response, _ = relay.open_resource(media['playback_url'].rsplit('/', 1)[1])
    with response:
        assert response.status == 200
        assert response.read(16)


def test_fast_capture_returns_before_full_observation_budget(media_site):
    base, _ = media_site
    start = monotonic()
    result = inspect_dynamic(base + '/session', lambda url: url.startswith(base + '/'),
                             observation_seconds=8, stop_after_first=True)
    elapsed = monotonic() - start
    assert any(item.get('evidence') == 'network' for item in result['media'])
    assert elapsed < 7, f'Early detection still waited {elapsed:.1f}s'
    print(f'Fast detection with an 8-second observation budget: {elapsed:.2f}s')


def test_explicit_embedded_player_errors_are_not_reported_as_generic_waiting():
    assert player_reports_unavailable('Video is unavailable')
    assert player_reports_unavailable('Este vídeo não está disponível')
    assert not player_reports_unavailable('Clique em play para começar')


def test_fast_detection_does_not_wait_for_unrelated_deferred_script(media_site):
    base, _ = media_site
    started = monotonic()
    result = inspect_dynamic(base + '/slow-page', lambda url: url.startswith(base + '/'),
                             observation_seconds=2, navigation_timeout=4500, stop_after_first=True)
    elapsed = monotonic() - started
    assert result['status'] == 'detected'
    assert any(item.get('evidence') == 'network' for item in result['media'])
    assert elapsed < 3.5, f'Detection waited for the 4-second unrelated script: {elapsed:.2f}s'


def test_browser_worker_reuses_process_isolates_context_and_recovers(media_site):
    from app.services.cinema_workers import BrowserWorkers
    from app.services.cinema_page import _inspect_on_browser
    base, _ = media_site
    workers = BrowserWorkers(size=1, idle_seconds=1)
    closed = Event()
    def first(browser):
        browser.on('disconnected', lambda _: closed.set())
        result = _inspect_on_browser(browser, base + '/session', lambda u: u.startswith(base + '/'),
                                     observation_seconds=2, stop_after_first=True)
        assert result['media'] and browser.contexts == []
        return browser._impl_obj._guid
    def second(browser):
        with browser.new_context() as context:
            assert context.cookies() == []
        return browser._impl_obj._guid
    try:
        identity = workers.run(first)
        assert workers.run(second) == identity
        assert closed.wait(4), 'Idle Chromium should be released'
        assert workers.run(second) != identity
        def fail(browser):
            raise ValueError('probe failed')
        with pytest.raises(ValueError, match='probe failed'):
            workers.run(fail)
        assert workers.run(second)
    finally:
        workers.close()
    assert all(not thread.is_alive() for thread in workers._threads)


def test_session_keeps_cookie_for_actual_video_and_releases_on_close(media_site, monkeypatch):
    base, played = media_site
    monkeypatch.setattr(CinemaDiscoveryService, '_is_public_http_url', staticmethod(lambda url: url.startswith(base + '/')))
    manager = CinemaSessions(headless=True)
    try:
        result = manager.open(base + '/session')
        assert result['ok']
        assert played.wait(5), 'Video must be served with the page session cookie'
        assert result['session_id'] in manager._sessions
        manager.close(result['session_id'])
        deadline = monotonic() + 5
        while manager._sessions and monotonic() < deadline:
            sleep(.1)
        assert not manager._sessions
        assert manager.close(result['session_id'])['ok']
    finally:
        manager.close_all()


def test_session_rejects_local_urls_and_limits_windows(monkeypatch):
    manager = CinemaSessions(headless=True)
    assert not manager.open('http://127.0.0.1/')['ok']
    monkeypatch.setattr(CinemaDiscoveryService, '_is_public_http_url', staticmethod(lambda url: True))
    manager._sessions = {'one': {}, 'two': {}}
    assert not manager.open('https://example.org/')['ok']


def test_session_reads_iframe_dom_and_exposes_capture_diagnostics(media_site, monkeypatch):
    base, _ = media_site
    monkeypatch.setattr(CinemaDiscoveryService, '_is_public_http_url', staticmethod(lambda url: url.startswith(base + '/')))
    manager = CinemaSessions(headless=True)
    try:
        opened = manager.open(base + '/dom-embedded')
        assert opened['ok']
        deadline = monotonic() + 5
        while monotonic() < deadline:
            status = manager.snapshot(opened['session_id'])
            if status['media']:
                break
            sleep(.1)
        assert status['media'][0]['evidence'] == 'dom'
        assert status['diagnostics']['frames'] == 2
        assert status['diagnostics']['videos'] == 1
        assert status['diagnostics']['captured'] == 1
        assert 'Selecione Assistir' in status['message']
    finally:
        manager.close_all()


def test_live_audit_distinguishes_decoded_sample_from_no_capture(media_site, monkeypatch, tmp_path):
    from scripts.cinema_live_audit import run
    base, _ = media_site
    monkeypatch.setattr(CinemaDiscoveryService, '_is_public_http_url', staticmethod(lambda url: url.startswith(base + '/')))
    output = tmp_path / 'audit.json'
    result = run('', [base + '/known-player', base + '/unknown-player'], 2, 2, output)
    assert result['sample_played'] == 1
    first, second = result['results']
    assert first['playback'][0]['status'] == 'sample_played'
    assert first['playback'][0]['width'] > 0
    assert first['playback'][0]['seconds_advanced'] >= .2
    assert second['candidates'] == 0 and second['playback'] == []
    assert output.exists()
    assert '/clip.mp4' not in output.read_text(encoding='utf-8')


def test_http_failure_still_runs_browser_probe(monkeypatch, tmp_path):
    import urllib.request
    from app.services import cinema_page
    monkeypatch.setattr(CinemaDiscoveryService, '_is_public_http_url', staticmethod(lambda url: True))
    def fail(*args, **kwargs):
        raise TimeoutError()
    monkeypatch.setattr(urllib.request, 'build_opener', lambda *a: type('Opener', (), {'open': fail})())
    monkeypatch.setattr(cinema_page, 'inspect_dynamic', lambda *a, **kwargs: {'media': [], 'episodes': [], 'status': 'timeout', 'message': 'Tempo esgotado'})
    result = CinemaDiscoveryService(tmp_path / 'sources.json').probe('https://example.org/page')
    assert result['ok'] and result['status'] == 'timeout'


def test_session_routes_validate_payload_and_delegate(monkeypatch):
    from app.ui.panel.server import PanelHandler
    from app.services.cinema_session import cinema_sessions
    calls, sent = [], []
    monkeypatch.setattr(cinema_sessions, 'open', lambda url: calls.append(url) or {'ok': True, 'session_id': 'test'})
    handler = object.__new__(PanelHandler)
    handler.path = '/api/cinema/session/open'
    handler.command = 'POST'
    handler._authorize_api = lambda *args: object()
    handler._send_json = lambda status, data: sent.append((status, data))
    for payload in [{'url': []}, {'url': 'https://example.org/page'}]:
        body = json.dumps(payload).encode()
        handler.headers = {'Content-Length': str(len(body))}
        handler.rfile = io.BytesIO(body)
        handler.do_POST()
    assert sent[0][0] == 400 and sent[1][0] == 200
    assert calls == ['https://example.org/page']
