"""Pesquisa e detecção de mídia pública em fontes de cinema aprovadas."""
from __future__ import annotations

import ipaddress
import base64
import json
import re
import socket
import urllib.parse
import urllib.request
from html import unescape
from pathlib import Path
from typing import Any

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


DEFAULT_SOURCES = [
    {"id": "archive", "name": "Internet Archive", "domains": ["archive.org"], "enabled": True},
    {"id": "youtube", "name": "YouTube", "domains": ["youtube.com", "youtu.be"], "enabled": True},
    {"id": "plex", "name": "Plex", "domains": ["plex.tv"], "enabled": True},
    {"id": "pluto", "name": "Pluto TV", "domains": ["pluto.tv"], "enabled": True},
    {"id": "netflix", "name": "Netflix", "domains": ["netflix.com"], "enabled": True},
    {"id": "primevideo", "name": "Prime Video", "domains": ["primevideo.com", "amazon.com"], "enabled": True},
]
_MEDIA_PATTERN = re.compile(r"(?:https?:)?//[^\s\"'<>]+?\.(?:m3u8|mp4|webm|ogv|mov)(?:\?[^\s\"'<>]*)?", re.I)
_SRC_PATTERN = re.compile(r"<(?:video|source)\b[^>]*?\bsrc\s*=\s*[\"']([^\"']+)[\"']", re.I)
_OG_VIDEO_PATTERN = re.compile(r"<meta\b[^>]*?(?:property|name)\s*=\s*[\"']og:video(?::url)?[\"'][^>]*?content\s*=\s*[\"']([^\"']+)[\"']", re.I)
_IFRAME_PATTERN = re.compile(r"<iframe\b[^>]*?\bsrc\s*=\s*[\"']([^\"']+)[\"']", re.I)


def _unwrap_search_url(url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(url)
        encoded = urllib.parse.parse_qs(parsed.query).get("u", [""])[0]
        if encoded.startswith("a1"):
            target = base64.b64decode(encoded[2:] + "===").decode("utf-8", errors="ignore")
            if target.startswith(("http://", "https://")):
                return target
    except Exception:
        pass
    return url


class CinemaDiscoveryService:
    """Só analisa URLs escolhidas pelo usuário; não tenta contornar proteção de sites."""

    def __init__(self, sources_path: str | Path = "data/cinema_sources.json") -> None:
        self.sources_path = Path(sources_path)

    def search(self, query: str, limit: int = 12) -> dict[str, Any]:
        clean_query = " ".join(str(query or "").split())[:160]
        if not clean_query:
            return {"ok": False, "error": "Informe o título que deseja pesquisar."}
        sources = self._sources()
        domains = [domain for source in sources if source.get("enabled", True) for domain in source.get("domains", [])]
        if not domains:
            return {"ok": False, "error": "Nenhuma fonte aprovada está configurada."}

        results: list[dict[str, str]] = []
        if any(source.get("enabled", True) and source.get("id") == "archive" for source in sources):
            results.extend(self._search_internet_archive(clean_query, limit))
        if len(results) < limit:
            results.extend(self._search_web(clean_query, domains, limit - len(results)))
        unique_results: list[dict[str, str]] = []
        seen_urls: set[str] = set()
        for result in results:
            if result["url"] not in seen_urls:
                seen_urls.add(result["url"])
                host = (urllib.parse.urlparse(result["url"]).hostname or "").lower()
                enriched = dict(result)
                if any(host == domain or host.endswith(f".{domain}") for domain in ("netflix.com", "primevideo.com", "amazon.com")):
                    enriched["media_hint"] = "DRM/login: o site pode bloquear incorporação"
                elif host in {"youtube.com", "www.youtube.com", "youtu.be"}:
                    enriched["media_hint"] = "Player incorporado ou vídeo público"
                else:
                    enriched["media_hint"] = "Detectar mídia pública"
                unique_results.append(enriched)
            if len(unique_results) >= limit:
                break
        return {"ok": True, "query": clean_query, "results": unique_results, "sources": sources}

    def probe(self, url: str) -> dict[str, Any]:
        clean_url = str(url or "").strip()
        if not self._is_public_http_url(clean_url):
            return {"ok": False, "error": "A URL deve ser HTTP/HTTPS pública."}

        if re.search(r"\.(?:m3u8|mp4|webm|ogv|mov)(?:$|[?#])", clean_url, re.I):
            return {"ok": True, "page_url": clean_url, "media": [{"url": clean_url, "label": "URL direta", "kind": self._media_kind(clean_url), "direct": True, "source_url": clean_url}]}

        archive_media = self._probe_internet_archive(clean_url)
        if archive_media is not None:
            return archive_media

        try:
            request = urllib.request.Request(clean_url, headers={"User-Agent": "JarvisCinema/1.0"})
            with urllib.request.urlopen(request, timeout=8) as response:
                final_url = response.geturl()
                content_type = response.headers.get_content_type()
                raw_html = response.read(1_500_000).decode("utf-8", errors="replace")
            if content_type.startswith("video/"):
                return {"ok": True, "page_url": final_url, "media": [{"url": final_url, "label": content_type, "kind": "direct", "direct": True, "source_url": clean_url}]}
        except Exception as exc:
            return {"ok": False, "error": f"Não foi possível analisar esta página: {exc}"}

        candidates: list[str] = []
        candidates.extend(_SRC_PATTERN.findall(raw_html))
        candidates.extend(_OG_VIDEO_PATTERN.findall(raw_html))
        candidates.extend(_MEDIA_PATTERN.findall(raw_html))
        seen: set[str] = set()
        media = []
        for candidate in candidates:
            resolved = urllib.parse.urljoin(final_url, unescape(candidate.replace("\\/", "/")))
            if resolved in seen or not self._is_public_http_url(resolved):
                continue
            seen.add(resolved)
            media.append({"url": resolved, "label": self._media_kind(resolved), "kind": self._media_kind(resolved), "direct": True, "source_url": final_url})
        # Alguns sites expõem somente o endereço do próprio player dentro de iframe.
        # Isso continua sujeito à política de incorporação do site, mas evita abrir uma
        # nova aba quando o iframe é permitido.
        for candidate in _IFRAME_PATTERN.findall(raw_html):
            resolved = urllib.parse.urljoin(final_url, unescape(candidate.replace("\\/", "/")))
            if resolved in seen or not self._is_public_http_url(resolved):
                continue
            seen.add(resolved)
            media.append({"url": resolved, "label": "Player incorporado", "kind": "embed", "direct": False, "embed_url": resolved, "source_url": final_url})
        if not media:
            media = self._probe_dynamic_video(final_url)
        return {
            "ok": True,
            "page_url": final_url,
            "media": media[:8],
            "message": "Nenhuma mídia pública foi exposta nesta página." if not media else "Mídia pública detectada.",
        }

    def _sources(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self.sources_path.read_text(encoding="utf-8"))
            sources = data.get("sources", []) if isinstance(data, dict) else []
            if isinstance(sources, list):
                return sources
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        self.sources_path.parent.mkdir(parents=True, exist_ok=True)
        self.sources_path.write_text(json.dumps({"sources": DEFAULT_SOURCES}, ensure_ascii=False, indent=2), encoding="utf-8")
        return DEFAULT_SOURCES

    @staticmethod
    def _search_web(query: str, domains: list[str], limit: int) -> list[dict[str, str]]:
        results: list[dict[str, str]] = []
        try:
            from duckduckgo_search import DDGS
            with DDGS() as search:
                raw_results = list(search.text(query, max_results=max(limit * 3, 20)))
            for result in raw_results:
                url = str(result.get("href", ""))
                host = (urllib.parse.urlparse(url).hostname or "").lower()
                if any(host == domain or host.endswith(f".{domain}") for domain in domains):
                    results.append({"title": str(result.get("title") or host), "url": url, "source": host, "snippet": str(result.get("body") or "")})
                if len(results) >= limit:
                    break
        except Exception:
            search_url = "https://www.bing.com/search?q=" + urllib.parse.quote_plus(query)
            try:
                request = urllib.request.Request(search_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(request, timeout=8) as response:
                    html = response.read(1_000_000).decode("utf-8", errors="replace")
                anchors = re.findall(r'<li[^>]+class="b_algo"[\s\S]*?<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', html, re.I)
                for href, title in anchors:
                    url = _unwrap_search_url(unescape(href))
                    host = (urllib.parse.urlparse(url).hostname or "").lower()
                    if any(host == domain or host.endswith(f".{domain}") for domain in domains):
                        clean_title = re.sub(r"<[^>]+>", "", unescape(title)).strip()
                        results.append({"title": clean_title or host, "url": url, "source": host, "snippet": ""})
                    if len(results) >= limit:
                        break
            except Exception:
                # Last fallback: DuckDuckGo HTML, useful when Bing is unavailable.
                try:
                    search_url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote_plus(query)
                    request = urllib.request.Request(search_url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(request, timeout=8) as response:
                        html = response.read(1_000_000).decode("utf-8", errors="replace")
                    anchors = re.findall(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.I | re.S)
                    for href, title in anchors:
                        url = unescape(href)
                        host = (urllib.parse.urlparse(url).hostname or "").lower()
                        if any(host == domain or host.endswith(f".{domain}") for domain in domains):
                            clean_title = re.sub(r"<[^>]+>", "", unescape(title)).strip()
                            results.append({"title": clean_title or host, "url": url, "source": host, "snippet": ""})
                        if len(results) >= limit:
                            break
                except Exception:
                    pass
        return results

    @staticmethod
    def _search_internet_archive(query: str, limit: int) -> list[dict[str, str]]:
        try:
            params = urllib.parse.urlencode({
                "q": f"({query}) AND mediatype:movies AND collection:publicdomain",
                "fl[]": ["identifier", "title"],
                "rows": str(limit),
                "output": "json",
            }, doseq=True)
            request = urllib.request.Request(
                f"https://archive.org/advancedsearch.php?{params}", headers={"User-Agent": "JarvisCinema/1.0"}
            )
            with urllib.request.urlopen(request, timeout=8) as response:
                docs = json.loads(response.read().decode("utf-8")).get("response", {}).get("docs", [])
            return [
                {
                    "title": str(doc.get("title") or doc["identifier"]),
                    "url": f"https://archive.org/details/{urllib.parse.quote(str(doc['identifier']))}",
                    "source": "archive.org",
                    "snippet": "Internet Archive",
                }
                for doc in docs if doc.get("identifier")
            ]
        except Exception:
            return []

    def _probe_internet_archive(self, url: str) -> dict[str, Any] | None:
        parsed = urllib.parse.urlparse(url)
        host = (parsed.hostname or "").lower()
        match = re.match(r"^/details/([^/?#]+)", parsed.path)
        if not (host == "archive.org" or host.endswith(".archive.org")) or not match:
            return None
        identifier = urllib.parse.unquote(match.group(1))
        try:
            request = urllib.request.Request(
                f"https://archive.org/metadata/{urllib.parse.quote(identifier)}", headers={"User-Agent": "JarvisCinema/1.0"}
            )
            with urllib.request.urlopen(request, timeout=8) as response:
                files = json.loads(response.read().decode("utf-8")).get("files", [])
            media = []
            for item in files:
                name = str(item.get("name") or "")
                if re.search(r"\.(?:m3u8|mp4|webm|ogv|mov)$", name, re.I):
                    media.append({
                        "url": f"https://archive.org/download/{urllib.parse.quote(identifier)}/{urllib.parse.quote(name)}",
                        "label": str(item.get("format") or self._media_kind(name)),
                        "kind": self._media_kind(name),
                        "direct": True,
                        "source_url": url,
                    })
            return {"ok": True, "page_url": url, "media": media[:8], "message": "Nenhum arquivo de vídeo público foi encontrado." if not media else "Mídia pública detectada."}
        except Exception as exc:
            return {"ok": False, "error": f"Não foi possível analisar o item do Internet Archive: {exc}"}

    def _probe_dynamic_video(self, url: str) -> list[dict[str, str]]:
        """Lê fontes já expostas pela própria página, sem contornar autenticação ou DRM."""
        if not PLAYWRIGHT_AVAILABLE:
            return []
        browser = None
        playwright = None
        try:
            playwright = sync_playwright().start()
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=12_000)
            page.wait_for_timeout(1_000)
            candidates = page.evaluate("""
                () => {
                    const urls = new Set();
                    document.querySelectorAll('video, video source').forEach(el => {
                        [el.currentSrc, el.src, el.getAttribute('src')].filter(Boolean).forEach(value => urls.add(value));
                    });
                    performance.getEntriesByType('resource').forEach(entry => {
                        if (/\\.(m3u8|mp4|webm|ogv|mov)(?:$|[?#])/i.test(entry.name)) urls.add(entry.name);
                    });
                    return [...urls];
                }
            """)
            media = []
            for candidate in candidates:
                resolved = urllib.parse.urljoin(url, str(candidate))
                if self._is_public_http_url(resolved) and re.search(r"\.(?:m3u8|mp4|webm|ogv|mov)(?:$|[?#])", resolved, re.I):
                    media.append({"url": resolved, "label": self._media_kind(resolved), "kind": self._media_kind(resolved), "direct": True, "source_url": url})
            return media[:8]
        except Exception:
            return []
        finally:
            if browser:
                browser.close()
            if playwright:
                playwright.stop()

    @staticmethod
    def _is_public_http_url(url: str) -> bool:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        host = parsed.hostname.lower()
        if host in {"localhost", "localhost.localdomain"}:
            return False
        try:
            addresses = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
            return bool(addresses) and all(ipaddress.ip_address(entry[4][0]).is_global for entry in addresses)
        except (OSError, ValueError):
            return False

    @staticmethod
    def _media_kind(url: str) -> str:
        if ".m3u8" in url.lower():
            return "HLS"
        suffix = Path(urllib.parse.urlparse(url).path).suffix.lstrip(".").upper()
        return suffix or "Vídeo"
