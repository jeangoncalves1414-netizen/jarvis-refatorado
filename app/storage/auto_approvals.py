"""Aprovações automáticas do Action Kernel: regras com escopo e duração, e o Modo liberado.

As regras ficam em ``data/auto_approvals.json`` (locais; não sincronizam com a nuvem). O Modo
liberado aprova tudo sem perguntar, inclusive risco alto e crítico. Ele nasce desligado a cada
início do backend, a menos que a usuária tenha escolhido mantê-lo (``persist``).
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from collections import OrderedDict
from typing import Any

DATA_DIR = os.path.join(os.getcwd(), "data")
APPROVALS_FILE = os.path.join(DATA_DIR, "auto_approvals.json")

# Duração -> segundos (None = sem validade). "now" vale por alguns minutos.
DURATIONS: dict[str, int | None] = {"now": 10 * 60, "today": None, "30d": 30 * 86400, "always": None}
DURATION_LABELS = {"now": "Só agora (10 min)", "today": "Hoje", "30d": "30 dias", "always": "Sempre"}
_MAX_PENDING_SCOPES = 300


def _expiry(duration: str, now: float) -> float | None:
    if duration == "today":
        local = time.localtime(now)
        return time.mktime((local.tm_year, local.tm_mon, local.tm_mday, 23, 59, 59, 0, 0, -1))
    seconds = DURATIONS[duration]
    return now + seconds if seconds else None


class AutoApprovalStore:
    def __init__(self, path: str | None = None) -> None:
        self.path = path or APPROVALS_FILE
        self._lock = threading.RLock()
        self._pending: OrderedDict[str, tuple[str, str, str]] = OrderedDict()
        data = self._read()
        self._liberated = bool(data.get("liberated") and data.get("persist"))

    # ── arquivo ─────────────────────────────────────────────────────────────
    def _read(self) -> dict[str, Any]:
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _write(self, data: dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = f"{self.path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    # ── escopo das propostas pendentes ──────────────────────────────────────
    def remember_scope(self, action_id: str, tool: str, operation: str, target: str) -> None:
        with self._lock:
            self._pending[action_id] = (tool, operation, target)
            while len(self._pending) > _MAX_PENDING_SCOPES:
                self._pending.popitem(last=False)

    def scope_of(self, action_id: str) -> tuple[str, str, str] | None:
        with self._lock:
            return self._pending.get(action_id)

    # ── regras ──────────────────────────────────────────────────────────────
    @staticmethod
    def _label(tool: str, operation: str, target: str) -> str:
        return " ".join(part for part in (tool, operation, target) if part)

    @staticmethod
    def _active(rule: dict[str, Any], now: float) -> bool:
        return not rule.get("revoked") and (rule.get("expires_at") is None or rule["expires_at"] > now)

    def list_rules(self, *, include_inactive: bool = False) -> list[dict[str, Any]]:
        now = time.time()
        with self._lock:
            rules = self._read().get("rules", [])
        result = []
        for rule in rules:
            active = self._active(rule, now)
            if active or include_inactive:
                result.append({**rule, "active": active})
        return result

    def add_rule(self, tool: str, operation: str, target: str, duration: str, *, origin: str = "manual") -> dict[str, Any]:
        tool, operation, target = tool.strip()[:120], operation.strip().lower()[:80], target.strip()[:200]
        if not tool:
            raise ValueError("Informe a ferramenta da regra.")
        if duration not in DURATIONS:
            raise ValueError("Duração inválida.")
        now = time.time()
        rule = {
            "id": f"apr_{uuid.uuid4().hex[:12]}", "tool": tool, "operation": operation, "target": target,
            "label": self._label(tool, operation, target), "duration": duration,
            "created_at": now, "expires_at": _expiry(duration, now), "uses": 0,
            "last_used_at": None, "revoked": False, "origin": origin[:40],
        }
        with self._lock:
            data = self._read()
            data["rules"] = [*data.get("rules", [])[-199:], rule]
            self._write(data)
        return {**rule, "active": True}

    def update_rule(self, rule_id: str, duration: str) -> dict[str, Any]:
        if duration not in DURATIONS:
            raise ValueError("Duração inválida.")
        now = time.time()
        with self._lock:
            data = self._read()
            for rule in data.get("rules", []):
                if rule.get("id") == rule_id and not rule.get("revoked"):
                    rule["duration"], rule["expires_at"] = duration, _expiry(duration, now)
                    self._write(data)
                    return {**rule, "active": self._active(rule, now)}
        raise KeyError(rule_id)

    def revoke_rule(self, rule_id: str) -> bool:
        with self._lock:
            data = self._read()
            for rule in data.get("rules", []):
                if rule.get("id") == rule_id and not rule.get("revoked"):
                    rule["revoked"] = True
                    self._write(data)
                    return True
        return False

    def match(self, tool: str, operation: str, target: str) -> dict[str, Any] | None:
        """Regra ativa que cobre a chamada; conta o uso. Operação/alvo vazios na regra valem para qualquer um."""
        now = time.time()
        operation, target = operation.strip().lower(), target.strip().lower()
        with self._lock:
            data = self._read()
            for rule in data.get("rules", []):
                if rule.get("tool") != tool or not self._active(rule, now):
                    continue
                if rule.get("operation") and rule["operation"] != operation:
                    continue
                if rule.get("target") and rule["target"].lower() != target:
                    continue
                rule["uses"] = int(rule.get("uses", 0)) + 1
                rule["last_used_at"] = now
                self._write(data)
                return dict(rule)
        return None

    # ── Modo liberado ───────────────────────────────────────────────────────
    def mode(self) -> dict[str, Any]:
        with self._lock:
            return {"enabled": self._liberated, "persist": bool(self._read().get("persist"))}

    def set_mode(self, enabled: bool, persist: bool | None = None) -> dict[str, Any]:
        with self._lock:
            data = self._read()
            if persist is not None:
                data["persist"] = bool(persist)
            data["liberated"] = bool(enabled)
            self._liberated = bool(enabled)
            self._write(data)
        return self.mode()

    def liberated(self) -> bool:
        return self._liberated


auto_approvals = AutoApprovalStore()
