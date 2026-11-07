"""Contracts for safe, observable Jarvis actions.

The action kernel intentionally keeps policy separate from individual tools.  A
tool describes what it can do; this module describes what Jarvis promised to
do, whether it needs consent and what actually happened.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Literal

ActionRisk = Literal["observe", "low", "high", "critical"]
ActionStatus = Literal[
    "proposed", "awaiting_confirmation", "authorized", "running",
    "succeeded", "failed", "cancelled", "expired", "interrupted",
]

RISKS: frozenset[str] = frozenset({"observe", "low", "high", "critical"})
STATUSES: frozenset[str] = frozenset({
    "proposed", "awaiting_confirmation", "authorized", "running",
    "succeeded", "failed", "cancelled", "expired", "interrupted",
})
TERMINAL_STATUSES: frozenset[str] = frozenset({"succeeded", "failed", "cancelled", "expired", "interrupted"})
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "proposed": frozenset({"awaiting_confirmation", "authorized", "running", "cancelled", "expired"}),
    "awaiting_confirmation": frozenset({"authorized", "cancelled", "expired"}),
    "authorized": frozenset({"running", "cancelled", "expired"}),
    "running": frozenset({"succeeded", "failed", "interrupted"}),
}

_SENSITIVE_KEY = re.compile(r"(?:token|secret|password|authorization|api[_-]?key|audio|transcript|prompt|code|script)", re.I)
_CREDENTIAL_TEXT = re.compile(r'''((?:api[_-]?key|token|secret|password|authorization)\s*[=:]\s*)(?:"[^"]*"|'[^']*'|[^\s,;]+)|\bBearer\s+[^\s,;]+''', re.I)


def redact(value: Any, *, limit: int = 240) -> Any:
    """Return a small, journal-safe representation without credential bodies."""
    if isinstance(value, dict):
        return {str(key)[:80]: "[redacted]" if _SENSITIVE_KEY.search(str(key)) else redact(item, limit=limit)
                for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item, limit=limit) for item in value[:20]]
    if isinstance(value, str):
        return _CREDENTIAL_TEXT.sub(lambda match: (match.group(1) or "") + "[redacted]", value).replace("\n", " ")[:limit]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:limit]


def summarize_result(message: str, arguments: dict[str, Any]) -> str:
    """Hide known sensitive argument values before persisting a short outcome."""
    def scrub(value: Any, sensitive: bool = False) -> None:
        nonlocal message
        if isinstance(value, dict):
            for key, item in value.items():
                scrub(item, sensitive or bool(_SENSITIVE_KEY.search(str(key))))
        elif isinstance(value, (list, tuple)):
            for item in value:
                scrub(item, sensitive)
        elif sensitive and isinstance(value, str) and value:
            message = message.replace(value, "[redacted]")
    scrub(arguments)
    return redact(message, limit=500)


def arguments_digest(arguments: dict[str, Any]) -> str:
    normalized = json.dumps(arguments or {}, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class PendingActionBroker:
    """Short-lived in-memory callbacks for user-approved actions.

    The action journal deliberately stores only a digest. Raw arguments and
    executor closures never reach disk; they disappear on restart or expiry.
    """
    def __init__(self, ttl_seconds: int = 600) -> None:
        self.ttl_seconds = ttl_seconds
        self._items: dict[str, tuple[float, Callable[[], str]]] = {}
        self._lock = threading.Lock()

    def register(self, action_id: str, callback: Callable[[], str]) -> None:
        with self._lock:
            now = time.monotonic()
            self._items = {key: item for key, item in self._items.items() if item[0] >= now}
            self._items[action_id] = (now + self.ttl_seconds, callback)

    def take(self, action_id: str) -> Callable[[], str] | None:
        with self._lock:
            item = self._items.pop(action_id, None)
        if item is None or item[0] < time.monotonic():
            return None
        return item[1]

    def discard(self, action_id: str) -> None:
        with self._lock:
            self._items.pop(action_id, None)


pending_action_broker = PendingActionBroker()


@dataclass(frozen=True, slots=True)
class ToolMetadata:
    capabilities: tuple[str, ...] = ("general",)
    default_risk: ActionRisk = "low"
    reversible: bool = False

    requires_confirmation: bool = False

    def __post_init__(self) -> None:
        if self.default_risk not in RISKS:
            raise ValueError(f"Risco de ferramenta inválido: {self.default_risk}")


@dataclass(slots=True)
class ActionRecord:
    id: str
    source: str
    tool_name: str
    capability: str
    arguments_digest: str
    risk: ActionRisk
    preview: str
    status: ActionStatus
    created_at: float
    updated_at: float
    correlation_id: str
    receipt_reference: str | None = None
    result_summary: str | None = None
    undo_payload: dict[str, Any] | None = None
    reversible: bool = False
    run_id: str | None = None

    @classmethod
    def create(cls, *, source: str, tool_name: str, metadata: ToolMetadata, arguments: dict[str, Any], preview: str) -> "ActionRecord":
        now = time.time()
        status: ActionStatus = "awaiting_confirmation" if metadata.requires_confirmation or metadata.default_risk in {"high", "critical"} else "proposed"
        return cls(
            id=f"act_{uuid.uuid4().hex}", source=source[:80], tool_name=tool_name[:120],
            capability=(metadata.capabilities[0] if metadata.capabilities else "general")[:80],
            arguments_digest=arguments_digest(arguments), risk=metadata.default_risk,
            preview=redact(preview, limit=500), status=status, created_at=now, updated_at=now,
            correlation_id=uuid.uuid4().hex, reversible=metadata.reversible,
        )

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ActionRecord":
        if value.get("risk") not in RISKS or value.get("status") not in STATUSES:
            raise ValueError("Registro de ação inválido.")
        return cls(**{key: value[key] for key in cls.__dataclass_fields__ if key in value})

    def public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["undo_available"] = bool(self.reversible and self.status == "succeeded" and self.undo_payload)
        data.pop("undo_payload", None)
        data.pop("receipt_reference", None)
        return redact(data)
