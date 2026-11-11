"""Console em pipe cp1252 não derruba o app nem a chamada ao modelo (A1)."""
from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.core.stdio import configure_utf8_stdio

ROOT = Path(__file__).resolve().parent.parent


def test_piped_stdout_without_utf8_env_prints_arrow():
    env = {key: value for key, value in os.environ.items() if key not in {"PYTHONIOENCODING", "PYTHONUTF8"}}
    code = (
        "from app.core.stdio import configure_utf8_stdio; configure_utf8_stdio(); "
        "print('\\u2192\\u202f'); import sys; print('\\u2192', file=sys.stderr)"
    )
    done = subprocess.run([sys.executable, "-c", code], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=60)
    assert done.returncode == 0, done.stderr
    assert "\u2192\u202f" in done.stdout.decode("utf-8")
    assert "\u2192" in done.stderr.decode("utf-8")


def test_missing_streams_under_pythonw_are_ignored(monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    configure_utf8_stdio()


def test_streams_without_reconfigure_are_ignored(monkeypatch):
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    configure_utf8_stdio()


def test_main_configures_stdio_first(monkeypatch):
    import app.main as main_module

    calls = []

    class Sentinel(Exception):
        pass

    def build_app():
        raise Sentinel()

    monkeypatch.setattr(main_module, "configure_utf8_stdio", lambda: calls.append("stdio"))
    monkeypatch.setattr(main_module, "build_app", build_app)
    monkeypatch.setattr(sys, "argv", ["x"])
    with pytest.raises(Sentinel):
        main_module.main()
    assert calls == ["stdio"]


def test_llm_log_survives_cp1252_stdout(monkeypatch):
    from app.services import llm

    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", stream)
    llm._log("\u2192 seta")
    stream.flush()
    assert b"seta" in buffer.getvalue()
