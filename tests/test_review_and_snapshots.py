"""
Unit tests for CodeSnapshotManager and CodeReviewPipeline.
"""
import os
import tempfile
import pytest
from pathlib import Path
from app.services.code_snapshots import CodeSnapshotManager
from app.services.code_reviewer import CodeReviewPipeline


# ── 1. CodeSnapshotManager Tests ─────────────────────────────────────────────

def test_code_snapshot_creation_and_rollback():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_file = Path(tmpdir) / "test_script.py"
        tmp_file.write_text("print('Versão 1 - Original')", encoding="utf-8")

        mgr = CodeSnapshotManager(base_dir=Path(tmpdir) / "snaps")

        # 1. Cria snapshot v1
        snap1 = mgr.create_snapshot(str(tmp_file), summary="Primeira versão")
        assert snap1 is not None
        assert snap1.version_id.startswith("v_")

        # 2. Modifica arquivo para v2
        tmp_file.write_text("print('Versão 2 - Editado')", encoding="utf-8")
        snap2 = mgr.create_snapshot(str(tmp_file), summary="Segunda versão")
        assert snap2 is not None

        # 3. Modifica arquivo para v3 (com bug)
        tmp_file.write_text("print('Versão 3 - Com Bug!')", encoding="utf-8")
        assert "Com Bug" in tmp_file.read_text(encoding="utf-8")

        # 4. Executa Rollback para v1
        ok, msg = mgr.rollback(str(tmp_file), version_id=snap1.version_id)
        assert ok
        assert "Versão 1 - Original" in tmp_file.read_text(encoding="utf-8")


def test_code_snapshot_list():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_file = Path(tmpdir) / "app.py"
        tmp_file.write_text("x = 10", encoding="utf-8")

        mgr = CodeSnapshotManager(base_dir=Path(tmpdir) / "snaps")
        mgr.create_snapshot(str(tmp_file))

        snaps = mgr.list_snapshots(str(tmp_file))
        assert len(snaps) == 1
        assert snaps[0]["filepath"] == str(tmp_file.resolve())


# ── 2. CodeReviewPipeline Tests ──────────────────────────────────────────────

def test_code_reviewer_syntax_valid():
    pipeline = CodeReviewPipeline()
    valid_code = "def hello():\n    return 'Hello World'"
    ok, msg = pipeline.check_syntax(valid_code, language="python")
    assert ok
    assert "Válida" in msg


def test_code_reviewer_syntax_invalid():
    pipeline = CodeReviewPipeline()
    invalid_code = "def hello(\n    return 'Faltando parêntese'"
    ok, msg = pipeline.check_syntax(invalid_code, language="python")
    assert not ok
    assert "Sintaxe" in msg


def test_code_reviewer_autofix_loop():
    pipeline = CodeReviewPipeline(max_iterations=2)

    def dummy_fixer(bad_code: str, error_msg: str) -> str:
        return "def fixed():\n    return 42"

    bad_code = "def broken(\n    pass"
    res = pipeline.run_review_and_fix_loop(bad_code, fix_generator_fn=dummy_fixer, language="python")
    assert res.ok
    assert res.attempts_made == 2
    assert "fixed" in res.final_code
