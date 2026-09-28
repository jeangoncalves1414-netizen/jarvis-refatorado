"""
Unit tests for Jarvis System Resilience:
1. System backup ZIP packaging and validation
2. Evolute status extraction with vices and corruption recovery
3. Safe fallback when databases or files are missing
"""
import io
import json
import zipfile
import tempfile
from pathlib import Path
import pytest

from app.ui.panel.api.evolute import handle_evolute_status_get, handle_evolute_sync_get


def test_evolute_status_schema():
    """Verify that handle_evolute_status_get always returns a valid schema with vices."""
    status_code, data = handle_evolute_status_get()
    assert status_code == 200
    assert "habits" in data
    assert "waterMl" in data
    assert "score" in data
    assert "vices" in data
    assert isinstance(data["vices"], list)
    assert isinstance(data["habits"], list)


def test_system_backup_zip_creation():
    """Verify that backup packaging generates a valid zip with non-zero bytes."""
    data_dir = Path(__file__).resolve().parents[1] / "data"
    assert data_dir.exists(), "Data directory should exist"

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in data_dir.glob("*.json"):
            zf.write(f, arcname=f"data/{f.name}")

    zip_data = zip_buffer.getvalue()
    assert len(zip_data) > 0

    # Verify that the zip is valid and can be opened
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as check_zf:
        names = check_zf.namelist()
        assert len(names) > 0
        assert any(n.startswith("data/") for n in names)


def test_evolute_corrupted_db_resilience(monkeypatch):
    """Verify handle_evolute_status_get does not crash when DB has invalid JSON."""
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as tmp:
        tmp.write("INVALID JSON CONTENT { [ broken")
        tmp_path = Path(tmp.name)

    try:
        from app.ui.panel.api import evolute
        monkeypatch.setattr(evolute, "_get_db_file", lambda: tmp_path)

        status_code, data = handle_evolute_status_get()
        assert status_code == 500
        assert "error" in data
        assert data["habits"] == []
        assert data["waterMl"] == 0
        assert data["vices"] == []
    finally:
        tmp_path.unlink(missing_ok=True)


def test_panel_handler_logging_resilience():
    """Verify that PanelHandler logging never raises IndexError on single-item or timeout tuples."""
    from app.ui.panel.server import PanelHandler

    handler = PanelHandler.__new__(PanelHandler)
    # Single item args (as raised by http.server on TimeoutError)
    handler.log_error("Request timed out: %r", TimeoutError("timed out"))
    handler.log_message("Request timed out: %r", TimeoutError("timed out"))

    # Normal HTTP requests
    handler.log_message('"%s" %s %s', "GET / HTTP/1.1", "200", "1234")
    handler.log_message('"%s" %s %s', "GET /api HTTP/1.1", "500", "0")

    # Empty args
    handler.log_error("Generic error with no args")
    handler.log_message("Generic message with no args")
