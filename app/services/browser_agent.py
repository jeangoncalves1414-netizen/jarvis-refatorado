from __future__ import annotations

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


import os
import time
from pathlib import Path

CAPTURES_DIR = Path("data/captures")
CAPTURES_DIR.mkdir(parents=True, exist_ok=True)


class BrowserAgent:
    """Automação web com Playwright."""

    def __init__(self, headless: bool = True):
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright não disponível")
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._page = None

    def start(self) -> None:
        """Inicia navegador Chromium."""
        if self._playwright:
            return
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self._page = context.new_page()
        self._page.set_default_timeout(15000)

    def stop(self) -> None:
        """Para o navegador e encerra o processo do Playwright."""
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
        self._browser = None
        self._playwright = None
        self._page = None

    def goto(self, url: str) -> None:
        """Navega para a URL com timeout seguro."""
        if not self._page:
            self.start()
        try:
            self._page.goto(url, wait_until="domcontentloaded", timeout=15000)
        except Exception as exc:
            print(f"[BrowserAgent] Aviso ao navegar para {url}: {exc}")

    def click(self, selector: str) -> None:
        """Clica no elemento pelo seletor."""
        if not self._page:
            raise RuntimeError("Navegador não iniciado")
        self._page.click(selector, timeout=5000)

    def fill(self, selector: str, text: str) -> None:
        """Preenche o campo pelo seletor."""
        if not self._page:
            raise RuntimeError("Navegador não iniciado")
        self._page.fill(selector, text, timeout=5000)

    def text(self, selector: str) -> str:
        """Retorna o conteúdo textual do elemento."""
        if not self._page:
            raise RuntimeError("Navegador não iniciado")
        return self._page.text_content(selector, timeout=5000) or ""

    def screenshot(self) -> bytes:
        """Captura screenshot em bytes PNG."""
        if not self._page:
            raise RuntimeError("Navegador não iniciado")
        return self._page.screenshot(type="png", full_page=False)

    def save_screenshot(self, prefix: str = "browser") -> tuple[str, str]:
        """Salva screenshot da página em data/captures/ e retorna (filepath, filename)."""
        data = self.screenshot()
        filename = f"{prefix}_{int(time.time())}_{os.urandom(2).hex()}.png"
        filepath = CAPTURES_DIR / filename
        filepath.write_bytes(data)
        return str(filepath), filename
