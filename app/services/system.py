from __future__ import annotations

from typing import Any

class SystemMetrics:
    @staticmethod
    def get_metrics() -> dict[str, Any]:
        """
        Retorna o consumo real de CPU e RAM do sistema do usuário.
        """
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory()
            
            ram_used_gb = ram.used / (1024 ** 3)
            ram_total_gb = ram.total / (1024 ** 3)
            ram_percent = ram.percent
            
            return {
                "cpu": cpu_percent,
                "ram_used": round(ram_used_gb, 2),
                "ram_total": round(ram_total_gb, 2),
                "ram_percent": ram_percent,
                "status": "online"
            }
        except Exception as e:
            # Fallback seguro caso psutil falhe ou não esteja disponível
            return {
                "cpu": 5.0,
                "ram_used": 4.2,
                "ram_total": 16.0,
                "ram_percent": 26.0,
                "status": "fallback"
            }
