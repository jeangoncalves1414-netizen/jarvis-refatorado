from __future__ import annotations

import os
import json
import shutil
import time
import subprocess
import winreg
import ctypes
from ctypes import wintypes
from pathlib import Path
from typing import List, Optional

CONFIG_DIR = Path("C:/Users/maria/Desktop/Jarvis/data/config")
ALIASES_FILE = CONFIG_DIR / "aliases.json"

APP_ALIASES: dict[str, str] = {
    "chrome": "chrome", "navegador": "chrome", "google chrome": "chrome",
    "bloco de notas": "notepad", "bloco de nota": "notepad", "notepad": "notepad", "bloco": "notepad",
    "código": "code", "vscode": "code", "vs code": "code", "visual studio code": "code",
    "spotify": "spotify",
    "explorador": "explorer", "arquivos": "explorer", "explorador de arquivos": "explorer",
    "calculadora": "calc", "calc": "calc",
    "paint": "mspaint",
    "terminal": "wt", "windows terminal": "wt",
    "cmd": "cmd", "prompt": "cmd",
    "powershell": "powershell",
    "discord": "discord",
    "steam": "steam",
    "word": "winword", "excel": "excel", "powerpoint": "powerpnt",
    "teams": "teams", "microsoft teams": "teams",
    "outlook": "outlook",
    "edge": "msedge", "microsoft edge": "msedge",
    "whatsapp": "whatsapp"
}

_URI_PROTOCOLS = {
    "spotify": "spotify:", "discord": "discord:", "steam": "steam://open/main",
    "teams": "msteams:", "slack": "slack:", "zoom": "zoommtg:",
}

_SYSTEM_COMMANDS = {"notepad", "calc", "mspaint", "cmd", "powershell", "explorer", "wt", "code", "chrome", "msedge"}

_CREATE_NEW_CONSOLE = 0x00000010
_CREATE_NO_WINDOW = 0x08000000


def _exe_stem(name: str) -> str:
    """Nome do executável sem pasta nem ``.exe``, em minúsculas."""
    stem = name.strip().replace("\\", "/").rsplit("/", 1)[-1].lower()
    return stem[:-4] if stem.endswith(".exe") else stem


def _spawn(argv: list[str]) -> bool:
    """Inicia o executável sem shell: nenhum texto passa por cmd.exe como comando."""
    try:
        if argv[0].lower().endswith((".cmd", ".bat")):
            subprocess.Popen(argv, shell=False, creationflags=_CREATE_NO_WINDOW,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            # Apps de console (cmd, powershell) ganham janela própria; apps gráficos ignoram a flag.
            subprocess.Popen(argv, shell=False, creationflags=_CREATE_NEW_CONSOLE)
        return True
    except (OSError, ValueError):
        return False


class AppManager:
    """Gerenciamento robusto de aplicativos Windows."""
    
    def __init__(self):
        self._apps_cache = {}
        self._cache_time = 0
        self._cache_ttl = 3600  # 1 hora
        self._load_aliases()
    
    def _load_aliases(self):
        self.aliases = dict(APP_ALIASES)
        if ALIASES_FILE.exists():
            try:
                with open(ALIASES_FILE, "r", encoding="utf-8") as f:
                    custom_aliases = json.load(f)
                    self.aliases.update(custom_aliases)
            except (OSError, json.JSONDecodeError):
                pass
    
    def _scan_registry(self) -> dict[str, str]:
        """Escaneia registry por paths de .exe de apps instalados (como o projeto antigo)."""
        now = time.time()
        if self._apps_cache and (now - self._cache_time) < self._cache_ttl:
            return self._apps_cache
            
        apps = {}
        reg_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        
        for hive, key_path in reg_paths:
            key = None
            try:
                key = winreg.OpenKey(hive, key_path)
                for i in range(winreg.QueryInfoKey(key)[0]):
                    subkey = None
                    try:
                        subkey = winreg.OpenKey(key, winreg.EnumKey(key, i))
                        display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                        if not display_name:
                            continue
                            
                        exe_path = ""
                        try:
                            icon = winreg.QueryValueEx(subkey, "DisplayIcon")[0]
                            icon = icon.split(",")[0].strip().strip('"')
                            if icon.lower().endswith(".exe") and Path(icon).is_file():
                                exe_path = icon
                        except (FileNotFoundError, OSError):
                            pass
                        
                        if not exe_path:
                            try:
                                loc = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                                if loc and Path(loc).is_dir():
                                    for f in Path(loc).glob("*.exe"):
                                        fname = f.stem.lower()
                                        dname = display_name.lower()
                                        if fname in dname or dname.startswith(fname):
                                            exe_path = str(f)
                                            break
                            except (FileNotFoundError, OSError):
                                pass

                        if exe_path:
                            apps[display_name.lower()] = exe_path
                    except (OSError, FileNotFoundError):
                        continue
                    finally:
                        if subkey:
                            winreg.CloseKey(subkey)
            except (OSError, FileNotFoundError):
                continue
            finally:
                if key:
                    winreg.CloseKey(key)
        
        self._apps_cache = apps
        self._cache_time = now
        return apps
    
    def find_app(self, query: str) -> str | None:
        """Busca app por nome retornando o caminho do EXE ou None."""
        query = query.lower().strip()
        if query in self.aliases:
            return self.aliases[query]
        
        apps_cache = self._scan_registry()
        
        if query in apps_cache:
            return apps_cache[query]
            
        for name_lower, exe_path in apps_cache.items():
            if query in name_lower or name_lower.startswith(query):
                return exe_path
                
        return None

    def is_known_target(self, name: str) -> bool:
        """Se ``name`` resolve por alias, comando do sistema, protocolo URI conhecido ou app do registro.

        Nome livre e caminho de arquivo digitado não contam: abri-los exige aprovação.
        """
        query = str(name or "").lower().strip()
        if not query:
            return False
        base = query[:-4] if query.endswith(".exe") else query
        if query in self.aliases or base in _SYSTEM_COMMANDS or base in _URI_PROTOCOLS:
            return True
        try:
            return self.find_app(query) is not None
        except Exception:
            return False
    
    # ── Caminhos de executável conhecidos (mais confiável que URI para estes apps) ──
    _EXEC_PATHS: dict[str, str] = {
        "spotify": r"%APPDATA%\Spotify\Spotify.exe",
        "whatsapp": r"%LOCALAPPDATA%\WhatsApp\WhatsApp.exe",
        "discord": r"%LOCALAPPDATA%\Discord\Update.exe --processStart Discord.exe",
    }

    def focus_window(self, title_fragment: str) -> bool:
        """Traz para frente qualquer janela visível cujo título contenha title_fragment.
        
        Também tenta localizar por nome de classe de janela (útil para Spotify
        que fica na bandeja sem título).
        """
        target_hwnd: Optional[int] = None

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _enum_cb(hwnd, lparam):
            nonlocal target_hwnd
            # Busca por título
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                if title_fragment.lower() in buf.value.lower():
                    target_hwnd = hwnd
                    return False
            # Busca por classe de janela (ex: SpotifyMainWindow, Chrome_WidgetWin_1)
            class_buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetClassNameW(hwnd, class_buf, 256)
            if title_fragment.lower() in class_buf.value.lower():
                target_hwnd = hwnd
                return False
            return True

        ctypes.windll.user32.EnumWindows(_enum_cb, 0)

        if target_hwnd:
            # Mostra a janela se estiver oculta ou minimizada
            ctypes.windll.user32.ShowWindow(target_hwnd, 9)   # SW_RESTORE
            ctypes.windll.user32.ShowWindow(target_hwnd, 5)   # SW_SHOW
            ctypes.windll.user32.SetForegroundWindow(target_hwnd)
            return True
        return False

    def open_app(self, name: str) -> bool:
        """Abre aplicativo de maneira robusta, imitando o comportamento do Projeto AI.

        Ordem de tentativas:
        1. Executável absoluto conhecido (_EXEC_PATHS)
        2. Comandos de sistema (notepad, calc, etc.)
        3. Caminho direto de arquivo (cache)
        4. URI Protocol (spotify:, discord:, steam://)
        5. Executável encontrado no PATH, sem shell

        Nada é passado ao shell: um nome com argumentos ou operadores não vira comando.
        """
        resolved = self.find_app(name)
        if not resolved:
            resolved = name.lower()

        # Normaliza chave removendo .exe se houver (ex: spotify.exe -> spotify)
        key = resolved.lower().strip()
        base_key = key[:-4] if key.endswith(".exe") else key

        # 1. Executável absoluto conhecido
        target_path = self._EXEC_PATHS.get(base_key) or self._EXEC_PATHS.get(key)
        if target_path:
            path_expanded = os.path.expandvars(target_path)
            base_exe, _, extra = path_expanded.partition(" --")
            if Path(base_exe).is_file():
                argv = [base_exe] + (("--" + extra).split() if extra else [])
                if _spawn(argv):
                    return True

        # 2. Comandos de sistema do Windows (notepad, calc, cmd, etc.)
        if base_key in _SYSTEM_COMMANDS:
            exe = shutil.which(base_key)
            if exe and _spawn([exe]):
                return True
            try:
                # Sem PATH (ex.: chrome), o Windows resolve pelo registro App Paths, sem cmd.exe.
                os.startfile(base_key)
                return True
            except Exception:
                pass

        # 3. Caminho absoluto encontrado no cache de registro
        if Path(resolved).is_file():
            try:
                os.startfile(resolved)
                return True
            except Exception:
                pass

        # 4. URI Protocol (spotify:, discord:, steam:// …)
        uri = _URI_PROTOCOLS.get(base_key) or _URI_PROTOCOLS.get(key)
        if uri:
            try:
                os.startfile(uri)
                return True
            except Exception:
                pass

        # 5. Último recurso: executável com esse nome exato no PATH, sem shell
        exe = shutil.which(resolved.strip())
        if exe:
            return _spawn([exe])

        return False

    def is_app_running(self, name: str) -> tuple[bool, list[Any]]:
        """Verifica se um aplicativo está em execução. Retorna (bool, lista_de_processos).

        O casamento é exato no nome do executável, sem ``.exe`` e sem diferenciar maiúsculas:
        ``close_app`` encerra tudo o que casar, então "code" não pode pegar "vscode-helper".
        """
        import psutil
        resolved = self.find_app(name) or name
        target_stem = _exe_stem(resolved)
        if not target_stem:
            return (False, [])
        
        matches = []
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if _exe_stem(proc.info['name'] or "") == target_stem:
                    matches.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return (len(matches) > 0, matches)

    def close_app(self, name: str) -> tuple[bool, str]:
        """Encerra um aplicativo em execução de maneira graciosa (terminate), depois kill se necessário."""
        import psutil
        running, procs = self.is_app_running(name)
        if not running or not procs:
            return False, f"O aplicativo '{name}' não está em execução no momento."

        closed = 0
        for proc in procs:
            try:
                proc.terminate()
                closed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
                
        time.sleep(0.3)
        still_running, remaining = self.is_app_running(name)
        if still_running:
            for proc in remaining:
                try:
                    proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

        return True, f"Aplicativo '{name}' encerrado com sucesso."

    def list_running_apps(self) -> list[str]:
        """Retorna a lista de todos os aplicativos e janelas ativas do usuário em execução."""
        import subprocess
        import csv
        import io
        import psutil

        apps = set()
        ignored_procs = {
            "svchost.exe", "shellexperiencehost.exe", "startmenuexperiencehost.exe",
            "textinputhost.exe", "searchapp.exe", "presentmon-x64.exe", "radeonsoftware.exe",
            "atieclxx.exe", "taskhostw.exe", "lockapp.exe", "amdow.exe", "dllhost.exe",
            "runtimebroker.exe", "applicationframehost.exe", "dwm.exe", "ctfmon.exe"
        }
        ignored_titles = {
            "n/a", "program manager", "settings", "default ime", "msctfime ui",
            "windows input experience", "dwm notification window", "discord overlay input trap",
            "gdi+ window (amdrsserv.exe)", "system dashboard", "iniciar", "pesquisar",
            "presentmonwnd", "radeonsoftware", "smartdc", "task host window",
            "tela de bloqueio padrão do windows", "windows push notifications platform",
            "amd dvr overlay", "olemainthreadwndname", "olechannelwnd"
        }
        
        try:
            raw = subprocess.check_output("tasklist /v /fo csv", shell=True, errors="replace")
            decoded = raw.decode("latin1", errors="replace") if isinstance(raw, bytes) else str(raw)
            reader = csv.reader(io.StringIO(decoded))
            next(reader, None)
            
            for row in reader:
                if len(row) >= 9:
                    pname = row[0].strip()
                    title = row[8].strip()
                    t_lower = title.lower()
                    p_lower = pname.lower()
                    
                    if p_lower in ignored_procs or t_lower in ignored_titles or t_lower.startswith("gdi+"):
                        continue
                    if title:
                        apps.add(f"{title} ({pname})")
        except Exception:
            pass

        try:
            known = {"notepad", "spotify", "chrome", "msedge", "calc", "code", "discord", "steam", "wt", "cmd", "powershell", "whatsapp", "mspaint", "opera", "brave"}
            for proc in psutil.process_iter(['name']):
                try:
                    name = (proc.info['name'] or "").lower()
                    stem = name.replace(".exe", "")
                    if stem in known and not any(stem in a.lower() for a in apps):
                        apps.add(f"{stem.title()} ({name})")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception:
            pass

        return sorted(list(apps))


    def open_batch(self, names: List[str]) -> dict[str, bool]:
        """Abre múltiplos apps."""
        results = {}
        for name in names:
            results[name] = self.open_app(name)
            time.sleep(0.4)
        return results


_shared_manager: AppManager | None = None


def running_processes_for(name: str) -> list[tuple[str, int]]:
    """Processos que ``close_app(name)`` encerraria agora: ``[(nome do executável, quantidade)]``.

    Só lê a lista de processos; usa o mesmo casamento exato de ``is_app_running``.
    """
    global _shared_manager
    if _shared_manager is None:
        _shared_manager = AppManager()
    _running, procs = _shared_manager.is_app_running(name)
    labels: dict[str, str] = {}
    counts: dict[str, int] = {}
    for proc in procs:
        try:
            label = str(proc.info.get("name") or "") if isinstance(proc.info, dict) else ""
        except Exception:
            label = ""
        label = label or "processo sem nome"
        key = label.lower()
        labels.setdefault(key, label)
        counts[key] = counts.get(key, 0) + 1
    return [(labels[key], counts[key]) for key in sorted(counts)]


def is_known_app_target(name: str) -> bool:
    """Classificação de risco: ``AppManager.is_known_target`` com aliases e cache de registro compartilhados."""
    global _shared_manager
    if _shared_manager is None:
        _shared_manager = AppManager()
    return _shared_manager.is_known_target(name)

