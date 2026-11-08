"""Snapshot dos dados do backend para a sincronização total com a nuvem.

Entra no snapshot (e volta na restauração): configurações, chaves de API,
perfil do agente, memórias, preferências, notas do cofre, tarefas, metas,
hábitos e finanças. Ficam fora caches, logs e o journal de ações
(data/action_journal.sqlite3), que é local de cada máquina.

Regras de mesclagem (função pura ``merge_snapshots``):
- Configurações: campo a campo, com carimbo de data por campo. Um valor vazio
  nunca substitui um preenchido; campos que só um dispositivo conhece são
  preservados; no mesmo campo vence o carimbo mais recente (empate: local).
- Registros (tarefas, metas, finanças...): união por identificador, vence o
  registro mais recente. Nada é apagado pela mesclagem.
- Notas: vence a de modificação mais recente; a versão local substituída é
  guardada em ``.conflitos`` dentro do cofre.

As chaves de API viajam completas (decisão da usuária, protegidas por login e
RLS no Supabase). Nenhuma função aqui imprime valores.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from app.storage import runtime_settings as rs

SCHEMA_VERSION = 1
MAX_NOTE_BYTES = 512 * 1024
MAX_NOTES = 500
MEMORY_FILE = Path("data/memory.json")

_API_KEY_IDS = {"oxyy", "groq", "gemini", "openrouter", "fish"}
_PATH_RE = re.compile(r"^[A-Za-z0-9_]{1,60}(\.[A-Za-z0-9_\-]{1,60})?$")


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def is_empty(value: Any) -> bool:
    return value is None or value == "" or value == {} or value == []


def _stamp(record: dict[str, Any], names: tuple[str, ...]) -> float:
    for name in names:
        raw = record.get(name)
        if isinstance(raw, bool):
            continue
        if isinstance(raw, (int, float)):
            return float(raw)
        if isinstance(raw, str) and raw:
            with contextlib.suppress(ValueError):
                return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    return 0.0


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=path.stem + "-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


# ---------------------------------------------------------------------------
# Configurações (campo a campo)
# ---------------------------------------------------------------------------
def collect_settings_fields() -> dict[str, dict[str, Any]]:
    data = rs._read()
    stamps = _dict(data.get(rs.SYNC_META_KEY))
    try:
        fallback = int(os.path.getmtime(rs.RUNTIME_SETTINGS_FILE) * 1000)
    except OSError:
        fallback = 0
    fields: dict[str, dict[str, Any]] = {}
    for path, value in rs.flatten_settings(data).items():
        if not _PATH_RE.match(path):
            continue
        ts = stamps.get(path)
        fields[path] = {"v": value, "ts": int(ts) if isinstance(ts, (int, float)) and ts else fallback}
    return fields


def _valid_field(path: Any, entry: Any) -> bool:
    return (
        isinstance(path, str)
        and bool(_PATH_RE.match(path))
        and isinstance(entry, dict)
        and "v" in entry
        and isinstance(entry.get("ts", 0), (int, float))
        and not isinstance(entry.get("ts", 0), bool)
    )


def merge_settings_fields(local: dict[str, Any], remote: dict[str, Any]) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for path in {**_dict(local), **_dict(remote)}:
        left, right = _dict(local).get(path), _dict(remote).get(path)
        left = left if _valid_field(path, left) else None
        right = right if _valid_field(path, right) else None
        if left is None and right is None:
            continue
        if left is None:
            winner = right
        elif right is None:
            winner = left
        else:
            left_empty, right_empty = is_empty(left["v"]), is_empty(right["v"])
            if left_empty and not right_empty:
                winner = right
            elif right_empty and not left_empty:
                winner = left
            elif left["v"] == right["v"]:
                winner = left if left.get("ts", 0) >= right.get("ts", 0) else right
            else:
                winner = right if right.get("ts", 0) > left.get("ts", 0) else left
        merged[path] = {"v": winner["v"], "ts": int(winner.get("ts", 0) or 0)}
    return merged


def apply_settings_fields(fields: dict[str, dict[str, Any]]) -> int:
    """Grava os campos mesclados em runtime_settings.json preservando os carimbos."""
    data = rs._read()
    stamps = dict(_dict(data.get(rs.SYNC_META_KEY)))
    current = rs.flatten_settings(data)
    changed = 0
    for path, entry in fields.items():
        if not _valid_field(path, entry):
            continue
        section, _, sub = path.partition(".")
        if section == "api_keys" and sub not in _API_KEY_IDS:
            continue
        value = entry["v"]
        if section == "llm_provider" and str(value).lower() not in rs._VALID_PROVIDERS:
            continue
        if section == "tts_provider" and str(value).lower() not in rs._VALID_TTS_PROVIDERS:
            continue
        if section == "stt_provider" and str(value).lower() not in rs._VALID_STT_PROVIDERS:
            continue
        if current.get(path, rs._MISSING) != value:
            rs.unflatten_into(data, path, value)
            changed += 1
        stamps[path] = int(entry.get("ts", 0) or 0)
    data[rs.SYNC_META_KEY] = stamps
    rs._write_raw(data)
    rs.sync_api_keys_to_env()
    for env_name, key in (("LLM_PROVIDER", "llm_provider"), ("TTS_PROVIDER", "tts_provider"), ("STT_PROVIDER", "stt_provider")):
        if isinstance(data.get(key), str) and data[key]:
            os.environ[env_name] = data[key]
    return changed


# ---------------------------------------------------------------------------
# Registros por identificador (tarefas, metas)
# ---------------------------------------------------------------------------
def merge_records(local: Any, remote: Any, stamp_names: tuple[str, ...] = ("updated_at", "created_at")) -> dict[str, Any]:
    merged: dict[str, Any] = {k: v for k, v in _dict(local).items() if isinstance(v, dict)}
    for record_id, record in _dict(remote).items():
        if not isinstance(record, dict):
            continue
        existing = merged.get(record_id)
        if existing is None or _stamp(record, stamp_names) > _stamp(existing, stamp_names):
            merged[record_id] = record
    return merged


def _collect_tasks() -> dict[str, Any]:
    from app.storage import task_store

    with task_store._lock:
        tasks = task_store._read().get("tasks", [])
    return {str(t["id"]): t for t in tasks if isinstance(t, dict) and t.get("id")}


def _apply_tasks(merged: dict[str, Any]) -> None:
    from app.storage import task_store

    with task_store._lock:
        data = task_store._read()
        data["tasks"] = sorted(merged.values(), key=lambda t: _stamp(t, ("created_at",)), reverse=True)
        task_store._write(data)


def _collect_goals() -> dict[str, Any]:
    from app.storage import goal_store as goal_module

    store = goal_module.goal_store
    with store._lock:
        goals = store._read().get("goals", [])
    return {str(g["id"]): g for g in goals if isinstance(g, dict) and g.get("id")}


def _apply_goals(merged: dict[str, Any]) -> None:
    from app.storage import goal_store as goal_module

    store = goal_module.goal_store
    with store._lock:
        data = store._read()
        data["goals"] = sorted(merged.values(), key=lambda g: _stamp(g, ("created_at",)))
        store._write(data)


# ---------------------------------------------------------------------------
# Memórias e preferências
# ---------------------------------------------------------------------------
def _preferences_store():
    from app.storage import user_preferences

    return user_preferences.preference_store


def _collect_memory() -> dict[str, Any]:
    try:
        raw = json.loads(Path(MEMORY_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = {}
    return {
        "facts": [f for f in _list(_dict(raw).get("facts")) if isinstance(f, str)],
        "preferences": [p for p in _list(_dict(raw).get("preferences")) if isinstance(p, dict)],
        "user_preferences": [p for p in _list(_preferences_store()._read().get("preferences")) if isinstance(p, str)],
    }


def _union(first: list[Any], second: list[Any]) -> list[Any]:
    seen: set[str] = set()
    result: list[Any] = []
    for item in [*first, *second]:
        marker = json.dumps(item, sort_keys=True, ensure_ascii=False)
        if marker not in seen:
            seen.add(marker)
            result.append(item)
    return result


def merge_memory(local: Any, remote: Any) -> dict[str, list[Any]]:
    left, right = _dict(local), _dict(remote)
    return {
        name: _union(_list(left.get(name)), _list(right.get(name)))
        for name in ("facts", "preferences", "user_preferences")
    }


def _apply_memory(merged: dict[str, list[Any]]) -> None:
    path = Path(MEMORY_FILE)
    try:
        raw = _dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        raw = {}
    raw["facts"] = merged["facts"]
    raw["preferences"] = merged["preferences"]
    raw.setdefault("sessions", [])
    _atomic_write_text(path, json.dumps(raw, indent=2, ensure_ascii=False))
    store = _preferences_store()
    prefs = _dict(store._read())
    prefs["preferences"] = merged["user_preferences"]
    store._write(prefs)


# ---------------------------------------------------------------------------
# Notas do cofre (Markdown)
# ---------------------------------------------------------------------------
def _vault_root() -> Path:
    from app.services import memory_vault

    return Path(memory_vault.VAULT_DIR)


def _collect_notes() -> dict[str, Any]:
    root = _vault_root()
    notes: dict[str, Any] = {}
    if not root.exists():
        return notes
    for file in sorted(root.rglob("*.md")):
        relative = file.relative_to(root)
        if any(part.startswith(".") for part in relative.parts):
            continue
        try:
            if file.stat().st_size > MAX_NOTE_BYTES:
                continue
            notes[relative.as_posix()] = {"content": file.read_text(encoding="utf-8"), "mtime": file.stat().st_mtime}
        except (OSError, UnicodeDecodeError):
            continue
        if len(notes) >= MAX_NOTES:
            break
    return notes


def _valid_note(path: Any, entry: Any) -> bool:
    return (
        isinstance(path, str)
        and path.endswith(".md")
        and isinstance(entry, dict)
        and isinstance(entry.get("content"), str)
        and len(entry["content"].encode("utf-8")) <= MAX_NOTE_BYTES
        and isinstance(entry.get("mtime", 0), (int, float))
    )


def merge_notes(local: Any, remote: Any) -> dict[str, Any]:
    merged = {p: e for p, e in _dict(local).items() if _valid_note(p, e)}
    for path, entry in _dict(remote).items():
        if not _valid_note(path, entry):
            continue
        existing = merged.get(path)
        if existing is None or (existing["content"] != entry["content"] and entry.get("mtime", 0) > existing.get("mtime", 0)):
            merged[path] = entry
    return dict(list(merged.items())[:MAX_NOTES])


def _apply_notes(merged: dict[str, Any]) -> None:
    root = _vault_root().resolve()
    for relative, entry in merged.items():
        target = (root / relative).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            continue
        if any(part.startswith(".") for part in Path(relative).parts):
            continue
        if target.exists():
            try:
                current = target.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if current == entry["content"]:
                continue
            backup = root / ".conflitos" / f"{target.stem}.{int(time.time() * 1000)}.md"
            _atomic_write_text(backup, current)
        _atomic_write_text(target, entry["content"])
        with contextlib.suppress(OSError):
            os.utime(target, (entry["mtime"], entry["mtime"]))


# ---------------------------------------------------------------------------
# Hábitos, tarefas da rotina e finanças (SQLite data/lifestyle.db)
# ---------------------------------------------------------------------------
# tabela -> (colunas de identidade, colunas ignoradas na cópia)
_LIFESTYLE_TABLES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "habits": (("id",), ()),
    "habit_logs": (("habit_id", "date_str"), ("id",)),
    "tasks": (("id",), ()),
    "task_subtasks": (("task_id", "title"), ("id",)),
    "finance_transactions": (("id",), ()),
    "finance_categories": (("name",), ()),
}


def _lifestyle_connection():
    from app.services import habits, tasks, finance

    habits.init_db()
    tasks.init_task_tables()
    finance.init_finance_tables()
    return contextlib.closing(habits.get_db_connection())


def _row_key(row: dict[str, Any], key_cols: tuple[str, ...]) -> str:
    return json.dumps([row.get(col) for col in key_cols], ensure_ascii=False)


def _collect_lifestyle() -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    with _lifestyle_connection() as conn:
        for table, (_, skip) in _LIFESTYLE_TABLES.items():
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()  # nome vem da lista fixa acima
            result[table] = [{k: row[k] for k in row.keys() if k not in skip} for row in rows]
    return result


def _prefer_remote(table: str) -> Callable[[dict[str, Any], dict[str, Any]], bool]:
    if table in {"habit_logs", "finance_transactions"}:
        return lambda local, remote: float(remote.get("timestamp") or 0) > float(local.get("timestamp") or 0)
    if table == "tasks":
        return lambda local, remote: bool(remote.get("completed")) and not bool(local.get("completed"))
    if table == "task_subtasks":
        return lambda local, remote: bool(remote.get("completed")) and not bool(local.get("completed"))
    if table == "finance_categories":
        return lambda local, remote: not float(local.get("monthly_limit") or 0) and float(remote.get("monthly_limit") or 0) > 0
    return lambda local, remote: False


def merge_lifestyle(local: Any, remote: Any) -> dict[str, list[dict[str, Any]]]:
    left, right = _dict(local), _dict(remote)
    merged: dict[str, list[dict[str, Any]]] = {}
    for table, (key_cols, _) in _LIFESTYLE_TABLES.items():
        rows = {_row_key(r, key_cols): r for r in _list(left.get(table)) if isinstance(r, dict)}
        prefer_remote = _prefer_remote(table)
        for row in _list(right.get(table)):
            if not isinstance(row, dict) or any(row.get(col) in (None, "") for col in key_cols):
                continue
            key = _row_key(row, key_cols)
            if key not in rows or prefer_remote(rows[key], row):
                rows[key] = row
        merged[table] = list(rows.values())
    return merged


def _apply_lifestyle(merged: dict[str, list[dict[str, Any]]]) -> int:
    written = 0
    with _lifestyle_connection() as conn:
        for table, (key_cols, skip) in _LIFESTYLE_TABLES.items():
            columns = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall() if r[1] not in skip]
            existing = {
                _row_key(dict(r), key_cols): {k: r[k] for k in columns}
                for r in conn.execute(f"SELECT * FROM {table}").fetchall()
            }
            for row in merged.get(table, []):
                values = {col: row.get(col) for col in columns if col in row}
                if any(col not in values for col in key_cols):
                    continue
                if existing.get(_row_key(values, key_cols)) == {c: values.get(c) for c in columns}:
                    continue
                names = ", ".join(values)  # colunas vêm do PRAGMA local, nunca do remoto
                marks = ", ".join("?" for _ in values)
                conn.execute(f"INSERT OR REPLACE INTO {table} ({names}) VALUES ({marks})", list(values.values()))
                written += 1
        conn.commit()
    return written


# ---------------------------------------------------------------------------
# Snapshot completo
# ---------------------------------------------------------------------------
def collect_snapshot() -> dict[str, Any]:
    return {
        "schema": SCHEMA_VERSION,
        "collected_at": int(time.time() * 1000),
        "settings": collect_settings_fields(),
        "tasks": _collect_tasks(),
        "goals": _collect_goals(),
        "memory": _collect_memory(),
        "notes": _collect_notes(),
        "lifestyle": _collect_lifestyle(),
    }


def merge_snapshots(local: Any, remote: Any) -> dict[str, Any]:
    left, right = _dict(local), _dict(remote)
    return {
        "schema": SCHEMA_VERSION,
        "collected_at": int(time.time() * 1000),
        "settings": merge_settings_fields(_dict(left.get("settings")), _dict(right.get("settings"))),
        "tasks": merge_records(left.get("tasks"), right.get("tasks")),
        "goals": merge_records(left.get("goals"), right.get("goals")),
        "memory": merge_memory(left.get("memory"), right.get("memory")),
        "notes": merge_notes(left.get("notes"), right.get("notes")),
        "lifestyle": merge_lifestyle(left.get("lifestyle"), right.get("lifestyle")),
    }


def apply_snapshot(snapshot: dict[str, Any]) -> dict[str, int]:
    """Grava no armazenamento local um snapshot já mesclado. Devolve só contagens."""
    summary = {
        "settings": apply_settings_fields(_dict(snapshot.get("settings"))),
        "tasks": len(_dict(snapshot.get("tasks"))),
        "goals": len(_dict(snapshot.get("goals"))),
        "notes": len(_dict(snapshot.get("notes"))),
    }
    _apply_tasks(_dict(snapshot.get("tasks")))
    _apply_goals(_dict(snapshot.get("goals")))
    _apply_memory(merge_memory(snapshot.get("memory"), {}))
    _apply_notes(_dict(snapshot.get("notes")))
    summary["lifestyle_rows_written"] = _apply_lifestyle(_dict(snapshot.get("lifestyle")))
    return summary


def sync_with_remote(remote: Any) -> tuple[dict[str, Any], dict[str, int]]:
    """Mescla o snapshot remoto com o local, grava o resultado e o devolve."""
    merged = merge_snapshots(collect_snapshot(), remote)
    summary = apply_snapshot(merged)
    return merged, summary
