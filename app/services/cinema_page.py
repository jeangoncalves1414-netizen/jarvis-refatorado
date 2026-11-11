"""Extrai fontes e episódios publicados no HTML/DOM, sem adaptadores privados."""
from __future__ import annotations

import atexit
import json
import re
import unicodedata
from time import monotonic
from html.parser import HTMLParser
from threading import BoundedSemaphore
from urllib.parse import urljoin, urlparse, urldefrag
from app.services.cinema_workers import BrowserWorkers


_BROWSERS = BoundedSemaphore(4)
_WORKERS = BrowserWorkers()
atexit.register(_WORKERS.close)
_MEDIA = re.compile(r"\.(m3u8|mp4|webm|ogv|mov|m4v)(?:$|[?#])", re.I)
_AD_MEDIA = re.compile(r"(?:adserver|doubleclick|googlesyndication|adsystem|advertis|pre[-_]?roll|/ads?/|\bvast\b)", re.I)


def episode_info(text: str, attrs: dict | None = None) -> tuple[int, int] | None:
    attrs = attrs or {}
    pair = re.search(r"(?:s|t)(\d{1,3})[ ._-]*(?:e|x)(\d{1,4})|\b(\d{1,3})x(\d{1,4})\b", text, re.I)
    if pair:
        values = pair.groups()
        return int(values[0] or values[2]), int(values[1] or values[3])
    number = attrs.get("data-episode") or attrs.get("episodeNumber")
    match = re.search(r"(?:epis[oó]dio|episode|ep)[\s_./:-]*(\d{1,4})\b", text, re.I)
    if not number and match:
        number = match[1]
    if not str(number or "").isdigit():
        return None
    season = attrs.get("data-season") or attrs.get("seasonNumber")
    match = re.search(r"(?:temporada|season)[\s_./:-]*(\d{1,3})\b", text, re.I)
    if not season and match:
        season = match[1]
    return int(season) if str(season or "").isdigit() else 1, int(number)


def media_info(url: str, label: str = "", source_url: str = "") -> dict:
    quality = re.search(r"\b(2160|1440|1080|720|540|480|360)p\b", label + " " + url, re.I)
    audio = re.search(r"\b(dublado|legendado|dual|pt-br|portugu[eê]s|english|japon[eê]s)\b", label, re.I)
    kind = "HLS" if ".m3u8" in url.lower() else urlparse(url).path.rsplit(".", 1)[-1].upper()
    return {"url": url, "label": label.strip()[:120] or kind, "kind": kind,
            "direct": True, "source_url": source_url,
            "quality": quality[0] if quality else "", "audio": audio[0] if audio else "",
            "suspected_ad": is_probable_ad_media(url, label)}


def is_probable_ad_media(url: str, label: str = "") -> bool:
    """Keep obvious ad endpoints out of automatic playback without guessing at page content."""
    return bool(_AD_MEDIA.search(f"{url} {label}"))


class _Page(HTMLParser):
    def __init__(self, url):
        super().__init__(convert_charrefs=True)
        self.url = url
        self.media = []
        self.episodes = []
        self.links = []
        self.anchor = None
        self.script = None

    def resolve(self, value):
        url = urljoin(self.url, str(value or ""))
        return url if urlparse(url).scheme in {"http", "https"} else ""

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag in {"video", "source"} and values.get("src"):
            url = self.resolve(values["src"])
            if url:
                self.media.append(media_info(url, values.get("label") or values.get("data-quality") or values.get("title") or "", self.url))
        if tag == "a" and values.get("href"):
            self.anchor = [values, ""]
        if tag == "script" and values.get("type") == "application/ld+json":
            self.script = ""

    def handle_data(self, data):
        if self.anchor is not None:
            self.anchor[1] += data
        if self.script is not None:
            self.script += data

    def handle_endtag(self, tag):
        if tag == "a" and self.anchor:
            attrs, text = self.anchor
            self.add_episode(attrs.get("href"), text, attrs)
            if text.strip():
                self.links.append({"url": self.resolve(attrs.get("href")), "title": " ".join(text.split())[:200]})
            self.anchor = None
        if tag == "script" and self.script is not None:
            try:
                self.structured(json.loads(self.script))
            except (ValueError, TypeError, RecursionError):
                pass
            self.script = None

    def add_episode(self, url, title, attrs=None):
        if not url or str(url).startswith('#'):
            return
        resolved = self.resolve(url)
        # Comments/player tabs inherit the episode number from the current URL.
        if urlparse(resolved).fragment and urldefrag(resolved)[0] == urldefrag(self.url)[0]:
            return
        resolved = urldefrag(resolved)[0]
        # Números isolados não são episódios: podem ser a paginação ou anúncios.
        info = episode_info(title + " " + resolved, attrs)
        if resolved and info and 0 < info[0] <= 100 and 0 < info[1] <= 10000:
            self.episodes.append({"url": resolved, "title": title.strip()[:160] or f"Episódio {info[1]}", "season": info[0], "episode": info[1]})

    def structured(self, value, depth=0):
        if depth > 12:
            return
        if isinstance(value, list):
            for item in value[:500]:
                self.structured(item, depth + 1)
        elif isinstance(value, dict):
            if value.get("@type") in ("TVEpisode", "Episode"):
                season = value.get("partOfSeason", {})
                self.add_episode(value.get("url"), str(value.get("name") or ""), {
                    "episodeNumber": value.get("episodeNumber"),
                    "seasonNumber": season.get("seasonNumber") if isinstance(season, dict) else None,
                })
            if value.get("@type") == "VideoObject" and value.get("contentUrl"):
                url = self.resolve(value["contentUrl"])
                if url:
                    self.media.append(media_info(url, str(value.get("name") or ""), self.url))
            for child in value.values():
                if isinstance(child, (dict, list)):
                    self.structured(child, depth + 1)


def parse_page(html: str, url: str) -> dict:
    page = _Page(url)
    page.feed(html[:1_500_000])
    episodes = {item["url"]: item for item in page.episodes}
    series_url = ""
    parsed_url = urlparse(url)
    # This source publishes an explicit series index; ignore recommendations.
    if parsed_url.hostname in {"animesonlinecc.to", "www.animesonlinecc.to"}:
        match = re.fullmatch(r"/(?:episodio/([^/]+?)-episodio-\d+|anime/([^/]+))/?", parsed_url.path)
        if match:
            slug = match[1] or match[2]
            prefix = f"/episodio/{slug}-episodio-"
            episodes = {key: item for key, item in episodes.items()
                        if urlparse(key).hostname == parsed_url.hostname
                        and re.fullmatch(re.escape(prefix) + r"\d+/?", urlparse(key).path)}
            if match[1]:
                expected = f"/anime/{slug}/"
                series_url = next((item['url'] for item in page.links
                                   if urlparse(item['url']).hostname == parsed_url.hostname
                                   and urlparse(item['url']).path == expected), "")
    return {"media": page.media[:24], "episodes": list(episodes.values())[:1000], "series_url": series_url}


def search_links(html: str, url: str, query: str) -> list[dict]:
    page = _Page(url)
    page.feed(html[:1_500_000])
    normalize = lambda value: unicodedata.normalize("NFKD", value.lower()).encode("ascii", "ignore").decode()
    terms = re.findall(r"[a-z0-9]{3,}", normalize(query))
    host = urlparse(url).hostname
    seen = set()
    results = []
    for item in page.links:
        target = urlparse(item["url"])
        if (target.hostname != host or target.path == "/" or item["url"] in seen or not terms
                or not all(term in normalize(item["title"]) for term in terms)):
            continue
        seen.add(item["url"])
        results.append({**item, "source": host, "snippet": "Resultado da pesquisa pública do próprio site."})
    return results


# Run before page scripts so late videos in new frames are observed too.
_VIDEO_OBSERVER = r"""(() => {
  const seen = new WeakSet();
  const watch = () => document.querySelectorAll('video').forEach(v => {
    if (seen.has(v)) return;
    seen.add(v); v.muted = true;
    v.addEventListener('loadedmetadata', () => v.play().catch(() => {}), {once:true});
    v.play().catch(() => {});
  });
  new MutationObserver(watch).observe(document, {childList:true, subtree:true});
  document.addEventListener('DOMContentLoaded', watch); watch();
})();"""


def response_media(url: str, content_type: str) -> bool:
    # Transport/init fragments are not standalone playable titles.
    path = urlparse(url).path.lower()
    if re.search(r"\.(?:ts|m4s|aac|vtt|key)$", path) or 'mp2t' in content_type.lower():
        return False
    return bool(_MEDIA.search(url) or 'mpegurl' in content_type.lower()
                or content_type.lower().split(';')[0] in {'video/mp4', 'video/webm', 'video/ogg', 'video/quicktime'})


def player_reports_unavailable(text: str) -> bool:
    """Recognize the small, explicit error messages emitted by embedded players."""
    normalized = unicodedata.normalize('NFKD', str(text or '').lower()).encode('ascii', 'ignore').decode()
    return any(message in normalized for message in (
        'video is unavailable', 'video unavailable', 'video indisponivel',
        'este video nao esta disponivel', 'this video is not available',
    ))


def response_belongs_to_page(response, page) -> bool:
    try:
        return response.request.frame.page == page
    except Exception:
        # Popup/navigation responses may arrive before their frame exists.
        return False


def _activate_player_control(frame, clicked: set, source_url: str) -> bool:
    """Try one explicit playback action, never arbitrary buttons or external links."""
    known = '.vjs-big-play-button, .jw-display-icon-container .jw-icon-display, .plyr__control--overlaid'
    groups = [(known, True), ('button, [role="button"], [role="tab"], .dooplay_player_option', False), ('a[href]', False)]
    for selector, trusted in groups:
        controls = frame.locator(selector)
        candidates = controls.evaluate_all("""elements => elements.slice(0, 60).map(el => ({
                label: el.getAttribute('aria-label') || el.querySelector('.title')?.textContent || el.textContent || '',
                href: el.tagName === 'A' ? el.href : '', id: el.id,
                submit: !!el.closest('form') && (el.type === 'submit' || el.tagName === 'INPUT')
            }))""")
        for index, info in enumerate(candidates):
            control = controls.nth(index)
            label = unicodedata.normalize('NFKD', info['label'].strip().lower()).encode('ascii', 'ignore').decode()
            label = re.sub(r'\s+', ' ', label)
            playback = bool(re.fullmatch(r'(?:play|reproduzir|iniciar|assistir)(?: (?:video|filme|episodio|agora))?', label))
            alternative = bool(re.fullmatch(r'(?:player|servidor|server)\s*\d+(?:\s*[-:·]?\s*(?:dublado|legendado|hd|full hd))?', label))
            if info['submit'] or not (trusted or playback or alternative):
                continue
            if info['href']:
                target, source = urlparse(info['href']), urlparse(source_url)
                if not playback or (target.scheme, target.netloc) != (source.scheme, source.netloc):
                    continue
                # Follow at most one same-site landing link during a probe.
                if 'landing-link' in clicked or info['href'] == frame.url:
                    continue
            key = (frame.url, info['id'] or label or selector, info['href'])
            if key in clicked or not control.is_visible() or not control.is_enabled():
                continue
            clicked.add(key)
            if info['href']:
                clicked.add('landing-link')
                frame.goto(info['href'], wait_until='commit', timeout=1500)
            else:
                control.click(timeout=600, no_wait_after=True)
            return True
    return False


def inspect_dynamic(url: str, is_public, *, observation_seconds: float = 6, navigation_timeout: int = 12000, stop_after_first: bool = False) -> dict:
    if not _BROWSERS.acquire(timeout=20):
        return {"media": [], "episodes": [], "status": "busy", "message": "Detector ocupado. Tente novamente."}
    try:
        return _WORKERS.run(lambda browser: _inspect_on_browser(
            browser, url, is_public, observation_seconds=observation_seconds,
            navigation_timeout=navigation_timeout, stop_after_first=stop_after_first))
    except Exception:
        return {"media": [], "episodes": [], "status": "error",
                "message": "Não foi possível concluir a inspeção no navegador. Tente novamente ou abra a sessão do site."}
    finally:
        _BROWSERS.release()


def _inspect_on_browser(browser, url, is_public, *, observation_seconds=6, navigation_timeout=12000, stop_after_first=False):
    from playwright.sync_api import TimeoutError as BrowserTimeout
    result = {"media": [], "episodes": [], "status": "unconfirmed", "message": "Nenhum vídeo confirmado. A página pode exigir interação."}
    result['diagnostics'] = {'frames': 0, 'video_elements': 0, 'actions': 0, 'dash_responses': 0, 'request_failures': []}
    # Reuse the process, never the cookies/storage or response listeners.
    with browser.new_context(service_workers="block", accept_downloads=False) as context:
        context.set_default_timeout(1000)
        context.route("**/*", lambda route: route.continue_() if route.request.resource_type not in {"image", "font"} and is_public(route.request.url) else route.abort())
        context.add_init_script(_VIDEO_OBSERVER)
        page = context.new_page()
        def failed(request):
            failures = result['diagnostics']['request_failures']
            if len(failures) < 12 and request.resource_type in {'document', 'script', 'xhr', 'fetch', 'media'}:
                # Domain and error code are enough; never retain signed URLs or headers.
                failures.append({'host': urlparse(request.url).hostname, 'type': request.resource_type,
                                 'error': request.failure if str(request.failure).startswith('net::ERR_') else 'request_failed'})
        page.on('requestfailed', failed)
        page.on("popup", lambda popup: popup.close())
        seen = set()
        request_headers = {}
        def capture(response):
            if not response_belongs_to_page(response, page):
                return
            target = response.url
            content_type = response.headers.get("content-type", "").lower()
            if response.status < 400 and ('dash+xml' in content_type or urlparse(target).path.lower().endswith('.mpd')):
                result['diagnostics']['dash_responses'] += 1
            if response.status < 400 and response_media(target, content_type) and target not in seen and is_public(target):
                seen.add(target)
                item = media_info(target, source_url=url)
                if "mpegurl" in content_type or ".m3u8" in target.lower():
                    item.update(kind="HLS", label="HLS")
                item["evidence"] = "network"
                request_headers[target] = response.request.all_headers()
                result["media"].append(item)
        context.on("response", capture)
        try:
            response = page.goto(url, wait_until="commit" if stop_after_first else "domcontentloaded", timeout=navigation_timeout)
            if response and response.status in {401, 403, 429}:
                result.update(status="blocked", message="O site restringiu esta consulta. Abra a sessão do site para continuar.")
        except BrowserTimeout:
            result.update(status="timeout", message="O site demorou a responder. A verificação não foi concluída.")
        deadline = monotonic() + observation_seconds
        clicked = set()
        last_action = 0.0
        actions = 0
        embedded_player_unavailable = False
        while monotonic() < deadline:
            if stop_after_first and any(not item.get('suspected_ad') for item in result['media']):
                break
            for frame in page.frames[:8]:
                try:
                    if actions < 6 and monotonic() - last_action >= (.75 if stop_after_first else 2):
                        if _activate_player_control(frame, clicked, url):
                            actions += 1
                            last_action = monotonic()
                            break
                except Exception:
                    pass
            page.wait_for_timeout(250)
        series_url = ''
        result['diagnostics'].update(frames=len(page.frames), actions=actions)
        result['diagnostics']['frame_hosts'] = [urlparse(frame.url).hostname for frame in page.frames[:8]]
        for frame in page.frames[:8]:
            try:
                result['diagnostics']['video_elements'] += frame.locator('video').count()
                parsed = parse_page(frame.content(), frame.url)
                if frame != page.main_frame:
                    embedded_player_unavailable = embedded_player_unavailable or player_reports_unavailable(
                        frame.locator('body').inner_text(timeout=400)
                    )
                if frame == page.main_frame:
                    result["episodes"].extend(parsed["episodes"])
                    series_url = parsed['series_url']
                candidates = frame.evaluate("""() => [...document.querySelectorAll('video, video source')].map(v => ({url: v.currentSrc || v.src, label: v.getAttribute('label') || v.getAttribute('data-quality') || ''}))""")
                for item in [*parsed["media"], *candidates]:
                    if item.get("url") and item["url"] not in seen and is_public(item["url"]):
                        seen.add(item["url"])
                        result["media"].append(media_info(item["url"], item.get("label", ""), url))
            except Exception:
                continue
        if not stop_after_first and series_url and is_public(series_url):
            index = context.new_page()
            try:
                index.goto(series_url, wait_until='domcontentloaded', timeout=8000)
                if urlparse(index.url).hostname == urlparse(series_url).hostname and urlparse(index.url).path == urlparse(series_url).path:
                    result['episodes'].extend(parse_page(index.content(), series_url)['episodes'])
            except Exception:
                pass
            finally:
                index.close()
        result["media"].sort(key=lambda item: (item.get('suspected_ad', False), item.get('kind') != 'HLS', item.get('evidence') != 'network'))
        result["media"] = result["media"][:16]
        result["episodes"] = list({item['url']: item for item in result['episodes']}.values())[:1000]
        if result['media']:
            from app.services.cinema_relay import probe_relay
            relay = probe_relay(context.cookies(), is_public)
            user_agent = page.evaluate('navigator.userAgent')
            for item in result['media']:
                headers = request_headers.get(item['url'], {})
                item['playback_url'] = relay.register(item['url'], headers.get('referer', url), item['kind'], headers.get('user-agent', user_agent), headers.get('origin', ''))
                item['session_id'] = relay.session_id
            result.update(status="detected", message="Fontes detectadas; a reprodução no Jarvis ainda precisa ser verificada.")
        elif page.url.startswith(('about:', 'chrome-error:')):
            result.update(status='interaction_required', message='A página do player ficou vazia ou falhou ao abrir nesta verificação. Abra a sessão do site; isso não confirma ausência de vídeo.')
        elif result['status'] == 'unconfirmed' and embedded_player_unavailable:
            result.update(status='unavailable', message='O player incorporado informou que o vídeo não está disponível nesta página.')
    return result
