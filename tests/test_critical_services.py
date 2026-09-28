"""
Unit tests for critical services that were previously untested:
1. identity.py (IdentityService)
2. calendar.py (CalendarService)
3. oxyy.py (infer_capability)
4. notifications.py (WindowsNotification)
5. autotune.py (AutoTuneSamplingEngine)
6. smart_folder_watchdog.py (SmartFolderWatchdog)
7. recovery_engine.py (RecoveryEngine)
"""
import os
import pytest
from app.services.identity import IdentityService
from app.services.calendar import CalendarService
from app.services.oxyy import infer_capability, _FALLBACK_MODELS
from app.services.notifications import WindowsNotification
from app.services.autotune import AutoTuneSamplingEngine
from app.services.smart_folder_watchdog import SmartFolderWatchdog
from app.services.recovery_engine import RecoveryEngine


# ── 1. IdentityService ───────────────────────────────────────────────────────

def test_identity_service():
    identity = IdentityService()
    assert identity is not None
    st = identity.status()
    assert isinstance(st, dict)


# ── 2. CalendarService ───────────────────────────────────────────────────────

def test_calendar_service():
    cal = CalendarService()
    events = cal.get_today_events()
    assert isinstance(events, list)


# ── 3. Oxyy Service ──────────────────────────────────────────────────────────

def test_oxyy_capability_inference():
    for item in _FALLBACK_MODELS:
        cap = infer_capability(item)
        assert cap in ("chat", "image", "video", "tts", "stt", "embedding")


# ── 4. WindowsNotification ───────────────────────────────────────────────────

def test_windows_notification():
    notif = WindowsNotification()
    res = notif.show("Jarvis Test", "Notificação de teste unitário")
    assert isinstance(res, bool)


# ── 5. AutoTuneSamplingEngine ────────────────────────────────────────────────

def test_autotune_engine():
    engine = AutoTuneSamplingEngine()
    params = engine.get_params("code")
    assert isinstance(params, dict)


# ── 6. SmartFolderWatchdog ───────────────────────────────────────────────────

def test_smart_folder_watchdog():
    watchdog = SmartFolderWatchdog()
    assert hasattr(watchdog, "CATEGORIES")
    assert isinstance(watchdog.CATEGORIES, dict)


# ── 7. RecoveryEngine ────────────────────────────────────────────────────────

def test_recovery_engine():
    rec = RecoveryEngine()
    dummy_fn = lambda: "OK"
    res = rec.execute_with_recovery("test_task", dummy_fn)
    assert isinstance(res, dict)
    assert res.get("result") == "OK"
