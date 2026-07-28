from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


LOG_FILE = Path("data/telemetry.log")


class Telemetry:
    """Logging estruturado simples."""
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    def log(self, event: str, data: dict) -> None:
        """Registra evento."""
        if not self.enabled:
            return
        entry = {
            "ts": datetime.now().isoformat(),
            "event": event,
            "data": data
        }
        try:
            with LOG_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass
    
    def log_tool(self, tool: str, ok: bool, ms: int) -> None:
        """Registra execução de ferramenta."""
        self.log("tool_run", {"tool": tool, "ok": ok, "ms": ms})
