"""Serviço de automação ativa de navegador web via Playwright.

Permite navegação programática, extração de texto limpo e links,
pesquisa inteligente dentro do DOM, cliques validados, preenchimento de formulários
e captura de tela para diagnósticos e visualização.
"""
from __future__ import annotations

import html as html_lib
import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

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


def _clean_html_string(html_str: str) -> str:
    """Limpa tags irrelevantes, anúncios, menus e scripts de uma string HTML."""
    if not html_str:
        return ""

    raw = str(html_str)
    # Remove blocos inteiros de script, style, noscript, svg, iframe, header, footer, nav, aside
    for tag in ("script", "style", "noscript", "svg", "iframe", "header", "footer", "nav", "aside"):
        raw = re.sub(rf"<{tag}[^>]*>[\s\S]*?</{tag}>", " ", raw, flags=re.I)

    # Remove elementos com classes/ids de anúncios, cookies e banners
    clutter_pattern = re.compile(
        r"<([a-zA-Z0-9]+)[^>]*(?:class|id)=[\"'][^\"']*(?:cookie|advertisement|ad-container|ad-box|sidebar|banner|newsletter|modal|popup)[^\"']*[\"'][^>]*>[\s\S]*?</\1>",
        re.I
    )
    raw = clutter_pattern.sub(" ", raw)
    raw = clutter_pattern.sub(" ", raw)

    # Converte tags de bloco em quebras de linha
    raw = re.sub(r"</?(?:p|h[1-6]|li|tr|div|section|article)[^>]*>", "\n", raw, flags=re.I)
    raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)

    # Remove todas as demais tags HTML
    raw = re.sub(r"<[^>]+>", " ", raw)

    text = html_lib.unescape(raw)
    return _clean_text(text)


def extract_clean_text(html_or_page: Any) -> str:
    """Extrai conteúdo principal limpo de menus, cabeçalhos, rodapés, anúncios e tags de script/style.
    
    Aceita um objeto Page do Playwright ou uma string HTML direta.
    """
    if html_or_page is None:
        return ""

    # Se for uma página Playwright (ou mock com evaluate)
    if hasattr(html_or_page, "evaluate"):
        clean_script = """
        () => {
            const root = document.querySelector('article, main, [role="main"]') || document.body;
            if (!root) return '';
            const clone = root.cloneNode(true);
            
            const unwanted = [
                'script', 'style', 'noscript', 'svg', 'iframe', 'canvas',
                'header', 'footer', 'nav', 'aside',
                '[role="banner"]', '[role="navigation"]', '[role="complementary"]', '[role="dialog"]',
                '.header', '.footer', '.navbar', '.nav', '.menu', '.sidebar',
                '.ad', '.ads', '.advertisement', '.ad-box', '.banner-ad',
                '.cookie-banner', '.cookie-consent', '.cookie-notice', '#cookie-banner', '#cookie-consent',
                '.popup', '.modal', '.newsletter', '.social-share', '.share-buttons'
            ];
            unwanted.forEach(sel => {
                try {
                    clone.querySelectorAll(sel).forEach(el => el.remove());
                } catch(e) {}
            });
            return clone.innerText || clone.textContent || '';
        }
        """
        try:
            raw = html_or_page.evaluate(clean_script)
            if raw and str(raw).strip():
                return _clean_text(raw)
        except Exception:
            pass

        # Fallback se evaluate falhar: tenta content()
        if hasattr(html_or_page, "content"):
            try:
                html_str = html_or_page.content()
                return _clean_html_string(html_str)
            except Exception:
                pass

    return _clean_html_string(str(html_or_page))


def _parse_interactive_elements_from_html(html_str: str) -> list[dict[str, Any]]:
    """Extrai elementos interativos de HTML estático para testes e ambientes offline."""
    if not html_str:
        return []

    results: list[dict[str, Any]] = []
    counter = 1

    # Procura botões: <button[^>]*>(.*?)</button>
    for m in re.finditer(r"<button[^>]*>([\s\S]*?)</button>", html_str, re.I):
        txt = re.sub(r"<[^>]+>", " ", m.group(1)).strip()
        txt = html_lib.unescape(txt)[:40] or "Botão"
        results.append({
            "id": counter,
            "label": f"[{counter}] Botão '{txt}'",
            "kind": "Botão",
            "text": txt,
            "tag": "button",
            "type": "button",
            "role": "button",
        })
        counter += 1

    # Procura inputs: <input([^>]+)>
    for m in re.finditer(r"<input([^>]+)>", html_str, re.I):
        attrs = m.group(1)
        type_m = re.search(r'type=[\"\']([^\"\']+)[\"\']', attrs, re.I)
        itype = type_m.group(1).lower() if type_m else "text"
        placeholder_m = re.search(r'placeholder=[\"\']([^\"\']+)[\"\']', attrs, re.I)
        name_m = re.search(r'name=[\"\']([^\"\']+)[\"\']', attrs, re.I)
        txt = placeholder_m.group(1) if placeholder_m else (name_m.group(1) if name_m else itype)
        txt = html_lib.unescape(txt)[:40]
        kind = f"Campo ({itype})" if itype not in ("text", "") else "Campo"
        results.append({
            "id": counter,
            "label": f"[{counter}] {kind} '{txt}'",
            "kind": kind,
            "text": txt,
            "tag": "input",
            "type": itype,
            "role": "",
        })
        counter += 1

    # Procura links: <a [^>]*href=...>(.*?)</a>
    for m in re.finditer(r"<a\s+[^>]*href=[\"']([^\"']+)[\"'][^>]*>([\s\S]*?)</a>", html_str, re.I):
        href = m.group(1)
        txt = re.sub(r"<[^>]+>", " ", m.group(2)).strip()
        txt = html_lib.unescape(txt)[:40] or href
        results.append({
            "id": counter,
            "label": f"[{counter}] Link '{txt}'",
            "kind": "Link",
            "text": txt,
            "tag": "a",
            "type": "",
            "role": "link",
        })
        counter += 1

    return results


def get_interactive_snapshot(page: Any) -> list[dict[str, Any]]:
    """Mapeia elementos visíveis clicáveis/digitáveis numerados para cliques exatos sem ambiguidades de CSS.
    
    Retorna uma lista de dicionários contendo:
    id, label (ex: "[1] Botão 'Entrar'", "[2] Campo 'Pesquisar'"), kind, text, tag, type, role.
    """
    if page is None:
        return []

    if hasattr(page, "evaluate"):
        snapshot_script = """
        () => {
            window.__interactive_elements = {};
            const candidates = Array.from(document.querySelectorAll(
                'button, a[href], input, textarea, select, [role="button"], [role="link"], [role="checkbox"], [role="radio"], [role="textbox"], [onclick], [tabindex]:not([tabindex="-1"])'
            ));

            const results = [];
            let counter = 1;

            for (const el of candidates) {
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;
                const rect = el.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0) continue;

                const tag = el.tagName.toLowerCase();
                const role = el.getAttribute('role') || '';
                const inputType = (el.getAttribute('type') || '').toLowerCase();

                let kind = "Elemento";
                let labelText = "";

                if (tag === 'button' || role === 'button' || (tag === 'input' && ['button', 'submit', 'reset'].includes(inputType))) {
                    kind = "Botão";
                    labelText = (el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('title') || '').trim();
                } else if (tag === 'a' || role === 'link') {
                    kind = "Link";
                    labelText = (el.innerText || el.getAttribute('aria-label') || el.getAttribute('title') || '').trim();
                    const href = el.getAttribute('href') || '';
                    if (href && !labelText) labelText = href;
                } else if (tag === 'input') {
                    if (['checkbox', 'radio'].includes(inputType)) {
                        kind = inputType === 'checkbox' ? "Caixa de Seleção" : "Opção";
                        labelText = (el.getAttribute('aria-label') || el.name || el.id || '').trim();
                    } else {
                        kind = "Campo";
                        labelText = (el.placeholder || el.getAttribute('aria-label') || el.name || el.id || '').trim();
                        if (inputType) kind += ` (${inputType})`;
                    }
                } else if (tag === 'textarea') {
                    kind = "Área de Texto";
                    labelText = (el.placeholder || el.getAttribute('aria-label') || el.name || el.id || '').trim();
                } else if (tag === 'select') {
                    kind = "Seleção";
                    labelText = (el.getAttribute('aria-label') || el.name || el.id || '').trim();
                } else {
                    labelText = (el.innerText || el.getAttribute('aria-label') || '').trim();
                }

                labelText = labelText.replace(/\\s+/g, ' ').slice(0, 50);
                if (!labelText) {
                    labelText = el.id ? `#${el.id}` : (el.className ? `.${el.className.toString().split(' ')[0]}` : tag);
                }

                const formattedLabel = `[${counter}] ${kind} '${labelText}'`;
                window.__interactive_elements[counter] = el;

                results.push({
                    id: counter,
                    label: formattedLabel,
                    kind: kind,
                    text: labelText,
                    tag: tag,
                    type: inputType,
                    role: role
                });
                counter++;
                if (counter > 100) break;
            }
            return results;
        }
        """
        try:
            res = page.evaluate(snapshot_script)
            if res:
                return res
        except Exception as e:
            logger.warning("Falha ao executar script de snapshot no navegador: %s", e)

    return _parse_interactive_elements_from_html(str(page))


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

    def extract_clean_text(self, selector: str | None = None) -> str:
        """Extrai texto limpo e legível da página ativa, livre de scripts, menus e cookies."""
        if not self._available:
            return ""
        try:
            page = self.ensure_page()
            if selector and selector.strip():
                try:
                    el = page.locator(selector.strip()).first
                    if el.count() > 0:
                        return _clean_html_string(el.inner_html())
                except Exception:
                    pass
            return extract_clean_text(page)
        except Exception as exc:
            logger.warning("Erro ao extrair texto limpo da página: %s", exc)
            return ""

    def get_interactive_snapshot(self) -> list[dict[str, Any]]:
        """Retorna snapshot semântico de elementos interativos numerados da página ativa."""
        if not self._available:
            return []
        try:
            page = self.ensure_page()
            return get_interactive_snapshot(page)
        except Exception as exc:
            logger.warning("Erro ao gerar snapshot interativo da página: %s", exc)
            return []

    def click_interactive_element(self, element_id: int) -> dict[str, Any]:
        """Clica no elemento pelo ID numérico do snapshot interativo."""
        if not self._available:
            return {"ok": False, "error": "Playwright não disponível."}

        try:
            page = self.ensure_page()
            script = """
            (id) => {
                if (!window.__interactive_elements || !window.__interactive_elements[id]) {
                    return false;
                }
                const el = window.__interactive_elements[id];
                el.scrollIntoView({ behavior: 'instant', block: 'center' });
                el.click();
                return true;
            }
            """
            success = page.evaluate(script, int(element_id))
            if not success:
                return {
                    "ok": False,
                    "element_id": element_id,
                    "error": f"Elemento [{element_id}] não encontrado na página. Execute get_interactive_snapshot primeiro.",
                }
            try:
                page.wait_for_load_state("domcontentloaded", timeout=2500)
            except Exception:
                pass
            return {
                "ok": True,
                "element_id": element_id,
                "url": page.url,
                "title": page.title(),
                "message": f"Elemento [{element_id}] clicado com sucesso. Página atual: {page.url} ({page.title()}).",
            }
        except Exception as exc:
            return {"ok": False, "element_id": element_id, "error": str(exc)}

    def type_interactive_element(self, element_id: int, text: str, press_enter: bool = False) -> dict[str, Any]:
        """Digita texto no elemento pelo ID numérico do snapshot interativo."""
        if not self._available:
            return {"ok": False, "error": "Playwright não disponível."}

        try:
            page = self.ensure_page()
            focus_script = """
            (id) => {
                if (!window.__interactive_elements || !window.__interactive_elements[id]) {
                    return false;
                }
                const el = window.__interactive_elements[id];
                el.scrollIntoView({ behavior: 'instant', block: 'center' });
                el.focus();
                if ('value' in el) el.value = '';
                return true;
            }
            """
            success = page.evaluate(focus_script, int(element_id))
            if not success:
                return {
                    "ok": False,
                    "element_id": element_id,
                    "error": f"Elemento [{element_id}] não encontrado na página.",
                }
            page.keyboard.type(str(text))
            if press_enter:
                page.keyboard.press("Enter")
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=2500)
                except Exception:
                    pass
            return {
                "ok": True,
                "element_id": element_id,
                "text": text,
                "url": page.url,
                "message": f"Texto digitado no elemento [{element_id}] com sucesso.",
            }
        except Exception as exc:
            return {"ok": False, "element_id": element_id, "error": str(exc)}

    def deep_search(self, query: str, max_sites: int = 3) -> dict[str, Any]:
        """Busca os melhores links e lê o conteúdo textual das páginas em paralelo para gerar síntese profunda citando fontes."""
        query_str = str(query or "").strip()
        if not query_str:
            return {"ok": False, "error": "Termo de busca (query) é obrigatório para deep_search."}

        limit = max(1, min(int(max_sites or 3), 6))

        # 1. Busca os links usando o mecanismo de busca existente com suporte a refinamento iterativo
        try:
            from app.agent.tools.web_search import _fallback_search, _needs_refinement, search_with_refinement
            search_items = _fallback_search(query_str, limit=limit)
            if _needs_refinement(search_items):
                refined_items, _, _ = search_with_refinement(query_str, limit=limit)
                if refined_items:
                    search_items = refined_items
        except Exception as search_err:
            search_items = []
            logger.warning("Erro na busca de links para deep_search: %s", search_err)

        if not search_items:
            # Fallback direto via DuckDuckGo HTML se Bing falhar
            try:
                import urllib.parse
                import urllib.request
                ddg_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(query_str)}"
                req = urllib.request.Request(ddg_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    ddg_html = resp.read().decode("utf-8", errors="replace")
                from app.agent.tools.web_search import _DuckDuckGoParser
                parser = _DuckDuckGoParser()
                parser.feed(ddg_html)
                from app.agent.tools.web_search import _normalise_result
                search_items = [_normalise_result(r) for r in parser.results[:limit]]
            except Exception:
                pass

        if not search_items:
            return {
                "ok": False,
                "query": query_str,
                "error": "Nenhum resultado retornado pelo buscador para esta consulta.",
                "message": f"Não foi possível encontrar páginas para '{query_str}'.",
            }

        # 2. Lê o conteúdo das páginas em paralelo
        import concurrent.futures
        import urllib.request

        def _fetch_page(item: dict[str, Any]) -> dict[str, Any]:
            url = item.get("url") or ""
            title = item.get("title") or "Página Web"
            snippet = item.get("snippet") or ""
            source = item.get("source") or "web"

            if not url.startswith(("http://", "https://")):
                return {"title": title, "url": url, "source": source, "text": snippet, "ok": False}

            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    }
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    raw_html = resp.read().decode("utf-8", errors="replace")

                clean_content = extract_clean_text(raw_html)
                content = clean_content[:5000] if clean_content else snippet
                return {
                    "title": title,
                    "url": url,
                    "source": source,
                    "text": content,
                    "ok": bool(clean_content),
                }
            except Exception as e:
                return {
                    "title": title,
                    "url": url,
                    "source": source,
                    "text": snippet or f"Erro ao acessar {url}: {e}",
                    "ok": False,
                }

        pages_data: list[dict[str, Any]] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(search_items), 5)) as executor:
            futures = [executor.submit(_fetch_page, item) for item in search_items[:limit]]
            for future in concurrent.futures.as_completed(futures):
                try:
                    pages_data.append(future.result())
                except Exception as exc:
                    logger.warning("Erro no worker de download: %s", exc)

        # 3. Monta o contexto das fontes
        sources_context = []
        for i, page_info in enumerate(pages_data, 1):
            status = "conteúdo completo" if page_info.get("ok") else "resumo"
            sources_context.append(
                f"Fonte [{i}]: {page_info.get('title')} ({page_info.get('url')}) [{status}]\n"
                f"{page_info.get('text')}\n"
            )

        context_str = "\n---\n".join(sources_context)

        prompt = (
            "Você é o analista de pesquisa web aprofundada do Jarvis.\n"
            f"O usuário pesquisou por: '{query_str}'\n\n"
            "Abaixo estão os conteúdos principais extraídos em tempo real das páginas consultadas:\n\n"
            f"{context_str}\n\n"
            "INSTRUÇÕES OBRIGATÓRIAS:\n"
            "1. Crie uma síntese aprofundada, precisa e estruturada respondendo à pesquisa.\n"
            "2. CITE EXPRESSAMENTE as fontes consultadas ao longo do texto usando [Nome da Fonte - URL].\n"
            "3. Se houver divergências ou dados específicos (datas, números, preços), destaque-os com precisão.\n"
        )

        try:
            from app.config import load_settings
            from app.services.llm import LLMService
            settings = load_settings()
            llm = LLMService(settings=settings)
            synthesis = llm.ask(prompt)
        except Exception as llm_err:
            synthesis = (
                f"Conteúdo de {len(pages_data)} páginas lido com sucesso, mas ocorreu erro ao chamar LLM: {llm_err}\n\n"
                f"Fontes consultadas:\n" + "\n".join(f"- {p['title']}: {p['url']}" for p in pages_data)
            )

        successful_reads = len([p for p in pages_data if p.get("ok")])
        return {
            "ok": True,
            "query": query_str,
            "synthesis": synthesis,
            "sites_read": successful_reads,
            "total_sites": len(pages_data),
            "sources": [{"title": p["title"], "url": p["url"], "source": p["source"]} for p in pages_data],
            "message": synthesis,
        }

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

