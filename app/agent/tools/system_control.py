from __future__ import annotations

import ctypes
import re
import subprocess
import sys
import time
import psutil
import logging
from typing import Any
from .base import BaseTool, ToolResult
from app.services.system import SystemMetrics

logger = logging.getLogger(__name__)

# Virtual Key Codes para controle de mídia e volume do Windows
_VK_MEDIA_PLAY_PAUSE = 0xB3
_VK_MEDIA_NEXT = 0xB0
_VK_MEDIA_PREV = 0xB1
_VK_VOLUME_MUTE = 0xAD
_VK_VOLUME_DOWN = 0xAE
_VK_VOLUME_UP = 0xAF
_KEYEVENTF_EXTENDEDKEY = 0x0001
_KEYEVENTF_KEYUP = 0x0002

# Whitelist of allowed applications with their executable names
# Only these applications can be opened by the system_control tool
ALLOWED_APPS = {
    "notepad": "notepad.exe",
    "calc": "calc.exe",
    "mspaint": "mspaint.exe",
    "cmd": "cmd.exe",
    "explorer": "explorer.exe",
    "notepad++": "notepad++.exe",
    "code": "code.exe",  # VS Code
    "chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
}

# Brilho via WMI (sem dependência nova). Os comandos são fixos; o único valor variável é o nível,
# um inteiro de 0 a 100 já validado. Monitor externo ou PC de mesa costuma não expor esta interface.
_POWERSHELL = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command"]
_GET_BRIGHTNESS_SCRIPT = (
    "$ErrorActionPreference='Stop'; "
    "$m = Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness | Select-Object -First 1; "
    "if ($null -eq $m) { exit 3 }; [Console]::Out.Write($m.CurrentBrightness)"
)
_SET_BRIGHTNESS_SCRIPT = (
    "$ErrorActionPreference='Stop'; "
    "$m = Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods | Select-Object -First 1; "
    "if ($null -eq $m) { exit 3 }; "
    "Invoke-CimMethod -InputObject $m -MethodName WmiSetBrightness "
    "-Arguments @{Timeout=[uint32]0; Brightness=[byte]%d} | Out-Null"
)
_LOCK_SCREEN_COMMAND = ["rundll32.exe", "user32.dll,LockWorkStation"]
_COMMAND_TIMEOUT_SECONDS = 15
_BRIGHTNESS_UNSUPPORTED = (
    "Controle de brilho não suportado neste equipamento. Monitores externos e PCs de mesa normalmente "
    "não expõem o brilho ao Windows."
)


def parse_brightness_level(value: Any) -> int | None:
    """Aceita inteiro de 0 a 100 (também texto só com dígitos). Qualquer outra coisa é inválida."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        level = value
    elif isinstance(value, float) and value.is_integer():
        level = int(value)
    elif isinstance(value, str) and re.fullmatch(r"\d{1,3}", value.strip()):
        level = int(value.strip())
    else:
        return None
    return level if 0 <= level <= 100 else None


def _run_command(argv: list[str]) -> subprocess.CompletedProcess:
    # shell=False e argumentos fixos: nada vindo do usuário ou do modelo vira linha de comando.
    return subprocess.run(
        argv, shell=False, capture_output=True, text=True, timeout=_COMMAND_TIMEOUT_SECONDS,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _press_media_key(vk: int, repeat: int = 1) -> None:
    try:
        user32 = ctypes.windll.user32
        for _ in range(repeat):
            user32.keybd_event(vk, 0, _KEYEVENTF_EXTENDEDKEY, 0)
            user32.keybd_event(vk, 0, _KEYEVENTF_EXTENDEDKEY | _KEYEVENTF_KEYUP, 0)
            time.sleep(0.05)
    except Exception as e:
        print(f"[SystemControl] Erro ao pressionar tecla de mídia: {e}")


class SystemControlTool(BaseTool):
    @property
    def name(self) -> str:
        return "system_control"

    @property
    def description(self) -> str:
        return "Controla funções do sistema local (CPU/RAM, abrir apps), mídia/volume (play, pause, próxima, anterior, volume), brilho da tela (get_brightness, set_brightness com level 0-100) e bloqueio de tela (lock_screen)."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "telemetry", "open_app", "list_processes",
                        "media_play_pause", "media_next", "media_prev",
                        "volume_up", "volume_down", "volume_mute",
                        "get_brightness", "set_brightness", "lock_screen"
                    ],
                    "description": "Ação a ser executada: 'telemetry', 'open_app', 'list_processes', 'media_play_pause', 'media_next', 'media_prev', 'volume_up', 'volume_down', 'volume_mute', 'get_brightness', 'set_brightness', 'lock_screen'."
                },
                "level": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Nível de brilho de 0 a 100 (somente com action 'set_brightness')."
                },
                "app_name": {
                    "type": "string",
                    "description": "Nome do aplicativo a abrir (ex: notepad, calc, mspaint)."
                }
            },
            "required": ["action"]
        }

    def _validate_app_name(self, app_name: str) -> str | None:
        """Validate and normalize application name against whitelist.
        
        Args:
            app_name: The application name to validate
            
        Returns:
            The normalized executable name if valid, None otherwise
        """
        if not app_name or not isinstance(app_name, str):
            return None
        
        app_name = app_name.strip().lower()
        
        # Check against whitelist
        if app_name in ALLOWED_APPS:
            return ALLOWED_APPS[app_name]
        
        return None

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        action = str(args.get("action", "telemetry")).lower()

        if action == "telemetry":
            metrics = SystemMetrics.get_metrics()
            msg = f"Telemetria do Sistema:\n- CPU: {metrics['cpu']}%\n- RAM: {metrics['ram_percent']}% ({metrics['ram_used']}GB usados de {metrics['ram_total']}GB)"
            return ToolResult(ok=True, message=msg, data=metrics)

        elif action == "list_processes":
            try:
                processes = []
                for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
                    try:
                        proc_info = proc.info
                        if proc_info['name']:
                            processes.append(f"{proc_info['name']} (PID: {proc_info['pid']})")
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
                
                processes = processes[:20]
                msg = f"Aplicativos em execução:\n" + "\n".join(f"- {p}" for p in processes)
                return ToolResult(ok=True, message=msg, data={"processes": processes})
            except Exception as e:
                logger.error(f"Error listing processes: {e}")
                return ToolResult(ok=False, message=f"Erro ao listar processos: {e}")

        elif action == "open_app":
            app_name = args.get("app_name", "")
            
            # Validate app name
            exe_name = self._validate_app_name(app_name)
            if not exe_name:
                logger.warning(f"Attempted to open unapproved application: {app_name}")
                return ToolResult(ok=False, message=f"Aplicativo '{app_name}' não é permitido ou seguro de abrir.")

            try:
                # Use shell=False to prevent command injection
                subprocess.Popen(exe_name, shell=False)
                logger.info(f"Successfully opened application: {app_name} -> {exe_name}")
                return ToolResult(ok=True, message=f"Aplicativo '{app_name}' iniciado com sucesso.")
            except FileNotFoundError:
                logger.error(f"Application executable not found: {exe_name}")
                return ToolResult(ok=False, message=f"Aplicativo '{app_name}' não encontrado no sistema.")
            except Exception as e:
                logger.error(f"Failed to start application {app_name}: {e}")
                return ToolResult(ok=False, message=f"Falha ao iniciar aplicativo: {e}")

        # --- Brilho e bloqueio de tela ---
        elif action == "get_brightness":
            try:
                completed = _run_command(_POWERSHELL + [_GET_BRIGHTNESS_SCRIPT])
            except (OSError, subprocess.SubprocessError) as exc:
                logger.warning("Brightness read failed: %s", type(exc).__name__)
                return ToolResult(ok=False, message=_BRIGHTNESS_UNSUPPORTED, data={"supported": False})
            if completed.returncode != 0:
                return ToolResult(ok=False, message=_BRIGHTNESS_UNSUPPORTED, data={"supported": False})
            level = parse_brightness_level((completed.stdout or "").strip())
            if level is None:
                return ToolResult(ok=False, message="O Windows retornou um valor de brilho inesperado; leitura não confirmada.")
            return ToolResult(ok=True, message=f"Brilho atual da tela: {level}%.", data={"brightness": level, "supported": True})

        elif action == "set_brightness":
            level = parse_brightness_level(args.get("level"))
            if level is None:
                return ToolResult(ok=False, message="Brilho inválido: informe um número inteiro de 0 a 100.")
            try:
                completed = _run_command(_POWERSHELL + [_SET_BRIGHTNESS_SCRIPT % level])
            except (OSError, subprocess.SubprocessError) as exc:
                logger.warning("Brightness change failed: %s", type(exc).__name__)
                return ToolResult(ok=False, message=_BRIGHTNESS_UNSUPPORTED, data={"supported": False})
            if completed.returncode != 0:
                return ToolResult(ok=False, message=_BRIGHTNESS_UNSUPPORTED, data={"supported": False})
            logger.info("Brightness set to %s", level)
            return ToolResult(ok=True, message=f"Brilho da tela ajustado para {level}%.", data={"brightness": level, "supported": True})

        elif action == "lock_screen":
            try:
                completed = _run_command(_LOCK_SCREEN_COMMAND)
            except (OSError, subprocess.SubprocessError) as exc:
                logger.warning("Screen lock failed: %s", type(exc).__name__)
                return ToolResult(ok=False, message="Não foi possível bloquear a tela neste equipamento.")
            if completed.returncode != 0:
                return ToolResult(ok=False, message="O Windows não confirmou o bloqueio da tela.")
            logger.info("Screen lock requested")
            return ToolResult(ok=True, message="Tela bloqueada.")

        # --- Controle Universal de Mídia & Volume ---
        elif action in ("media_play_pause", "play", "pause"):
            _press_media_key(_VK_MEDIA_PLAY_PAUSE)
            logger.info("Media play/pause executed")
            return ToolResult(ok=True, message="Play/Pause de mídia alterado no sistema.")

        elif action in ("media_next", "next"):
            _press_media_key(_VK_MEDIA_NEXT)
            logger.info("Media next executed")
            return ToolResult(ok=True, message="Avançado para a próxima faixa no player ativo.")

        elif action in ("media_prev", "prev", "previous"):
            _press_media_key(_VK_MEDIA_PREV)
            logger.info("Media previous executed")
            return ToolResult(ok=True, message="Retornado para a faixa anterior no player ativo.")

        elif action == "volume_up":
            _press_media_key(_VK_VOLUME_UP, repeat=5)
            logger.info("Volume up executed")
            return ToolResult(ok=True, message="Volume do sistema aumentado.")

        elif action == "volume_down":
            _press_media_key(_VK_VOLUME_DOWN, repeat=5)
            logger.info("Volume down executed")
            return ToolResult(ok=True, message="Volume do sistema diminuído.")

        elif action == "volume_mute":
            _press_media_key(_VK_VOLUME_MUTE)
            logger.info("Volume mute executed")
            return ToolResult(ok=True, message="Mute/Unmute do sistema alterado.")

        logger.warning(f"Unknown action attempted: {action}")
        return ToolResult(ok=False, message=f"Ação desconhecida: {action}")
