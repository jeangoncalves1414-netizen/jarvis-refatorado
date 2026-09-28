"""
Desktop Automation - Automação básica de desktop inspirada no Brahma-AI-Lite.
Funcionalidades:
- Abrir/fechar aplicações
- Controlar janelas
- Automação de arquivos
"""

from __future__ import annotations

import os
import subprocess
import platform
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class OSType(Enum):
    """Tipos de sistemas operacionais."""
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"


@dataclass
class AppInfo:
    """Informações sobre uma aplicação."""
    name: str
    executable: str
    path: str | None = None


class DesktopAutomation:
    """
    Automação básica de desktop.
    Suporta Windows, Linux e macOS.
    """

    def __init__(self):
        self.os_type = self._detect_os()
        self._apps: Dict[str, AppInfo] = {}
        self._load_common_apps()

    def _detect_os(self) -> OSType:
        """Detecta o sistema operacional."""
        system = platform.system().lower()
        if system == "windows":
            return OSType.WINDOWS
        elif system == "linux":
            return OSType.LINUX
        elif system == "darwin":
            return OSType.MACOS
        else:
            return OSType.WINDOWS  # Fallback

    def _load_common_apps(self) -> None:
        """Carrega aplicações comuns baseadas no OS."""
        if self.os_type == OSType.WINDOWS:
            self._apps = {
                "notepad": AppInfo("Notepad", "notepad.exe"),
                "chrome": AppInfo("Google Chrome", "chrome.exe"),
                "firefox": AppInfo("Firefox", "firefox.exe"),
                "edge": AppInfo("Microsoft Edge", "msedge.exe"),
                "explorer": AppInfo("File Explorer", "explorer.exe"),
                "cmd": AppInfo("Command Prompt", "cmd.exe"),
                "powershell": AppInfo("PowerShell", "powershell.exe"),
                "vscode": AppInfo("Visual Studio Code", "code.exe"),
                "spotify": AppInfo("Spotify", "spotify.exe"),
            }
        elif self.os_type == OSType.LINUX:
            self._apps = {
                "firefox": AppInfo("Firefox", "firefox"),
                "chrome": AppInfo("Google Chrome", "google-chrome"),
                "code": AppInfo("Visual Studio Code", "code"),
                "terminal": AppInfo("Terminal", "gnome-terminal"),
                "files": AppInfo("Files", "nautilus"),
            }
        elif self.os_type == OSType.MACOS:
            self._apps = {
                "safari": AppInfo("Safari", "Safari"),
                "chrome": AppInfo("Google Chrome", "Google Chrome"),
                "firefox": AppInfo("Firefox", "Firefox"),
                "terminal": AppInfo("Terminal", "Terminal"),
                "finder": AppInfo("Finder", "Finder"),
            }

    def open_app(self, app_name: str, args: List[str] | None = None) -> bool:
        """
        Abre uma aplicação.
        
        Args:
            app_name: Nome da aplicação (ex: chrome, notepad)
            args: Argumentos de linha de comando
            
        Returns:
            True se sucesso, False caso contrário
        """
        app = self._apps.get(app_name.lower())
        if not app:
            print(f"[DesktopAutomation] App não encontrada: {app_name}")
            return False

        try:
            if self.os_type == OSType.WINDOWS:
                cmd = [app.executable]
                if app.path:
                    cmd = [app.path]
                if args:
                    cmd.extend(args)
                subprocess.Popen(cmd, shell=False)
            elif self.os_type == OSType.LINUX:
                cmd = [app.executable]
                if args:
                    cmd.extend(args)
                subprocess.Popen(cmd, shell=False)
            elif self.os_type == OSType.MACOS:
                cmd = ["open", "-a", app.executable]
                if args:
                    cmd.extend(args)
                subprocess.Popen(cmd, shell=False)
            
            print(f"[DesktopAutomation] App aberta: {app.name}")
            return True
        except Exception as e:
            print(f"[DesktopAutomation] Erro ao abrir {app_name}: {e}")
            return False

    def open_url(self, url: str) -> bool:
        """Abre uma URL no navegador padrão."""
        # Validar URL básica
        if not url or not isinstance(url, str):
            return False
        if not (url.startswith("http://") or url.startswith("https://") or url.startswith("file://")):
            print(f"[DesktopAutomation] URL inválida: {url}")
            return False
        
        try:
            if self.os_type == OSType.WINDOWS:
                os.startfile(url)
            elif self.os_type == OSType.LINUX:
                subprocess.Popen(["xdg-open", url], shell=False)
            elif self.os_type == OSType.MACOS:
                subprocess.Popen(["open", url], shell=False)
            print(f"[DesktopAutomation] URL aberta: {url}")
            return True
        except Exception as e:
            print(f"[DesktopAutomation] Erro ao abrir URL: {e}")
            return False

    def open_file(self, file_path: str) -> bool:
        """Abre um arquivo com a aplicação padrão."""
        if not os.path.exists(file_path):
            print(f"[DesktopAutomation] Arquivo não encontrado: {file_path}")
            return False

        try:
            if self.os_type == OSType.WINDOWS:
                os.startfile(file_path)
            elif self.os_type == OSType.LINUX:
                subprocess.Popen(["xdg-open", file_path], shell=False)
            elif self.os_type == OSType.MACOS:
                subprocess.Popen(["open", file_path], shell=False)
            print(f"[DesktopAutomation] Arquivo aberto: {file_path}")
            return True
        except Exception as e:
            print(f"[DesktopAutomation] Erro ao abrir arquivo: {e}")
            return False

    def open_folder(self, folder_path: str) -> bool:
        """Abre uma pasta no gerenciador de arquivos."""
        if not os.path.exists(folder_path):
            print(f"[DesktopAutomation] Pasta não encontrada: {folder_path}")
            return False

        try:
            if self.os_type == OSType.WINDOWS:
                subprocess.Popen(["explorer", folder_path], shell=False)
            elif self.os_type == OSType.LINUX:
                subprocess.Popen(["xdg-open", folder_path], shell=False)
            elif self.os_type == OSType.MACOS:
                subprocess.Popen(["open", folder_path], shell=False)
            print(f"[DesktopAutomation] Pasta aberta: {folder_path}")
            return True
        except Exception as e:
            print(f"[DesktopAutomation] Erro ao abrir pasta: {e}")
            return False

    def list_open_windows(self) -> List[Dict[str, Any]]:
        """
        Lista janelas abertas (Windows apenas).
        Retorna lista de dicionários com título e handle.
        """
        if self.os_type != OSType.WINDOWS:
            print("[DesktopAutomation] Listagem de janelas suportada apenas no Windows")
            return []

        try:
            import win32gui
            windows = []
            
            def enum_handler(hwnd, ctx):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title:
                        windows.append({
                            "handle": hwnd,
                            "title": title
                        })
            
            win32gui.EnumWindows(enum_handler, None)
            return windows
        except ImportError:
            print("[DesktopAutomation] pywin32 não instalado. Instale com: pip install pywin32")
            return []
        except Exception as e:
            print(f"[DesktopAutomation] Erro ao listar janelas: {e}")
            return []

    def focus_window(self, title: str) -> bool:
        """
        Foca em uma janela pelo título (Windows apenas).
        """
        if self.os_type != OSType.WINDOWS:
            print("[DesktopAutomation] Foco de janela suportado apenas no Windows")
            return False

        try:
            import win32gui
            import win32con
            
            found = False
            def enum_handler(hwnd, ctx):
                nonlocal found
                if win32gui.IsWindowVisible(hwnd):
                    window_title = win32gui.GetWindowText(hwnd)
                    if title.lower() in window_title.lower():
                        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                        win32gui.SetForegroundWindow(hwnd)
                        found = True
                        return True
                return False
            
            win32gui.EnumWindows(enum_handler, None)
            if found:
                print(f"[DesktopAutomation] Janela focada: {title}")
                return True
            else:
                print(f"[DesktopAutomation] Janela não encontrada: {title}")
                return False
        except ImportError:
            print("[DesktopAutomation] pywin32 não instalado")
            return False
        except Exception as e:
            print(f"[DesktopAutomation] Erro ao focar janela: {e}")
            return False

    def minimize_window(self, title: str) -> bool:
        """Minimiza uma janela pelo título (Windows apenas)."""
        if self.os_type != OSType.WINDOWS:
            return False

        try:
            import win32gui
            import win32con
            
            found = False
            def enum_handler(hwnd, ctx):
                nonlocal found
                if win32gui.IsWindowVisible(hwnd):
                    window_title = win32gui.GetWindowText(hwnd)
                    if title.lower() in window_title.lower():
                        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                        found = True
                        return True
                return False
            
            win32gui.EnumWindows(enum_handler, None)
            if found:
                print(f"[DesktopAutomation] Janela minimizada: {title}")
                return True
            else:
                print(f"[DesktopAutomation] Janela não encontrada: {title}")
                return False
        except Exception as e:
            print(f"[DesktopAutomation] Erro ao minimizar janela: {e}")
            return False

    def get_system_info(self) -> Dict[str, Any]:
        """Retorna informações do sistema."""
        return {
            "os": platform.system(),
            "os_version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
        }

    def get_screen_resolution(self) -> tuple[int, int] | None:
        """Retorna a resolução da tela."""
        try:
            if self.os_type == OSType.WINDOWS:
                import win32api
                return (win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1))
            elif self.os_type == OSType.LINUX:
                import subprocess
                result = subprocess.run(["xrandr"], capture_output=True, text=True)
                if result.returncode == 0:
                    for line in result.stdout.split("\n"):
                        if "*" in line:
                            parts = line.split()
                            for part in parts:
                                if "x" in part:
                                    width, height = part.split("x")
                                    return (int(width), int(height))
            elif self.os_type == OSType.MACOS:
                from AppKit import NSScreen
                screen = NSScreen.mainScreen()
                return (int(screen.frame().size.width), int(screen.frame().size.height))
        except Exception as e:
            print(f"[DesktopAutomation] Erro ao obter resolução: {e}")
        return None


# Singleton global
_automation_instance: Optional[DesktopAutomation] = None


def get_automation() -> DesktopAutomation:
    """Retorna instância singleton do DesktopAutomation."""
    global _automation_instance
    if _automation_instance is None:
        _automation_instance = DesktopAutomation()
    return _automation_instance
