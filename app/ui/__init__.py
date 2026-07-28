from __future__ import annotations

try:
    from .tray_icon import TrayIcon
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

__all__ = []

if TRAY_AVAILABLE:
    __all__.append("TrayIcon")
