"""Saída de console em UTF-8 (A1).

No Windows, stdout em pipe usa cp1252 e um "→" num print derrubava a chamada ao modelo
com UnicodeEncodeError. Módulo leve: não importa nada do app.
"""
from __future__ import annotations

import sys


def configure_utf8_stdio() -> None:
    """Troca stdout/stderr para UTF-8 com ``errors="replace"``; sob pythonw eles são ``None``."""
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if stream is None or reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass
