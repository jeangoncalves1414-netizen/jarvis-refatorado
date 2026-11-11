"""Pesquisa e detecção de mídia pública em fontes de cinema aprovadas."""
from __future__ import annotations

import ipaddress
import base64
import json
import re
import socket
import unicodedata
import urllib.parse
import urllib.request
from html import unescape
from http.cookiejar import CookieJar
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any



DEFAULT_SOURCES = [
    {"id": "plex", "name": "Plex", "domains": ["plex.tv"], "enabled": True, "priority": 10},
    {"id": "pluto", "name": "Pluto TV", "domains": ["pluto.tv"], "enabled": True, "priority": 20},
    {"id": "youtube", "name": "YouTube", "domains": ["youtube.com", "youtu.be"], "enabled": True, "priority": 30},
    {"id": "archive", "name": "Internet Archive", "domains": ["archive.org"], "enabled": True, "priority": 40},
]
EXCLUDED_DOMAINS = ("netflix.com", "primevideo.com", "amazon.com", "amazon.com.br")
_MEDIA_PATTERN = re.compile(r"(?:https?:)?//[^\s\"'<>]+?\.(?:m3u8|mp4|webm|ogv|mov)(?:\?[^\s\"'<>]*)?", re.I)
_SRC_PATTERN = re.compile(r"<(?:video|source)\b[^>]*?\bsrc\s*=\s*[\"']([^\"']+)[\"']", re.I)
_OG_VIDEO_PATTERN = re.compile(r"<meta\b[^>]*?(?:property|name)\s*=\s*[\"']og:video(?::url)?[\"'][^>]*?content\s*=\s*[\"']([^\"']+)[\"']", re.I)
_IFRAME_PATTERN = re.compile(r"<iframe\b[^>]*?\bsrc\s*=\s*[\"']([^\"']+)[\"']", re.I)


def _normalized(text: str) -> str:
    return unicodedata.normalize('NFKD', text.lower()).encode('ascii', 'ignore').decode()


_EDITORIAL = re.compile(r'\b(?:trailers?|teasers?|noticias?|criticas?|reviews?|sinopse|curiosidades?|elenco|resumo|analise)\b')


def _watch_query(query: str) -> str:
    words = _normalized(query)
    if _EDITORIAL.search(words):
        return query
    prefix = '' if re.search(r'\b(?:assistir|watch)\b', words) else 'Assistir '
    suffix = '' if re.search(r'\b(?:completo|completa|full)\b', words) else ' completo'
    if not re.search(r'\b(?:dublado|dublada|legendado|legendada|dual|original|ingles|english|japones|subbed|dubbed)\b', words):
        suffix += ' dublado'
    return prefix + query + suffix


def _watch_rank(item: dict, query: str) -> int:
    # Ranking hints only: a search snippet is never proof of playable media.
    if _EDITORIAL.search(_normalized(query)):
        return 0
    title = _normalized(str(item.get('title') or ''))
    content = title + ' ' + _normalized(str(item.get('snippet') or item.get('body') or ''))
    host = urllib.parse.urlparse(item['url']).hostname or ''
    score = 60 if _EDITORIAL.search(title) else 0
    score += 15 if _EDITORIAL.search(content) else 0
    if any(host == d or host.endswith('.' + d) for d in ('youtube.com', 'youtu.be', 'globo.com')):
        score += 10
    if re.search(r'\b(?:assistir|watch|completo|completa|full movie)\b', title):
        score -= 30
    if re.search(r'\b(?:dublado|legendado|online)\b', content):
        score -= 5
    return score


class _PublicRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not CinemaDiscoveryService._is_public_http_url(newurl):
            raise ValueError("Redirecionamento para endereço não público.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _unwrap_search_url(url: str) -> str:
    try:
        if url.startswith("//"):
            url = "https:" + url
        parsed = urllib.parse.urlparse(url)
        host = (parsed.hostname or "").lower()
        params = urllib.parse.parse_qs(parsed.query)
        if host == "duckduckgo.com" or host.endswith(".duckduckgo.com"):
            return params.get("uddg", [url])[0]
        encoded = params.get("u", [""])[0]
        if (host == "bing.com" or host.endswith(".bing.com")) and encoded.startswith("a1"):
            target = base64.urlsafe_b64decode(encoded[2:] + "===").decode("utf-8")
            if target.startswith(("http://", "https://")):
                return target
    except Exception:
        pass
    return url


class CinemaDiscoveryService:
    """Só analisa URLs escolhidas pelo usuário; não tenta contornar proteção de sites."""

    def __init__(self, sources_path: str | Path = "data/cinema_sources.json") -> None:
        self.sources_path = Path(sources_path)

    def search(self, query: str, limit: int = 48, *, scope: str = "web", source_id: str = "", page: int = 1) -> dict[str, Any]:
        clean_query = " ".join(str(query or "").split())[:160]
        if not clean_query:
            return {"ok": False, "error": "Informe o título ou assunto que deseja pesquisar."}
        if scope not in {"approved", "web"}:
            return {"ok": False, "error": "Escopo de pesquisa inválido."}
        try:
            limit, page = int(limit), int(page)
            if not 1 <= limit <= 60 or not 1 <= page <= 100:
                raise ValueError
        except (TypeError, ValueError):
            return {"ok": False, "error": "Limite ou página de pesquisa inválidos."}
        sources = self._sources()
        if source_id.startswith("domain:"):
            domain = source_id[7:].lower().strip()
            if not re.fullmatch(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,63}", domain):
                return {"ok": False, "error": "Domínio inválido."}
            selected = [next((item for item in sources if domain in item.get("domains", [])), {"id": source_id, "domains": [domain]})]
        else:
            selected = [s for s in sources if s.get("enabled", True) and (not source_id or s.get("id") == source_id)]
        if source_id and not selected:
            return {"ok": False, "error": "Fonte não encontrada ou desativada."}
        restricted = scope == "approved" or bool(source_id)
        domains = [str(d).lower().strip() for s in selected for d in s.get("domains", [])
                   if re.fullmatch(r"[a-zA-Z0-9.-]+", str(d))] if restricted else []
        if restricted and not domains:
            return {"ok": False, "error": "Nenhuma fonte aprovada está configurada."}

        results: list[dict[str, str]] = []
        warnings = []
        # As fontes web têm espaço mesmo quando o Archive preenche todo o limite.
        with ThreadPoolExecutor(max_workers=3) as pool:
            jobs = [("Web", pool.submit(self._search_web, clean_query, domains, limit, **({"page": page} if page > 1 else {})))]
            for source in selected:
                if page == 1 and source.get("search_url") and (source_id or re.search(r"\banime[s]?\b", clean_query, re.I)):
                    jobs.append((source["name"], pool.submit(self._search_native, clean_query, source, limit)))
            if page == 1 and restricted and any(s.get("id") == "archive" for s in selected):
                jobs.append(("Internet Archive", pool.submit(self._search_internet_archive, clean_query, limit)))
            batches = []
            for label, job in jobs:
                try:
                    batches.append(job.result())
                except Exception:
                    warnings.append(f"{label} indisponível nesta pesquisa.")
            for index in range(max((len(batch) for batch in batches), default=0)):
                results.extend(batch[index] for batch in batches if index < len(batch))
        unique_results: list[dict[str, str]] = []
        seen_urls: set[str] = set()
        for result in results:
            url = self._result_url(str(result.get("url") or result.get("href") or ""))
            if not url:
                continue
            host = (urllib.parse.urlparse(url).hostname or "").lower()
            if any(host == d or host.endswith(f".{d}") for d in EXCLUDED_DOMAINS):
                continue
            if restricted and not any(host == d or host.endswith(f".{d}") for d in domains):
                continue
            if url not in seen_urls:
                seen_urls.add(url)
                enriched = dict(result)
                enriched.update(url=url, source=host.removeprefix("www."))
                matching_sources = [item for item in sources if any(host == domain or host.endswith(f".{domain}")
                                    for domain in item.get("domains", []))]
                enriched["source_priority"] = min((int(item.get("priority", 100)) for item in matching_sources), default=100)
                if host in {"youtube.com", "www.youtube.com", "youtu.be"}:
                    enriched["media_hint"] = "Player incorporado ou vídeo público"
                else:
                    enriched["media_hint"] = "Página encontrada; disponibilidade de vídeo ainda não verificada"
                unique_results.append(enriched)
            if restricted and len(unique_results) >= limit:
                break
        if restricted:
            unique_results.sort(key=lambda item: int(item.get("source_priority", 100)))
        else:
            unique_results.sort(key=lambda item: _watch_rank(item, clean_query))
        unique_results = unique_results[:limit]
        if not unique_results and warnings:
            return {"ok": False, "error": "Não foi possível consultar as fontes agora. Tente novamente.", "warnings": warnings}
        return {"ok": True, "query": clean_query, "results": unique_results, "sources": sources,
                "scope": scope, "source_id": source_id, "warnings": warnings,
                "next_page": page + 1 if results and page < 100 else None}

    @staticmethod
    def _result_url(url: str) -> str:
        """Normaliza links do buscador sem visitar as páginas encontradas."""
        try:
            if any(ord(char) < 32 or ord(char) == 127 for char in url):
                return ""
            parsed = urllib.parse.urlsplit(_unwrap_search_url(unescape(url.strip())))
            host = (parsed.hostname or "").lower()
            if (parsed.scheme not in {"http", "https"} or not host or parsed.username or parsed.password
                    or host == "localhost" or host.endswith((".localhost", ".local"))):
                return ""
            try:
                if not ipaddress.ip_address(host).is_global:
                    return ""
            except ValueError:
                pass
            # Preserva identificadores de vídeo e assinaturas; remove só rastreamento conhecido.
            query = "&".join(part for part in parsed.query.split("&")
                             if not urllib.parse.unquote_plus(part.split("=", 1)[0]).lower().startswith("utm_")
                             and part.split("=", 1)[0].lower() not in {"fbclid", "gclid"})
            return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path or "/", query, ""))
        except ValueError:
            return ""

    def probe(self, url: str, *, fast: bool = False) -> dict[str, Any]:
        clean_url = str(url or "").strip()
        if not self._is_public_http_url(clean_url):
            return {"ok": False, "error": "A URL deve ser HTTP/HTTPS pública."}

        if re.search(r"\.(?:m3u8|mp4|webm|ogv|mov)(?:$|[?#])", clean_url, re.I):
            return {"ok": True, "page_url": clean_url, "media": [{"url": clean_url, "label": "URL direta", "kind": self._media_kind(clean_url), "direct": True, "source_url": clean_url}]}

        archive_media = self._probe_internet_archive(clean_url)
        if archive_media is not None:
            return archive_media

        cookies = CookieJar()
        try:
            request = urllib.request.Request(clean_url, headers={"User-Agent": "JarvisCinema/1.0"})
            with urllib.request.build_opener(_PublicRedirectHandler(), urllib.request.HTTPCookieProcessor(cookies)).open(request, timeout=3 if fast else 8) as response:
                final_url = response.geturl()
                content_type = response.headers.get_content_type()
                raw_html = response.read(1_500_000).decode("utf-8", errors="replace")
            if content_type.startswith("video/"):
                return {"ok": True, "page_url": final_url, "media": [{"url": final_url, "label": content_type, "kind": "direct", "direct": True, "source_url": clean_url}]}
        except Exception as exc:
            from app.services.cinema_page import inspect_dynamic
            dynamic = inspect_dynamic(
                clean_url, self._is_public_http_url,
                observation_seconds=2 if fast else 6,
                navigation_timeout=4500 if fast else 12000,
                stop_after_first=fast,
            )
            return {"ok": True, "page_url": clean_url, **dynamic}

        from app.services.cinema_page import is_probable_ad_media
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
            media.append({"url": resolved, "label": self._media_kind(resolved), "kind": self._media_kind(resolved), "direct": True, "source_url": final_url,
                          "suspected_ad": is_probable_ad_media(resolved)})
        # Alguns sites expõem somente o endereço do próprio player dentro de iframe.
        # Isso continua sujeito à política de incorporação do site, mas evita abrir uma
        # nova aba quando o iframe é permitido.
        for candidate in _IFRAME_PATTERN.findall(raw_html):
            resolved = urllib.parse.urljoin(final_url, unescape(candidate.replace("\\/", "/")))
            if resolved in seen or not self._is_public_http_url(resolved):
                continue
            seen.add(resolved)
            media.append({"url": resolved, "label": "Player incorporado", "kind": "embed", "direct": False, "embed_url": resolved, "source_url": final_url})
        from app.services.cinema_page import parse_page, inspect_dynamic
        page_data = parse_page(raw_html, final_url)
        for candidate in page_data["media"]:
            existing = next((item for item in media if item["url"] == candidate["url"]), None)
            if existing:
                existing.update(candidate)
            elif self._is_public_http_url(candidate["url"]):
                media.append(candidate)
                seen.add(candidate["url"])
        episodes = page_data["episodes"]
        if not fast and page_data.get("series_url"):
            try:
                index_url = page_data["series_url"]
                if self._is_public_http_url(index_url):
                    request = urllib.request.Request(index_url, headers={"User-Agent": "JarvisCinema/1.0"})
                    with urllib.request.build_opener(_PublicRedirectHandler()).open(request, timeout=8) as response:
                        if urllib.parse.urlparse(response.geturl()).path == urllib.parse.urlparse(index_url).path:
                            index_html = response.read(1_500_000).decode("utf-8", errors="replace")
                            episodes.extend(parse_page(index_html, index_url)["episodes"])
            except Exception:
                pass  # Keep the episode links on the original page if the index is unavailable.
        # A varredura rápida não abre um navegador quando o HTML já revelou mídia.
        # shortcut: players que só carregam após interação exigem a detecção completa do cartão.
        dynamic = {"media": [], "episodes": [], "status": "detected" if media else "unconfirmed", "message": "Verificação concluída."}
        if not fast or not any(item.get("direct") and not item.get("suspected_ad") for item in media):
            dynamic = inspect_dynamic(
                final_url, self._is_public_http_url,
                observation_seconds=2 if fast else 6,
                navigation_timeout=4500 if fast else 12000,
                stop_after_first=fast,
            )
            for candidate in dynamic["media"]:
                existing = next((item for item in media if item["url"] == candidate["url"]), None)
                if existing:
                    existing.update(candidate)
                else:
                    media.append(candidate)
                    seen.add(candidate["url"])
            episodes.extend(dynamic["episodes"])
        # Static detection also needs the page's cookies/referer and a same-origin URL.
        static_media = [item for item in media if item.get("direct") and not item.get("playback_url") and not item.get("suspected_ad")]
        if static_media:
            from app.services.cinema_relay import probe_relay
            relay = probe_relay([{"name": c.name, "value": c.value, "domain": c.domain,
                                  "path": c.path, "secure": c.secure, "expires": c.expires or -1}
                                 for c in cookies], self._is_public_http_url)
            for item in static_media:
                item["playback_url"] = relay.register(item["url"], final_url, item["kind"], "JarvisCinema/1.0")
                item["session_id"] = relay.session_id
        unique_episodes = {item["url"]: item for item in episodes if self._result_url(item["url"])}
        media.sort(key=lambda item: (item.get("suspected_ad", False), not item.get("direct", False), item.get("kind") != "HLS", item.get("evidence") != "network"))
        return {
            "ok": True,
            "page_url": final_url,
            "media": media[:8],
            "episodes": sorted(unique_episodes.values(), key=lambda item: (item["season"], item["episode"]))[:1000],
            "status": dynamic.get("status", "detected" if media else "unconfirmed"),
            "diagnostics": dynamic.get("diagnostics", {}),
            "message": dynamic.get("message", "Verificação concluída."),
        }

    def _sources(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self.sources_path.read_text(encoding="utf-8"))
            sources = data.get("sources", []) if isinstance(data, dict) else []
            if isinstance(sources, list):
                filtered = [s for s in sources if isinstance(s, dict) and s.get("id") not in {"netflix", "primevideo"}
                            and not any(d in EXCLUDED_DOMAINS for d in s.get("domains", []))]
                defaults = {item["id"]: item for item in DEFAULT_SOURCES}
                filtered = [{**defaults.get(str(item.get("id")), {}), **item} for item in filtered]
                known = {s.get("id") for s in filtered}
                return filtered + [s for s in DEFAULT_SOURCES if s["id"] not in known]
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        self.sources_path.parent.mkdir(parents=True, exist_ok=True)
        self.sources_path.write_text(json.dumps({"sources": DEFAULT_SOURCES}, ensure_ascii=False, indent=2), encoding="utf-8")
        return DEFAULT_SOURCES

    @staticmethod
    def _search_native(query: str, source: dict, limit: int) -> list[dict[str, str]]:
        from app.services.cinema_page import search_links
        clean = re.sub(r"\b(?:anime[s]?|assistir|online|gr[aá]tis|dublado|legendado)\b", "", query, flags=re.I).strip()
        if not clean:
            return []
        url = source["search_url"].replace("{query}", urllib.parse.quote_plus(clean))
        if not CinemaDiscoveryService._is_public_http_url(url):
            return []
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (JarvisCinema)"})
        with urllib.request.build_opener(_PublicRedirectHandler()).open(request, timeout=8) as response:
            html = response.read(1_500_000).decode("utf-8", errors="replace")
            final_url = response.geturl()
        return search_links(html, final_url, clean)[:limit]

    @staticmethod
    def _search_web(query: str, domains: list[str], limit: int, *, page: int = 1) -> list[dict[str, str]]:
        # Reutiliza os provedores do Jarvis, sem depender de endpoints do APK.
        from app.agent.tools.web_search import _search, _fallback_search

        scoped_query = query if domains else _watch_query(query)
        if domains:
            scoped_query += " (" + " OR ".join(f"site:{domain}" for domain in domains) + ")"
        normalize = lambda text: unicodedata.normalize('NFKD', text.lower()).encode('ascii', 'ignore').decode()
        generic = {'a', 'o', 'as', 'os', 'de', 'da', 'do', 'das', 'dos', 'e', 'em', 'um', 'uma', 'the', 'of', 'and',
                   'assistir', 'online', 'gratis', 'gratuito', 'gratuitos', 'filme', 'filmes', 'serie', 'series', 'anime', 'animes', 'dublado', 'legendado', 'completo', 'completa'}
        terms = {word for word in re.findall(r'[a-z0-9]+', normalize(query)) if word not in generic and not re.fullmatch(r'(?:19|20)\d{2}', word)}
        def allowed(row):
            url = CinemaDiscoveryService._result_url(str(row.get("url") or row.get("href") or ""))
            host = urllib.parse.urlparse(url).hostname or ""
            content = normalize(' '.join(str(row.get(key) or '') for key in ('title', 'snippet', 'body')) + ' ' + urllib.parse.unquote(url))
            words = set(re.findall(r'[a-z0-9]+', content))
            relevant = not terms or len(terms & words) >= max(1, (len(terms) * 7 + 9) // 10)
            return bool(url) and relevant and (not domains or any(host == d or host.endswith("." + d) for d in domains))
        requested = max(limit, 20)
        if page > 1:
            from ddgs import DDGS
            from app.agent.tools.web_search import _normalise_result
            batch = DDGS(timeout=8).text(scoped_query, max_results=requested, page=page)
            return [row for item in batch if allowed(row := _normalise_result(item))]
        # A primeira página de um mecanismo costuma ter menos de 10 resultados. Combine
        # mecanismos públicos e deduplique abaixo, em vez de aceitar o primeiro lote curto.
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(provider, scoped_query, requested) for provider in (_search, _fallback_search)]
            rows = []
            for job in jobs:
                try:
                    rows.extend(row for row in job.result() if allowed(row))
                except Exception:
                    pass
        if len({CinemaDiscoveryService._result_url(str(row.get("url") or row.get("href") or "")) for row in rows}) < limit:
            # A provider can return unrelated results instead of a network error.
            from app.agent.tools.web_search import _DuckDuckGoParser, _normalise_result
            request = urllib.request.Request('https://html.duckduckgo.com/html/?q=' + urllib.parse.quote_plus(scoped_query), headers={'User-Agent': 'Mozilla/5.0 (JarvisCinema)'})
            try:
                with urllib.request.urlopen(request, timeout=8) as response:
                    parser = _DuckDuckGoParser()
                    parser.feed(response.read(1_500_000).decode('utf-8', errors='replace'))
                rows.extend(row for item in parser.results if allowed(row := _normalise_result(item)))
            except Exception:
                pass
        return rows

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
        except Exception as exc:
            raise RuntimeError("Internet Archive indisponível") from exc

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

    @staticmethod
    def _is_public_http_url(url: str) -> bool:
        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                return False
            host = parsed.hostname.lower()
            if host in {"localhost", "localhost.localdomain"} or host.endswith((".localhost", ".local")):
                return False
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
