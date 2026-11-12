"""Organizer operations over the existing personal stores."""
from __future__ import annotations

import calendar
from contextlib import closing
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import json
import math
import time
import uuid

from app.services.habits import get_db_connection
from app.services import personal_history as journal
from app.services.lifeos import LifeOSService
from app.agent.tools.base import ToolResult

KINDS = {'habit', 'task', 'finance', 'note', 'workout', 'workout_plan', 'sleep', 'mood', 'personal', 'checklist', 'rule', 'recurrence', 'transfer'}
LABELS = {'habit': 'Hábito', 'task': 'Tarefa', 'finance': 'Lançamento', 'note': 'Anotação', 'workout': 'Treino', 'workout_plan': 'Plano de treino', 'sleep': 'Sono', 'mood': 'Humor', 'personal': 'Registro', 'rule': 'Relação', 'recurrence': 'Recorrência', 'transfer': 'Transferência', 'checklist': 'Lista'}

ALLOWED_FIELDS = {
    'habit': {'title', 'name', 'category', 'routine_block', 'days_of_week', 'start_time', 'items_list', 'day_slots', 'time_exceptions', 'target_value', 'unit', 'value', 'date', 'habits'},
    'task': {'title', 'description', 'priority', 'project', 'due_date', 'subtasks'},
    'note': {'title', 'content', 'folder', 'tags', 'priority', 'due_date', 'project'},
    'checklist': {'title', 'text', 'items'},
    'workout': {'title', 'name', 'date', 'exercises', 'notes', 'plan_id', 'completed'},
    'workout_plan': {'title', 'date', 'exercises', 'days', 'notes', 'enabled'},
    'sleep': {'title', 'date', 'hours', 'content'}, 'mood': {'title', 'date', 'score', 'content'},
    'personal': {'title', 'date', 'content', 'tags'},
    'recurrence': {'title', 'amount', 'category', 'type', 'account', 'date', 'next_date', 'frequency', 'enabled'},
    'transfer': {'title', 'amount', 'date', 'from_account', 'to_account'},
    'rule': {'title', 'source', 'target_kind', 'target_id', 'match_description', 'enabled'},
}

# Chaves somente leitura: ignoradas com aviso (nunca geram erro)
READONLY_FIELDS = {
    'id', 'kind', 'color', 'icon', 'frequency_type', 'target_days_per_week',
    'created_at', 'updated_at', 'archived', 'completed_today', 'completed_at',
    'current_streak', 'best_streak', 'current_value', 'source', 'effective_title',
    'is_priority', 'isPriority', 'created_date', 'connectedTo', 'streak', 'timestamp',
}


def stored(kind):
    journal.initialize()
    with closing(get_db_connection()) as conn:
        return [dict(json.loads(r['body']), id=r['id']) for r in conn.execute('SELECT * FROM personal_records WHERE kind=?', (kind,))]


def save(kind, key, body):
    journal.initialize()
    with closing(get_db_connection()) as conn, conn:
        conn.execute('INSERT INTO personal_records VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body', (key, kind, journal._dump(body)))
    return {**body, 'id': key}


def remove(key):
    with closing(get_db_connection()) as conn, conn:
        conn.execute('DELETE FROM personal_records WHERE id=?', (key,))


def records(kind, query=''):
    from app.services.personal_habits import PersonalHabits
    from app.services.tasks import TaskService
    from app.services.finance import FinanceService
    from app.storage.checklist_store import checklist_store
    if kind == 'habit':
        rows = PersonalHabits.list_habits(include_archived=True)
    elif kind == 'task':
        rows = TaskService.list_tasks(completed=None)
    elif kind == 'finance':
        with closing(get_db_connection()) as conn:
            rows = [dict(r) for r in conn.execute('SELECT * FROM finance_transactions ORDER BY date_str DESC,timestamp DESC')]
        metadata = {r['id'].removeprefix('meta:'): r for r in stored('finance_meta')}
        rows = [dict(row, **{k: v for k, v in metadata.get(row['id'], {}).items() if k != 'id'}) for row in rows]
    elif kind == 'workout':
        bucket = LifeOSService.get_data_bucket()
        rows = list(bucket.get('lifeos_workout_sessions') or [])
        for entry in bucket.get('lifeos_workouts') or []:
            if not entry.get('jarvis_session_id'):
                rows.append(dict(entry, name=entry.get('name') or entry.get('exerciseName') or 'Treino', _legacy_workout=True))
    elif kind == 'checklist':
        rows = checklist_store.list_all()
    elif kind == 'note':
        from app.services.memory_vault import VAULT_DIR
        from app.agent.tools.memory_vault_tool import NOTE_FOLDERS
        from app.ui.panel.api.recent_notes import _note_file
        rows = []
        for folder in NOTE_FOLDERS:
            for candidate in (VAULT_DIR / folder).glob('*.md'):
                relative = f'{folder}/{candidate.name}'
                try:
                    path = _note_file(VAULT_DIR, relative, NOTE_FOLDERS)
                    content = path.read_text(encoding='utf-8')
                    rows.append(dict(id=relative, title=content.splitlines()[0].removeprefix('# ') if content else path.stem, content=content, date=date.fromtimestamp(path.stat().st_mtime).isoformat()))
                except (OSError, ValueError, UnicodeError):
                    continue
        tags = {r['id'].removeprefix('note_meta:'): r.get('tags', []) for r in stored('note_meta')}
        rows = [dict(row, tags=tags.get(row['id'], [])) for row in rows]
    elif kind in KINDS:
        rows = stored(kind)
    else:
        raise ValueError('Tipo de registro desconhecido.')
    return [dict(r, kind=kind, title=r.get('title') or r.get('name') or r.get('description') or LABELS.get(kind, kind)) for r in rows
            if not query or query.casefold() in journal._dump(r).casefold()]


def resolve(kind, key='', query='', session=''):
    rows = records(kind)
    if key == 'last':
        for receipt in journal.history(session=session, limit=100):
            if receipt['undone']:
                continue
            found = []
            for change in receipt['changes']:
                for row in rows:
                    if change['store'] in {'habits', 'tasks', 'finance_transactions', 'notes', 'personal_records'} and change['key'] == row['id']:
                        found.append(row)
                    elif change['store'] == 'habit_logs' and kind == 'habit' and (change['after'] or change['before'] or {}).get('habit_id') == row['id']:
                        found.append(row)
                    elif change['store'] == 'personal_records' and kind == 'finance' and change['key'] == 'meta:' + row['id']:
                        found.append(row)
                    elif change['store'] == 'lifeos' and kind == 'workout' and change['key'] in {'lifeos_workouts', 'lifeos_workout_sessions'}:
                        old = {r['id']: r for r in change['before'] or []}
                        updated = next((r for r in change['after'] or [] if r['id'] == row['id']), None)
                        if updated and old.get(row['id']) != updated:
                            found.append(row)
            unique = {r['id']: r for r in found}
            if len(unique) == 1:
                return next(iter(unique.values()))
            if len(unique) > 1:
                raise ValueError('O último pedido alterou vários registros. Escolha um pelo título ou ID.')
        raise ValueError('Não encontrei um registro recente deste tipo nesta conversa.')
    matches = [r for r in rows if r['id'] == key] if key else [r for r in rows if r['title'].casefold() == query.strip().casefold()]
    if len(matches) != 1:
        choices = '; '.join(f"{r['title']} ({r['id']}, {r.get('date_str', r.get('date', ''))}, {r.get('amount', '')})" for r in matches[:5])
        raise ValueError('Escolha um registro: ' + choices if matches else 'Registro não encontrado. Consulte a lista antes de alterar.')
    return matches[0]


def _day(value):
    return date.fromisoformat(value or date.today().isoformat()).isoformat()


def _number(value, low, high, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{field}: informe um número entre {low} e {high}.')
    return value


def _text(value, field, max_length=300, required=True):
    if not isinstance(value, str) or len(value) > max_length or (required and not value.strip()):
        raise ValueError(f'{field}: informe texto de até {max_length} caracteres.')
    return value.strip()


def _exercises(value):
    if not isinstance(value, list) or len(value) > 50:
        raise ValueError('Informe até 50 exercícios.')
    result = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError('Exercício inválido.')
        entry = {'name': _text(item.get('name'), 'Exercício', 100)}
        for field, maximum in [('sets', 100), ('reps', 1000), ('weight', 2000), ('minutes', 1440)]:
            if field in item:
                entry[field] = _number(item[field], 0, maximum, field)
                if field in {'sets', 'reps'} and int(entry[field]) != entry[field]:
                    raise ValueError('Séries e repetições devem ser inteiras.')
        result.append(entry)
    return result


def _month(day, offset, anchor=None):
    value = date.fromisoformat(day)
    index = value.year * 12 + value.month - 1 + offset
    year, month = divmod(index, 12)
    return date(year, month + 1, min(anchor or value.day, calendar.monthrange(year, month + 1)[1])).isoformat()


def _result(message, **data):
    return ToolResult(True, message, data)


def _delegate(kind, action, fields, target=None):
    from app.agent.tools.lifestyle_tools import HabitTool, TaskTool, FinanceTool
    from app.agent.tools.checklist_tool import ChecklistTool
    from app.agent.tools.memory_vault_tool import VaultSaveNoteTool
    mapping = {'habit': HabitTool, 'task': TaskTool, 'finance': FinanceTool, 'checklist': ChecklistTool, 'note': VaultSaveNoteTool}
    args = dict(fields)
    args['action'] = action
    if target:
        args[{'habit': 'habit_id', 'task': 'task_id', 'finance': 'trans_id', 'checklist': 'list_id', 'note': 'id'}[kind]] = target['id']
    if kind == 'finance' and action == 'create':
        args['action'] = 'add'
    if kind == 'habit' and action == 'create':
        args['name'] = args.pop('title', args.get('name', ''))
    if kind == 'habit' and action == 'update' and 'title' in args:
        args['new_name'] = args.pop('title')
    if kind == 'habit' and action == 'reopen':
        # reopen habit = uncheck today
        args['action'] = 'uncheck'
    if kind == 'task' and action == 'update' and 'title' in args:
        args['new_title'] = args.pop('title')
    if kind == 'checklist':
        args['action'] = {'create': 'create_list', 'delete': 'delete_list'}.get(action, action)
    return mapping[kind]().execute(args)


def mutate(kind, action, fields, target=None):
    from app.services.personal_habits import PersonalHabits, _raw_id
    from app.services.finance import FinanceService
    key = target['id'] if target else 'rec_' + uuid.uuid4().hex
    ignored_readonly = []
    # Handle read-only keys: ignore with warning instead of error
    if kind in ALLOWED_FIELDS:
        readonly_present = set(fields) & READONLY_FIELDS - ALLOWED_FIELDS[kind]
        if readonly_present:
            ignored_readonly = sorted(readonly_present)
            fields = {k: v for k, v in fields.items() if k not in readonly_present}
        unknown = set(fields) - ALLOWED_FIELDS[kind]
        if unknown:
            raise ValueError('Campos não reconhecidos: ' + ', '.join(sorted(unknown)) + '. Aceitos para ' + kind + ': ' + ', '.join(sorted(ALLOWED_FIELDS[kind] - {'habits'})) + '.')
        # Batch habit creation via fields.habits
        if kind == 'habit' and action == 'create' and 'habits' in fields:
            habits_list = fields['habits']
            if not isinstance(habits_list, list):
                raise ValueError("fields.habits deve ser uma lista.")
            if set(fields) - {'habits'}:
                raise ValueError("Não misture fields.habits com campos de hábito único (name, start_time etc.).")
            # Clean readonly keys from each item and collect all ignored
            cleaned_items = []
            item_ignored = set()
            for item in habits_list:
                if not isinstance(item, dict):
                    raise ValueError("Cada item em fields.habits deve ser um objeto.")
                # title -> name mapping
                if 'title' in item and 'name' not in item:
                    item = dict(item, name=item.pop('title'))
                item_readonly = set(item.keys()) & READONLY_FIELDS
                if item_readonly:
                    item_ignored.update(item_readonly)
                cleaned_items.append({k: v for k, v in item.items() if k not in READONLY_FIELDS})
            if item_ignored:
                ignored_readonly.extend(sorted(item_ignored - set(ignored_readonly)))
            from app.agent.tools.lifestyle_tools import HabitTool
            result = HabitTool().execute({'action': 'create_many', 'habits': cleaned_items})
            # Apply target_value/unit per id if provided in items
            from app.services.personal_habits import PersonalHabits as _PH
            for i, item in enumerate(cleaned_items):
                if ('target_value' in item or 'unit' in item) and result.ok:
                    habit_ids = (result.data or {}).get('habit_ids', [])
                    if i < len(habit_ids):
                        updates = {}
                        if 'target_value' in item:
                            updates['target_value'] = item['target_value']
                        if 'unit' in item:
                            updates['unit'] = item['unit']
                        try:
                            _PH.update_habit(habit_ids[i], **updates)
                        except Exception:
                            pass
            if ignored_readonly:
                result = ToolResult(result.ok, result.message + f" Ignorei campos somente leitura: {', '.join(ignored_readonly)}.",
                                    data={**(result.data or {}), 'ignored_fields': ignored_readonly})
            return result
    if kind in ALLOWED_FIELDS and set(fields) - ALLOWED_FIELDS[kind]:
        raise ValueError('Campos não reconhecidos: ' + ', '.join(sorted(set(fields) - ALLOWED_FIELDS[kind])) + '. Aceitos para ' + kind + ': ' + ', '.join(sorted(ALLOWED_FIELDS[kind] - {'habits'})) + '.')
    if 'days_of_week' in fields and (not isinstance(fields['days_of_week'], list) or not fields['days_of_week']):
        raise ValueError('Escolha pelo menos um dia ou pause o hábito.')
    if 'tags' in fields:
        tags = fields['tags'].split(',') if isinstance(fields['tags'], str) else fields['tags']
        if not isinstance(tags, list) or len(tags) > 20:
            raise ValueError('Use até 20 etiquetas.')
        fields = dict(fields, tags=[_text(t, 'Etiqueta', 50) for t in tags if t])
    if 'subtasks' in fields:
        if not isinstance(fields['subtasks'], list) or len(fields['subtasks']) > 100:
            raise ValueError('Use até 100 etapas.')
        prepared = []
        for item in fields['subtasks']:
            if isinstance(item, str):
                prepared.append({'title': _text(item, 'Etapa'), 'completed': False})
            elif isinstance(item, dict) and type(item.get('completed', False)) is bool:
                prepared.append({'title': _text(item.get('title'), 'Etapa'), 'completed': item.get('completed', False)})
            else:
                raise ValueError('Etapa inválida.')
        fields = dict(fields, subtasks=prepared)
    if kind == 'habit' and action in {'pause', 'resume', 'progress'}:
        if action == 'progress':
            amount = _number(fields.get('value'), 0, 1e6, 'Progresso')
            day = _day(fields.get('date'))
            completed = amount >= float(target.get('target_value') or 1)
            if _raw_id(key) is not None:
                result = PersonalHabits._set_evolute_check(key, day, completed, '', value=amount)
            else:
                with closing(get_db_connection()) as conn, conn:
                    conn.execute('INSERT INTO habit_logs (habit_id,date_str,value,completed,notes,timestamp) VALUES (?,?,?,?,?,?) ON CONFLICT(habit_id,date_str) DO UPDATE SET value=excluded.value,completed=excluded.completed,timestamp=excluded.timestamp', (key, day, amount, int(completed), '', time.time()))
                result = dict(PersonalHabits.get_habit(key), current_value=amount, completed_today=completed)
        else:
            raw = _raw_id(key)
            if raw is None:
                with closing(get_db_connection()) as conn, conn:
                    conn.execute('UPDATE habits SET archived=?,updated_at=? WHERE id=?', (int(action == 'pause'), time.time(), key))
            else:
                bucket = LifeOSService.get_data_bucket()
                next(r for r in bucket['lifeos_habits'] if r['id'] == raw)['archived'] = action == 'pause'
                if not LifeOSService.save_data_bucket(bucket):
                    raise OSError('Não foi possível salvar o hábito.')
            result = PersonalHabits.get_habit(key)
        return _result('Hábito atualizado.', record=result)
    if kind == 'finance':
        if fields.get('type', 'expense') not in {'expense', 'income'}:
            raise ValueError('Tipo financeiro inválido: expense ou income.')
        allowed = {'type', 'amount', 'category', 'description', 'date', 'account', 'installments', 'recurrence_id', 'task_id'}
        if set(fields) - allowed:
            raise ValueError('Campos financeiros desconhecidos: ' + ', '.join(sorted(set(fields) - allowed)))
        if action == 'refund':
            if stored_refund := next((r for r in stored('finance_meta') if r.get('refund_of') == key), None):
                raise ValueError('Este lançamento já tem um estorno registrado: ' + stored_refund['id'])
            result = _delegate('finance', 'create', dict(type='income' if target['type'] == 'expense' else 'expense', amount=target['amount'], description='Estorno: ' + target['description'], category=target['category'], date=_day(fields.get('date'))))
            if result.ok:
                save('finance_meta', 'meta:' + result.data['trans_ids'][0], {'account': target.get('account', ''), 'refund_of': key})
            return result
        account = _text(fields['account'], 'Conta', 80, False) if 'account' in fields else None
        count = fields.get('installments', 1)
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 60:
            raise ValueError('Informe de 1 a 60 parcelas.')
        if action != 'create' and count != 1:
            raise ValueError('Parcelamento é definido na criação.')
        if action == 'create' and count > 1:
            entry = FinanceService.normalize_entry(fields.get('type', 'expense'), fields.get('amount'), fields.get('category'), fields.get('description'), fields.get('date'))
            cents = int((Decimal(str(entry['amount'])) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
            if cents < count:
                raise ValueError('Cada parcela precisa ter pelo menos um centavo.')
            entries = [dict(entry, id='fin_' + uuid.uuid4().hex, amount=(cents // count + (i < cents % count)) / 100, date_str=_month(entry['date_str'], i), description=f"{entry['description']} ({i+1}/{count})") for i in range(count)]
            result = _result(f'{count} parcelas registradas, total R$ {entry["amount"]:.2f}.', **FinanceService.record_with_receipt(entries), trans_ids=[r['id'] for r in entries])
        else:
            result = _delegate(kind, action, {k: v for k, v in fields.items() if k in {'type', 'amount', 'category', 'description', 'date'}}, target)
        if result.ok:
            for index, trans_id in enumerate(result.data.get('trans_ids', [])):
                if action == 'delete':
                    remove('meta:' + trans_id)
                elif account is not None or count > 1 or fields.get('recurrence_id'):
                    meta = next((r for r in stored('finance_meta') if r['id'] == 'meta:' + trans_id), {})
                    meta.pop('id', None)
                    if account is not None:
                        meta['account'] = account
                    if count > 1:
                        meta.update(installment=index + 1, installments=count)
                    if fields.get('recurrence_id'):
                        meta['recurrence_id'] = fields['recurrence_id']
                    save('finance_meta', 'meta:' + trans_id, meta)
            if action == 'create':
                apply_rules('finance', result.data.get('trans_ids', [''])[0], fields)
        return result
    if kind == 'note' and action in {'update', 'delete', 'to_task'}:
        from app.ui.panel.api.recent_notes import _note_file
        from app.services.memory_vault import VAULT_DIR
        from app.agent.tools.memory_vault_tool import NOTE_FOLDERS
        path = _note_file(VAULT_DIR, key, NOTE_FOLDERS)
        if action == 'to_task':
            return _delegate('task', 'create', {'title': fields.get('title') or target['title'], **{k: v for k, v in fields.items() if k in {'priority', 'due_date', 'project'}}})
        if action == 'delete':
            path.unlink()
            remove('note_meta:' + key)
        else:
            content = _text(fields.get('content', target['content']), 'Conteúdo', 30000, False)
            if 'title' in fields:
                title = _text(fields['title'], 'Título', 120)
                lines = content.splitlines()
                content = '# ' + title + '\n' + '\n'.join(lines[1:] if lines and lines[0].startswith('# ') else lines)
            temporary = path.with_suffix('.edit.tmp')
            temporary.write_text(content, encoding='utf-8')
            temporary.replace(path)
            if 'tags' in fields:
                save('note_meta', 'note_meta:' + key, {'tags': fields['tags']})
        return _result('Anotação excluída.' if action == 'delete' else 'Anotação atualizada.', record_id=key)
    if kind == 'checklist' and action == 'update':
        from app.storage.checklist_store import checklist_store, parse_spoken_items
        title = _text(fields.get('title', target['title']), 'Título', 200)
        items = fields.get('items')
        if 'text' in fields:
            items = parse_spoken_items(fields['text'])
        if items is not None:
            if not isinstance(items, list) or len(items) > 100:
                raise ValueError('Use até 100 itens.')
            items = [{'id': str(item.get('id') or 'item_' + uuid.uuid4().hex), 'text': _text(item.get('text'), 'Item'), 'completed': bool(item.get('completed', False))} for item in items]
        with closing(checklist_store._connect()) as conn, conn:
            conn.execute('UPDATE checklists SET title=?,updated_at=? WHERE id=?', (title, time.time(), key))
            if items is not None:
                conn.execute('DELETE FROM checklist_items WHERE list_id=?', (key,))
                for index, item in enumerate(items):
                    conn.execute('INSERT INTO checklist_items (id,list_id,text,completed,position,created_at,updated_at) VALUES (?,?,?,?,?,?,?)', (item['id'], key, item['text'], int(item['completed']), index, time.time(), time.time()))
        return _result('Lista atualizada.', record=checklist_store.get_list(key))
    if kind in {'habit', 'task', 'checklist', 'note'}:
        if kind == 'habit':
            if 'target_value' in fields:
                _number(fields['target_value'], .01, 1e6, 'Meta')
            if 'unit' in fields:
                _text(fields['unit'], 'Unidade', 40)
        if kind == 'task' and action == 'update' and set(fields) <= {'description', 'subtasks'}:
            result = _result('Tarefa atualizada.', task=target)
        else:
            result = _delegate(kind, action, fields, target)
        if result.ok and kind == 'task' and action in {'create', 'update'}:
            from app.services.tasks import TaskService
            saved = result.data.get('task') or target
            if saved:
                if 'description' in fields:
                    TaskService.update_task(saved['id'], description=_text(fields['description'], 'Descrição', 10000, False))
                if 'subtasks' in fields:
                    with closing(get_db_connection()) as conn, conn:
                        conn.execute('DELETE FROM task_subtasks WHERE task_id=?', (saved['id'],))
                        conn.executemany('INSERT INTO task_subtasks (task_id,title,completed) VALUES (?,?,?)', [(saved['id'], t['title'], int(t['completed'])) for t in fields['subtasks']])
        if result.ok and kind == 'note' and action == 'create' and 'tags' in fields:
            if result.data.get('path'):
                save('note_meta', 'note_meta:' + result.data['path'], {'tags': fields['tags']})
        if result.ok and kind == 'habit' and action in {'create', 'update'}:
            saved = result.data.get('habit') or target
            if saved and any(k in fields for k in ('target_value', 'unit')):
                PersonalHabits.update_habit(saved['id'], **{k: fields[k] for k in ('target_value', 'unit') if k in fields})
        return result
    if kind == 'workout':
        bucket = LifeOSService.get_data_bucket()
        rows = bucket.get('lifeos_workout_sessions') or []
        legacy = [r for r in bucket.get('lifeos_workouts') or [] if r.get('jarvis_session_id') != key and r['id'] != key]
        if action == 'delete':
            rows = [r for r in rows if r['id'] != key]
        else:
            body = {**(target or {}), **fields, 'id': key}
            # Existing Evolute exercises remain editable without losing individual sets.
            if body.get('_legacy_workout') and 'exercises' not in fields and not body.get('exercises') and body.get('exerciseName'):
                body['exercises'] = [{'name': body['exerciseName'], 'sets': 1, 'reps': s['reps'], 'weight': s['load']} for s in body.get('sets', [])]
            body.pop('_legacy_workout', None)
            body['name'] = _text(body.get('title') or body.get('name') or 'Treino', 'Treino')
            body['date'] = _day(body.get('date'))
            body['exercises'] = _exercises(body.get('exercises', []))
            body['timestamp'] = body.get('timestamp') or date.today().isoformat()
            body['completed'] = action != 'reopen' if action in {'complete', 'reopen'} else body.get('completed', True)
            rows = [r for r in rows if r['id'] != key] + [body]
            if body['completed']:
                for index, exercise in enumerate(body['exercises']):
                    if not all(k in exercise for k in ('sets', 'reps', 'weight')):
                        continue
                    sets = [{'reps': exercise['reps'], 'load': exercise['weight']} for _ in range(int(exercise['sets']))]
                    legacy.append({'id': f'{key}:{index}', 'jarvis_session_id': key, 'date': body['date'],
                                   'exerciseName': exercise['name'], 'muscleGroup': '', 'sets': sets,
                                   'totalVolume': sum(s['reps'] * s['load'] for s in sets), 'timestamp': body['timestamp']})
        bucket['lifeos_workout_sessions'] = rows
        bucket['lifeos_workouts'] = legacy
        if not LifeOSService.save_data_bucket(bucket):
            raise OSError('Não foi possível salvar o treino.')
        if action in {'create', 'complete'} and body['completed']:
            apply_rules('workout', key, body)
        return _result('Treino excluído.' if action == 'delete' else 'Sessão de treino registrada.', record_id=key, record=None if action == 'delete' else body)
    if action == 'delete':
        remove(key)
        return _result(LABELS[kind] + ' excluído.', record_id=key)
    body = {**(target or {}), **fields}
    body.pop('kind', None)
    if action in {'pause', 'resume'}:
        body['enabled'] = action == 'resume'
    body['title'] = _text(body.get('title') or LABELS[kind], 'Título')
    body['date'] = _day(body.get('date'))
    if 'content' in body:
        body['content'] = _text(body['content'], 'Conteúdo', 30000, False)
    if kind == 'sleep':
        body['hours'] = _number(body.get('hours'), 0, 24, 'Horas de sono')
    if kind == 'mood':
        body['score'] = _number(body.get('score'), 1, 5, 'Humor')
    if kind == 'workout_plan':
        body['exercises'] = _exercises(body.get('exercises', []))
        if 'days' in body and (not isinstance(body['days'], list) or any(type(d) is not int or not 0 <= d <= 6 for d in body['days'])):
            raise ValueError('Dias do plano: 0=segunda até 6=domingo.')
    if kind == 'transfer':
        body['amount'] = round(_number(body.get('amount'), .01, 1e9, 'Valor'), 2)
        body['from_account'] = _text(body.get('from_account'), 'Conta de origem', 80)
        body['to_account'] = _text(body.get('to_account'), 'Conta de destino', 80)
        if body['from_account'].casefold() == body['to_account'].casefold():
            raise ValueError('Escolha contas diferentes.')
    if kind == 'recurrence':
        body['amount'] = round(_number(body.get('amount'), .01, 1e9, 'Valor'), 2)
        body['next_date'] = _day(body.get('next_date') or body['date'])
        if not target or 'next_date' in fields:
            body['anchor_day'] = date.fromisoformat(body['next_date']).day
        if body.get('frequency', 'monthly') not in {'monthly', 'weekly'}:
            raise ValueError('Frequência: monthly ou weekly.')
        if body.get('type', 'expense') not in {'income', 'expense'}:
            raise ValueError('Tipo: income ou expense.')
        body.setdefault('frequency', 'monthly')
        body.setdefault('type', 'expense')
    if kind == 'rule':
        if body.get('source') not in {'workout', 'finance'} or body.get('target_kind') not in {'habit', 'task'}:
            raise ValueError('Relacione treino/finanças a hábito/tarefa.')
        if body.get('enabled', True):
            resolve(body['target_kind'], body.get('target_id', ''))
        if body['source'] == 'finance' and not body.get('match_description'):
            raise ValueError('Informe a descrição exata do pagamento que aciona a relação.')
        if type(body.get('enabled', True)) is not bool:
            raise ValueError('enabled deve ser verdadeiro ou falso.')
        body.setdefault('enabled', True)
    if action in {'pause', 'resume'}:
        body['enabled'] = action == 'resume'
    if action in {'complete', 'reopen'}:
        body['completed'] = action == 'complete'
    body['updated_at'] = time.time()
    result = save(kind, key, body)
    return _result(LABELS[kind] + ' salvo.', record=result, record_id=key)


def apply_rules(source, key, fields):
    if source == 'workout':
        from app.services.personal_habits import PersonalHabits
        for habit in PersonalHabits.list_habits():
            if habit.get('connectedTo') == 'treino':
                PersonalHabits.check_in(habit['id'], fields.get('date', ''))
    for rule in stored('rule'):
        if not rule.get('enabled') or rule.get('source') != source:
            continue
        if source == 'finance' and (fields.get('type', 'expense') != 'expense' or str(fields.get('description', '')).casefold() != rule.get('match_description', '').casefold()):
            continue
        target = resolve(rule['target_kind'], rule['target_id'])
        result = mutate(rule['target_kind'], 'complete', {}, target)
        if not result.ok:
            raise ValueError('Registro salvo, mas a relação falhou: ' + result.message)


def preferences(fields=None):
    current = next(iter(stored('preferences')), {'blocks': ['habits', 'tasks', 'workout', 'finance', 'notes'], 'reduced_motion': False, 'review': 'off'})
    if fields is None:
        return current
    if set(fields) - {'blocks', 'reduced_motion', 'review'}:
        raise ValueError('Preferência desconhecida.')
    if 'blocks' in fields and (not isinstance(fields['blocks'], list) or any(b not in {'habits', 'tasks', 'workout', 'finance', 'notes'} for b in fields['blocks'])):
        raise ValueError('Blocos inválidos.')
    if 'reduced_motion' in fields and type(fields['reduced_motion']) is not bool:
        raise ValueError('Movimento reduzido deve ser verdadeiro ou falso.')
    if fields.get('review', 'off') not in {'off', 'daily', 'weekly'}:
        raise ValueError('Revisão deve ser off, daily ou weekly.')
    return save('preferences', 'personal_preferences', {**current, **fields})


def today():
    day = date.today().isoformat()
    tasks = [r for r in records('task') if not r.get('completed')]
    plans = [r for r in records('workout_plan') if r.get('enabled', True) and (date.today().weekday() in r.get('days', []) or r.get('date') == day)]
    finance = records('finance')
    balances = {}
    for row in finance:
        if row['date_str'] <= day:
            account = row.get('account') or 'Sem conta informada'
            balances[account] = balances.get(account, 0) + row['amount'] * (1 if row['type'] == 'income' else -1)
    for row in stored('transfer'):
        if row['date'] <= day:
            for field, sign in [('from_account', -1), ('to_account', 1)]:
                balances[row[field]] = balances.get(row[field], 0) + sign * row['amount']
    return dict(tasks=tasks, plans=plans, workouts=[r for r in records('workout') if r['date'] == day],
                accounts={k: round(v, 2) for k, v in balances.items()},
                recurring_due=[r for r in stored('recurrence') if r.get('enabled', True) and r['next_date'] <= day],
                preferences=preferences(), history=journal.history(limit=10))


def dispatch(action='list', kind='personal', record_id='', query='', fields=None, receipt_id='', session='', **kwargs):
    fields = fields or {}
    if not isinstance(fields, dict) or len(journal._dump(fields)) > 50000:
        raise ValueError('Campos inválidos ou muito extensos.')
    if action == 'history':
        return _result('Histórico de alterações.', results=journal.history(session=session))
    if action == 'undo':
        if not receipt_id and kind != 'personal':
            stores = {'finance': {'finance_transactions'}, 'habit': {'habits', 'habit_logs'}, 'task': {'tasks', 'task_subtasks'}, 'note': {'notes'}, 'checklist': {'checklists', 'checklist_items'}}
            def matches(change):
                store = change['store']
                row = change['after'] or change['before'] or {}
                domain = store in stores.get(kind, set())
                if store == 'personal_records':
                    domain = row.get('kind') == kind
                if store == 'lifeos':
                    domain = (kind == 'workout' and change['key'] in {'lifeos_workouts', 'lifeos_workout_sessions'}) or (kind == 'habit' and change['key'].startswith(('lifeos_habits', 'lifeos_hlog_')))
                if record_id and record_id != 'last':
                    if domain and store == 'lifeos' and isinstance(row, list):
                        before = {r['id']: r for r in change['before'] or []}
                        after = {r['id']: r for r in change['after'] or []}
                        return before.get(record_id) != after.get(record_id)
                    return domain and (change['key'] == record_id or isinstance(row, dict) and row.get('habit_id', row.get('task_id')) == record_id)
                return domain
            previous = next((r for r in journal.history(session=session, limit=100) if not r['undone'] and any(matches(c) for c in r['changes'])), None)
            if not previous:
                raise ValueError('Nenhuma alteração deste tipo foi encontrada nesta conversa para desfazer.')
            receipt_id = previous['id']
        result = journal.undo(receipt_id, session=session)
        return _result(result['message'], **{k: v for k, v in result.items() if k != 'message'})
    if action == 'summary':
        return _result('Resumo pessoal atualizado.', results=today())
    if action in {'preferences_get', 'preferences_set'}:
        return _result('Preferências pessoais.', results=preferences(fields if action.endswith('set') else None))
    if kind not in KINDS:
        raise ValueError('Tipo de registro desconhecido.')
    if action == 'list':
        rows = records(kind, query)
        return _result(f'{len(rows)} registro(s).', results=rows[:100], truncated=len(rows) > 100)
    if action == 'delete_many':
        ids = kwargs.get('record_ids')
        if not isinstance(ids, list) or not ids or not all(isinstance(i, str) and i for i in ids):
            raise ValueError('Informe os IDs dos registros a excluir.')
        targets = {row['id']: row for row in records(kind, '')}
        if any(i not in targets for i in ids):
            raise ValueError('Os registros mudaram. Consulte a lista novamente.')
        removed = []
        for i in dict.fromkeys(ids):
            result = mutate(kind, 'delete', {}, targets[i])
            if not result.ok:
                return ToolResult(False, f'{len(removed)} registro(s) excluído(s). {result.message}', {'results': removed})
            removed.append(targets[i])
        return _result(f'{len(removed)} registro(s) excluído(s).', results=removed)
    if action == 'preview':
        rows = records(kind, query)
        # No executable token is exposed to the model; confirmation is a UI action.
        return _result(f'Prévia: {len(rows)} registro(s). Revise e confirme a exclusão na tela Hoje.', results=rows, bulk_preview={'kind': kind, 'query': query, 'count': len(rows)})
    allowed = {'create', 'update', 'delete', 'complete', 'reopen', 'pause', 'resume', 'progress', 'refund', 'to_task', 'pay', 'start'}
    if action not in allowed:
        raise ValueError('Ação desconhecida.')
    specific = {
        'complete': {'habit', 'task', 'workout'}, 'reopen': {'task', 'workout', 'habit'},
        'pause': {'habit', 'workout_plan', 'rule', 'recurrence'}, 'resume': {'habit', 'workout_plan', 'rule', 'recurrence'},
        'progress': {'habit'}, 'refund': {'finance'}, 'to_task': {'note'}, 'pay': {'recurrence'}, 'start': {'workout_plan'},
    }
    if action in specific and kind not in specific[action]:
        raise ValueError('Esta ação não se aplica a este tipo de registro.')
    target = None if action == 'create' else resolve(kind, record_id, query, session)
    if action == 'pay' and kind == 'recurrence':
        if not target.get('enabled', True):
            raise ValueError('Recorrência pausada.')
        result = mutate('finance', 'create', {'type': target.get('type', 'expense'), 'amount': target['amount'], 'description': target['title'], 'category': target.get('category', 'Outros'), 'date': target['next_date'], 'account': target.get('account', ''), 'recurrence_id': target['id']})
        if result.ok:
            day = target['next_date']
            target['next_date'] = _month(day, 1, target.get('anchor_day')) if target['frequency'] == 'monthly' else (date.fromisoformat(day) + timedelta(days=7)).isoformat()
            save(kind, target['id'], target)
        return result
    if action == 'start' and kind == 'workout_plan':
        if not target.get('enabled', True):
            raise ValueError('Plano pausado. Retome o plano antes de iniciar uma sessão.')
        day = _day(fields.get('date'))
        pending = next((r for r in records('workout') if r.get('plan_id') == target['id'] and r.get('date') == day and r.get('completed') is False), None)
        if pending:
            return _result('Esta sessão já está em andamento.', record=pending, record_id=pending['id'])
        return mutate('workout', 'create', {'title': target['title'], 'exercises': target.get('exercises', []), 'plan_id': target['id'], **fields, 'completed': False})
    return mutate(kind, action, fields, target)
