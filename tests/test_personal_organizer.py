import json
from datetime import date
from types import SimpleNamespace

import pytest

from app.services import personal_history as journal, personal_records as records
from app.agent.tools.personal_records_tool import PersonalRecordsTool
from app.ui.panel.api.personal_records import handle_personal_post


@pytest.fixture(autouse=True)
def isolated(isolated_lote6_data, monkeypatch):
    from app.storage.checklist_store import ChecklistStore
    store = ChecklistStore(isolated_lote6_data.root / 'lists.sqlite3')
    monkeypatch.setattr('app.storage.checklist_store.checklist_store', store)
    monkeypatch.setattr('app.agent.tools.checklist_tool.checklist_store', store)
    monkeypatch.setattr('app.storage.sync_tombstones.TOMBSTONES_FILE', isolated_lote6_data.root / 'tombstones.json')
    return isolated_lote6_data


def call(action, kind='personal', session='test', operation_id=None, **args):
    payload = dict(action=action, kind=kind, **args)
    return journal.execute('personal_records', payload, lambda: records.dispatch(**payload, session=session), session=session, operation_id=operation_id)


def test_persistent_receipt_undo_and_idempotency():
    result = call('create', 'finance', fields={'amount': 38, 'description': 'Almoço', 'account': 'Cartão'}, operation_id='same-request')
    assert result.ok, result.message
    duplicate = call('create', 'finance', fields={'amount': 38, 'description': 'Almoço', 'account': 'Cartão'}, operation_id='same-request')
    assert duplicate.data['personal_receipt']['id'] == result.data['personal_receipt']['id']
    assert len(records.records('finance')) == 1
    corrected = call('update', 'finance', record_id='last', fields={'amount': 32})
    assert corrected.ok, corrected.message
    row = records.records('finance')[0]
    assert row['amount'] == 32 and row['account'] == 'Cartão' and row['description'] == 'Almoço'
    assert call('undo', receipt_id=corrected.data['personal_receipt']['id']).ok
    assert records.records('finance')[0]['amount'] == 38
    assert call('undo', receipt_id=result.data['personal_receipt']['id']).ok
    assert records.records('finance') == []
    assert call('undo', receipt_id=result.data['personal_receipt']['id']).ok


def test_undo_rejects_later_changes_and_other_conversation_context():
    first = call('create', 'task', fields={'title': 'Ler'})
    assert first.ok
    assert call('update', 'task', record_id='last', fields={'title': 'Ler livro'}).ok
    with pytest.raises(ValueError, match='mudou'):
        journal.undo(first.data['personal_receipt']['id'])
    other = call('update', 'task', session='other', record_id='last', fields={'title': 'Errado'})
    assert not other.ok
    assert records.records('task')[0]['title'] == 'Ler livro'


def test_installment_cents_dates_account_transfer_refund():
    result = call('create', 'finance', fields={'amount': 100, 'description': 'Compra', 'date': '2026-01-31', 'installments': 3, 'account': 'Banco'})
    assert result.ok, result.message
    rows = sorted(records.records('finance'), key=lambda r: r['date_str'])
    assert [r['date_str'] for r in rows] == ['2026-01-31', '2026-02-28', '2026-03-31']
    assert [r['amount'] for r in rows] == [33.34, 33.33, 33.33]
    transfer = call('create', 'transfer', fields={'amount': 20, 'from_account': 'Banco', 'to_account': 'Carteira', 'date': '2026-01-01'})
    assert transfer.ok
    assert len(records.records('finance')) == 3
    assert records.today()['accounts'] == {'Banco': -120, 'Carteira': 20}
    refund = call('refund', 'finance', record_id=rows[0]['id'])
    assert refund.ok, refund.message
    assert not call('refund', 'finance', record_id=rows[0]['id']).ok


def test_recurrence_only_records_when_paid_and_undo_restores_due():
    result = call('create', 'recurrence', fields={'title': 'Internet', 'amount': 99, 'next_date': '2026-01-31'})
    assert result.ok, result.message
    assert not records.records('finance')
    key = result.data['record_id']
    paid = call('pay', 'recurrence', record_id=key)
    assert paid.ok, paid.message
    assert records.records('recurrence')[0]['next_date'] == '2026-02-28'
    journal.undo(paid.data['personal_receipt']['id'])
    assert not records.records('finance')
    assert records.records('recurrence')[0]['next_date'] == '2026-01-31'


def test_plan_session_rule_link_and_undo():
    habit = call('create', 'habit', fields={'title': 'Atividade física'})
    assert habit.ok, habit.message
    h_id = habit.data['habit_ids'][0]
    assert call('create', 'rule', fields={'source': 'workout', 'target_kind': 'habit', 'target_id': h_id}).ok
    plan = call('create', 'workout_plan', fields={'title': 'Peito', 'days': [date.today().weekday()], 'exercises': [{'name': 'Supino', 'sets': 3, 'reps': 10, 'weight': 20}]})
    session = call('start', 'workout_plan', record_id=plan.data['record_id'])
    assert session.ok, session.message
    repeated = call('start', 'workout_plan', record_id=plan.data['record_id'])
    assert repeated.data['record_id'] == session.data['record_id']
    assert len(records.records('workout')) == 1
    assert records.records('workout')[0]['completed'] is False
    from app.services.lifeos import LifeOSService
    assert LifeOSService.get_daily_summary()['workout']['completed'] is False
    assert LifeOSService.get_data_bucket().get('lifeos_workouts', []) == []
    assert not records.records('habit')[0]['completed_today']
    done = call('complete', 'workout', record_id=session.data['record_id'])
    assert done.ok, done.message
    assert records.records('habit')[0]['completed_today']
    assert LifeOSService.get_data_bucket()['lifeos_workouts'][0]['sets'] == [{'reps': 10, 'load': 20}] * 3
    assert LifeOSService.get_data_bucket()['lifeos_workouts'][0]['totalVolume'] == 600
    journal.undo(done.data['personal_receipt']['id'])
    assert records.records('workout')[0]['completed'] is False
    assert not records.records('habit')[0]['completed_today']


def test_workout_does_not_mark_unlinked_habit_and_ids_are_unique():
    call('create', 'habit', fields={'title': 'Treino'})
    for _ in range(2):
        assert call('create', 'workout', fields={'title': 'Treino'}).ok
    assert len({r['id'] for r in records.records('workout')}) == 2
    assert not records.records('habit')[0]['completed_today']


def test_habit_progress_pause_resume():
    created = call('create', 'habit', fields={'title': 'Água', 'target_value': 8, 'unit': 'copos'})
    assert created.ok, created.message
    key = created.data['habit_ids'][0]
    assert call('progress', 'habit', record_id=key, fields={'value': 3}).ok
    assert not records.records('habit')[0]['completed_today']
    assert call('progress', 'habit', record_id=key, fields={'value': 8}).ok
    assert records.records('habit')[0]['completed_today']
    assert call('pause', 'habit', record_id=key).ok
    assert records.records('habit')[0]['archived']
    assert call('resume', 'habit', record_id=key).ok
    assert not records.records('habit')[0]['archived']


def test_note_edit_task_delete_and_restore():
    created = call('create', 'note', fields={'title': 'Ideia', 'content': 'Comprar creatina'})
    assert created.ok, created.message
    key = records.records('note', 'Comprar creatina')[0]['id']
    assert call('update', 'note', record_id=key, fields={'content': 'Comparar preços'}).ok
    assert call('to_task', 'note', record_id=key, fields={'title': 'Comparar preços'}).ok
    removed = call('delete', 'note', record_id=key)
    assert removed.ok, removed.message
    journal.undo(removed.data['personal_receipt']['id'])
    assert records.resolve('note', key)['content'] == 'Comparar preços'


@pytest.mark.parametrize('kind,fields', [
    ('sleep', {'hours': 25}), ('mood', {'score': 0}), ('finance', {'amount': float('inf')}),
    ('transfer', {'amount': 5, 'from_account': 'Banco', 'to_account': 'Banco'}),
    ('workout', {'exercises': [{'name': 'Supino', 'sets': 1.5}]}),
    ('rule', {'source': 'finance', 'target_kind': 'task', 'target_id': 'missing'}),
])
def test_invalid_records_do_not_write(kind, fields):
    result = PersonalRecordsTool().execute({'action': 'create', 'kind': kind, 'fields': fields})
    assert not result.ok
    assert records.records(kind) == []


def api(payload):
    return handle_personal_post('/api/personal', json.dumps(payload).encode(), SimpleNamespace())


def test_bulk_preview_conflict_confirmation_and_group_undo():
    for title in ['A', 'B']:
        call('create', 'task', fields={'title': title})
    status, preview = api({'action': 'bulk_preview', 'kind': 'task'})
    assert status == 200
    call('create', 'task', fields={'title': 'C'})
    assert api({'action': 'bulk_confirm', 'token': preview['token']})[0] == 400
    _, preview = api({'action': 'bulk_preview', 'kind': 'task'})
    status, done = api({'action': 'bulk_confirm', 'token': preview['token']})
    assert status == 200, done
    assert records.records('task') == []
    journal.undo(done['personal_receipt']['id'])
    assert len(records.records('task')) == 3


def test_preferences_and_personal_records():
    for kind, fields in [('sleep', {'hours': 7.5}), ('mood', {'score': 4}), ('personal', {'title': 'Diário', 'content': 'Dia tranquilo'})]:
        result = call('create', kind, fields=fields)
        assert result.ok, result.message
        assert call('update', kind, record_id='last', fields={'title': 'Corrigido'}).ok
    prefs = call('preferences_set', fields={'blocks': ['tasks'], 'reduced_motion': True, 'review': 'weekly'})
    assert prefs.ok
    assert records.today()['preferences']['blocks'] == ['tasks']


def test_tool_is_available_for_contextual_followups():
    from app.agent.tools.registry import registry
    for text in ['Na verdade foram 32', 'Foi no cartão', 'Desfaz esse registro']:
        assert 'personal_records' in registry.allowed_tool_names(provider='groq', user_text=text)


def test_missing_step_accepts_unified_tool_receipt():
    from app.agent.loop_policy import missing_requested_steps
    assert missing_requested_steps('Crie uma tarefa ler', [{'name': 'personal_records', 'status': 'succeeded', 'args': {'kind': 'task', 'action': 'create'}}]) == []


def test_cross_tool_creation_and_explicit_defaults_are_deduplicated(isolated):
    from app.agent.action_executor import ActionExecutor
    from app.agent.tool_guardrails import ToolCallGuardrailController
    from app.agent.tools.registry import registry
    from app.core.actions import ToolMetadata
    run = ActionExecutor(None, ToolCallGuardrailController(), lambda name, args, text: registry.execute_tool(name, args), metadata_for=lambda _: ToolMetadata(default_risk='low'), store=isolated.store)
    fields = {'amount': 38, 'description': 'Almoço', 'account': 'Cartão'}
    run.execute('personal_records', {'action': 'create', 'kind': 'finance', 'fields': fields}, 'Registre um almoço')
    run.execute('finance_tool', {'action': 'add', **fields, 'type': 'expense'}, 'Registre um almoço')
    run.execute('personal_records', {'action': 'create', 'kind': 'finance', 'fields': {**fields, 'type': 'expense'}}, 'Registre um almoço')
    assert len(records.records('finance')) == 1
    assert records.records('finance')[0]['account'] == 'Cartão'
    assert len(journal.history()) == 1


def test_note_tags_and_task_steps_and_checklist_edit():
    result = call('create', 'note', fields={'title': 'Ideia', 'content': 'Comprar creatina', 'tags': 'compras, saúde'})
    assert result.ok, result.message
    assert records.records('note', 'creatina')[0]['tags'] == ['compras', 'saúde']
    task = call('create', 'task', fields={'title': 'Preparar', 'subtasks': ['Separar roupa', 'Encher garrafa']})
    assert task.ok, task.message
    row = records.records('task')[0]
    result = call('update', 'task', record_id=row['id'], fields={'subtasks': [{'title': 'Separar roupa', 'completed': True}, {'title': 'Encher garrafa', 'completed': False}]})
    assert result.ok, result.message
    assert [r['completed'] for r in records.records('task')[0]['subtasks']] == [1, 0]
    checklist = call('create', 'checklist', fields={'title': 'Compras', 'text': 'Café, Papel'})
    assert checklist.ok, checklist.message
    result = call('update', 'checklist', record_id=records.records('checklist')[0]['id'], fields={'title': 'Mercado', 'text': 'Arroz, Feijão'})
    assert result.ok, result.message
    assert records.records('checklist')[0]['title'] == 'Mercado'


def test_manual_api_is_undoable_and_preserves_response_contract():
    from app.ui.panel.api.routes.system_routes import handle_system_routes
    result = []
    handle_system_routes('/api/finance', json.dumps({'action': 'add', 'amount': 5, 'description': 'Manual'}).encode(), lambda status, data: result.append((status, data)))
    assert result[0][0] == 200
    receipt = result[0][1]['personal_receipt']
    journal.undo(receipt['id'])
    assert not records.records('finance')


def test_interrupted_operation_is_visible_and_never_replayed():
    journal.initialize()
    from app.services.habits import get_db_connection
    with get_db_connection() as conn:
        conn.execute('INSERT INTO personal_pending VALUES (?,?,?,?,?,?)', ('interrupted', 'test', 'personal_records', '{}', '{}', 1))
    result = call('create', 'task', fields={'title': 'Não repetir'}, operation_id='interrupted')
    assert not result.ok and not records.records('task')
    assert journal.history('test')[0]['can_undo'] is False


def test_undo_keeps_unrelated_later_record():
    first = call('create', 'task', fields={'title': 'A'})
    call('create', 'task', fields={'title': 'B'})
    journal.undo(first.data['personal_receipt']['id'])
    assert [r['title'] for r in records.records('task')] == ['B']


def test_monthly_recurrence_keeps_end_of_month_anchor():
    result = call('create', 'recurrence', fields={'title': 'Conta', 'amount': 10, 'next_date': '2026-01-31'})
    key = result.data['record_id']
    assert call('pay', 'recurrence', record_id=key).ok
    assert call('pay', 'recurrence', record_id=key).ok
    assert records.records('recurrence')[0]['next_date'] == '2026-03-31'


def test_finance_relation_and_group_undo():
    call('create', 'task', fields={'title': 'Pagar Internet'})
    key = records.records('task')[0]['id']
    assert call('create', 'rule', fields={'source': 'finance', 'match_description': 'Internet', 'target_kind': 'task', 'target_id': key}).ok
    expense = call('create', 'finance', fields={'amount': 99, 'description': 'Internet'})
    assert expense.ok and records.records('task')[0]['completed']
    journal.undo(expense.data['personal_receipt']['id'])
    assert not records.records('task')[0]['completed'] and not records.records('finance')


def test_undo_specific_area_does_not_undo_latest_unrelated_record():
    call('create', 'finance', fields={'amount': 5, 'description': 'Café'})
    call('create', 'task', fields={'title': 'Ler'})
    assert call('undo', 'finance').ok
    assert not records.records('finance')
    assert records.records('task')[0]['title'] == 'Ler'


def test_undo_retry_cannot_advance_to_previous_change():
    call('create', 'finance', fields={'amount': 38, 'description': 'Almoço', 'account': 'Cartão'})
    call('update', 'finance', record_id='last', fields={'amount': 32})
    call('update', 'finance', record_id='last', fields={'account': 'Carteira'})
    assert call('undo', 'finance', operation_id='same-undo').ok
    assert call('undo', 'finance', operation_id='same-undo').ok
    assert records.records('finance')[0]['amount'] == 32
    assert records.records('finance')[0]['account'] == 'Cartão'
    from app.agent.action_executor import ActionExecutor
    assert ActionExecutor._write_key('personal_records', {'action': 'undo', 'kind': 'finance', 'record_id': 'last'}) == ActionExecutor._write_key('personal_records', {'action': 'undo', 'record_id': 'last', 'fields': {}})


def test_exercise_only_sync_cannot_drop_workout_session():
    from app.ui.panel.api.evolute import handle_evolute_sync_post
    from app.services.lifeos import LifeOSService
    assert call('create', 'workout', fields={'title': 'Peito', 'exercises': [{'name': 'Supino', 'sets': 3, 'reps': 10, 'weight': 20}]}).ok
    assert handle_evolute_sync_post({'data': {'lifeos_workouts': [], 'lifeos_water_test': 250}})[0] == 200
    bucket = LifeOSService.get_data_bucket()
    assert len(bucket['lifeos_workout_sessions']) == 1
    assert len(bucket['lifeos_workouts']) == 1


def test_undo_workout_by_session_id():
    assert call('create', 'workout', fields={'title': 'Peito'}).ok
    row = records.records('workout')[0]
    assert call('undo', 'workout', record_id=row['id']).ok
    assert records.records('workout') == []
