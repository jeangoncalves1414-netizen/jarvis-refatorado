"""Persistent, conflict-checked receipts for local personal records.

Only differences are restored. A later edit always blocks undo instead of being
overwritten. The journal is local; it never stores arbitrary filesystem paths.
"""
from __future__ import annotations

from contextlib import closing
from copy import deepcopy
import json
import threading
import time
import uuid

from app.services.habits import get_db_connection
from app.services.lifeos import LifeOSService, _DB_LOCK

LOCK = threading.RLock()
_active = threading.local()
_inflight = set()
TABLES = ('habits', 'habit_logs', 'tasks', 'task_subtasks', 'finance_transactions', 'personal_records')
TOOLS = {'habit_tool', 'task_tool', 'finance_tool', 'lifeos_tool', 'checklist_tool', 'vault_save_note', 'vault_daily_log', 'personal_records'}
READS = {'list', 'get', 'summary', 'history', 'get_water', 'list_habits', 'motivate', 'preview', 'preferences_get'}


def initialize():
    with closing(get_db_connection()) as conn, conn:
        conn.execute('CREATE TABLE IF NOT EXISTS personal_records (id TEXT PRIMARY KEY, kind TEXT NOT NULL, body TEXT NOT NULL)')
        conn.execute('''CREATE TABLE IF NOT EXISTS personal_history (
            id TEXT PRIMARY KEY, session TEXT NOT NULL, tool TEXT NOT NULL,
            args TEXT NOT NULL, message TEXT NOT NULL, changes TEXT NOT NULL,
            created REAL NOT NULL, undone INTEGER NOT NULL DEFAULT 0,
            success INTEGER NOT NULL DEFAULT 1)''')
        conn.execute('CREATE TABLE IF NOT EXISTS personal_pending (id TEXT PRIMARY KEY, session TEXT NOT NULL, tool TEXT NOT NULL, args TEXT NOT NULL, before_state TEXT NOT NULL, created REAL NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS personal_undo_operations (id TEXT PRIMARY KEY, session TEXT NOT NULL, args TEXT NOT NULL, receipt_id TEXT NOT NULL)')


def _dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def snapshot():
    state = {}
    with closing(get_db_connection()) as conn:
        existing = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in TABLES:
            if table in existing:
                state[table] = {str(r['id']): dict(r) for r in conn.execute(f'SELECT * FROM {table}')}
    from app.storage.checklist_store import checklist_store
    with closing(checklist_store._connect()) as conn:
        for table in ('checklists', 'checklist_items'):
            state[table] = {str(r['id']): dict(r) for r in conn.execute(f'SELECT * FROM {table}')}
    state['lifeos'] = deepcopy(LifeOSService.get_data_bucket())
    from app.services import memory_vault
    from app.agent.tools.memory_vault_tool import NOTE_FOLDERS
    root = memory_vault.VAULT_DIR.resolve()
    state['notes'] = {}
    for folder in NOTE_FOLDERS:
        for path in (root / folder).glob('*.md'):
            if path.is_file() and not path.is_symlink() and path.resolve().parent == root / folder:
                state['notes'][f'{folder}/{path.name}'] = path.read_text(encoding='utf-8')
    return state


def differences(before, after):
    return [dict(store=store, key=key, before=before.get(store, {}).get(key), after=after.get(store, {}).get(key))
            for store in sorted(set(before) | set(after))
            for key in sorted(set(before.get(store, {})) | set(after.get(store, {})))
            if before.get(store, {}).get(key) != after.get(store, {}).get(key)]


def history(session=None, limit=30):
    initialize()
    with closing(get_db_connection()) as conn:
        query = 'SELECT * FROM personal_history'
        params = []
        if session is not None:
            query += ' WHERE session = ?'
            params.append(session)
        rows = conn.execute(query + ' ORDER BY created DESC LIMIT ?', (*params, min(100, max(1, int(limit)))))
        result = [public(dict(row)) for row in rows]
        for row in conn.execute('SELECT * FROM personal_pending ORDER BY created DESC'):
            if row['id'] not in _inflight and (session is None or row['session'] == session):
                result.insert(0, dict(id=row['id'], tool=row['tool'], args=json.loads(row['args']), created=row['created'], undone=0,
                    success=0, can_undo=False, changes=[], message='Execução interrompida. Confira os registros antes de repetir; a cópia anterior está preservada no histórico local.'))
        return result


def public(row):
    changes = json.loads(row['changes'])
    return {**{k: row[k] for k in ('id', 'tool', 'message', 'created', 'undone', 'success')},
            'changes': changes, 'args': json.loads(row['args']), 'can_undo': not bool(row['undone'])}


def execute(tool, args, callback, *, session='', operation_id=None):
    """Wrap both agent and organizer UI writes; nested calls share one receipt."""
    if tool not in TOOLS or args.get('action') in READS or getattr(_active, 'value', False):
        return callback()
    from app.agent.tools.base import ToolResult
    try:
        args_json = _dump(args)
    except (ValueError, TypeError):
        return ToolResult(False, 'Dados inválidos: use valores finitos e campos JSON válidos.')
    if tool == 'personal_records' and args.get('action') == 'undo':
        with LOCK:
            initialize()
            key = operation_id or 'undo_' + uuid.uuid4().hex
            with closing(get_db_connection()) as conn:
                prior = conn.execute('SELECT * FROM personal_undo_operations WHERE id=?', (key,)).fetchone()
            if prior:
                if prior['session'] != session or prior['args'] != args_json:
                    return ToolResult(False, 'Identificador de operação já usado com outros dados.')
                return ToolResult(True, 'Alteração já desfeita.', {'id': prior['receipt_id']})
            previous = getattr(_active, 'undo_operation', None)
            _active.undo_operation = (key, session, args_json)
            _active.value = True
            try:
                return callback()
            finally:
                _active.undo_operation = previous
                _active.value = False
    with LOCK, _DB_LOCK:
        initialize()
        key = operation_id or 'change_' + uuid.uuid4().hex
        with closing(get_db_connection()) as conn:
            prior = conn.execute('SELECT * FROM personal_history WHERE id=?', (key,)).fetchone()
            pending = conn.execute('SELECT id FROM personal_pending WHERE id=?', (key,)).fetchone()
        if pending:
            return ToolResult(False, 'Esta operação foi interrompida. Confira os registros antes de tentar novamente.')
        if prior:
            if prior['args'] != args_json or prior['tool'] != tool or prior['session'] != session:
                return ToolResult(False, 'Identificador de operação já usado com outros dados.')
            return ToolResult(bool(prior['success']), prior['message'], {'personal_receipt': public(dict(prior))})
        before = snapshot()
        with closing(get_db_connection()) as conn, conn:
            conn.execute('INSERT INTO personal_pending VALUES (?,?,?,?,?,?)', (key, session, tool, args_json, _dump(before), time.time()))
        _inflight.add(key)
        _active.value = True
        try:
            try:
                result = callback()
                if not isinstance(result, ToolResult):
                    with closing(get_db_connection()) as conn, conn:
                        conn.execute('DELETE FROM personal_pending WHERE id=?', (key,))
                    return result
                if result.ok and tool == 'finance_tool' and args.get('action') in {'add', 'create', 'add_many'}:
                    from app.services.personal_records import apply_rules
                    from app.services.finance import FinanceService
                    for trans_id in result.data.get('trans_ids', []):
                        entry = FinanceService.get_transaction(trans_id)
                        if entry:
                            apply_rules('finance', trans_id, entry)
            except Exception as exc:
                from app.core.runs import RunCancelled
                if isinstance(exc, RunCancelled):
                    raise
                result = ToolResult(False, f'Não foi possível concluir: {exc}')
            after = snapshot()
            changes = differences(before, after)
            if changes:
                row = dict(id=key, session=session, tool=tool, args=_dump(args), message=result.message,
                           changes=_dump(changes), created=time.time(), undone=0, success=int(result.ok))
                with closing(get_db_connection()) as conn, conn:
                    conn.execute('INSERT INTO personal_history VALUES (:id,:session,:tool,:args,:message,:changes,:created,:undone,:success)', row)
                    conn.execute('DELETE FROM personal_pending WHERE id=?', (key,))
                result.data['personal_receipt'] = public(row)
                if not result.ok:
                    result.message += ' Algumas alterações foram salvas; confira o histórico e use Desfazer se necessário.'
            else:
                with closing(get_db_connection()) as conn, conn:
                    conn.execute('DELETE FROM personal_pending WHERE id=?', (key,))
            return result
        finally:
            _active.value = False
            _inflight.discard(key)


def undo(receipt_id='', *, session=None):
    initialize()
    with LOCK, _DB_LOCK, closing(get_db_connection()) as conn:
        if not receipt_id:
            # An implicit undo must be scoped to the current conversation.
            row = conn.execute('SELECT * FROM personal_history WHERE session=? AND undone=0 ORDER BY created DESC LIMIT 1', (session or '',)).fetchone()
        else:
            row = conn.execute('SELECT * FROM personal_history WHERE id=?', (receipt_id,)).fetchone()
        if not row:
            raise ValueError('Nenhuma alteração encontrada para desfazer.')
        if row['undone']:
            return {'ok': True, 'message': 'Esta alteração já foi desfeita.', 'id': row['id']}
        changes = json.loads(row['changes'])
        from app.storage.checklist_store import checklist_store
        conn.execute('ATTACH DATABASE ? AS lists', (str(checklist_store.path.resolve()),))
        conn.execute('BEGIN IMMEDIATE')
        try:
            current = snapshot()
            for change in changes:
                if current.get(change['store'], {}).get(change['key']) != change['after']:
                    raise ValueError('O registro mudou depois desta operação. Nada foi desfeito; confira a edição mais recente.')
            bucket = deepcopy(current['lifeos'])
            file_changes = []
            for change in changes:
                store, key, value = change['store'], change['key'], change['before']
                if store == 'lifeos':
                    if value is None:
                        bucket.pop(key, None)
                    else:
                        bucket[key] = value
                elif store == 'notes':
                    file_changes.append(change)
                elif store in (*TABLES, 'checklists', 'checklist_items'):
                    table = ('lists.' if store.startswith('checklist') else '') + store
                    conn.execute(f'DELETE FROM {table} WHERE id=?', (key,))
                    if value is not None:
                        value = dict(value)
                        # A restored deletion must be newer than the distributed tombstone.
                        if change['after'] is None:
                            for stamp in ('updated_at', 'timestamp', 'created_at'):
                                if stamp in value:
                                    value[stamp] = time.time()
                                    break
                        columns = list(value)
                        conn.execute(f'INSERT INTO {table} ({",".join(columns)}) VALUES ({",".join("?" for _ in columns)})', tuple(value.values()))
            _write_files(file_changes, 'before')
            if bucket != current['lifeos'] and not LifeOSService.save_data_bucket(bucket):
                raise OSError('Falha ao restaurar os registros pessoais.')
            conn.execute('UPDATE personal_history SET undone=1 WHERE id=?', (row['id'],))
            operation = getattr(_active, 'undo_operation', None)
            if operation:
                conn.execute('INSERT INTO personal_undo_operations VALUES (?,?,?,?)', (*operation, row['id']))
            conn.commit()
        except Exception:
            conn.rollback()
            if 'file_changes' in locals():
                _write_files(file_changes, 'after')
            if 'bucket' in locals() and bucket != current['lifeos']:
                if not LifeOSService.save_data_bucket(current['lifeos']):
                    raise OSError('Falha ao recuperar os registros. O histórico preserva as duas versões.')
            raise
        from app.storage import sync_tombstones
        for change in changes:
            if change['before'] is None and change['after'] is not None:
                store = change['store']
                value = change['after']
                if store in {'habits', 'tasks', 'finance_transactions', 'habit_logs'}:
                    identity = (value['habit_id'], value['date_str']) if store == 'habit_logs' else (value['id'],)
                    sync_tombstones.record('lifestyle.' + store, sync_tombstones.row_key(*identity))
                elif store == 'notes':
                    sync_tombstones.record('notes', change['key'])
        return {'ok': True, 'message': 'Alteração desfeita, incluindo os registros vinculados.', 'id': row['id']}


def _write_files(changes, version):
    from app.services import memory_vault
    from app.agent.tools.memory_vault_tool import NOTE_FOLDERS
    from app.ui.panel.api.recent_notes import _note_file
    for change in changes:
        path = _note_file(memory_vault.VAULT_DIR, change['key'], NOTE_FOLDERS)
        content = change[version]
        if content is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix('.undo.tmp')
            temporary.write_text(content, encoding='utf-8')
            temporary.replace(path)
