from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import win10toast
    TOAST_AVAILABLE = True
except ImportError:
    TOAST_AVAILABLE = False
    logger.warning("win10toast não disponível. Notificações Windows serão desabilitadas.")


class WindowsNotification:
    """Notificações do Windows 10/11."""
    
    def __init__(self, app_name: str = "Jarvis"):
        if not TOAST_AVAILABLE:
            raise RuntimeError("win10toast não instalado. Instale com: pip install win10toast")
        
        self.app_name = app_name
        self._toaster = win10toast.ToastNotifier()
    
    def show(
        self,
        title: str,
        message: str,
        duration: int = 5,
        icon_path: Optional[str] = None
    ) -> bool:
        """Mostra notificação."""
        try:
            self._toaster.show_toast(
                title=title,
                msg=message,
                duration=duration,
                icon_path=icon_path,
                threaded=True
            )
            return True
        except Exception as e:
            logger.error(f"Falha ao mostrar notificação: {e}")
            return False
    
    def is_available(self) -> bool:
        return TOAST_AVAILABLE
