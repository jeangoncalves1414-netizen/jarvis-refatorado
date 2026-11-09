"""Serviço de automação ativa de navegador web via Playwright.

Permite navegação programática, extração de texto limpo e links,
pesquisa inteligente dentro do DOM, cliques validados, preenchimento de formulários
e captura de tela para diagnósticos e visualização.
"""
from __future__ import annotations

import os
import re
import threading
import time
from pathlib import Path
from typing import Any

try:
    from playwright.sync_api import sync_playwright, Playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Playwright = Any  # type: ignore
    Browser = Any  # type: ignore
    BrowserContext = Any  # type: ignore
    Page = Any  # type: ignore
    PlaywrightTimeoutError = Exception  # type: ignore

CAPTURES_DIR = Path("data/captures")
CAPTURES_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_TIMEOUT_MS = 15000
MAX_ACTION_TIMEOUT_MS = 15000


def _clean_text(raw: str) -> str:
    """Normaliza espaçamentos e quebras de linha de texto extraído do DOM."""
    if not raw:
        return ""
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw.splitlines()]
    return "\n".join(line for line in lines if line)


class BrowserService:
    """Gerenciador central do navegador Playwright."""

    def __init__(self, headless: bool | None = None, timeout_ms: int = DEFAULT_TIMEOUT_MS):
        if not PLAYWRIGHT_AVAILABLE:
            self._available = False
        else:
            self._available = True

        self._headless_override = headless
        self.timeout_ms = min(int(timeout_ms or DEFAULT_TIMEOUT_MS), MAX_ACTION_TIMEOUT_MS)
        self._lock = threading.RLock()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    @property
    def is_available(self) -> bool:
        return self._available

    def _resolve_headless(self) -> bool:
        if self._headless_override is not None:
            return bool(self._headless_override)
        try:
            from app.storage.runtime_settings import get_browser_settings
            return bool(get_browser_settings().get("headless", True))
        except Exception:
            return True

    def start(self) -> Page:
        """Inicia Chromium com contexto e página padrão."""
        if not self._available:
            raise RuntimeError("Playwright não está instalado ou disponível no ambiente.")

        with self._lock:
            if self._page and not self._page.is_closed():
                return self._page

            headless = self._resolve_headless()
            if not self._playwright:
                self._playwright = sync_playwright().start()

            if not self._browser:
                self._browser = self._playwright.chromium.launch(
                    headless=headless,
                    args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
                )

            self._context = self._browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            self._page = self._context.new_page()
            self._page.set_default_timeout(self.timeout_ms)
            return self._page

    def stop(self) -> None:
        """Encerra a sessão atual e libera recursos."""
        with self._lock:
            if self._page:
                try:
                    self._page.close()
                except Exception:
                    pass
                self._page = None
            if self._context:
                try:
                    self._context.close()
                except Exception:
                    pass
                self._context = None
            if self._browser:
                try:
                    self._browser.close()
                except Exception:
                    pass
                self._browser = None
            if self._playwright:
                try:
                    self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None

    def ensure_page(self) -> Page:
        """Retorna a página ativa ou cria uma nova se necessário."""
        with self._lock:
            if not self._page or self._page.is_closed():
                return self.start()
            return self._page

    def navigate(self, url: str) -> dict[str, Any]:
        """Navega para a URL com timeout defensivo e espera carregamento do DOM."""
        if not self._available:
            return {"ok": False, "error": "Playwright não disponível."}

        target_url = str(url or "").strip()
        if not target_url:
            return {"ok": False, "error": "URL não fornecida."}

        if not target_url.startswith(("http://", "https://", "file://", "about:")):
            target_url = f"https://{target_url}"

        try:
            page = self.ensure_page()
            response = page.goto(target_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            status_code = response.status if response else 200
            title = page.title()
            return {
                "ok": True,
                "url": page.url,
                "title": title,
                "status_code": status_code,
                "message": f"Navegou com sucesso para {page.url} (Título: '{title}', Status: {status_code})."
            }
        except PlaywrightTimeoutError:
            return {
                "ok": False,
                "url": target_url,
                "error": f"Tempo limite ({self.timeout_ms}ms) esgotado ao aguardar DOM de {target_url}."
            }
        except Exception as exc:
            return {"ok": False, "url": target_url, "error": str(exc)}

    def extract_content(self, selector: str | None = None) -> dict[str, Any]:
        """Extrai texto limpo, títulos e links do elemento ou do body."""
        if not self._available:
            return {"ok": False, "error": "Playwright não disponível."}

        try:
            page = self.ensure_page()
            if not page.url or page.url == "about:blank":
                return {"ok": False, "error": "Nenhuma página carregada para extração."}

            target_selector = (selector or "").strip()

            script = """
            (targetSelector) => {
                const root = targetSelector ? document.querySelector(targetSelector) : document.body;
                if (!root) return null;

                // Clona para não alterar o DOM real
                const clone = root.cloneNode(true);
                clone.querySelectorAll('script, style, noscript, svg, iframe').forEach(e => e.remove());

                // Coleta headings
                const headings = [];
                clone.querySelectorAll('h1, h2, h3, h4').forEach(h => {
                    const text = (h.innerText || '').trim();
                    if (text) headings.push({ tag: h.tagName.toLowerCase(), text });
                });

                // Coleta links
                const links = [];
                clone.querySelectorAll('a[href]').forEach(a => {
                    const text = (a.innerText || '').trim();
                    const href = a.getAttribute('href') || '';
                    if (text && href && !href.startsWith('javascript:')) {
                        links.push({ text: text.slice(0, 100), href });
                    }
                });

                const rawText = clone.innerText || clone.textContent || '';
                return {
                    text: rawText,
                    headings: headings.slice(0, 20),
                    links: links.slice(0, 50),
                    found: true
                };
            }
            """
            result = page.evaluate(script, target_selector if target_selector else None)
            if not result or not result.get("found"):
                return {
                    "ok": False,
                    "url": page.url,
                    "selector": target_selector,
                    "error": f"Seletor '{target_selector}' não encontrado na página."
                }

            cleaned = _clean_text(result.get("text", ""))
            # Truncamento de segurança para não explodir tokens
            truncated = cleaned[:12000]

            return {
                "ok": True,
                "url": page.url,
                "title": page.title(),
                "selector": target_selector or "body",
                "headings": result.get("headings", []),
                "links": result.get("links", []),
                "text": truncated,
                "total_chars": len(cleaned),
                "truncated": len(cleaned) > 12000,
                "message": f"Extraído conteúdo de {page.url} ({len(truncated)} caracteres, {len(result.get('links', []))} links)."
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def search_and_extract(self, query: str, url: str | None = None) -> dict[str, Any]:
        """Busca texto ou palavras-chave dentro da página para responder perguntas."""
        if not self._available:
            return {"ok": False, "error": "Playwright não disponível."}

        query_str = str(query or "").strip()
        if not query_str:
            return {"ok": False, "error": "Termo de busca (query) é obrigatório."}

        if url:
            nav = self.navigate(url)
            if not nav.get("ok"):
                return nav

        try:
            page = self.ensure_page()
            content = self.extract_content()
            if not content.get("ok"):
                return content

            full_text = content.get("text", "")
            title = content.get("title", "")
            keywords = [k.lower() for k in re.findall(r"\w+", query_str) if len(k) > 2]

            matches: list[dict[str, Any]] = []
            paragraphs = [p.strip() for p in full_text.split("\n") if len(p.strip()) > 15]

            # 1. Busca parágrafos relevantes
            for p in paragraphs:
                p_lower = p.lower()
                score = sum(1 for kw in keywords if kw in p_lower)
                if score > 0 or (len(keywords) == 0 and query_str.lower() in p_lower):
                    matches.append({"text": p[:400], "score": score})

            matches.sort(key=lambda x: x["score"], reverse=True)
            top_matches = matches[:8]

            # 2. Busca padrões de interesse adicionais (ex: preços, valores, datas)
            price_pattern = re.compile(r"(?:R\$\s*[\d\.,]+|\$\s*[\d\.,]+|EUR\s*[\d\.,]+|[\d\.,]+\s*reais)", re.I)
            prices_found = list(dict.fromkeys(price_pattern.findall(full_text)))[:10]

            summary_lines = [f"Resultados da busca por '{query_str}' em {page.url} ({title}):"]
            if top_matches:
                summary_lines.append("\nTrechos mais relevantes encontrados:")
                for i, m in enumerate(top_matches, 1):
                    summary_lines.append(f"{i}. {m['text']}")
            else:
                summary_lines.append("Nenhum trecho correspondente direto encontrado.")

            if prices_found:
                summary_lines.append(f"\nValores/Preços detectados na página: {', '.join(prices_found)}")

            return {
                "ok": True,
                "url": page.url,
                "title": title,
                "query": query_str,
                "matches": [m["text"] for m in top_matches],
                "prices": prices_found,
                "summary": "\n".join(summary_lines),
                "count": len(top_matches),
                "message": "\n".join(summary_lines)
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def click(self, selector: str) -> dict[str, Any]:
        """Clica no elemento pelo seletor com validação de visibilidade e estado."""
        if not self._available:
            return {"ok": False, "error": "Playwright não disponível."}

        target_selector = str(selector or "").strip()
        if not target_selector:
            return {"ok": False, "error": "Seletor é obrigatório para a ação click."}

        try:
            page = self.ensure_page()
            locator = page.locator(target_selector).first

            # Valida e aguarda o elemento ficar visível
            locator.wait_for(state="visible", timeout=min(self.timeout_ms, 8000))
            locator.click(timeout=min(self.timeout_ms, 8000))

            # Aguarda possíveis atualizações de DOM ou navegação
            try:
                page.wait_for_load_state("domcontentloaded", timeout=3000)
            except Exception:
                pass

            return {
                "ok": True,
                "selector": target_selector,
                "url": page.url,
                "title": page.title(),
                "message": f"Elemento '{target_selector}' clicado com sucesso. Página atual: {page.url} (Título: '{page.title()}')."
            }
        except PlaywrightTimeoutError:
            return {
                "ok": False,
                "selector": target_selector,
                "error": f"Elemento '{target_selector}' não ficou visível ou interativo no tempo limite."
            }
        except Exception as exc:
            return {"ok": False, "selector": target_selector, "error": str(exc)}

    def fill_form(self, fields: dict[str, str]) -> dict[str, Any]:
        """Preenche campos/inputs com validação individual."""
        if not self._available:
            return {"ok": False, "error": "Playwright não disponível."}

        if not isinstance(fields, dict) or not fields:
            return {"ok": False, "error": "O argumento 'fields' deve ser um dicionário não vazio (seletor -> valor)."}

        page = self.ensure_page()
        filled: list[dict[str, str]] = []
        failed: list[dict[str, str]] = []

        for key, val in fields.items():
            selector = str(key).strip()
            value = str(val if val is not None else "")
            try:
                # Tenta o seletor exato primeiro
                loc = page.locator(selector).first
                count = loc.count()
                if count == 0 and not any(selector.startswith(c) for c in ("#", ".", "[", "//")):
                    # Tenta seletores alternativos comuns
                    alternatives = [
                        f"input[name='{selector}']",
                        f"input[id='{selector}']",
                        f"textarea[name='{selector}']",
                        f"input[placeholder*='{selector}']",
                        f"[aria-label*='{selector}']",
                    ]
                    for alt in alternatives:
                        alt_loc = page.locator(alt).first
                        if alt_loc.count() > 0:
                            loc = alt_loc
                            selector = alt
                            break

                loc.wait_for(state="visible", timeout=min(self.timeout_ms, 5000))
                loc.fill(value, timeout=min(self.timeout_ms, 5000))
                filled.append({"selector": selector, "value": value})
            except Exception as exc:
                failed.append({"selector": selector, "error": str(exc)})

        success = len(failed) == 0 and len(filled) > 0
        status_msg = f"Preenchidos {len(filled)} campo(s) com sucesso."
        if failed:
            status_msg += f" Falha em {len(failed)} campo(s): " + ", ".join(f"{f['selector']}: {f['error']}" for f in failed)

        return {
            "ok": success,
            "filled": filled,
            "failed": failed,
            "url": page.url,
            "message": status_msg
        }

    def screenshot(self, path: str | Path | None = None, full_page: bool = False) -> dict[str, Any]:
        """Captura tela da página atual para diagnósticos e visualização."""
        if not self._available:
            return {"ok": False, "error": "Playwright não disponível."}

        try:
            page = self.ensure_page()
            if not page.url or page.url == "about:blank":
                return {"ok": False, "error": "Nenhuma página carregada para captura."}

            data = page.screenshot(type="png", full_page=bool(full_page), timeout=min(self.timeout_ms, 10000))

            if not path:
                filename = f"browser_{int(time.time())}_{os.urandom(2).hex()}.png"
                target_path = CAPTURES_DIR / filename
            else:
                target_path = Path(path)
                target_path.parent.mkdir(parents=True, exist_ok=True)

            target_path.write_bytes(data)

            return {
                "ok": True,
                "url": page.url,
                "title": page.title(),
                "path": str(target_path.resolve()),
                "filename": target_path.name,
                "size_bytes": len(data),
                "message": f"Captura de tela salva com sucesso em {target_path.name} ({len(data)} bytes)."
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def __enter__(self) -> "BrowserService":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()


_GLOBAL_SERVICE: BrowserService | None = None
_SERVICE_LOCK = threading.Lock()


def get_browser_service(headless: bool | None = None, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> BrowserService:
    """Retorna a instância singleton do serviço de navegador."""
    global _GLOBAL_SERVICE
    with _SERVICE_LOCK:
        if _GLOBAL_SERVICE is None:
            _GLOBAL_SERVICE = BrowserService(headless=headless, timeout_ms=timeout_ms)
        elif headless is not None and _GLOBAL_SERVICE._headless_override != headless:
            _GLOBAL_SERVICE.stop()
            _GLOBAL_SERVICE = BrowserService(headless=headless, timeout_ms=timeout_ms)
        return _GLOBAL_SERVICE


def close_browser_service() -> None:
    """Encerra a instância global se aberta."""
    global _GLOBAL_SERVICE
    with _SERVICE_LOCK:
        if _GLOBAL_SERVICE is not None:
            _GLOBAL_SERVICE.stop()
            _GLOBAL_SERVICE = None

