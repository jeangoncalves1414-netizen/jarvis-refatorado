"""Limpeza autorizada da memória; simulação por padrão, backup verificado em --apply.

Execute com o Jarvis fechado. O histórico de conversas não é memória semântica
e é preservado, inclusive a seção sessions do arquivo legado memory.json.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import shutil
import sqlite3
import sys
import os
import stat
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.storage import sync_tombstones as tomb
from scripts.cleanup_memory_habits import normalize_name

COLLECTIONS = ("user_memory", "episodic_memory", "conversations")


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Formato inesperado: {path.name}")
    return value


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def backup(data: Path, lock_handle=None) -> Path:
    """Copia todos os arquivos existentes e verifica hashes antes de permitir exclusões."""
    files = list(data.rglob("*"))
    for path in files:
        if path.is_symlink() or getattr(path.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError(f"Backup não segue links: {path}")
        path.resolve().relative_to(data)
    target = data / ("backup-pre-wipe-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    target.mkdir()
    manifest = {}
    for path in files:
        relative = path.relative_to(data)
        destination = target / relative
        if path.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        if path.name == "action_journal.runtime.lock" and path.parent == data and lock_handle:
            lock_handle.seek(0)
            content = lock_handle.read()
            destination.write_bytes(content)
            manifest[relative.as_posix()] = hashlib.sha256(content).hexdigest()
            continue
        before = digest(path)
        shutil.copy2(path, destination)
        if before != digest(destination) or before != digest(path):
            raise RuntimeError(f"Arquivo alterado durante backup: {relative}")
        manifest[relative.as_posix()] = before
    # A lista também deve ficar estável: interrompe se o aplicativo estiver gravando.
    current = {p.relative_to(data).as_posix() for p in data.rglob("*")
               if p.is_file() and not p.is_relative_to(target)}
    if current != set(manifest):
        raise RuntimeError("Os dados mudaram durante o backup. Feche o Jarvis e tente novamente.")
    (target / "backup-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return target


def plan(data: Path) -> dict:
    notes = []
    profile = data / "vault/02-User-Profile/USER-PROFILE.md"
    if profile.is_file():
        notes.append(profile.relative_to(data).as_posix())
    for note in (data / "vault/05-Notas").glob("*.md"):
        content = note.read_text(encoding="utf-8").casefold()
        if "testando integração do memory vault" in content or "unittest" in content or (
            note.name == "Fato-sobre-o-usuário.md" and "usuário gosta de pizza" in content
        ):
            notes.append(note.relative_to(data).as_posix())
    duplicates, invalid_logs = [], []
    db = data / "lifestyle.db"
    if db.exists():
        with sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            seen = set()
            for row in conn.execute("SELECT id, name FROM habits WHERE archived=0 ORDER BY created_at, id"):
                key = normalize_name(row["name"])
                if key in seen:
                    duplicates.append(row["id"])
                seen.add(key)
            for row in conn.execute("SELECT l.id, l.habit_id, l.date_str, l.timestamp, l.notes, h.name "
                                    "FROM habit_logs l JOIN habits h ON h.id=l.habit_id"):
                if ("acordar" in normalize_name(row["name"])
                        and "saudação matinal" in (row["notes"] or "").casefold()
                        and datetime.fromtimestamp(row["timestamp"]).hour >= 12):
                    invalid_logs.append(dict(row))
    return {"notes": sorted(notes), "duplicate_habits": duplicates,
            "invalid_logs": invalid_logs, "collections": list(COLLECTIONS)}


@contextlib.contextmanager
def offline_lock(data: Path):
    with (data / "action_journal.runtime.lock").open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError("Feche o backend Jarvis antes da limpeza.") from exc
        yield handle


def apply(data: Path, actions: dict, *, chroma_client=None) -> Path:
    with offline_lock(data) as handle:
        return _apply(data, actions, chroma_client=chroma_client, lock_handle=handle)


def _apply(data: Path, actions: dict, *, chroma_client=None, lock_handle=None) -> Path:
    data = data.resolve(strict=True)
    # Resolve every deletion target before making a backup or touching live data.
    for relative in actions["notes"]:
        (data / relative).resolve().relative_to(data / "vault")
    saved = backup(data, lock_handle)
    # Recheck the plan after backup, before any destructive change.
    if plan(data) != actions:
        raise RuntimeError("Os dados mudaram depois da simulação; nenhuma exclusão aplicada.")
    now = time.time()
    memory = read_json(data / "memory.json")
    prefs = read_json(data / "preferences.json")
    facts = read_json(data / "memory_facts.json")
    deleted = {}

    def mark(kind, key):
        deleted.setdefault(kind, {})[key] = now

    for name, values in (("facts", memory.get("facts", [])),
                         ("preferences", memory.get("preferences", [])),
                         ("user_preferences", prefs.get("preferences", []))):
        for value in values:
            mark("memory." + name, tomb.memory_key(value))
    for fact in facts.get("facts", []):
        mark("memory_facts", fact["id"])
    for relative in actions["notes"]:
        mark("notes", Path(relative).relative_to("vault").as_posix())
    for habit_id in actions["duplicate_habits"]:
        mark("lifestyle.habits", tomb.row_key(habit_id))
    for row in actions["invalid_logs"]:
        mark("lifestyle.habit_logs", tomb.row_key(row["habit_id"], row["date_str"]))
    tomb_path = data / "sync_tombstones.json"
    state = read_json(tomb_path)
    state.update(version=1, deleted=tomb.merge(state.get("deleted"), deleted, now))
    # Persist tombstones strictly: unlike best-effort ordinary deletes, a wipe must abort on failure.
    tomb_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    if chroma_client is None and (data / "vector_db/chroma.sqlite3").exists():
        import chromadb
        from chromadb.config import Settings
        chroma_client = chromadb.PersistentClient(path=str(data / "vector_db"),
                                                 settings=Settings(anonymized_telemetry=False))
    if chroma_client is not None:
        names = {getattr(c, "name", c) for c in chroma_client.list_collections()}
        for name in COLLECTIONS:
            if name in names:
                chroma_client.delete_collection(name)

    for filename, value in (("memory_facts.json", {"version": 1, "facts": []}),
                            ("memory.json", {"facts": [], "preferences": [], "sessions": memory.get("sessions", [])}),
                            ("preferences.json", {"preferences": []}),
                            ("profile_memories.json", {})):
        (data / filename).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    for relative in actions["notes"]:
        (data / relative).unlink()
    if (data / "lifestyle.db").exists():
        with sqlite3.connect(data / "lifestyle.db") as conn:
            for habit_id in actions["duplicate_habits"]:
                conn.execute("DELETE FROM habit_logs WHERE habit_id=?", (habit_id,))
                conn.execute("DELETE FROM habits WHERE id=?", (habit_id,))
            for row in actions["invalid_logs"]:
                conn.execute("DELETE FROM habit_logs WHERE id=?", (row["id"],))
    history = data / "sessions.json"
    if history.exists() and digest(history) != digest(saved / "sessions.json"):
        raise RuntimeError("O histórico mudou durante a limpeza; examine o backup.")
    return saved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    data = args.data_dir.resolve(strict=True)
    actions = plan(data)
    print(json.dumps({k: len(v) for k, v in actions.items()}, ensure_ascii=False))
    if args.apply:
        print(f"Limpeza concluída. Backup verificado: {apply(data, actions)}")
    else:
        print("Simulação; use --apply com o Jarvis fechado para criar backup e aplicar.")


if __name__ == "__main__":
    main()
