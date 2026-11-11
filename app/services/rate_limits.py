"""Provider retry hints without exposing credentials or raw provider errors to users."""
from __future__ import annotations
import math
import re
import time
from email.utils import parsedate_to_datetime


def is_rate_limit(error: Exception) -> bool:
    text = str(error).lower()
    return getattr(error, "status_code", None) == 429 or any(x in text for x in ("429", "rate_limit", "resource_exhausted"))


def retry_seconds(error: Exception, default: float = 60) -> float:
    headers = getattr(getattr(error, "response", None), "headers", {}) or {}
    delays = []
    raw = headers.get("retry-after") or headers.get("Retry-After")
    if raw:
        try:
            delays.append(float(raw))
        except (TypeError, ValueError):
            try:
                delays.append(parsedate_to_datetime(str(raw)).timestamp() - time.time())
            except (ValueError, TypeError, OverflowError):
                pass
    for duration in re.findall(r"(?:try again in|retry in|retryDelay[\"']?\s*:\s*[\"']?)([0-9.hms\s]+)", str(error), re.I):
        parts = re.findall(r"(\d+(?:\.\d+)?)\s*(h|m|s)", duration)
        if parts:
            delays.append(sum(float(n) * {"h": 3600, "m": 60, "s": 1}[unit] for n, unit in parts))
    valid = [d for d in delays if math.isfinite(d) and d > 0]
    return math.ceil(max(valid)) + 1 if valid else default


def limit_reason(error: Exception) -> str:
    text = str(error).lower()
    if "tokens per day" in text or "tpd" in text:
        return "cota diária de tokens"
    if "tokens per minute" in text or "tpm" in text:
        return "limite de tokens por minuto"
    if "requests per day" in text:
        return "cota diária de pedidos"
    return "limite temporário de uso"


class ProviderRateLimit(RuntimeError):
    """Safe message passed intact through the chat error path."""
