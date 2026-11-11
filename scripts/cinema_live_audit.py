"""Opt-in live audit: search -> detect -> decode a short sample through Jarvis's relay."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from threading import Thread
from time import monotonic
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.cinema_discovery import CinemaDiscoveryService
from app.services.cinema_page import _WORKERS
from app.services.cinema_relay import get_probe_relay, probe_relay


def public_page(url):
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', ''))


def playback_sample(browser, base, path, kind):
    with browser.new_context(accept_downloads=False) as context:
        context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(base + '/') else route.abort())
        page = context.new_page()
        page.goto(base, timeout=5000)
        return page.evaluate("""({url, kind}) => new Promise(resolve => {
            const video = document.querySelector('video');
            let hls, timer, interval, done = false;
            const finish = (status, detail) => {
                if (done) return; done = true;
                clearTimeout(timer); clearInterval(interval);
                const result = {status, detail, width: video.videoWidth, height: video.videoHeight,
                    duration: Number.isFinite(video.duration) ? video.duration : null,
                    seconds_advanced: video.currentTime};
                video.pause(); if (hls) hls.destroy();
                video.removeAttribute('src'); video.load(); resolve(result);
            };
            timer = setTimeout(() => finish('unconfirmed', 'playback_timeout'), 6500);
            interval = setInterval(() => {
                if (video.videoWidth > 0 && video.currentTime >= .2) finish('sample_played', 'decoded_video');
            }, 100);
            video.onerror = () => finish('failed', 'media_error_' + video.error?.code);
            if (kind === 'HLS' && window.Hls?.isSupported()) {
                hls = new Hls({maxBufferLength: 2, maxMaxBufferLength: 4});
                hls.on(Hls.Events.ERROR, (_, data) => { if(data.fatal) finish('failed', data.details); });
                hls.loadSource(url); hls.attachMedia(video);
            } else video.src = url;
            video.play().catch(() => {});
        })""", {'url': base + path, 'kind': kind})


def run(query, urls, limit, workers, output):
    service = CinemaDiscoveryService()
    started = monotonic()
    search = service.search(query, limit=limit) if query else {'results': []}
    targets = list(dict.fromkeys([*urls, *(r['url'] for r in search.get('results', []))]))[:limit]
    report = {'started_utc': datetime.now(timezone.utc).isoformat(), 'query': query,
              'search_seconds': round(monotonic() - started, 2), 'search_error': search.get('error'),
              'warnings': search.get('warnings', []), 'workers': workers, 'results': []}
    print(f'Search: {len(targets)} pages, {report["search_seconds"]}s', flush=True)
    def inspect(url):
        tick = monotonic()
        try:
            result = service.probe(url, fast=False)
        except Exception as error:
            result = {'status': 'error', 'error': type(error).__name__, 'media': []}
        row = {'page': public_page(url), 'detection_seconds': round(monotonic() - tick, 2),
               'status': result.get('status', 'rejected' if result.get('ok') is False else 'unconfirmed'), 'message': result.get('message', result.get('error')),
               'diagnostics': result.get('diagnostics', {}),
               'candidates': len(result.get('media', [])), 'playback': []}
        print(f'Detected: {row["page"]} | {row["status"]} | {row["candidates"]} candidates', flush=True)
        return row, [m for m in result.get('media', []) if m.get('direct') and not m.get('suspected_ad')][:2]
    # Separate phases keep browser concurrency at the chosen limit, including playback.
    with ThreadPoolExecutor(max_workers=workers) as executor:
        inspected = list(executor.map(inspect, targets))
    allowed_sessions = set()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def _send_json(self, status, data):
            self.send_response(status); self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        def do_GET(self):
            parts = self.path.split('/')
            if len(parts) == 7 and parts[1:5] == ['api', 'cinema', 'session', 'media']:
                relay = get_probe_relay(parts[5]) if parts[5] in allowed_sessions else None
                if relay:
                    relay.serve(self, parts[6]); return
            if self.path == '/':
                body, kind = b'<video muted playsinline></video><script src="/hls.js"></script>', 'text/html'
            elif self.path == '/hls.js':
                body, kind = (ROOT / 'frontend/node_modules/hls.js/dist/hls.min.js').read_bytes(), 'application/javascript'
            else:
                self._send_json(404, {'error': 'not found'}); return
            self.send_response(200); self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body))); self.end_headers()
            self.wfile.write(body)
    for row, media in inspected:
        for item in media:
            if not item.get('playback_url'):
                relay = probe_relay([], service._is_public_http_url)
                item['playback_url'] = relay.register(item['url'], row['page'], item.get('kind', 'MP4'))
                item['session_id'] = relay.session_id
            allowed_sessions.add(item['session_id'])
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'
    def verify(entry):
        row, media = entry
        for item in media:
            try:
                sample = _WORKERS.run(lambda browser: playback_sample(browser, base, item['playback_url'], item.get('kind')))
            except Exception as error:
                sample = {'status': 'error', 'detail': type(error).__name__}
            row['playback'].append({'kind': item.get('kind'), **sample})
            if sample['status'] == 'sample_played':
                break
        print(f'Playback: {row["page"]} | {[p["status"] for p in row["playback"]]}', flush=True)
        return row
    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            report['results'] = list(executor.map(verify, inspected))
    finally:
        server.shutdown(); server.server_close()
        for session in allowed_sessions:
            relay = get_probe_relay(session)
            if relay:
                relay.stop.set()
    report['total_seconds'] = round(monotonic() - started, 2)
    report['sample_played'] = sum(any(p['status'] == 'sample_played' for p in row['playback']) for row in report['results'])
    report['limit_note'] = 'Short decoded sample only; does not verify movie identity, full duration, audio or absence of ads. Unconfirmed is not absence of video.'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--query', default='')
    parser.add_argument('--url', action='append', default=[])
    parser.add_argument('--limit', type=int, choices=range(1, 21), default=6)
    parser.add_argument('--workers', type=int, choices=(1, 2, 3), default=3)
    parser.add_argument('--output', type=Path, default=ROOT / 'scratch/cinema-audit/latest.json')
    args = parser.parse_args()
    if not args.query and not args.url:
        parser.error('Use --query or --url')
    try:
        result = run(args.query, args.url, args.limit, args.workers, args.output)
        print(f'Report: {args.output} | played {result["sample_played"]}/{len(result["results"])}', flush=True)
    finally:
        _WORKERS.close()
