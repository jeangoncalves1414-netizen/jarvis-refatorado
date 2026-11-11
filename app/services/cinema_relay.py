"""Session-scoped media relay; upstream URLs and cookies never enter relay URLs."""
from __future__ import annotations

from http.cookiejar import Cookie, CookieJar
import re
from threading import Event, RLock
from time import monotonic
from urllib.error import HTTPError
from urllib.parse import urljoin
from urllib.request import Request, build_opener, HTTPCookieProcessor
from uuid import uuid4

from app.services.cinema_discovery import CinemaDiscoveryService, _PublicRedirectHandler


class _Redirect(_PublicRedirectHandler):
    def redirect_request(self, req, *args):
        result = super().redirect_request(req, *args)
        if result is not None:
            result.remove_header('Cookie')
            result.remove_header('Authorization')
        return result


class CinemaRelay:
    def __init__(self, session_id, stop, is_public=None):
        self.session_id, self.stop = session_id, stop
        self.lock = RLock()
        self.resources = {}
        self.urls = {}
        self.cookies = []
        self.is_public = is_public or CinemaDiscoveryService._is_public_http_url
        self.last_used = monotonic()

    def register(self, url, referer='', kind='resource', user_agent='', origin=''):
        if not self.is_public(url):
            raise ValueError('Recurso não público.')
        with self.lock:
            if self.stop.is_set():
                raise ValueError('Sessão encerrada.')
            if url not in self.urls:
                if len(self.resources) >= 8192:
                    raise ValueError('Limite de recursos da sessão atingido.')
                resource_id = uuid4().hex
                self.urls[url] = resource_id
                self.resources[resource_id] = {'url': url, 'referer': referer, 'kind': kind, 'user_agent': user_agent, 'origin': origin}
            else:
                resource_id = self.urls[url]
                if kind == 'HLS':
                    self.resources[resource_id]['kind'] = kind
            return f'/api/cinema/session/media/{self.session_id}/{resource_id}'

    def update_cookies(self, cookies):
        with self.lock:
            self.cookies = cookies

    def _opener(self):
        jar = CookieJar()
        with self.lock:
            for cookie in self.cookies:
                domain = cookie['domain']
                jar.set_cookie(Cookie(0, cookie['name'], cookie['value'], None, False,
                    domain, domain.startswith('.'), domain.startswith('.'), cookie['path'], True,
                    cookie.get('secure', False), int(cookie['expires']) if cookie.get('expires', -1) > 0 else None,
                    False, None, None, {}, False))
        return build_opener(_Redirect(), HTTPCookieProcessor(jar))

    def open_resource(self, resource_id, byte_range=''):
        with self.lock:
            resource = dict(self.resources.get(resource_id, {}))
        if not resource or self.stop.is_set():
            raise ValueError('Sessão ou recurso encerrado.')
        url = resource['url']
        if not self.is_public(url):
            raise ValueError('Recurso não público.')
        headers = {'Accept-Encoding': 'identity'}
        for key, field in [('Referer', 'referer'), ('User-Agent', 'user_agent'), ('Origin', 'origin')]:
            if resource[field]:
                headers[key] = resource[field]
        if byte_range:
            if not re.fullmatch(r'bytes=(?:\d+-\d*|-\d+)', byte_range):
                raise ValueError('Intervalo de vídeo inválido.')
            headers['Range'] = byte_range
        response = self._opener().open(Request(url, headers=headers), timeout=12)
        return response, resource

    def manifest(self, text, base_url, resource):
        if not text.lstrip('\ufeff').startswith('#EXTM3U'):
            raise ValueError('Manifesto HLS inválido.')
        def rewrite(value, playlist=False):
            target = urljoin(base_url, value)
            kind = 'HLS' if playlist or re.search(r'\.m3u8(?:$|[?#])', target, re.I) else 'resource'
            return self.register(target, resource['referer'], kind, resource['user_agent'], resource.get('origin', ''))
        lines = []
        playlist = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                line = rewrite(stripped, playlist)
                playlist = False
            elif stripped.startswith('#'):
                line = re.sub(r'\bURI="([^"]+)"', lambda match: 'URI="' + rewrite(match[1], stripped.startswith(('#EXT-X-MEDIA:', '#EXT-X-I-FRAME-STREAM-INF:'))) + '"', line)
                if stripped.startswith('#EXT-X-STREAM-INF:'):
                    playlist = True
            lines.append(line)
        return ('\n'.join(lines) + '\n').encode('utf-8')

    def serve(self, handler, resource_id):
        """Stream bounded chunks; preserve Range, never buffer a whole movie."""
        started = False
        self.last_used = monotonic()
        try:
            response, resource = self.open_resource(resource_id, handler.headers.get('Range', ''))
            with response:
                content_type = response.headers.get('Content-Type', 'application/octet-stream')
                is_hls = resource['kind'] == 'HLS' or 'mpegurl' in content_type.lower()
                if is_hls:
                    raw = response.read(2_000_001)
                    if len(raw) > 2_000_000:
                        raise ValueError('Manifesto excede o limite.')
                    data = self.manifest(raw.decode('utf-8-sig'), response.geturl(), resource)
                    handler.send_response(200)
                    handler.send_header('Content-Type', 'application/vnd.apple.mpegurl')
                    handler.send_header('Content-Length', str(len(data)))
                else:
                    if not (content_type.lower().startswith(('video/', 'audio/', 'text/vtt', 'application/octet-stream', 'application/mp4'))):
                        raise ValueError('A fonte não respondeu com mídia.')
                    handler.send_response(response.status)
                    handler.send_header('Content-Type', content_type)
                    for name in ('Content-Length', 'Content-Range', 'Accept-Ranges'):
                        if response.headers.get(name):
                            handler.send_header(name, response.headers[name])
                handler.send_header('Cache-Control', 'no-store')
                handler.send_header('X-Content-Type-Options', 'nosniff')
                handler.send_header('Content-Security-Policy', "sandbox; default-src 'none'")
                handler.send_header('Connection', 'close')
                handler.close_connection = True
                handler.end_headers()
                started = True
                if is_hls:
                    handler.wfile.write(data)
                else:
                    while not self.stop.is_set():
                        chunk = response.read(64 * 1024)
                        if not chunk:
                            break
                        handler.wfile.write(chunk)
                        self.last_used = monotonic()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:
            if not started:
                status = exc.code if isinstance(exc, HTTPError) and exc.code in {401, 403, 404, 416} else 502
                handler._send_json(status, {'ok': False, 'error': 'Esta fonte não respondeu à reprodução na sessão.'})
            else:
                handler.close_connection = True
        finally:
            self.last_used = monotonic()


_probe_lock = RLock()
_probe_relays = {}


def probe_relay(cookies, is_public):
    """Short-lived cookie snapshots for automatic scans; no idle browser retained."""
    with _probe_lock:
        now = monotonic()
        for key, (relay, touched) in list(_probe_relays.items()):
            if now - max(touched, relay.last_used) > 600:
                relay.stop.set()
                del _probe_relays[key]
        if len(_probe_relays) >= 72:
            oldest = min(_probe_relays, key=lambda key: _probe_relays[key][1])
            _probe_relays.pop(oldest)[0].stop.set()
        relay = CinemaRelay(uuid4().hex, Event(), is_public)
        relay.update_cookies(cookies)
        _probe_relays[relay.session_id] = (relay, now)
        return relay


def get_probe_relay(session_id):
    with _probe_lock:
        item = _probe_relays.get(session_id)
        if not item:
            return None
        relay, touched = item
        if monotonic() - max(touched, relay.last_used) > 600:
            relay.stop.set()
            del _probe_relays[session_id]
            return None
        _probe_relays[session_id] = (relay, monotonic())
        return relay
