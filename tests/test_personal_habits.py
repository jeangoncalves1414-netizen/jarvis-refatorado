from datetime import date, timedelta
from types import SimpleNamespace
import json

import pytest


@pytest.fixture
def catalogue(isolated_lote6_data):
    from app.services.habits import HabitService
    from app.services.lifeos import LifeOSService
    from app.services.personal_habits import PersonalHabits, public_evolute_id
    HabitService.create_habit('shared', 'Caminhar')
    tomorrow = (date.today() + timedelta(days=1)).weekday()
    HabitService.create_habit('later', 'Só amanhã', days_of_week=[tomorrow])
    LifeOSService.save_data_bucket({
        'lifeos_habits': [{'id': 'shared', 'title': 'Leitura', 'streak': 3, 'bestStreak': 5,
                           'isPriority': True, 'createdAt': '2020-01-01'}],
        'lifeos_infinite_notes': 'Preservar caderno',
    })
    return PersonalHabits, LifeOSService, public_evolute_id('shared')


def test_panel_schedule_and_agent_share_both_stores(catalogue, monkeypatch):
    habits, lifeos, evo_id = catalogue
    from app.ui.panel.api.checklists import handle_checklists_get, handle_checklists_post
    status, listing = handle_checklists_get(['api', 'lifeos', 'habits'], SimpleNamespace(path='/api/lifeos/habits?today=1'))
    assert status == 200
    assert {h['id'] for h in listing['habits']} == {'shared', evo_id}
    for changed in (True, False):
        status, result = handle_checklists_post(f'/api/lifeos/habits/{evo_id}/toggle', b'{"completed":true}', None)
        assert status == 200 and result['habit']['changed'] is changed
        assert result['habit']['current_streak'] == 4
    assert not habits.get_habit('shared')['completed_today']
    assert habits.get_habit(evo_id)['completed_at'] > 0
    assert lifeos.get_data_bucket()['lifeos_infinite_notes'] == 'Preservar caderno'
    assert lifeos.toggle_habit('Caminhar')['changed']
    assert lifeos.get_daily_summary()['habits']['completed'] == 2
    assert not lifeos.toggle_habit('Leitura')['changed']
    from app.ui.panel.api import evolute
    monkeypatch.setattr(evolute, '_get_db_file', lifeos.get_db_path)
    status, summary = evolute.handle_evolute_status_get()
    assert status == 200 and summary['score'] == 100
    assert {h['id'] for h in summary['habits']} == {'shared', evo_id}


def test_failed_write_and_ambiguous_name_do_not_claim_completion(catalogue, monkeypatch):
    habits, lifeos, evo_id = catalogue
    habits.update_habit('shared', name='Leitura')
    assert not lifeos.toggle_habit('Leitura')['ok']
    monkeypatch.setattr(lifeos, 'save_data_bucket', lambda _: False)
    with pytest.raises(OSError):
        habits.check_in(evo_id)
    assert not habits.get_habit(evo_id)['completed_today']


def test_agent_aliases_receipt_and_idempotent_check(catalogue):
    habits, lifeos, evo_id = catalogue
    from app.agent.tools.lifestyle_tools import HabitTool
    from app.agent.tools.lifeos_tool import LifeOSTool
    from app.agent.popups import popups_for_result
    tool = HabitTool()
    for action in ('complete', 'done', 'check'):
        habits.uncheck_in(evo_id)
        args = {'action': action, 'habit_id': evo_id}
        result = tool.execute(args)
        assert result.ok
        assert popups_for_result(tool.name, args, result)[0][2]['checked_ids'] == [evo_id]
        assert popups_for_result(tool.name, args, tool.execute(args)) == []
    undo = {'action': 'uncheck_habit', 'habit_name': 'Leitura'}
    result = LifeOSTool().execute(undo)
    assert result.ok
    assert popups_for_result('lifeos_tool', undo, result)[0][2]['updated_ids'] == [evo_id]
    assert not habits.get_habit(evo_id)['completed_today']


def test_update_preserves_source_and_other_fields(catalogue):
    habits, lifeos, evo_id = catalogue
    habits.update_habit(evo_id, name=None, isPriority=None, start_time='08:30')
    row = habits.get_habit(evo_id)
    assert row['name'] == 'Leitura' and row['isPriority'] and row['start_time'] == '08:30'
    from app.ui.panel.api.checklists import handle_checklists_post
    status, _ = handle_checklists_post(f'/api/lifeos/habits/{evo_id}/toggle', json.dumps({'completed': 'false'}).encode(), None)
    assert status == 400 and not habits.get_habit(evo_id)['completed_today']
