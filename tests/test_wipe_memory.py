import json
import sqlite3
from datetime import datetime

import pytest

from scripts import wipe_memory as wipe
from app.storage import backend_sync, sync_tombstones


def seed(root):
    (root / "vault/05-Notas").mkdir(parents=True)
    (root / "vault/05-Notas/Fato-sobre-o-usuário.md").write_text("Usuário gosta de pizza.", encoding="utf-8")
    (root / "vault/05-Notas/trabalho.md").write_text("Projeto pessoal", encoding="utf-8")
    (root / "sessions.json").write_text('{"sessions": [{"history": ["olá"]}]}', encoding="utf-8")
    (root / "memory.json").write_text(json.dumps({"facts": ["pizza"], "preferences": [], "sessions": ["legado"]}), encoding="utf-8")
    (root / "memory_facts.json").write_text(json.dumps({"facts": [{"id": "m1", "text": "pizza", "updated_at": 1}]}), encoding="utf-8")
    with sqlite3.connect(root / "lifestyle.db") as conn:
        conn.execute("CREATE TABLE habits(id TEXT, name TEXT, archived INTEGER, created_at REAL)")
        conn.execute("CREATE TABLE habit_logs(id TEXT, habit_id TEXT, date_str TEXT, timestamp REAL, notes TEXT)")
        conn.executemany("INSERT INTO habits VALUES (?, ?, 0, ?)", [("old", "Acordar às 5:00", 1), ("dup", "Acordar às 5:00", 2), ("other", "Ler", 3)])
        conn.execute("INSERT INTO habit_logs VALUES ('bad', 'old', '2026-11-11', ?, 'Auto-check contextual: saudação matinal')", (datetime(2026, 11, 11, 18).timestamp(),))


class Chroma:
    def __init__(self):
        self.names = {"user_memory", "episodic_memory", "conversations", "documents"}

    def list_collections(self):
        return list(self.names)

    def delete_collection(self, name):
        self.names.remove(name)


def test_wipe_backs_up_every_file_preserves_history_and_prevents_resurrection(tmp_path):
    seed(tmp_path)
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    actions = wipe.plan(tmp_path)
    assert actions["duplicate_habits"] == ["dup"]
    client = Chroma()
    saved = wipe.apply(tmp_path, actions, chroma_client=client)
    for relative, content in before.items():
        assert (saved / relative).read_bytes() == content
    assert (tmp_path / "sessions.json").read_bytes() == before[next(p for p in before if str(p) == "sessions.json")]
    assert wipe.read_json(tmp_path / "memory.json")["sessions"] == ["legado"]
    assert client.names == {"documents"}
    assert (tmp_path / "vault/05-Notas/trabalho.md").exists()
    with sqlite3.connect(tmp_path / "lifestyle.db") as conn:
        assert conn.execute("SELECT id FROM habits ORDER BY id").fetchall() == [("old",), ("other",)]
        assert conn.execute("SELECT * FROM habit_logs").fetchall() == []
    local = {"tombstones": wipe.read_json(tmp_path / "sync_tombstones.json")["deleted"]}
    remote = {"memory": {"facts": ["pizza"]}, "memory_facts": {"m1": {"text": "pizza", "updated_at": 1}}}
    merged = backend_sync.merge_snapshots(local, remote)
    assert merged["memory"]["facts"] == []
    assert merged["memory_facts"] == {}
    remote["memory_facts"]["m1"]["updated_at"] = 10**12
    assert "m1" in backend_sync.merge_snapshots(local, remote)["memory_facts"]


def test_failed_backup_never_deletes(tmp_path, monkeypatch):
    seed(tmp_path)
    actions = wipe.plan(tmp_path)
    monkeypatch.setattr(wipe.shutil, "copy2", lambda *args: (_ for _ in ()).throw(OSError("full")))
    with pytest.raises(OSError):
        wipe.apply(tmp_path, actions)
    assert wipe.read_json(tmp_path / "memory.json")["facts"] == ["pizza"]
    assert not (tmp_path / "sync_tombstones.json").exists()


def test_running_backend_blocks_wipe(tmp_path):
    seed(tmp_path)
    with wipe.offline_lock(tmp_path), pytest.raises(RuntimeError, match="backend"):
        wipe.apply(tmp_path, wipe.plan(tmp_path))
