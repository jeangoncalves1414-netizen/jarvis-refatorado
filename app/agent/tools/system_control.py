from __future__ import annotations

import ctypes
import subprocess
import sys
import time
import psutil
from typing import Any
from .base import BaseTool, ToolResult
from app.services.system import SystemMetrics

# Virtual Key Codes para controle de mídia e volume do Windows
_VK_MEDIA_PLAY_PAUSE = 0xB3
_VK_MEDIA_NEXT = 0xB0
_VK_MEDIA_PREV = 0xB1
_VK_VOLUME_MUTE = 0xAD
_VK_VOLUME_DOWN = 0xAE
_VK_VOLUME_UP = 0xAF
_KEYEVENTF_EXTENDEDKEY = 0x0001
_KEYEVENTF_KEYUP = 0x0002

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
        return "Controla funções do sistema local (CPU/RAM, abrir apps) e controle universal de mídia/volume (play, pause, próxima, anterior, volume)."

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
                        "volume_up", "volume_down", "volume_mute"
                    ],
                    "description": "Ação a ser executada: 'telemetry', 'open_app', 'list_processes', 'media_play_pause', 'media_next', 'media_prev', 'volume_up', 'volume_down', 'volume_mute'."
                },
                "app_name": {
                    "type": "string",
                    "description": "Nome do aplicativo a abrir (ex: notepad, calc, mspaint)."
                }
            },
            "required": ["action"]
        }

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
                return ToolResult(ok=False, message=f"Erro ao listar processos: {e}")

        elif action == "open_app":
            app_name = args.get("app_name", "").strip().lower()
            allowed_apps = {"notepad": "notepad.exe", "calc": "calc.exe", "mspaint": "mspaint.exe"}
            
            if app_name not in allowed_apps:
                return ToolResult(ok=False, message=f"Aplicativo '{app_name}' não é permitido ou seguro de abrir.")

            try:
                subprocess.Popen(allowed_apps[app_name], shell=True)
                return ToolResult(ok=True, message=f"Aplicativo '{app_name}' iniciado com sucesso.")
            except Exception as e:
                return ToolResult(ok=False, message=f"Falha ao iniciar aplicativo: {e}")

        # --- Controle Universal de Mídia & Volume ---
        elif action in ("media_play_pause", "play", "pause"):
            _press_media_key(_VK_MEDIA_PLAY_PAUSE)
            return ToolResult(ok=True, message="Play/Pause de mídia alterado no sistema.")

        elif action in ("media_next", "next"):
            _press_media_key(_VK_MEDIA_NEXT)
            return ToolResult(ok=True, message="Avançado para a próxima faixa no player ativo.")

        elif action in ("media_prev", "prev", "previous"):
            _press_media_key(_VK_MEDIA_PREV)
            return ToolResult(ok=True, message="Retornado para a faixa anterior no player ativo.")

        elif action == "volume_up":
            _press_media_key(_VK_VOLUME_UP, repeat=5)
            return ToolResult(ok=True, message="Volume do sistema aumentado.")

        elif action == "volume_down":
            _press_media_key(_VK_VOLUME_DOWN, repeat=5)
            return ToolResult(ok=True, message="Volume do sistema diminuído.")

        elif action == "volume_mute":
            _press_media_key(_VK_VOLUME_MUTE)
            return ToolResult(ok=True, message="Mute/Unmute do sistema alterado.")

        return ToolResult(ok=False, message=f"Ação desconhecida: {action}")
