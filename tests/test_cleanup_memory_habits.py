"""Tests for cleanup_memory_habits.py script (only in tmp_path)."""
import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

import pytest


# Import the script module
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import cleanup_memory_habits


def test_normalize_name():
    """normalize_name removes accents and normalizes spacing."""
    assert cleanup_memory_habits.normalize_name("Beber 2\u202fL de água") == "beber 2 l de agua"
    assert cleanup_memory_habits.normalize_name("  Múltiplos   Espaços  ") == "multiplos espacos"


def test_scan_user_profile_detects_issues(tmp_path):
    """scan_user_profile finds duplicates and placeholders."""
    vault_dir = tmp_path / "vault" / "02-User-Profile"
    vault_dir.mkdir(parents=True)
    profile = vault_dir / "USER-PROFILE.md"
    profile.write_text(
        "# Perfil\n"
        "Nome**: Usuário\n"
        "Linha duplicada\n"
        "Linha duplicada\n"
        "Testando unittest aqui\n",
        encoding="utf-8"
    )
    
    result = cleanup_memory_habits.scan_user_profile(tmp_path)
    assert result
    assert "issues" in result
    issues = result["issues"]
    assert any("placeholder" in issue.lower() or "usuário" in issue.lower() for issue in issues)
    assert any("duplicada" in issue.lower() for issue in issues)
    assert any("unittest" in issue.lower() or "test" in issue.lower() for issue in issues)


def test_scan_daily_notes_finds_test_notes(tmp_path):
    """scan_daily_notes finds notes with 'Testando integração do Memory Vault'."""
    vault_dir = tmp_path / "vault" / "01-Daily-Notes"
    vault_dir.mkdir(parents=True)
    test_note = vault_dir / "2026-11-11.md"
    test_note.write_text("# 2026-11-11\nTestando integração do Memory Vault", encoding="utf-8")
    clean_note = vault_dir / "2026-11-12.md"
    clean_note.write_text("# 2026-11-12\nConteúdo normal", encoding="utf-8")
    
    result = cleanup_memory_habits.scan_daily_notes(tmp_path)
    assert result
    assert "test_notes" in result
    assert any("2026-11-11" in note for note in result["test_notes"])
    assert not any("2026-11-12" in note for note in result["test_notes"])


def test_scan_duplicate_habits(tmp_path):
    """scan_duplicate_habits finds active habits with same normalized name."""
    db_path = tmp_path / "lifestyle.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE habits (id TEXT PRIMARY KEY, name TEXT, archived INTEGER, created_at REAL)"
    )
    now = datetime.now().timestamp()
    conn.execute("INSERT INTO habits VALUES (?, ?, 0, ?)", ("h1", "Beber água", now - 100))
    conn.execute("INSERT INTO habits VALUES (?, ?, 0, ?)", ("h2", "Beber Água", now - 50))  # Duplicate (newer)
    conn.execute("INSERT INTO habits VALUES (?, ?, 0, ?)", ("h3", "Ler livros", now))
    conn.commit()
    conn.close()
    
    result = cleanup_memory_habits.scan_duplicate_habits(tmp_path)
    assert result
    assert "duplicate_habits" in result
    actions = result["duplicate_habits"]
    # Should want to archive the newer duplicate
    assert len(actions) == 1
    assert actions[0]["id"] == "h2"
    assert actions[0]["action"] == "archive"


def test_scan_morning_logs_after_noon(tmp_path):
    """scan_morning_logs_after_noon finds 'saudação matinal' logs at or after 12h."""
    db_path = tmp_path / "lifestyle.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE habit_logs (id INTEGER PRIMARY KEY, habit_id TEXT, date_str TEXT, "
        "notes TEXT, timestamp REAL)"
    )
    # Valid morning log (7am)
    morning_ts = datetime(2026, 11, 11, 7, 0).timestamp()
    conn.execute("INSERT INTO habit_logs VALUES (1, 'h1', '2026-11-11', 'Auto-check contextual: saudação matinal', ?)", (morning_ts,))
    # Invalid afternoon log (14h)
    afternoon_ts = datetime(2026, 11, 11, 14, 30).timestamp()
    conn.execute("INSERT INTO habit_logs VALUES (2, 'h2', '2026-11-11', 'Auto-check contextual: saudação matinal', ?)", (afternoon_ts,))
    conn.commit()
    conn.close()
    
    result = cleanup_memory_habits.scan_morning_logs_after_noon(tmp_path)
    assert result
    assert "invalid_morning_logs" in result
    invalid = result["invalid_morning_logs"]
    assert len(invalid) == 1
    assert invalid[0]["id"] == 2
    assert invalid[0]["hour"] == 14


def test_apply_cleanup_with_backup(tmp_path):
    """apply_cleanup creates backups and applies changes."""
    # Setup test data
    vault_dir = tmp_path / "vault" / "01-Daily-Notes"
    vault_dir.mkdir(parents=True)
    test_note = vault_dir / "test.md"
    test_note.write_text("Testando integração do Memory Vault", encoding="utf-8")
    
    prefs_file = tmp_path / "preferences.json"
    prefs_file.write_text(json.dumps({"user_name": "Alex", "other": "value"}), encoding="utf-8")
    
    dry_run_results = {
        "daily_notes": {"test_notes": ["vault/01-Daily-Notes/test.md"]},
        "preferences_json": {"smoke_test_data": ["user_name='Alex'"]},
    }
    
    # Apply cleanup
    cleanup_memory_habits.apply_cleanup(tmp_path, dry_run_results)
    
    # Verify backup was created
    backup_dirs = list((tmp_path / "backups").glob("cleanup-*"))
    assert len(backup_dirs) == 1
    backup_dir = backup_dirs[0]
    assert (backup_dir / "test.md").exists()
    assert (backup_dir / "preferences.json").exists()
    
    # Verify changes
    assert not test_note.exists()  # Removed
    prefs_data = json.loads(prefs_file.read_text(encoding="utf-8"))
    assert "user_name" not in prefs_data  # Cleaned
    assert prefs_data["other"] == "value"  # Preserved


def test_main_refuses_real_data_dir(monkeypatch, capsys):
    """main() with --apply refuses to touch real Jarvis data directory."""
    # Simulate a path that looks like the real project data dir
    fake_real = Path("C:/Users/maria/Desktop/Jarvis/data")
    
    monkeypatch.setattr(sys, "argv", ["cleanup_memory_habits.py", "--data-dir", str(fake_real), "--apply"])
    monkeypatch.setattr(Path, "resolve", lambda self: fake_real if self == Path(str(fake_real)) else self)
    monkeypatch.setattr(Path, "exists", lambda self: True)
    
    with pytest.raises(SystemExit) as exc_info:
        cleanup_memory_habits.main()
    
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "ERRO" in captured.err
    assert "Recusado aplicar --apply" in captured.err
