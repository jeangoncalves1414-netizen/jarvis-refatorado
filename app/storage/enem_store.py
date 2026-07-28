from __future__ import annotations

import json
import uuid
from datetime import date
from pathlib import Path
from typing import Any


class EnemStore:
    """Local ENEM question bank stored as JSON files under data/enem/questions/."""

    def __init__(self, storage_dir: str | None = None) -> None:
        self.questions_dir = Path(storage_dir or "data/enem/questions")
        self.questions_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, qid: str) -> Path:
        safe_id = qid.replace("/", "_").replace("\\", "_")
        return self.questions_dir / f"{safe_id}.json"

    def _read_file(self, path: Path) -> dict[str, Any] | None:
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _summarize(self, data: dict[str, Any]) -> dict[str, Any]:
        text = str(data.get("text", ""))
        preview = text[:120].replace("\n", " ")
        if len(text) > 120:
            preview += "…"
        return {
            "id": data.get("id", ""),
            "subject": data.get("subject", data.get("area", "")),
            "year": data.get("year"),
            "preview": preview,
            "has_image": bool(data.get("image_base64")),
            "created": data.get("created", data.get("date", "")),
        }

    def list_questions(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for path in sorted(self.questions_dir.glob("*.json")):
            data = self._read_file(path)
            if data and data.get("id"):
                items.append(self._summarize(data))
        items.sort(key=lambda q: (q.get("year") or 0, q.get("id", "")), reverse=True)
        return items

    def get_question(self, qid: str) -> dict[str, Any] | None:
        data = self._read_file(self._path_for(qid))
        if not data:
            return None
        return dict(data)

    def save_question(self, data: dict[str, Any]) -> dict[str, Any]:
        qid = str(data.get("id") or uuid.uuid4().hex[:8])
        record: dict[str, Any] = {
            "id": qid,
            "text": str(data.get("text", "")).strip(),
            "subject": str(data.get("subject", data.get("area", ""))).strip(),
            "year": data.get("year"),
            "image_base64": data.get("image_base64"),
            "source": str(data.get("source", "manual")),
            "created": str(data.get("created") or date.today()),
        }
        if record["year"] is not None:
            try:
                record["year"] = int(record["year"])
            except (TypeError, ValueError):
                record["year"] = None
        path = self._path_for(qid)
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return record
