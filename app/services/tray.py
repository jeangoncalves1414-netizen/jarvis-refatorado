"""Serviço de System Tray e Boot Automático do Jarvis para Windows."""
from __future__ import annotations

import os
import sys
import threading
import winreg
from pathlib import Path
from typing import Any, Callable

_STARTUP_REG_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "JarvisAssistant"


class BootService:
    """Gerencia a inicialização automática do Jarvis com o Windows (sem .exe)."""

    @staticmethod
    def _get_pythonw() -> str:
        """Retorna o caminho do pythonw.exe (sem janela de console)."""
        python_dir = Path(sys.executable).parent
        pythonw = python_dir / "pythonw.exe"
        return str(pythonw) if pythonw.exists() else sys.executable

    @staticmethod
    def _get_startup_command() -> str:
        """Retorna o comando de inicialização: pythonw + caminho absoluto do main.py."""
        pythonw = BootService._get_pythonw()
        # Detecta o diretório raiz do projeto (onde fica app/)
        app_dir = Path(__file__).resolve().parent.parent.parent
        main_script = app_dir / "run_jarvis.pyw"
        if not main_script.exists():
            # Cria o script .pyw wrapper se não existir
            BootService._create_pyw_script(app_dir, main_script)
        return f'"{pythonw}" "{main_script}"'

    @staticmethod
    def _create_pyw_script(app_dir: Path, script_path: Path) -> None:
        """Cria run_jarvis.pyw — wrapper sem console para inicialização automática."""
        content = f"""\
# Jarvis — Script de inicialização automática (sem janela de console)
import sys
import os
sys.path.insert(0, r"{app_dir}")
os.chdir(r"{app_dir}")
from app.main import main
main()
"""
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(content)

    @staticmethod
    def is_enabled() -> bool:
        """Verifica se o Jarvis está registrado na inicialização automática."""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _STARTUP_REG_KEY) as key:
                winreg.QueryValueEx(key, _APP_NAME)
                return True
        except FileNotFoundError:
            return False
        except Exception:
            return False

    @staticmethod
    def enable() -> bool:
        """Registra o Jarvis para iniciar automaticamente com o Windows."""
        try:
            command = BootService._get_startup_command()
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, _STARTUP_REG_KEY, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, command)
            return True
        except Exception as e:
            print(f"[BootService] Falha ao ativar boot automático: {e}")
            return False

    @staticmethod
    def disable() -> bool:
        """Remove o Jarvis da inicialização automática do Windows."""
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, _STARTUP_REG_KEY, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.DeleteValue(key, _APP_NAME)
            print("[BootService] Inicialização automática removida com sucesso.")
            return True
        except FileNotFoundError:
            print("[BootService] Entrada não encontrada no registro (já estava desativada).")
            return True
        except Exception as e:
            print(f"[BootService] Falha ao desativar boot automático: {e}")
            return False


class TrayService:
    """
    Ícone do Jarvis na barra do sistema (System Tray) com menu de contexto.
    Usa pystray + PIL para ícone gerado dinamicamente.
    """

    def __init__(
        self,
        panel_url: str = "http://127.0.0.1:8000",
        on_quit: Callable[[], None] | None = None,
        on_open: Callable[[], None] | None = None,
        boot_service: type[BootService] | None = None,
    ) -> None:
        self.panel_url = panel_url
        self.on_quit = on_quit
        self.on_open = on_open
        self.boot_service = boot_service or BootService
        self._icon: Any = None
        self._thread: threading.Thread | None = None

    def _make_icon_image(self) -> Any:
        """Gera o ícone do Jarvis dinamicamente usando PIL (círculo azul com 'J')."""
        try:
            from PIL import Image, ImageDraw, ImageFont
            size = 64
            img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            # Círculo de fundo azul escuro
            draw.ellipse([2, 2, size - 2, size - 2], fill=(20, 100, 200, 255))
            # Letra J branca
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 40)
            except Exception:
                font = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), "J", font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text(((size - tw) / 2, (size - th) / 2 - 4), "J", fill="white", font=font)
            return img
        except ImportError:
            # PIL não disponível — ícone mínimo 1x1
            try:
                from PIL import Image
                return Image.new("RGB", (1, 1), (20, 100, 200))
            except Exception:
                return None

    def _build_menu(self) -> Any:
        try:
            import pystray
            from pystray import MenuItem as Item

            boot_label = lambda item: (
                "✅ Iniciar com Windows (ativo)"
                if self.boot_service.is_enabled()
                else "🔲 Iniciar com Windows"
            )

            def toggle_boot(icon, item):
                if self.boot_service.is_enabled():
                    self.boot_service.disable()
                else:
                    self.boot_service.enable()
                # Reconstrói e aplica o menu atualizado
                icon.menu = self._build_menu()
                try:
                    icon.update_menu()
                except Exception:
                    pass  # Alguns backends não suportam update_menu()

            def open_panel(icon, item):
                if self.on_open:
                    try:
                        # Executa o callback em thread separada para evitar bloquear o thread do pystray
                        threading.Thread(target=self.on_open, daemon=True).start()
                    except Exception:
                        try:
                            self.on_open()
                        except Exception:
                            pass
                else:
                    import webbrowser
                    webbrowser.open(self.panel_url)  # fallback: abre navegador

            def quit_app(icon, item):
                icon.stop()
                if self.on_quit:
                    self.on_quit()

            return pystray.Menu(
                Item("🤖 JARVIS Assistant", open_panel, default=True),
                pystray.Menu.SEPARATOR,
                Item("🖥️ Mostrar Janela", open_panel),
                Item(boot_label, toggle_boot),
                pystray.Menu.SEPARATOR,
                Item("❌ Sair do Jarvis", quit_app),
            )
        except ImportError:
            return None

    def start(self) -> None:
        """Inicia o ícone no system tray em thread separada."""
        try:
            import pystray

            image = self._make_icon_image()
            if image is None:
                print("[TrayService] PIL não disponível — ícone do tray desabilitado.")
                return

            menu = self._build_menu()
            self._icon = pystray.Icon(
                name="jarvis",
                icon=image,
                title="JARVIS Assistant",
                menu=menu,
            )

            self._thread = threading.Thread(target=self._icon.run, daemon=True, name="TrayIcon")
            self._thread.start()
            print("[TrayService] Ícone do Jarvis iniciado no System Tray.")
        except ImportError:
            print("[TrayService] pystray não instalado — System Tray desabilitado.")
        except Exception as e:
            print(f"[TrayService] Falha ao iniciar System Tray: {e}")

    def stop(self) -> None:
        """Para o ícone do tray."""
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass

    def notify(self, title: str, message: str) -> None:
        """Shows a native tray notification when the desktop tray is available."""
        if not self._icon:
            return
        try:
            self._icon.notify(message, title)
        except Exception as exc:
            print(f"[TrayService] Falha ao notificar: {exc}")

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
