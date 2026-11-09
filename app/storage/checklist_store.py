"""Armazenamento e modelo de Checklists Inteligentes (estilo Google Keep).

Permite criar listas, adicionar itens com parsing inteligente de linguagem natural
(extraindo quantidade e condições), alternar conclusão com afundamento (sink) de itens
concluídos para o rodapé, e reordenar.
"""
from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
import uuid
from contextlib import closing
from pathlib import Path
from typing import Any

from app.storage import runtime_settings


_CONDITION_REGEX = re.compile(
    r"\b(se\s+(?:tiver|estiver|custar|abaixo|menos|em|na|estiver|for)\b.+|caso\s+(?:tiver|esteja|seja|custe)\b.+|caso\s+.+|somente\s+se\b.+|apenas\s+se\b.+|se\s+.+)$",
    re.IGNORECASE,
)

_UNITS = (
    r"garrafas?|pacotes?|unidades?|quilos?|kilos?|gramas?|litros?|caixas?|fatias?|dúzias?|duzias?|barras?|vidros?|potes?|sacos?|latas?|kg|un|x|g|l"
)

_QUANTITY_PREFIX_REGEX = re.compile(
    rf"^\s*(\d+(?:[.,]\d+)?(?:\s*(?:{_UNITS}))?)\b\s*(?:de\s+)?(.+)$",
    re.IGNORECASE,
)

_QUANTITY_SUFFIX_REGEX = re.compile(
    rf"^(.+?)\s+(\d+(?:[.,]\d+)?(?:\s*(?:{_UNITS})))\b$",
    re.IGNORECASE,
)

_COMMAND_VERBS_REGEX = re.compile(
    r"^(?:comprar|pegar|trazer|levar|adicionar|preciso de|colocar)\s+",
    re.IGNORECASE,
)


def parse_spoken_items(raw_text: str) -> list[dict[str, Any]]:
    """Converte texto falado ou livre em uma lista de itens estruturados.

    Exemplo:
    '1 saco de arroz, 10 batatas chips, 2 coca colas se tiver abaixo de 10 reais, 5 batatas inglesas'
    -> [
        {"text": "arroz", "quantity": "1 saco", "condition_note": ""},
        {"text": "batatas chips", "quantity": "10", "condition_note": ""},
        {"text": "coca colas", "quantity": "2", "condition_note": "se tiver abaixo de 10 reais"},
        {"text": "batatas inglesas", "quantity": "5", "condition_note": ""},
    ]
    """
    if not raw_text or not raw_text.strip():
        return []

    # Normaliza quebras de linha e separadores
    text = raw_text.strip()
    # Troca conjunções ' e ' por vírgula se seguido de número ou item claro (ex: '2 cocas e 5 batatas')
    text = re.sub(r"\s+e\s+(?=\d+\b|[a-zA-ZÀ-ÿ]{2,})", ", ", text)

    raw_segments = re.split(r"[,;\n]+", text)
    items: list[dict[str, Any]] = []

    for seg in raw_segments:
        segment = seg.strip()
        if not segment:
            continue

        # Remove verbos de comando comuns no início do segmento
        segment = _COMMAND_VERBS_REGEX.sub("", segment).strip()
        if not segment:
            continue

        condition_note = ""
        # Verifica se há condição (ex: 'se tiver abaixo de 10 reais')
        cond_match = _CONDITION_REGEX.search(segment)
        if cond_match and cond_match.start() > 0:
            condition_note = cond_match.group(1).strip()
            item_candidate = segment[: cond_match.start()].strip()
        else:
            item_candidate = segment

        quantity = ""
        item_text = item_candidate

        # Tenta casar quantidade no início (ex: '1 saco de arroz', '10 batatas')
        qty_prefix = _QUANTITY_PREFIX_REGEX.match(item_candidate)
        if qty_prefix:
            quantity = qty_prefix.group(1).strip()
            item_text = qty_prefix.group(2).strip()
        else:
            # Tenta casar quantidade no final (ex: 'arroz 5kg')
            qty_suffix = _QUANTITY_SUFFIX_REGEX.match(item_candidate)
            if qty_suffix:
                item_text = qty_suffix.group(1).strip()
                quantity = qty_suffix.group(2).strip()

        # Limpa resquícios de "de " no início do texto
        item_text = re.sub(r"^(?:de\s+)", "", item_text, flags=re.IGNORECASE).strip()
        # Remove pontuação residual
        item_text = item_text.strip(".- ,")

        if item_text:
            items.append({
                "text": item_text,
                "quantity": quantity,
                "condition_note": condition_note,
            })

    return items


class ChecklistStore:
    """Repositório SQLite de Checklists com persistência e afundamento de concluídos."""

    def __init__(self, path: str | Path | None = None) -> None:
        if path is None:
            data_dir = getattr(runtime_settings, "DATA_DIR", "data")
            self.path = Path(data_dir) / "checklists.sqlite3"
        else:
            self.path = Path(path)
        self._lock = threading.RLock()
        self._initialized = False

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        if not self._initialized:
            with db:
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS checklists (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL,
                        archived INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS checklist_items (
                        id TEXT PRIMARY KEY,
                        list_id TEXT NOT NULL,
                        text TEXT NOT NULL,
                        quantity TEXT,
                        condition_note TEXT,
                        completed INTEGER NOT NULL DEFAULT 0,
                        position INTEGER NOT NULL DEFAULT 0,
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL,
                        FOREIGN KEY (list_id) REFERENCES checklists(id) ON DELETE CASCADE
                    )
                    """
                )
                db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_items_list ON checklist_items(list_id, completed, position)"
                )
            self._initialized = True
        return db

    # ── Listas ─────────────────────────────────────────────────────────────

    def create_list(
        self,
        title: str,
        items: list[dict[str, Any]] | str | None = None,
        list_id: str | None = None,
    ) -> dict[str, Any]:
        """Cria uma nova lista de checklist."""
        clean_title = (title or "Lista sem título").strip()
        lid = list_id or f"list_{uuid.uuid4().hex[:8]}"
        now = time.time()

        with self._lock, closing(self._connect()) as db, db:
            db.execute(
                "INSERT INTO checklists (id, title, created_at, updated_at, archived) VALUES (?, ?, ?, ?, 0)",
                (lid, clean_title, now, now),
            )

        if items:
            self.add_items(lid, items)

        return self.get_list(lid) or {"id": lid, "title": clean_title, "items": []}

    def get_list(self, list_id: str) -> dict[str, Any] | None:
        """Obtém a lista com os itens ordenados (itens pendentes primeiro, concluídos afundados ao final)."""
        with self._lock, closing(self._connect()) as db:
            row = db.execute("SELECT * FROM checklists WHERE id = ?", (list_id,)).fetchone()
            if not row:
                return None
            list_dict = dict(row)
            # Ordenação com Sink: completed ASC (0 antes de 1), position ASC, created_at ASC
            item_rows = db.execute(
                "SELECT * FROM checklist_items WHERE list_id = ? ORDER BY completed ASC, position ASC, created_at ASC",
                (list_id,),
            ).fetchall()

        items = [dict(r) for r in item_rows]
        # Converter completed para booleano
        for it in items:
            it["completed"] = bool(it["completed"])
            it["quantity"] = it.get("quantity") or ""
            it["condition_note"] = it.get("condition_note") or ""

        pending_count = sum(1 for it in items if not it["completed"])
        completed_count = sum(1 for it in items if it["completed"])

        return {
            "id": list_dict["id"],
            "title": list_dict["title"],
            "archived": bool(list_dict["archived"]),
            "created_at": list_dict["created_at"],
            "updated_at": list_dict["updated_at"],
            "items": items,
            "pending_count": pending_count,
            "completed_count": completed_count,
            "total_count": len(items),
        }

    def list_all(self, include_archived: bool = False) -> list[dict[str, Any]]:
        """Lista todas as checklists com resumo de pendências."""
        query = "SELECT * FROM checklists" + ("" if include_archived else " WHERE archived = 0") + " ORDER BY updated_at DESC"
        with self._lock, closing(self._connect()) as db:
            rows = db.execute(query).fetchall()
            results = []
            for row in rows:
                lid = row["id"]
                counts = db.execute(
                    "SELECT completed, count(*) as cnt FROM checklist_items WHERE list_id = ? GROUP BY completed",
                    (lid,),
                ).fetchall()
                pending = 0
                completed = 0
                for c in counts:
                    if c["completed"]:
                        completed = c["cnt"]
                    else:
                        pending = c["cnt"]
                results.append({
                    "id": lid,
                    "title": row["title"],
                    "archived": bool(row["archived"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "pending_count": pending,
                    "completed_count": completed,
                    "total_count": pending + completed,
                })
        return results

    def find_list_by_title(self, query: str) -> dict[str, Any] | None:
        """Busca uma lista pelo título aproximado ou exato."""
        clean = (query or "").strip().lower()
        if not clean:
            return None
        all_lists = self.list_all()
        # Busca exata
        for l in all_lists:
            if l["title"].lower() == clean:
                return self.get_list(l["id"])
        # Busca por substring
        for l in all_lists:
            if clean in l["title"].lower():
                return self.get_list(l["id"])
        return None

    def delete_list(self, list_id: str) -> bool:
        """Exclui a checklist e seus itens."""
        with self._lock, closing(self._connect()) as db, db:
            db.execute("DELETE FROM checklist_items WHERE list_id = ?", (list_id,))
            res = db.execute("DELETE FROM checklists WHERE id = ?", (list_id,))
            return res.rowcount > 0

    # ── Itens ──────────────────────────────────────────────────────────────

    def add_items(
        self,
        list_id: str,
        items: list[dict[str, Any]] | str,
    ) -> list[dict[str, Any]]:
        """Adiciona itens à lista especificada.

        Suporta tanto uma lista de dicionários quanto uma string crua em linguagem natural.
        """
        if isinstance(items, str):
            structured = parse_spoken_items(items)
        elif isinstance(items, list):
            structured = []
            for it in items:
                if isinstance(it, str):
                    structured.extend(parse_spoken_items(it))
                elif isinstance(it, dict):
                    structured.append({
                        "text": str(it.get("text", "")).strip(),
                        "quantity": str(it.get("quantity") or "").strip(),
                        "condition_note": str(it.get("condition_note") or "").strip(),
                        "completed": bool(it.get("completed", False)),
                    })
        else:
            return []

        if not structured:
            return []

        now = time.time()
        added_items: list[dict[str, Any]] = []

        with self._lock, closing(self._connect()) as db, db:
            # Pega a posição máxima atual
            max_pos_row = db.execute(
                "SELECT COALESCE(MAX(position), -1) as max_pos FROM checklist_items WHERE list_id = ?",
                (list_id,),
            ).fetchone()
            curr_pos = (max_pos_row["max_pos"] if max_pos_row else -1) + 1

            for it in structured:
                text = (it.get("text") or "").strip()
                if not text:
                    continue
                item_id = f"item_{uuid.uuid4().hex[:8]}"
                qty = it.get("quantity") or ""
                cond = it.get("condition_note") or ""
                completed = 1 if it.get("completed") else 0

                db.execute(
                    """
                    INSERT INTO checklist_items 
                    (id, list_id, text, quantity, condition_note, completed, position, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (item_id, list_id, text, qty, cond, completed, curr_pos, now, now),
                )
                curr_pos += 1
                added_items.append({
                    "id": item_id,
                    "list_id": list_id,
                    "text": text,
                    "quantity": qty,
                    "condition_note": cond,
                    "completed": bool(completed),
                    "position": curr_pos - 1,
                    "created_at": now,
                    "updated_at": now,
                })

            db.execute("UPDATE checklists SET updated_at = ? WHERE id = ?", (now, list_id))

        return added_items

    def toggle_item(self, item_id: str, completed: bool | None = None) -> dict[str, Any] | None:
        """Alterna ou define o estado de conclusão de um item."""
        now = time.time()
        with self._lock, closing(self._connect()) as db, db:
            row = db.execute("SELECT * FROM checklist_items WHERE id = ?", (item_id,)).fetchone()
            if not row:
                return None
            new_val = (1 - row["completed"]) if completed is None else (1 if completed else 0)
            db.execute(
                "UPDATE checklist_items SET completed = ?, updated_at = ? WHERE id = ?",
                (new_val, now, item_id),
            )
            db.execute("UPDATE checklists SET updated_at = ? WHERE id = ?", (now, row["list_id"]))
            updated = db.execute("SELECT * FROM checklist_items WHERE id = ?", (item_id,)).fetchone()
            res = dict(updated)
            res["completed"] = bool(res["completed"])
            return res

    def update_item(self, item_id: str, **kwargs: Any) -> dict[str, Any] | None:
        """Atualiza campos de um item (text, quantity, condition_note, position, completed)."""
        now = time.time()
        fields = {}
        for key in ("text", "quantity", "condition_note"):
            if key in kwargs and kwargs[key] is not None:
                fields[key] = str(kwargs[key]).strip()
        if "completed" in kwargs and kwargs["completed"] is not None:
            fields["completed"] = 1 if kwargs["completed"] else 0
        if "position" in kwargs and kwargs["position"] is not None:
            fields["position"] = int(kwargs["position"])

        if not fields:
            with self._lock, closing(self._connect()) as db:
                row = db.execute("SELECT * FROM checklist_items WHERE id = ?", (item_id,)).fetchone()
                return dict(row) if row else None

        fields["updated_at"] = now
        set_clause = ", ".join(f"{k} = ?" for k in fields.keys())
        params = list(fields.values())
        params.append(item_id)

        with self._lock, closing(self._connect()) as db, db:
            db.execute(f"UPDATE checklist_items SET {set_clause} WHERE id = ?", params)
            row = db.execute("SELECT * FROM checklist_items WHERE id = ?", (item_id,)).fetchone()
            if not row:
                return None
            db.execute("UPDATE checklists SET updated_at = ? WHERE id = ?", (now, row["list_id"]))
            res = dict(row)
            res["completed"] = bool(res["completed"])
            return res

    def delete_item(self, item_id: str) -> bool:
        """Remove um item da lista."""
        now = time.time()
        with self._lock, closing(self._connect()) as db, db:
            row = db.execute("SELECT list_id FROM checklist_items WHERE id = ?", (item_id,)).fetchone()
            if not row:
                return False
            db.execute("DELETE FROM checklist_items WHERE id = ?", (item_id,))
            db.execute("UPDATE checklists SET updated_at = ? WHERE id = ?", (now, row["list_id"]))
            return True


checklist_store = ChecklistStore()
