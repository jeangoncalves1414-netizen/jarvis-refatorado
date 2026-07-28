from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)

try:
    import pystray
    from PIL import Image
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False
    logger.warning("pystray não disponível. Tray icon será desabilitado.")


class TrayIcon:
    """Ícone na bandeja do sistema com menu de contexto."""
    
    def __init__(self, app_name: str = "Jarvis"):
        if not TRAY_AVAILABLE:
            raise RuntimeError("pystray não instalado. Instale com: pip install pystray pillow")
        
        self.app_name = app_name
        self._icon = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._menu_items: list[tuple[str, Callable]] = []
    
    def _create_icon(self) -> Image.Image:
        """Cria ícone simples."""
        # Cria um ícone quadrado azul simples
        img = Image.new("RGB", (64, 64), color=(0, 100, 200))
        return img
    
    def _on_clicked(self, icon, item):
        """Handler para clique no menu."""
        callback = item.callback
        if callback:
            try:
                callback()
            except Exception as e:
                logger.error(f"Erro no callback do menu: {e}")
    
    def set_menu_items(self, items: list[tuple[str, Callable]]):
        """Define itens do menu (label, callback)."""
        self._menu_items = items
    
    def _build_menu(self):
        """Constrói menu do pystray."""
        menu_items = []
        for label, callback in self._menu_items:
            item = pystray.MenuItem(label, lambda i, cb=callback: cb())
            menu_items.append(item)
        
        if menu_items:
            return pystray.Menu(*menu_items)
        return None
    
    def _run_icon(self):
        """Loop do ícone na tray."""
        try:
            icon_image = self._create_icon()
            menu = self._build_menu()
            
            self._icon = pystray.Icon(
                name=self.app_name,
                icon=icon_image,
                title=self.app_name,
                menu=menu
            )
            
            self._icon.run()
        except Exception as e:
            logger.error(f"Erro no tray icon: {e}")
    
    def start(self):
        """Inicia ícone na tray."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_icon, daemon=True)
        self._thread.start()
        logger.info(f"Tray icon '{self.app_name}' iniciado")
    
    def stop(self):
        """Para ícone na tray."""
        if not self._running:
            return
        
        self._running = False
        if self._icon:
            self._icon.stop()
        
        if self._thread:
            self._thread.join(timeout=2)
        
        logger.info("Tray icon parado")
    
    def notify(self, title: str, message: str):
        """Mostra notificação via tray icon."""
        if self._icon:
            try:
                self._icon.notify(title, message)
            except Exception as e:
                logger.error(f"Falha ao notificar via tray: {e}")
    
    def is_available(self) -> bool:
        return TRAY_AVAILABLE
