from __future__ import annotations

import ctypes
from typing import Callable

class WindowControl:
    """Controle básico de janelas Windows."""
    
    def __init__(self):
        self.user32 = ctypes.windll.user32
    
    def find_window(self, title: str) -> int | None:
        """Encontra janela por título."""
        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
        def callback(hwnd, _):
            length = self.user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                self.user32.GetWindowTextW(hwnd, buff, length + 1)
                if title.lower() in buff.value.lower():
                    callback.hwnd = hwnd
                    return False
            return True
        
        callback.hwnd = None
        self.user32.EnumWindows(callback, 0)
        return callback.hwnd
    
    def focus_window(self, hwnd: int) -> bool:
        """Foca janela."""
        try:
            if self.user32.IsIconic(hwnd):
                self.user32.ShowWindow(hwnd, 9)
            self.user32.SetForegroundWindow(hwnd)
            return True
        except (OSError, RuntimeError):
            return False
    
    def close_window(self, hwnd: int) -> bool:
        """Fecha janela."""
        try:
            self.user32.PostMessageW(hwnd, 0x0010, 0, 0)
            return True
        except (OSError, RuntimeError):
            return False
