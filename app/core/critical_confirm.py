from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path


CONFIRM_FILE = Path("data/critical_confirm.json")


class CriticalConfirm:
    """Sistema de confirmação para ações críticas."""
    
    def __init__(self, enabled: bool = True):
        self.enabled = self._load_pref(enabled)
        self._lock = threading.Lock()
        self._pending: dict | None = None
        self._done = threading.Event()
        self._approved = False
    
    def _load_pref(self, default: bool) -> bool:
        if not CONFIRM_FILE.exists():
            return default
        try:
            data = json.loads(CONFIRM_FILE.read_text())
            return data.get("enabled", default)
        except Exception:
            return default
    
    def save_pref(self, enabled: bool) -> None:
        CONFIRM_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIRM_FILE.write_text(json.dumps({"enabled": enabled}))
        self.enabled = enabled
    
    def request(self, tool: str, detail: str = "") -> bool:
        """Solicita confirmação para ação crítica."""
        if not self.enabled:
            return True
        
        req_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._pending = {"id": req_id, "tool": tool, "detail": detail}
            self._approved = False
            self._done.clear()
        
        print(f"\n[CONFIRMAÇÃO] {detail or f'Executar {tool}?'}")
        print("Confirme no painel ou diga 'confirmar'/'cancelar'")
        
        if self._done.wait(timeout=300):
            with self._lock:
                return self._approved
        return False
    
    def resolve(self, req_id: str, approved: bool) -> bool:
        """Resolve confirmação pendente."""
        with self._lock:
            if not self._pending or self._pending["id"] != req_id:
                return False
            self._approved = approved
            self._pending = None
        self._done.set()
        return True
    
    def get_pending(self) -> dict | None:
        """Retorna requisição pendente."""
        with self._lock:
            return dict(self._pending) if self._pending else None
