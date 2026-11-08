"""Transactional action snapshots and append-only events for retained actions."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import closing
from dataclasses import asdict
from pathlib import Path

from app.core.actions import ALLOWED_TRANSITIONS, ActionRecord, TERMINAL_STATUSES, redact
from app.core.diagnostics import record
from app.core.runs import RUN_TERMINAL, RunCancelled, RunRecord, run_origin

# Leitura concluída pedida por uma janela do painel (origem "panel:..."), sem alterar nada.
# Fica fora das listas da Central por padrão para não gerar ruído a cada abertura de janela.
_PANEL_READ = "(json_extract({a}.payload, '$.risk') = 'observe' AND {a}.status = 'succeeded' AND json_extract({a}.payload, '$.source') LIKE 'panel:%')"


class ActionStore:
    def __init__(self, path: str | Path = "data/action_journal.sqlite3", max_records: int = 2_000) -> None:
        supplied = Path(path)
        self.path = supplied.with_suffix(".sqlite3") if supplied.suffix == ".jsonl" else supplied
        self.legacy_path = supplied if supplied.suffix == ".jsonl" else supplied.with_suffix(".jsonl")
        self.max_records = max(1, max_records)
        self._lock = threading.RLock()
        self._initialized = False
        self._runtime_lock = None

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            if not self._initialized:
                with db:
                    db.execute("BEGIN IMMEDIATE")
                    db.execute("CREATE TABLE IF NOT EXISTS actions (sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, status TEXT NOT NULL, updated_at REAL NOT NULL, payload TEXT NOT NULL)")
                    db.execute("CREATE TABLE IF NOT EXISTS action_events (id INTEGER PRIMARY KEY AUTOINCREMENT, action_id TEXT NOT NULL REFERENCES actions(id) ON DELETE CASCADE, status TEXT NOT NULL, kind TEXT NOT NULL, timestamp REAL NOT NULL, summary TEXT)")
                    db.execute("CREATE INDEX IF NOT EXISTS action_events_by_action ON action_events(action_id, id)")
                    db.execute("CREATE INDEX IF NOT EXISTS actions_by_status ON actions(status, sequence)")
                    db.execute("CREATE TABLE IF NOT EXISTS action_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                    db.execute("CREATE TABLE IF NOT EXISTS runs (sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, status TEXT NOT NULL, session_id TEXT, payload TEXT NOT NULL)")
                    db.execute("CREATE TABLE IF NOT EXISTS run_events (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE, action_id TEXT, kind TEXT NOT NULL, status TEXT NOT NULL, timestamp REAL NOT NULL, summary TEXT)")
                    db.execute("CREATE INDEX IF NOT EXISTS run_events_by_run ON run_events(run_id, id)")
                    db.execute("CREATE INDEX IF NOT EXISTS actions_by_run ON actions(json_extract(payload, '$.run_id'))")
                    if not db.execute("SELECT 1 FROM action_meta WHERE key = 'legacy_imported'").fetchone():
                        self._import_legacy(db)
                        db.execute("INSERT INTO action_meta VALUES ('legacy_imported', '1')")
                self._initialized = True
        except Exception:
            db.close()
            raise
        return db

    def _import_legacy(self, db: sqlite3.Connection) -> None:
        if not self.legacy_path.exists():
            return
        snapshots: dict[str, ActionRecord] = {}
        skipped = 0
        for line in self.legacy_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = ActionRecord.from_dict(json.loads(line))
                snapshots[item.id] = item
            except (ValueError, TypeError, AttributeError):
                skipped += 1
        for item in sorted(snapshots.values(), key=lambda action: action.created_at):
            self._insert(db, item)
            self._event(db, item, "legacy_import", "Snapshot importado do registro anterior; etapas anteriores indisponíveis.")
        if skipped:
            record("action_kernel", "legacy_import_skipped", count=skipped)

    @staticmethod
    def _insert(db: sqlite3.Connection, action: ActionRecord) -> None:
        db.execute("INSERT INTO actions(id, status, updated_at, payload) VALUES (?, ?, ?, ?)",
                   (action.id, action.status, action.updated_at, json.dumps(asdict(action), ensure_ascii=False)))

    def _event(self, db: sqlite3.Connection, action: ActionRecord, kind: str, summary: str | None = None) -> None:
        db.execute("INSERT INTO action_events(action_id, status, kind, timestamp, summary) VALUES (?, ?, ?, ?, ?)",
                   (action.id, action.status, kind, action.updated_at, summary))
        if action.run_id:
            db.execute("INSERT INTO run_events(run_id, action_id, kind, status, timestamp, summary) VALUES (?, ?, ?, ?, ?, ?)",
                       (action.run_id, action.id, "action_" + kind, action.status, action.updated_at, summary))
            if kind != "recovery":
                self._refresh_run(db, action.run_id)

    @staticmethod
    def _read(db: sqlite3.Connection, action_id: str) -> ActionRecord | None:
        row = db.execute("SELECT payload FROM actions WHERE id = ?", (action_id,)).fetchone()
        return ActionRecord.from_dict(json.loads(row[0])) if row else None

    def create(self, action: ActionRecord) -> ActionRecord:
        with self._lock, closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if self._read(db, action.id):
                raise ValueError("ID de ação já existe.")
            if action.run_id:
                self._check_run(db, action.run_id)
            self._insert(db, action)
            self._event(db, action, "created", action.preview)
            excess = db.execute("SELECT COUNT(*) FROM actions").fetchone()[0] - self.max_records
            if excess > 0:
                placeholders = ",".join("?" for _ in TERMINAL_STATUSES)
                # Linked actions are retained with their whole request, never partly pruned.
                db.execute(f"DELETE FROM actions WHERE id IN (SELECT id FROM actions WHERE json_extract(payload, '$.run_id') IS NULL AND status IN ({placeholders}) ORDER BY updated_at LIMIT ?)", (*sorted(TERMINAL_STATUSES), excess))
        return action

    def get(self, action_id: str) -> ActionRecord | None:
        with self._lock, closing(self._connect()) as db:
            return self._read(db, action_id)

    def transition(self, action_id: str, status: str, *, result_summary: str | None = None, receipt_reference: str | None = None, undo_payload: dict | None = None, expected_status: str | None = None) -> ActionRecord:
        with self._lock, closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            current = self._read(db, action_id)
            if not current:
                raise KeyError("Ação não encontrada.")
            if expected_status is not None and current.status != expected_status:
                raise ValueError("O estado da ação mudou; atualize o painel.")
            if status not in ALLOWED_TRANSITIONS.get(current.status, frozenset()):
                raise ValueError(f"Transição inválida: {current.status} → {status}")
            if current.run_id and status in {"authorized", "running"}:
                self._check_run(db, current.run_id)
            updated = ActionRecord(**{
                **asdict(current), "status": status, "updated_at": time.time(),
                "result_summary": result_summary if result_summary is not None else current.result_summary,
                "receipt_reference": receipt_reference if receipt_reference is not None else current.receipt_reference,
                "undo_payload": undo_payload if undo_payload is not None else current.undo_payload,
            })
            db.execute("UPDATE actions SET status = ?, updated_at = ?, payload = ? WHERE id = ?",
                       (status, updated.updated_at, json.dumps(asdict(updated), ensure_ascii=False), action_id))
            self._event(db, updated, "transition", result_summary)
        return updated

    def list(self, *, limit: int = 100, status: str | None = None) -> list[ActionRecord]:
        with self._lock, closing(self._connect()) as db:
            rows = db.execute("SELECT payload FROM actions WHERE (? IS NULL OR status = ?) ORDER BY updated_at DESC, sequence DESC LIMIT ?", (status, status, max(1, min(limit, 500))))
            return [ActionRecord.from_dict(json.loads(row[0])) for row in rows]

    def page(self, *, limit: int = 30, before: int | None = None, status: str | None = None, query: str = "", include_reads: bool = False) -> dict:
        limit = max(1, min(limit, 100))
        with self._lock, closing(self._connect()) as db:
            search = "%" + query.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            rows = db.execute(f"SELECT sequence, payload FROM actions WHERE (? IS NULL OR sequence < ?) AND (? IS NULL OR status = ?) AND lower(json_extract(payload, '$.tool_name') || ' ' || json_extract(payload, '$.preview')) LIKE ? ESCAPE '\\' AND (? OR NOT {_PANEL_READ.format(a='actions')}) ORDER BY sequence DESC LIMIT ?", (before, before, status, status, search, include_reads, limit + 1)).fetchall()
            items = rows[:limit]
            return {"actions": [ActionRecord.from_dict(json.loads(row["payload"])).public_dict() for row in items],
                    "next_cursor": items[-1]["sequence"] if len(rows) > limit else None}

    def status_counts(self) -> dict[str, int]:
        with self._lock, closing(self._connect()) as db:
            return dict(db.execute("SELECT status, COUNT(*) FROM actions GROUP BY status"))

    def pending(self, *, limit: int = 10) -> list[ActionRecord]:
        with self._lock, closing(self._connect()) as db:
            rows = db.execute("SELECT payload FROM actions WHERE status IN ('awaiting_confirmation', 'authorized', 'running') ORDER BY updated_at DESC LIMIT ?", (max(1, min(limit, 500)),))
            return [ActionRecord.from_dict(json.loads(row[0])) for row in rows]

    def details(self, action_id: str, *, after_event_id: int = 0) -> dict | None:
        with self._lock, closing(self._connect()) as db, db:
            db.execute("BEGIN")
            action = self._read(db, action_id)
            if action is None:
                return None
            events = [redact(dict(row), limit=500) for row in db.execute("SELECT * FROM action_events WHERE action_id = ? AND id > ? ORDER BY id", (action_id, after_event_id))]
            return {"action": action.public_dict(), "events": events}

    @staticmethod
    def _read_run(db: sqlite3.Connection, run_id: str) -> RunRecord | None:
        row = db.execute("SELECT payload FROM runs WHERE id = ?", (run_id,)).fetchone()
        return RunRecord(**json.loads(row[0])) if row else None

    def _check_run(self, db: sqlite3.Connection, run_id: str) -> RunRecord:
        run = self._read_run(db, run_id)
        if not run:
            raise ValueError("Pedido não encontrado.")
        if run.cancel_requested:
            raise RunCancelled("Cancelamento solicitado; nenhuma nova etapa será iniciada.")
        if run.status in RUN_TERMINAL:
            raise ValueError("Este pedido já foi encerrado.")
        return run

    @staticmethod
    def _save_run(db: sqlite3.Connection, run: RunRecord, kind: str, summary: str) -> None:
        run.updated_at = time.time()
        db.execute("UPDATE runs SET status = ?, payload = ? WHERE id = ?",
                   (run.status, json.dumps(asdict(run), ensure_ascii=False), run.id))
        db.execute("INSERT INTO run_events(run_id, kind, status, timestamp, summary) VALUES (?, ?, ?, ?, ?)",
                   (run.id, kind, run.status, run.updated_at, summary))

    def _refresh_run(self, db: sqlite3.Connection, run_id: str) -> RunRecord:
        run = self._read_run(db, run_id)
        if run.status in RUN_TERMINAL:
            return run
        counts = dict(db.execute("SELECT status, COUNT(*) FROM actions WHERE json_extract(payload, '$.run_id') = ? GROUP BY status", (run_id,)))
        active = any(status not in TERMINAL_STATUSES for status in counts)
        if run.turn_done and not active:
            if run.cancel_requested:
                status, summary = "cancelled", "Pedido encerrado após cancelamento. Etapas já executadas não foram desfeitas."
            elif run.turn_failed or any(counts.get(s) for s in ("failed", "expired", "interrupted")):
                status, summary = "failed", "Pedido encerrado com falha ou ação sem conclusão confirmada."
            elif counts.get("cancelled"):
                status, summary = "cancelled", "Pedido encerrado com etapas recusadas ou bloqueadas."
            elif counts:
                status, summary = "succeeded", "Resposta encerrada e ações registradas concluídas."
            else:
                status, summary = "succeeded", "Resposta encerrada; nenhuma ferramenta registrada." if run.source == "conversation" else "Concluído; nenhuma ferramenta registrada."
        elif run.cancel_requested:
            status, summary = "cancel_requested", "Cancelamento solicitado; aguardando a etapa em andamento retornar."
        elif run.turn_done and counts.get("awaiting_confirmation") and not counts.get("running") and not counts.get("authorized"):
            status, summary = "awaiting_confirmation", "Aguardando sua decisão sobre as propostas."
        else:
            status, summary = "running", "Pedido em andamento."
        if status != run.status:
            run.status, run.result_summary = status, summary
            if status in RUN_TERMINAL:
                run.finished_at = time.time()
            self._save_run(db, run, "status", summary)
        return run

    def start_runtime(self) -> None:
        """One journal-owning process; recover only after the previous owner exits."""
        with self._lock:
            if self._runtime_lock is not None:
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            handle = self.path.with_suffix(".runtime.lock").open("a+b")
            try:
                handle.seek(0, 2)
                if handle.tell() == 0:
                    handle.write(b"0")
                    handle.flush()
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                handle.close()
                raise RuntimeError("O registro de execuções já está em uso por outro backend.") from exc
            self._runtime_lock = handle
            try:
                self._recover_interrupted()
            except Exception:
                self._runtime_lock = None
                handle.close()
                raise

    def _recover_interrupted(self) -> None:
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("SELECT payload FROM actions WHERE status IN ('running', 'authorized', 'proposed', 'awaiting_confirmation')").fetchall()
            for row in rows:
                action = ActionRecord.from_dict(json.loads(row[0]))
                action.status = "interrupted" if action.status == "running" else "expired"
                action.updated_at = time.time()
                action.result_summary = "Backend reiniciado; efeito externo não confirmado. Não houve reexecução." if action.status == "interrupted" else "Proposta expirada após reinício; solicite novamente."
                db.execute("UPDATE actions SET status = ?, updated_at = ?, payload = ? WHERE id = ?", (action.status, action.updated_at, json.dumps(asdict(action), ensure_ascii=False), action.id))
                self._event(db, action, "recovery", action.result_summary)
            rows = db.execute("SELECT payload FROM runs WHERE status IN ('running', 'awaiting_confirmation', 'cancel_requested')").fetchall()
            for row in rows:
                run = RunRecord(**json.loads(row[0]))
                run.status, run.turn_done, run.finished_at = "interrupted", True, time.time()
                run.result_summary = "Backend reiniciado; pedido interrompido e não reexecutado. Confira os efeitos das etapas iniciadas."
                self._save_run(db, run, "recovery", run.result_summary)

    def create_run(self, *, session_id: str | None, mode: str, source: str = "conversation", origin: str = "chat") -> RunRecord:
        self.start_runtime()
        run = RunRecord(session_id=session_id[:200] if session_id else None, mode=mode[:40],
                        source=(source or "conversation")[:80], origin=run_origin(origin))
        with self._lock, closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT INTO runs(id, status, session_id, payload) VALUES (?, ?, ?, ?)", (run.id, run.status, run.session_id, json.dumps(asdict(run))))
            self._save_run(db, run, "created", "Pedido recebido. Conteúdo da conversa não é copiado para o registro.")
            excess = db.execute("SELECT COUNT(*) FROM runs").fetchone()[0] - self.max_records
            if excess > 0:
                marks = ",".join("?" for _ in RUN_TERMINAL)
                ids = [row[0] for row in db.execute(f"SELECT id FROM runs WHERE status IN ({marks}) ORDER BY sequence LIMIT ?", (*sorted(RUN_TERMINAL), excess))]
                for old_id in ids:
                    db.execute("DELETE FROM actions WHERE json_extract(payload, '$.run_id') = ?", (old_id,))
                    db.execute("DELETE FROM runs WHERE id = ?", (old_id,))
        return run

    def finish_run(self, run_id: str, *, failed: bool = False) -> RunRecord:
        with self._lock, closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            run = self._read_run(db, run_id)
            if not run:
                raise KeyError("Pedido não encontrado.")
            if not run.turn_done:
                run.turn_done, run.turn_failed = True, failed
                self._save_run(db, run, "response_finished", "Processamento da resposta encerrado." if not failed else "Processamento da resposta falhou.")
            return self._refresh_run(db, run_id)

    def add_run_event(self, run_id: str, kind: str, summary: str) -> None:
        """Etapa interna sem ferramenta (Swarm, Racing, memória): só um evento no pedido (C6).

        Não muda o estado do pedido e pode ser gravada depois do encerramento, como uma
        memória salva em segundo plano depois que a resposta terminou.
        """
        text = str(redact(str(summary or ""), limit=300))
        with self._lock, closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            run = self._read_run(db, run_id)
            if run is None:
                return
            db.execute("INSERT INTO run_events(run_id, kind, status, timestamp, summary) VALUES (?, ?, ?, ?, ?)",
                       (run.id, kind[:40], run.status, time.time(), text))

    def check_cancelled(self, run_id: str) -> None:
        with self._lock, closing(self._connect()) as db:
            self._check_run(db, run_id)

    def cancel_run(self, run_id: str) -> dict:
        from app.core.actions import pending_action_broker
        with self._lock, closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            run = self._read_run(db, run_id)
            if not run:
                raise KeyError("Pedido não encontrado.")
            if run.status in RUN_TERMINAL:
                if run.status == "cancelled" and run.cancel_requested:
                    return run.public_dict()
                raise ValueError("Este pedido já foi encerrado.")
            if not run.cancel_requested:
                run.cancel_requested, run.status = True, "cancel_requested"
                run.result_summary = "Cancelamento solicitado pelo usuário; etapas concluídas não são desfeitas."
                self._save_run(db, run, "cancel_requested", run.result_summary)
            rows = db.execute("SELECT payload FROM actions WHERE json_extract(payload, '$.run_id') = ? AND status IN ('proposed', 'awaiting_confirmation', 'authorized')", (run_id,)).fetchall()
            for row in rows:
                action = ActionRecord.from_dict(json.loads(row[0]))
                action.status, action.updated_at = "cancelled", time.time()
                action.result_summary = "Etapa não iniciada: pedido cancelado pelo usuário."
                db.execute("UPDATE actions SET status = ?, updated_at = ?, payload = ? WHERE id = ?", (action.status, action.updated_at, json.dumps(asdict(action)), action.id))
                self._event(db, action, "transition", action.result_summary)
            result = self._refresh_run(db, run_id).public_dict()
        for row in rows:
            pending_action_broker.discard(json.loads(row[0])["id"])
        return result

    def run_page(self, *, limit: int = 20, before: int | None = None, status: str | None = None, session_id: str | None = None, include_reads: bool = False) -> dict:
        # Por padrão, pedidos que só fizeram leituras de janelas do painel ficam fora da lista (C12).
        quiet = (
            "EXISTS (SELECT 1 FROM actions x WHERE json_extract(x.payload, '$.run_id') = runs.id) "
            f"AND NOT EXISTS (SELECT 1 FROM actions x WHERE json_extract(x.payload, '$.run_id') = runs.id AND NOT {_PANEL_READ.format(a='x')})"
        )
        with self._lock, closing(self._connect()) as db:
            rows = db.execute(f"SELECT sequence, payload FROM runs WHERE (? IS NULL OR sequence < ?) AND (? IS NULL OR status = ?) AND (? IS NULL OR session_id = ?) AND (? OR NOT ({quiet})) ORDER BY sequence DESC LIMIT ?", (before, before, status, status, session_id, session_id, include_reads, limit + 1)).fetchall()
            items = rows[:limit]
            return {"runs": [RunRecord(**json.loads(row["payload"])).public_dict() for row in items], "next_cursor": items[-1]["sequence"] if len(rows) > limit else None}

    def run_details(self, run_id: str, *, after_event_id: int = 0) -> dict | None:
        with self._lock, closing(self._connect()) as db, db:
            db.execute("BEGIN")
            run = self._read_run(db, run_id)
            if not run:
                return None
            actions = [ActionRecord.from_dict(json.loads(row[0])).public_dict() for row in db.execute("SELECT payload FROM actions WHERE json_extract(payload, '$.run_id') = ? ORDER BY sequence", (run_id,))]
            events = [dict(row) for row in db.execute("SELECT * FROM run_events WHERE run_id = ? AND id > ? ORDER BY id", (run_id, after_event_id))]
            return {"run": run.public_dict(), "actions": actions, "events": events}


action_store = ActionStore()
