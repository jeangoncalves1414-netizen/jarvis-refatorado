"""Study panel API: unified dashboard, statistics and Pomodoro XP."""
from __future__ import annotations

import json
from typing import Any

from app.storage.study_stats import build_dashboard, build_stats
from app.storage.study_xp import POMODORO_MAX_MINUTES, POMODORO_MIN_MINUTES, XP_POMODORO, level_for


def _stores(handler: Any) -> tuple[Any | None, Any | None]:
    orch = getattr(handler, "orchestrator", None)
    if orch is None:
        orch = getattr(type(handler), "orchestrator", None)
    if orch is None:
        try:
            from app.ui.panel.server import _orchestrator
            orch = _orchestrator
        except ImportError:
            pass
    if not orch:
        return None, None
    return getattr(orch, "tutor_store", None), getattr(orch, "language_store", None)


def handle_study_get(parts: list[str], handler: Any) -> tuple[int, dict[str, Any]] | None:
    """Routes: /api/study/dashboard, /api/study/stats (other /api/study/* are served by server.py)."""
    if parts not in (["api", "study", "dashboard"], ["api", "study", "stats"]):
        return None
    tutor, language = _stores(handler)
    if not tutor or not language:
        return 503, {"ok": False, "error": "study_store_unavailable"}
    if parts[2] == "dashboard":
        return 200, build_dashboard(tutor, language)
    return 200, build_stats(tutor, language)


def handle_study_post(path: str, body: bytes, handler: Any) -> tuple[int, dict[str, Any]] | None:
    if path != "/api/study/pomodoro":
        return None
    tutor, _ = _stores(handler)
    if not tutor:
        return 503, {"ok": False, "error": "study_store_unavailable"}
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except Exception:
        payload = {}
    minutes = payload.get("minutes") if isinstance(payload, dict) else None
    if (
        isinstance(minutes, bool)
        or not isinstance(minutes, int)
        or not POMODORO_MIN_MINUTES <= minutes <= POMODORO_MAX_MINUTES
    ):
        return 400, {"ok": False, "error": "invalid_minutes"}
    tutor.xp.add(XP_POMODORO, "pomodoro")
    tutor.xp.count_pomodoro()
    summary = tutor.xp.summary()
    return 200, {"ok": True, "xp": summary, "level": level_for(summary["total_xp"])}
