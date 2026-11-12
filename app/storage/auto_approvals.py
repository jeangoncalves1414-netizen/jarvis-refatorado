"""Aprovações automáticas do Action Kernel: regras com escopo e duração, e o Modo liberado.

As regras ficam em ``data/auto_approvals.json`` (locais; não sincronizam com a nuvem). O Modo
liberado aprova tudo sem perguntar, inclusive risco alto e crítico. Ele nasce desligado a cada
início do backend, a menos que a usuária tenha escolhido mantê-lo (``persist``). Ao ligar, a
validade é opcional (1 hora, hoje ou até desligar); o padrão é até desligar.

Regras para ações de risco alto ou crítico não podem ficar largas: a regra de uma ação crítica
(ex.: ``script_runner``) vale só para os argumentos exatos aprovados (digest), e a de uma ação
alta sem alvo (ex.: ``phantom_typer``) também, a menos que a usuária confirme que vale para qualquer alvo.
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
# Validade do Modo liberado ao ligar. "forever" = até desligar (comportamento anterior).
LIBERATED_VALIDITIES: dict[str, int | None] = {"forever": None, "1h": 3600, "today": None}
LIBERATED_VALIDITY_LABELS = {"forever": "Até desligar", "1h": "1 hora", "today": "Hoje"}
_MAX_PENDING_SCOPES = 300


CATEGORIES = {
    "commands": "Comandos e scripts", "changes": "Criação e edição",
    "remove": "Remoção de itens", "bulk": "Remoção em lote",
    "external": "Ações externas e integrações", "other": "Outras ações",
}


def approval_category(tool: str, operation: str) -> str:
    if operation in {"delete_many", "bulk_delete", "bulk_confirm", "clear", "wipe", "purge_all"} or tool == "whiteboard_clear":
        return "bulk"
    if operation.startswith(("delete", "remove", "forget", "purge", "trash")):
        return "remove"
    if tool in {"script_runner", "system_control", "hacker_mode", "mobile_adb", "phantom_typer", "open_windows_app", "terminal"}:
        return "commands"
    if tool.startswith("mcp_") or tool in {"whatsapp", "telegram_bot", "home", "kasa_control", "browser", "browser_agent", "browser_tool", "wormhole", "spotify", "notification"}:
        return "external"
    if tool in {"personal_records", "memory", "memory_tool", "habit_tool", "task_tool", "checklist_tool", "finance_tool", "calendar", "file_manager", "routine", "lifeos_tool"} or tool.startswith(("vault_", "whiteboard_", "tutor_", "language_")):
        return "changes"
    return "other"


def _end_of_day(now: float) -> float:
    local = time.localtime(now)
    return time.mktime((local.tm_year, local.tm_mon, local.tm_mday, 23, 59, 59, 0, 0, -1))


def _expiry(duration: str, now: float) -> float | None:
    if duration == "today":
        return _end_of_day(now)
    seconds = DURATIONS[duration]
    return now + seconds if seconds else None


def _liberated_until(validity: str, now: float) -> float | None:
    if validity == "today":
        return _end_of_day(now)
    seconds = LIBERATED_VALIDITIES[validity]
    return now + seconds if seconds else None


def needs_exact_arguments(risk: str, target: str) -> bool:
    """Regra criada a partir de uma proposta que precisa ficar amarrada aos argumentos exatos."""
    return risk == "critical" or (risk == "high" and not target.strip())


class AutoApprovalStore:
    def __init__(self, path: str | None = None) -> None:
        self.path = path or APPROVALS_FILE
        self._lock = threading.RLock()
        self._pending: OrderedDict[str, tuple[str, str, str, str, str]] = OrderedDict()
        data = self._read()
        self._categories = {key: data.get("categories", {}).get(key, True) for key in CATEGORIES}
        self._until: float | None = None
        self._liberated = bool(data.get("liberated") and data.get("persist"))
        if self._liberated:
            until = data.get("liberated_until")
            self._until = float(until) if isinstance(until, (int, float)) else None
            if self._until is not None and self._until <= time.time():
                self._liberated, self._until = False, None

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
    def remember_scope(self, action_id: str, tool: str, operation: str, target: str, risk: str = "", digest: str = "") -> None:
        with self._lock:
            self._pending[action_id] = (tool, operation, target, risk, digest)
            while len(self._pending) > _MAX_PENDING_SCOPES:
                self._pending.popitem(last=False)

    def scope_of(self, action_id: str) -> tuple[str, str, str] | None:
        with self._lock:
            scope = self._pending.get(action_id)
        return scope[:3] if scope else None

    def scope_detail(self, action_id: str) -> dict[str, str] | None:
        """Escopo completo da proposta: ferramenta, operação, alvo, risco e digest dos argumentos."""
        with self._lock:
            scope = self._pending.get(action_id)
        if scope is None:
            return None
        return dict(zip(("tool", "operation", "target", "risk", "digest"), scope))

    # ── regras ──────────────────────────────────────────────────────────────
    @staticmethod
    def _label(tool: str, operation: str, target: str, digest: str = "") -> str:
        label = " ".join(part for part in (tool, operation, target) if part)
        return f"{label} (argumentos exatos)" if digest else label

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

    def add_rule(
        self, tool: str, operation: str, target: str, duration: str, *,
        origin: str = "manual", risk: str = "low", digest: str = "", broad: bool = False,
    ) -> dict[str, Any]:
        tool, operation, target = tool.strip()[:120], operation.strip().lower()[:80], target.strip()[:200]
        digest = digest.strip()[:128]
        if not tool:
            raise ValueError("Informe a ferramenta da regra.")
        if duration not in DURATIONS:
            raise ValueError("Duração inválida.")
        if risk == "critical" and not digest:
            raise ValueError("Ações críticas só ganham regra amarrada aos argumentos exatos: use “Permitir e autorizar” numa proposta pendente.")
        if risk == "high" and not target and not digest and not broad:
            raise ValueError("Esta ferramenta é de risco alto e a regra não tem alvo. Informe o alvo ou confirme que a regra vale para qualquer alvo.")
        now = time.time()
        rule = {
            "id": f"apr_{uuid.uuid4().hex[:12]}", "tool": tool, "operation": operation, "target": target,
            "label": self._label(tool, operation, target, digest), "duration": duration,
            "created_at": now, "expires_at": _expiry(duration, now), "uses": 0,
            "last_used_at": None, "revoked": False, "origin": origin[:40],
            "risk": risk[:20], "digest": digest, "broad": bool(broad and not digest),
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

    def match(self, tool: str, operation: str, target: str, *, risk: str = "low", digest: str = "") -> dict[str, Any] | None:
        """Regra ativa que cobre a chamada; conta o uso. Operação/alvo vazios na regra valem para qualquer um.

        Regra com digest só vale para os mesmos argumentos. Chamada crítica exige regra com digest, e
        chamada alta sem alvo exige digest ou regra confirmada como ampla (regras antigas ficam de fora).
        """
        now = time.time()
        operation, target = operation.strip().lower(), target.strip().lower()
        with self._lock:
            data = self._read()
            for rule in data.get("rules", []):
                if rule.get("tool") != tool or not self._active(rule, now):
                    continue
                rule_digest = rule.get("digest") or ""
                if rule_digest and rule_digest != digest:
                    continue
                if risk == "critical" and not rule_digest:
                    continue
                if risk == "high" and not target and not rule_digest and not rule.get("broad"):
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
    def categories(self) -> dict[str, bool]:
        with self._lock:
            return self._categories.copy()

    def allows(self, category: str) -> bool:
        with self._lock:
            return self.liberated() and self._categories.get(category, False)

    def mode(self) -> dict[str, Any]:
        enabled = self.liberated()
        with self._lock:
            return {
                "enabled": enabled, "persist": bool(self._read().get("persist")),
                "until": self._until if enabled else None,
            }

    def set_mode(self, enabled: bool, persist: bool | None = None, validity: str | None = None, categories: dict | None = None) -> dict[str, Any]:
        if validity is not None and validity not in LIBERATED_VALIDITIES:
            raise ValueError("Validade inválida.")
        with self._lock:
            data = self._read()
            if categories is not None:
                if not isinstance(categories, dict) or any(k not in CATEGORIES or type(v) is not bool for k, v in categories.items()):
                    raise ValueError("Categorias de aprovação inválidas.")
                self._categories.update(categories)
                data["categories"] = self.categories()
            if persist is not None:
                data["persist"] = bool(persist)
            was_on = self.liberated()
            if not enabled:
                self._until = None
            elif validity is not None:
                self._until = _liberated_until(validity, time.time())
            elif not was_on:
                self._until = None  # sem escolha ao ligar: até desligar, como sempre foi
            data["liberated"] = bool(enabled)
            data["liberated_until"] = self._until
            self._liberated = bool(enabled)
            self._write(data)
        return self.mode()

    def liberated(self) -> bool:
        with self._lock:
            if self._liberated and self._until is not None and time.time() >= self._until:
                data = self._read()
                self._liberated, self._until = False, None
                data["liberated"], data["liberated_until"] = False, None
                self._write(data)
            return self._liberated


auto_approvals = AutoApprovalStore()
