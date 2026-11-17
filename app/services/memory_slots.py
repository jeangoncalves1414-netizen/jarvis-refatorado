"""Parser de slots de memória (fase contexto 2): regex pura, sem chamada ao modelo.

``parse("de manhã prefiro a playlist Foco")`` -> ``("music", "Foco", "manha")``. O valor é
recortado do texto original (acentos e maiúsculas preservados) pelos mesmos índices do
texto normalizado. Sem casamento -> ``None`` (memória só textual).
"""
from __future__ import annotations

import re
import unicodedata

MAX_VALUE = 80
SLOTS = ("music", "city", "app.navegador", "app.editor", "app.player", "name")
APP_CATEGORIES = ("navegador", "editor", "player")

_WHEN = (
    (re.compile(r"\b(?:de|pela|na) manha\b"), "manha"),
    (re.compile(r"\b(?:a|de|na|pela) tarde\b"), "tarde"),
    (re.compile(r"\b(?:a|de|na|pela) noite\b"), "noite"),
)
# Valor: até pontuação, um marcador de período ou um conector que começa outra ideia.
_VALUE = (
    r"(?P<v>[^\s,.;!?\"'][^,.;!?]*?)"
    r"(?=\s+(?:(?:de|pela|na)\s+manha|(?:a|de|na|pela)\s+(?:tarde|noite)|quando|porque|pois|mas|e|para|pra|no|na)\b"
    r"|\s*[,.;!?]|\s*$)"
)
_MUSIC_KIND = r"(?:(?:a\s+)?playlist|(?:a\s+)?musica|(?:o\s+)?album|(?:o\s+)?artista|(?:a\s+)?banda)"
_PATTERNS: tuple[tuple[re.Pattern[str], str | None], ...] = (
    (re.compile(r"\bprefiro\s+(?:(?:ouvir|escutar)\s+)?" + _MUSIC_KIND + r"\s+" + _VALUE), "music"),
    (re.compile(r"\bprefiro\s+(?:ouvir|escutar)\s+" + _VALUE), "music"),
    (re.compile(r"\bminha\s+playlist\s+(?:preferida|favorita)\s+e\s+(?:a\s+)?" + _VALUE), "music"),
    (re.compile(r"\bprefiro\s+(?:usar\s+)?o\s+(?P<cat>navegador|editor|player)\s+" + _VALUE), None),
    (re.compile(r"\bmeu\s+(?P<cat>navegador|editor|player)\s+(?:preferido|favorito)\s+e\s+o\s+" + _VALUE), None),
    (re.compile(r"\b(?:eu\s+)?mor[oa]\s+em\s+" + _VALUE), "city"),
    (re.compile(r"\bminha\s+cidade\s+e\s+" + _VALUE), "city"),
    (re.compile(r"\bmeu\s+nome\s+e\s+" + _VALUE), "name"),
    (re.compile(r"\bme\s+chamo\s+" + _VALUE), "name"),
    (re.compile(r"\bpode\s+me\s+chamar\s+de\s+" + _VALUE), "name"),
)


def normalize_aligned(text: str) -> str:
    """Minúsculas sem acento, com o mesmo comprimento do original (índice a índice)."""
    out = []
    for ch in str(text or ""):
        base = "".join(c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c))
        low = (base or ch).lower()
        out.append(low[0] if low else ch)
    return "".join(out)


def when_of(text: str) -> str | None:
    value = normalize_aligned(text)
    for pattern, when in _WHEN:
        if pattern.search(value):
            return when
    return None


def parse(text: str) -> tuple[str, str, str | None] | None:
    """Slot, valor e período de uma preferência explícita; ``None`` sem casamento."""
    original = str(text or "")
    normalized = normalize_aligned(original)
    for pattern, slot in _PATTERNS:
        match = pattern.search(normalized)
        if not match:
            continue
        start, end = match.span("v")
        value = original[start:end].strip(" \"'“”‘’").strip()
        if not value:
            continue
        resolved = slot or f"app.{match.group('cat')}"
        if resolved == "name":
            spelled = re.fullmatch(r"(.+?)\s+com\s+([^\W\d_])", value, re.I)
            if spelled and spelled[2].casefold() in spelled[1].casefold():
                value = re.sub(r"\b([^\W\d_]+)\s+\1$", r"\1", spelled[1], flags=re.I)
        return resolved, value[:MAX_VALUE], when_of(original) if resolved == "music" else None
    return None
