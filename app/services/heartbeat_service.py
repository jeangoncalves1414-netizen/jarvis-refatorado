"""
Heartbeat Health Service — inspirado no Ada-SI
Loop em segundo plano que inspeciona a integridade das ferramentas nativas e subsistemas.
"""
from __future__ import annotations

import shutil
import time
from typing import Any


class HeartbeatHealthService:
    """Monitor de saúde de subsistemas e ferramentas nativas."""

    @staticmethod
    def check_health() -> dict[str, Any]:
        """Realiza diagnóstico em tempo real dos binários e dependências essenciais."""
        status = {
            "adb": shutil.which("adb") is not None,
            "git": shutil.which("git") is not None,
            "cloudflared": shutil.which("cloudflared") is not None,
            "python": shutil.which("python") is not None,
            "timestamp": time.time(),
        }
        all_ok = status["git"] and status["python"]
        return {
            "ok": all_ok,
            "services": status,
            "message": "Todos os subsistemas críticos operacionais." if all_ok else "Atenção: algumas ferramentas externas estão indisponíveis.",
        }
