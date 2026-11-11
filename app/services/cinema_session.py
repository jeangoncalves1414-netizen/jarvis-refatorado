"""User-opened browser windows: playback stays in the site's original context."""
from __future__ import annotations

import atexit
from threading import Event, Lock, Thread
from uuid import uuid4
from time import monotonic
from app.core.logger import logger

from app.services.cinema_discovery import CinemaDiscoveryService
from app.services.cinema_relay import CinemaRelay, get_probe_relay
from app.services.cinema_page import response_media, parse_page, response_belongs_to_page


class CinemaSessions:
    def __init__(self, *, headless=False):
        self.headless = headless
        self._lock = Lock()
        self._sessions = {}

    def open(self, url):
        if not isinstance(url, str) or not CinemaDiscoveryService._is_public_http_url(url):
            return {"ok": False, "error": "Informe uma URL HTTP/HTTPS pública."}
        with self._lock:
            if len(self._sessions) >= 2:
                return {"ok": False, "error": "Feche uma sessão de cinema antes de abrir outra (máximo: 2)."}
            session_id = uuid4().hex
            state = {"stop": Event(), "ready": Event(), "status": "opening", "media": {}, "episodes": [], "url": url,
                     "diagnostics": {"frames": 0, "videos": 0, "blob_videos": 0, "dash_responses": 0, "capture_errors": 0}}
            state['relay'] = CinemaRelay(session_id, state['stop'])
            self._sessions[session_id] = state
        worker = Thread(target=self._run, args=(url, state), daemon=True, name="cinema-session")
        state["worker"] = worker
        worker.start()
        if not state["ready"].wait(18):
            state["stop"].set()
            return {"ok": False, "error": "O navegador demorou a abrir. Tente novamente."}
        if state["status"] != "open":
            return {"ok": False, "error": "Não foi possível abrir a sessão. Verifique a instalação do Chromium do Playwright."}
        return {"ok": True, "session_id": session_id, "message": "Sessão aberta. Use o player nessa janela; a sessão será mantida até você fechá-la."}

    def _remember_media(self, state, url, *, source_url, kind, label, referer='', user_agent='', origin='', evidence='network'):
        """Keep the strongest observation for each session relay resource."""
        try:
            relay_url = state['relay'].register(url, referer, kind, user_agent, origin)
        except Exception:
            return
        with self._lock:
            existing = state['media'].get(relay_url)
            if existing and existing.get('evidence') == 'network' and evidence != 'network':
                return
            state['media'][relay_url] = {
                'url': relay_url,
                'kind': kind,
                'label': label,
                'direct': True,
                'source_url': source_url,
                'session_id': state['relay'].session_id,
                'evidence': evidence,
                'last_seen': monotonic(),
            }

    def _run(self, url, state):
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=self.headless)
                try:
                    context = browser.new_context(accept_downloads=False, service_workers="block")
                    # This window has no Jarvis bridge, profile, or local-panel access.
                    context.route("**/*", lambda route: route.continue_() if CinemaDiscoveryService._is_public_http_url(route.request.url) else route.abort())
                    def capture(response):
                        if not response_belongs_to_page(response, page):
                            return
                        content_type = response.headers.get('content-type', '')
                        if response.status < 400 and ('dash+xml' in content_type.lower() or '.mpd' in response.url.lower().split('?')[0]):
                            with self._lock:
                                state['diagnostics']['dash_responses'] += 1
                        if response.status >= 400 or not response_media(response.url, content_type):
                            return
                        try:
                            headers = response.request.all_headers()
                            kind = 'HLS' if 'mpegurl' in content_type.lower() or '.m3u8' in response.url.lower() else 'MP4'
                            state['relay'].update_cookies(context.cookies())
                            self._remember_media(
                                state, response.url, source_url=page.url, kind=kind, label=kind + ' · sessão',
                                referer=headers.get('referer', ''), user_agent=headers.get('user-agent', ''),
                                origin=headers.get('origin', ''), evidence='network',
                            )
                        except Exception as exc:
                            with self._lock:
                                state['diagnostics']['capture_errors'] += 1
                            logger.warn('cinema_session', 'Falha ao registrar mídia da sessão', {'error_type': type(exc).__name__})
                    context.on('response', capture)
                    page = context.new_page()
                    def navigated(frame):
                        if frame == page.main_frame:
                            with self._lock:
                                state['url'] = frame.url
                                state['media'] = {}
                                state['episodes'] = []
                                state['diagnostics'] = dict.fromkeys(state['diagnostics'], 0)
                    page.on('framenavigated', navigated)
                    page.on("popup", lambda popup: popup.close())
                    page.on("download", lambda download: download.cancel())
                    page.on("dialog", lambda dialog: dialog.dismiss())
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=12000)
                    except Exception:
                        # A slow page may still render and be usable in the visible window.
                        pass
                    state["status"] = "open"
                    state["ready"].set()
                    last_update = 0
                    while not state["stop"].is_set() and not page.is_closed():
                        page.wait_for_timeout(250)
                        if monotonic() - last_update >= 1:
                            last_update = monotonic()
                            state['relay'].update_cookies(context.cookies())
                            try:
                                episodes, videos, blobs = [], 0, 0
                                for frame in page.frames[:8]:
                                    try:
                                        parsed = parse_page(frame.content(), frame.url)
                                        counts = frame.evaluate("""() => {
                                            const videos = [...document.querySelectorAll('video')];
                                            return {videos: videos.length, blobs: videos.filter(v => (v.currentSrc || v.src).startsWith('blob:')).length};
                                        }""")
                                        videos += counts['videos']
                                        blobs += counts['blobs']
                                        if frame == page.main_frame:
                                            episodes = parsed['episodes']
                                        for candidate in parsed['media']:
                                            if candidate.get('direct') and not candidate.get('suspected_ad'):
                                                self._remember_media(
                                                    state, candidate['url'], source_url=page.url,
                                                    kind=candidate.get('kind') or 'Vídeo',
                                                    label=(candidate.get('label') or 'Vídeo') + ' · página',
                                                    referer=frame.url, evidence='dom',
                                                )
                                    except Exception:
                                        continue
                                with self._lock:
                                    state['url'] = page.url
                                    state['episodes'] = episodes
                                    state['diagnostics'].update(frames=len(page.frames), videos=videos, blob_videos=blobs)
                            except Exception:
                                pass
                finally:
                    browser.close()
        except Exception as exc:
            logger.warn('cinema_session', 'Sessão de captura interrompida', {'error_type': type(exc).__name__})
            state["status"] = "error"
        finally:
            state['stop'].set()
            state["ready"].set()
            with self._lock:
                for session_id, current in list(self._sessions.items()):
                    if current is state:
                        del self._sessions[session_id]

    def snapshot(self, session_id):
        with self._lock:
            state = self._sessions.get(session_id)
            if not state or state['stop'].is_set():
                return {'ok': True, 'status': 'closed', 'media': [], 'episodes': []}
            evidence_rank = {'network': 2, 'dom': 1}
            media = sorted(state['media'].values(), key=lambda item: (
                evidence_rank.get(item.get('evidence'), 0), item.get('kind') == 'HLS', item.get('last_seen', 0),
            ), reverse=True)
            diagnostics = dict(state.get('diagnostics', {}))
            diagnostics['captured'] = len(media)
            if diagnostics != state.get('logged_diagnostics'):
                logger.info('cinema_session', 'Diagnóstico da captura', diagnostics)
                state['logged_diagnostics'] = diagnostics
            if media:
                message = f'{len(media)} fonte(s) capturada(s). Selecione Assistir abaixo; a reprodução ainda precisa ser verificada.'
            elif diagnostics.get('dash_responses'):
                message = 'Stream DASH detectado, mas este formato ainda não está integrado ao player do Jarvis.'
            elif diagnostics.get('videos'):
                message = 'Player de vídeo encontrado, mas nenhuma fonte compatível foi capturada. Isso não significa que o site não tenha vídeo.'
            else:
                message = 'Nenhuma fonte capturada nesta sessão. Inicie o vídeo na janela aberta pelo Jarvis e consulte novamente.'
            return {'ok': True, 'status': state['status'], 'page_url': state['url'],
                    'media': media[:24], 'episodes': list(state['episodes']), 'diagnostics': diagnostics, 'message': message}

    def serve(self, handler, session_id, resource_id):
        with self._lock:
            state = self._sessions.get(session_id)
        if not state or state['stop'].is_set():
            relay = get_probe_relay(session_id)
            if relay:
                relay.serve(handler, resource_id)
                return
            handler._send_json(410, {'ok': False, 'error': 'Sessão encerrada. Abra novamente o site.'})
            return
        state['relay'].serve(handler, resource_id)

    def close(self, session_id):
        with self._lock:
            state = self._sessions.get(session_id)
            if state:
                state["stop"].set()
        return {"ok": True}

    def close_all(self):
        with self._lock:
            workers = [state.get("worker") for state in self._sessions.values()]
            for state in self._sessions.values():
                state["stop"].set()
        for worker in workers:
            if worker:
                worker.join(timeout=3)


cinema_sessions = CinemaSessions()
atexit.register(cinema_sessions.close_all)
