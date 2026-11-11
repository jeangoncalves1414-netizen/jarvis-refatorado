import io
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event, Thread
from time import monotonic, sleep
from urllib.request import urlopen

import pytest

from app.services.cinema_discovery import CinemaDiscoveryService
from app.services.cinema_relay import CinemaRelay
from app.services.cinema_session import CinemaSessions


@pytest.fixture
def relay_site(monkeypatch):
    fixtures = Path(__file__).parents[1] / 'frontend/tests/fixtures/cinema'
    requests = []
    manager = CinemaSessions(headless=True)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send_json(self, status, data):
            self.send_response(status)
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

        def do_GET(self):
            if self.path.startswith('/api/cinema/session/media/'):
                _, _, _, _, _, session, resource = self.path.split('/')
                manager.serve(self, session, resource)
                return
            if self.path == '/page':
                body = b'<video autoplay muted src="/clip.mp4"></video>'
                self.send_response(200)
                self.send_header('Set-Cookie', 'fixture=1; Path=/; HttpOnly; SameSite=Lax')
                self.send_header('Content-Type', 'text/html')
            elif self.path == '/consumer':
                body = b'<video muted controls></video>'
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
            elif self.path == '/hls.js':
                body = (fixtures.parents[2] / 'node_modules/hls.js/dist/hls.min.js').read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', 'text/javascript')
            else:
                if 'fixture=1' not in self.headers.get('Cookie', ''):
                    self._send_json(403, {})
                    return
                name = self.path.strip('/')
                # Extensionless variant exercises playlist inference in the relay.
                name = 'video.m3u8' if name == 'variant' else name
                if name not in {'clip.mp4', 'master.m3u8', 'video.m3u8', 'video0.segment', 'audio.m3u8', 'audio0.segment', 'audio1.segment'}:
                    self._send_json(404, {})
                    return
                body = (fixtures / name).read_bytes()
                if name == 'master.m3u8':
                    body = body.replace(b'video.m3u8', b'variant')
                total = len(body)
                byte_range = self.headers.get('Range', '')
                requests.append((self.path, byte_range))
                if byte_range:
                    match = re.fullmatch(r'bytes=(\d+)-(\d*)', byte_range)
                    start, end = int(match[1]), min(int(match[2] or total-1), total-1)
                    body = body[start:end+1]
                    self.send_response(206)
                    self.send_header('Content-Range', f'bytes {start}-{end}/{total}')
                else:
                    self.send_response(200)
                kind = 'video/mp4' if name.endswith('.mp4') else 'application/vnd.apple.mpegurl' if name.endswith('.m3u8') else 'video/mp2t'
                self.send_header('Content-Type', kind)
                self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    base = f'http://127.0.0.1:{server.server_port}'
    monkeypatch.setattr(CinemaDiscoveryService, '_is_public_http_url', staticmethod(lambda url: url.startswith(base + '/')))
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield base, manager, requests
    finally:
        manager.close_all()
        server.shutdown()
        server.server_close()


def test_session_relay_plays_cookie_video_in_a_new_browser_and_preserves_range(relay_site):
    from playwright.sync_api import sync_playwright
    base, manager, requests = relay_site
    opened = manager.open(base + '/page')
    assert opened['ok']
    session_id = opened['session_id']
    deadline = monotonic() + 5
    while monotonic() < deadline:
        snapshot = manager.snapshot(session_id)
        if snapshot['media']:
            break
        sleep(.1)
    media = snapshot['media'][0]
    assert 'fixture' not in json.dumps(snapshot)
    assert media['url'].startswith('/api/cinema/session/media/')
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(base + '/consumer')
            assert not page.context.cookies(), 'Consumer must not receive upstream cookies'
            page.evaluate('(url)=>{const v=document.querySelector("video");v.src=url;v.play()}', media['url'])
            page.wait_for_function('document.querySelector("video").videoWidth > 0 && document.querySelector("video").currentTime > 0')
            assert any(path == '/clip.mp4' and value.startswith('bytes=') for path, value in requests)
        finally:
            browser.close()
    manager.close(session_id)
    assert manager.snapshot(session_id)['status'] == 'closed'
    from urllib.error import HTTPError
    with pytest.raises(HTTPError) as error:
        urlopen(base + media['url'])
    assert error.value.code == 410


def test_session_keeps_network_evidence_over_a_weaker_dom_match():
    manager = CinemaSessions(headless=True)
    stop = Event()
    state = {
        'stop': stop, 'status': 'open', 'media': {}, 'episodes': [], 'url': 'https://example.org/page',
        'relay': CinemaRelay('session', stop, is_public=lambda url: url.startswith('https://example.org/')),
    }
    manager._sessions['session'] = state
    try:
        manager._remember_media(state, 'https://example.org/video.mp4', source_url=state['url'], kind='MP4', label='MP4 · página', evidence='dom')
        manager._remember_media(state, 'https://example.org/video.mp4', source_url=state['url'], kind='MP4', label='MP4 · sessão', evidence='network')
        snapshot = manager.snapshot('session')
        assert len(snapshot['media']) == 1
        assert snapshot['media'][0]['evidence'] == 'network'
        assert snapshot['media'][0]['label'] == 'MP4 · sessão'
    finally:
        manager.close_all()


def test_hls_rewrites_variants_audio_segments_and_keeps_cookie(relay_site):
    base, manager, _ = relay_site
    opened = manager.open(base + '/page')
    relay = manager._sessions[opened['session_id']]['relay']
    deadline = monotonic() + 5
    while not relay.cookies and monotonic() < deadline:
        sleep(.1)
    path = relay.register(base + '/master.m3u8', base + '/page', 'HLS')
    master = urlopen(base + path).read().decode()
    assert 'fixture' not in master and 'http://' not in master
    variant = next(line for line in master.splitlines() if line and not line.startswith('#'))
    playlist = urlopen(base + variant).read().decode()
    segment = next(line for line in playlist.splitlines() if line and not line.startswith('#'))
    assert len(urlopen(base + segment).read()) > 1000
    audio = re.search(r'URI="([^"]+)"', master)[1]
    assert '#EXTINF:' in urlopen(base + audio).read().decode()
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(base + '/consumer')
            page.add_script_tag(url=base + '/hls.js')
            page.evaluate('''url => {
              const hls = new Hls(); const video = document.querySelector('video');
              hls.attachMedia(video); hls.loadSource(url);
              hls.on(Hls.Events.MANIFEST_PARSED, () => video.play());
            }''', path)
            page.wait_for_function('document.querySelector("video").videoWidth > 0 && document.querySelector("video").currentTime > 0')
        finally:
            browser.close()
    # MP4 byte offsets survive the relay too.
    mp4 = relay.register(base + '/clip.mp4')
    response, _ = relay.open_resource(mp4.rsplit('/', 1)[1], 'bytes=10-19')
    with response:
        assert response.status == 206 and len(response.read()) == 10
        assert response.headers['Content-Range'].startswith('bytes 10-19/')


def test_relay_rejects_private_resources_unknown_ids_and_invalid_ranges():
    relay = CinemaRelay('test', Event())
    with pytest.raises(ValueError):
        relay.register('http://127.0.0.1/secret')
    with pytest.raises(ValueError):
        relay.open_resource('unknown')
    resource = {'referer': '', 'user_agent': ''}
    with pytest.raises(ValueError):
        relay.manifest('#EXTM3U\nhttp://127.0.0.1/secret\n', 'https://example.org/master', resource)


def test_episode_comments_are_not_episodes_and_anime_catalog_is_scoped():
    from app.services.cinema_page import parse_page
    url = 'https://animesonlinecc.to/episodio/naruto-shippuden-episodio-1/'
    html = f'''<a href="#comment-1">Responder</a><a href="{url}#option-2">Legendado</a>
      <a href="/episodio/naruto-shippuden-episodio-2/">Próximo</a>
      <a href="/episodio/bleach-episodio-3/">Bleach episódio 3</a>
      <a href="/anime/naruto-shippuden/">Todos os episódios</a>'''
    result = parse_page(html, url)
    assert [item['episode'] for item in result['episodes']] == [2]
    assert result['series_url'] == 'https://animesonlinecc.to/anime/naruto-shippuden/'


def test_automatic_probe_retains_cookie_after_browser_closes(relay_site):
    from app.services.cinema_page import inspect_dynamic
    base, manager, _ = relay_site
    result = inspect_dynamic(base + '/page', lambda url: url.startswith(base + '/'), observation_seconds=.5)
    assert result['status'] == 'detected'
    media = next(item for item in result['media'] if item['url'].endswith('/clip.mp4'))
    assert not manager._sessions
    assert len(urlopen(base + media['playback_url']).read()) > 1000


def test_relay_expiry_and_redirect_cookie_isolation(monkeypatch):
    from app.services import cinema_relay
    from urllib.request import Request
    monkeypatch.setattr(CinemaDiscoveryService, '_is_public_http_url', staticmethod(lambda url: True))
    request = Request('https://example.org/video', headers={'Cookie': 'secret=1', 'Authorization': 'private'})
    redirected = cinema_relay._Redirect().redirect_request(request, None, 302, 'Found', {}, 'https://other.example/video')
    assert redirected.get_header('Cookie') is None and redirected.get_header('Authorization') is None
    relay = cinema_relay.probe_relay([], lambda url: True)
    clock = monotonic()
    monkeypatch.setattr(cinema_relay, 'monotonic', lambda: clock + 601)
    assert cinema_relay.get_probe_relay(relay.session_id) is None
    assert relay.stop.is_set()


def test_panel_session_get_routes_are_authorized(monkeypatch):
    from app.ui.panel.server import PanelHandler
    from app.services.cinema_session import cinema_sessions
    calls = []
    monkeypatch.setattr(cinema_sessions, 'snapshot', lambda session: calls.append(('status', session)) or {'ok': True})
    monkeypatch.setattr(cinema_sessions, 'serve', lambda handler, session, resource: calls.append(('media', session, resource)))
    handler = object.__new__(PanelHandler)
    handler.headers = {}
    handler._send_json = lambda *args: None
    handler._authorize_api = lambda *args: None
    handler.path = '/api/cinema/session/media/session/resource'
    handler.do_GET()
    assert not calls
    handler._authorize_api = lambda *args: object()
    handler.do_GET()
    handler.path = '/api/cinema/session/status/session'
    handler.do_GET()
    assert calls == [('media', 'session', 'resource'), ('status', 'session')]
