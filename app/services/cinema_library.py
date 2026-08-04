"""Biblioteca local de fontes de vídeo adicionadas pelo usuário."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4


class CinemaLibraryService:
    """Persiste filmes, séries e URLs de mídia sem buscar ou extrair conteúdo de sites."""

    def __init__(self, library_path: str | Path = "data/cinema_library.json") -> None:
        self.library_path = Path(library_path)

    def list_items(self) -> dict[str, Any]:
        return {"ok": True, "items": self._read().get("items", [])}

    def upsert_source(self, payload: dict[str, Any]) -> dict[str, Any]:
        title = self._clean_text(payload.get("title"), 160)
        media_type = str(payload.get("type", "movie")).lower()
        source_url = self._validate_url(payload.get("url"))
        if not title:
            return {"ok": False, "error": "Informe o título da mídia."}
        if media_type not in {"movie", "tv"}:
            return {"ok": False, "error": "O tipo deve ser filme ou série."}
        if not source_url:
            return {"ok": False, "error": "Informe uma URL HTTP ou HTTPS válida."}

        label = self._clean_text(payload.get("label"), 50) or "Fonte padrão"
        season = self._positive_int(payload.get("season"), 1)
        episode = self._positive_int(payload.get("episode"), 1)
        data = self._read()
        items = data["items"]
        item_id = str(payload.get("item_id", "")).strip()
        item = next((entry for entry in items if entry.get("id") == item_id), None)
        if item is None:
            item = next(
                (entry for entry in items if entry.get("title", "").casefold() == title.casefold() and entry.get("type") == media_type),
                None,
            )
        if item is None:
            item = {"id": uuid4().hex, "title": title, "type": media_type, "sources": [], "episodes": []}
            items.append(item)

        item["title"] = title
        source = {"label": label, "url": source_url}
        if media_type == "tv":
            episodes = item.setdefault("episodes", [])
            target = next((entry for entry in episodes if entry["season"] == season and entry["episode"] == episode), None)
            if target is None:
                target = {"season": season, "episode": episode, "title": f"T{season} E{episode}", "sources": []}
                episodes.append(target)
            self._upsert_source(target["sources"], source)
            episodes.sort(key=lambda entry: (entry["season"], entry["episode"]))
        else:
            self._upsert_source(item.setdefault("sources", []), source)

        items.sort(key=lambda entry: entry["title"].casefold())
        self._write(data)
        return {"ok": True, "item": item}

    @staticmethod
    def _upsert_source(sources: list[dict[str, str]], source: dict[str, str]) -> None:
        existing = next((entry for entry in sources if entry.get("label") == source["label"]), None)
        if existing is None:
            sources.append(source)
        else:
            existing["url"] = source["url"]

    def _read(self) -> dict[str, list[dict[str, Any]]]:
        try:
            raw = json.loads(self.library_path.read_text(encoding="utf-8"))
            return {"items": raw.get("items", [])} if isinstance(raw, dict) else {"items": []}
        except (OSError, ValueError, json.JSONDecodeError):
            return {"items": []}

    def _write(self, data: dict[str, Any]) -> None:
        self.library_path.parent.mkdir(parents=True, exist_ok=True)
        self.library_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _clean_text(value: Any, limit: int) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]

    @staticmethod
    def _positive_int(value: Any, default: int) -> int:
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _validate_url(value: Any) -> str:
        url = str(value or "").strip()
        parsed = urlparse(url)
        return url if parsed.scheme in {"http", "https"} and parsed.netloc else ""
