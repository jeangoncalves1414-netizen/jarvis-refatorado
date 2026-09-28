"""Short-lived, single-use approvals for privileged local execution."""
from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass

from app.core.diagnostics import record


@dataclass
class _Receipt:
    principal: str
    action: str
    digest: str
    expires_at: float


class ExecutionReceipts:
    def __init__(self, ttl_seconds: int = 120) -> None:
        self.ttl_seconds = ttl_seconds
        self._items: dict[str, _Receipt] = {}

    @staticmethod
    def digest(value: str) -> str:
        return hashlib.sha256(value.strip().encode("utf-8")).hexdigest()

    def issue(self, principal: str, action: str, value: str) -> str:
        receipt = secrets.token_urlsafe(32)
        self._items[receipt] = _Receipt(principal, action, self.digest(value), time.time() + self.ttl_seconds)
        record("execution", "receipt_issued", correlation_id=secrets.token_hex(8), action=action)
        return receipt

    def consume(self, receipt: str, principal: str, action: str, value: str) -> bool:
        item = self._items.pop(receipt, None)
        valid = bool(item and item.expires_at >= time.time() and item.principal == principal and item.action == action and item.digest == self.digest(value))
        record("execution", "receipt_consumed" if valid else "receipt_denied", correlation_id=secrets.token_hex(8), action=action)
        return valid


receipts = ExecutionReceipts()
