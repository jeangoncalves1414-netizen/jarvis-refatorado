from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any, List, Dict

DATA_DIR = os.path.join(os.getcwd(), "data")
LOGS_FILE = os.path.join(DATA_DIR, "logs.jsonl")
os.makedirs(DATA_DIR, exist_ok=True)

class StructuredLogger:
    def __init__(self, max_in_memory: int = 200) -> None:
        self.max_in_memory = max_in_memory
        self.memory_logs: List[Dict[str, Any]] = []
        self._seq = 0

        # Telemetria acumulada
        self.metrics = {
            "total_requests": 0,
            "total_errors": 0,
            "tools_executed": {},
            "start_time": time.time()
        }

    def log(self, level: str, component: str, message: str, data: Dict[str, Any] | None = None) -> Dict[str, Any]:
        self._seq += 1
        entry = {
            "id": f"log-{self._seq}-{int(time.time()*1000)}",
            "timestamp": datetime.now().isoformat(),
            "level": level.upper(),
            "component": component,
            "message": message,
            "data": data or {}
        }
        
        self.memory_logs.append(entry)
        if len(self.memory_logs) > self.max_in_memory:
            self.memory_logs.pop(0)

        # Append to jsonl
        try:
            with open(LOGS_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

        return entry

    def info(self, component: str, message: str, data: Dict[str, Any] | None = None) -> Dict[str, Any]:
        return self.log("INFO", component, message, data)

    def warn(self, component: str, message: str, data: Dict[str, Any] | None = None) -> Dict[str, Any]:
        return self.log("WARN", component, message, data)

    def error(self, component: str, message: str, data: Dict[str, Any] | None = None) -> Dict[str, Any]:
        self.metrics["total_errors"] += 1
        return self.log("ERROR", component, message, data)

    def record_request(self) -> None:
        self.metrics["total_requests"] += 1

    def record_tool_execution(self, tool_name: str) -> None:
        tools = self.metrics["tools_executed"]
        tools[tool_name] = tools.get(tool_name, 0) + 1

    def get_logs(self, level: str | None = None, limit: int = 100) -> List[Dict[str, Any]]:
        logs = self.memory_logs
        if level:
            logs = [l for l in logs if l.get("level") == level.upper()]
        return logs[-limit:]

    def get_metrics_summary(self) -> Dict[str, Any]:
        uptime_seconds = int(time.time() - self.metrics["start_time"])
        return {
            "total_requests": self.metrics["total_requests"],
            "total_errors": self.metrics["total_errors"],
            "tools_executed": self.metrics["tools_executed"],
            "uptime_seconds": uptime_seconds
        }

logger = StructuredLogger()
