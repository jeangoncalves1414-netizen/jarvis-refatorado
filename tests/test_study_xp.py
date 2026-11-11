"""Unified study XP, streak, levels and badges (StudyXP on temp dirs)."""
from __future__ import annotations

from datetime import date, timedelta

from app.storage.study_xp import StudyXP, badges, get_study_xp, level_for

DAY = date(2026, 3, 10)


def _day(offset: int) -> date:
    return DAY + timedelta(days=offset)


def test_add_accumulates_total_and_daily(tmp_path) -> None:
    xp = StudyXP(tmp_path / "study")
    assert xp.add(10, "tutor", _day(0)) == 10
    assert xp.add(15, "language", _day(0)) == 25
    summary = xp.summary(_day(0))
    assert summary["total_xp"] == 25
    assert summary["daily_xp"] == 25
    assert summary["studied_today"] is True


def test_daily_xp_resets_next_day_without_writes(tmp_path) -> None:
    xp = StudyXP(tmp_path / "study")
    xp.add(30, "tutor", _day(0))
    mtime = xp.path.stat().st_mtime_ns
    summary = xp.summary(_day(1))
    assert summary["daily_xp"] == 0
    assert summary["total_xp"] == 30
    assert summary["studied_today"] is False
    assert xp.path.stat().st_mtime_ns == mtime


def test_goal_met(tmp_path) -> None:
    xp = StudyXP(tmp_path / "study")
    xp.add(90, "tutor", _day(0))
    assert xp.summary(_day(0))["goal_met"] is False
    xp.add(10, "tutor", _day(0))
    assert xp.summary(_day(0))["goal_met"] is True


def test_streak_rules(tmp_path) -> None:
    xp = StudyXP(tmp_path / "study")
    for offset in range(3):
        xp.add(10, "tutor", _day(offset))
    assert xp.summary(_day(2))["streak"] == 3
    # today inactive: the streak continues from yesterday
    assert xp.summary(_day(3))["streak"] == 3
    # missed a whole day: streak broken
    assert xp.summary(_day(4))["streak"] == 0
    xp.add(10, "tutor", _day(5))
    summary = xp.summary(_day(5))
    assert summary["streak"] == 1
    assert summary["best_streak"] == 3


def test_revoke_lowers_daily_and_can_break_today(tmp_path) -> None:
    xp = StudyXP(tmp_path / "study")
    xp.add(10, "tutor", _day(0))
    xp.add(10, "tutor", _day(1))
    assert xp.summary(_day(1))["streak"] == 2
    xp.revoke(10, _day(1))
    summary = xp.summary(_day(1))
    assert summary["daily_xp"] == 0
    assert summary["studied_today"] is False
    assert summary["streak"] == 1  # continues from yesterday
    assert summary["total_xp"] == 10
    xp.revoke(50, _day(0))
    assert xp.summary(_day(1))["total_xp"] == 0


def test_set_daily_goal_clamped(tmp_path) -> None:
    xp = StudyXP(tmp_path / "study")
    assert xp.set_daily_goal(5) == 10
    assert xp.set_daily_goal(900) == 500
    assert xp.summary()["daily_goal"] == 500


def test_import_legacy_merges_and_is_idempotent(tmp_path) -> None:
    xp = StudyXP(tmp_path / "study")
    xp.import_legacy("tutor", total_xp=120, daily_xp=20, last_study_date=str(_day(-5)), streak_count=4, daily_goal=100)
    xp.import_legacy("language", total_xp=80, daily_xp=30, last_study_date=str(_day(0)), streak_count=2, daily_goal=50)
    summary = xp.summary(_day(0))
    assert summary["total_xp"] == 200
    assert summary["daily_xp"] == 30
    assert xp.daily_totals()[str(_day(-5))] == 20
    assert summary["daily_goal"] == 100
    # most recent legacy streak (language: 2 days ending today) wins
    assert summary["streak"] == 2
    assert summary["best_streak"] == 2
    assert not xp.path.exists()

    xp.add(10, "tutor", _day(0))
    assert xp.path.exists()

    again = StudyXP(tmp_path / "study")
    again.import_legacy("tutor", total_xp=120, daily_xp=20, last_study_date=str(_day(-5)), streak_count=4, daily_goal=100)
    again.import_legacy("language", total_xp=80, daily_xp=30, last_study_date=str(_day(0)), streak_count=2, daily_goal=50)
    assert again.summary(_day(0))["total_xp"] == 210


def test_construction_and_reads_do_not_write(tmp_path) -> None:
    directory = tmp_path / "study"
    xp = StudyXP(directory)
    xp.summary()
    xp.daily_totals()
    xp.import_legacy("tutor", total_xp=10)
    assert not directory.exists()


def test_level_thresholds_and_names() -> None:
    assert level_for(0)["level"] == 1 and level_for(0)["name"] == "Iniciante"
    assert level_for(99)["level"] == 1
    level_two = level_for(100)
    assert level_two["level"] == 2 and level_two["name"] == "Aprendiz"
    assert level_two["xp_into_level"] == 0 and level_two["xp_for_next"] == 200
    assert level_two["next_threshold"] == 300
    assert level_for(300)["level"] == 3 and level_for(300)["name"] == "Estudante"
    assert level_for(4500)["name"] == "Lenda"
    assert level_for(5500)["name"] == "Lenda 2"


def test_badges_earned_flags() -> None:
    result = {b["id"]: b["earned"] for b in badges(1, 7, 1000, 9, 50)}
    assert result == {
        "first_review": True,
        "reviews_100": False,
        "streak_7": True,
        "streak_30": False,
        "xp_1000": True,
        "pomodoro_10": False,
        "vocab_50": True,
    }
    assert all(b["label"] and b["description"] for b in badges(0, 0, 0, 0, 0))


def test_count_pomodoro(tmp_path) -> None:
    xp = StudyXP(tmp_path / "study")
    xp.count_pomodoro()
    xp.count_pomodoro()
    assert xp.summary()["pomodoros"] == 2


def test_get_study_xp_caches_per_path(tmp_path) -> None:
    first = get_study_xp(tmp_path / "study")
    assert get_study_xp(str(tmp_path / "study")) is first
    assert get_study_xp(tmp_path / "other") is not first
