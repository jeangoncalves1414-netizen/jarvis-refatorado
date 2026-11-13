import pytest

from app.agent.tools.run_control import RunControlTool
from app.core.runs import current_run, RunCancelled
from app.storage.action_store import ActionStore


@pytest.fixture
def conversation(tmp_path):
    store = ActionStore(tmp_path / 'runs.sqlite3')
    previous = store.create_run(session_id='chat-a', mode='general')
    other = store.create_run(session_id='chat-b', mode='general')
    current = store.create_run(session_id='chat-a', mode='general')
    token = current_run.set((store, current.id))
    yield store, previous, other, current
    current_run.reset(token)


def test_status_uses_receipts_and_excludes_self_and_other_chats(conversation):
    store, previous, other, current = conversation
    store.update_run_progress(previous.id, {'phase': 'waiting', 'step': 1})
    result = RunControlTool().execute({'action': 'status'})
    assert result.ok
    assert [item['id'] for item in result.data['results']] == [previous.id]
    assert result.data['results'][0]['progress']['phase'] == 'waiting'
    assert other.id not in result.message and current.id not in result.message


def test_cancel_is_cooperative_and_does_not_claim_completion(conversation):
    store, previous, _, _ = conversation
    result = RunControlTool().execute({'action': 'cancel', 'run_id': previous.id})
    assert result.ok and result.data['status'] == 'cancel_requested'
    assert 'aguardando' in result.message and 'não foram desfeitas' in result.message
    with pytest.raises(RunCancelled):
        store.check_cancelled(previous.id)
    store.finish_run(previous.id)
    assert RunControlTool().execute({'action': 'cancel', 'run_id': previous.id}).data['status'] == 'cancelled'


def test_status_does_not_present_execution_budget_as_remaining_work(conversation):
    store, previous, _, _ = conversation
    progress = {'phase': 'waiting', 'step': 1, 'max_steps': 8, 'model_calls': 1,
                'max_model_calls': 10, 'wait_remaining': 179, 'wait_total': 180}
    store.update_run_progress(previous.id, progress)
    result = RunControlTool().execute({'action': 'status'})
    assert result.data['results'][0]['progress'] == {
        'phase': 'waiting', 'step': 1, 'wait_remaining': 179, 'wait_total': 180}
    assert 'prazo total não são conhecidos' in result.message
    assert 'apenas a espera atual' in result.message
    assert store.run_details(previous.id)['run']['progress'] == progress


@pytest.mark.parametrize('target', ['self', 'other', 'missing', None])
def test_cancel_never_guesses_a_target(conversation, target):
    store, previous, other, current = conversation
    target = {'self': current.id, 'other': other.id}.get(target, target)
    result = RunControlTool().execute({'action': 'cancel', 'run_id': target})
    assert not result.ok
    for run in (previous, other, current):
        store.check_cancelled(run.id)


def test_finished_and_unscoped_requests_are_not_cancelled(conversation):
    store, previous, _, _ = conversation
    store.finish_run(previous.id)
    assert not RunControlTool().execute({'action': 'cancel', 'run_id': previous.id}).ok
    token = current_run.set(None)
    try:
        assert not RunControlTool().execute({'action': 'status'}, {'session_id': 'chat-a'}).ok
    finally:
        current_run.reset(token)


def test_older_active_request_is_not_hidden_by_recent_completed_ones(conversation):
    store, previous, _, _ = conversation
    for _ in range(8):
        run = store.create_run(session_id='chat-a', mode='general')
        store.finish_run(run.id)
    result = RunControlTool().execute({'action': 'status'})
    assert previous.id in result.message


def test_tool_discovery_and_readonly_retrospective(conversation):
    from app.agent.tools.registry import ToolRegistry
    from app.agent.action_executor import ActionExecutor
    from app.agent.tool_guardrails import ToolCallGuardrailController
    from app.agent.tools.catalog import TOOL_CATALOG

    registry = ToolRegistry()
    for text in ('O que está em andamento?', 'Cancele esse pedido', 'O que você executou?',
                 'Qual o progresso?', 'Quanto falta para terminar?', 'Se o limite é 8, faltam 7 etapas?'):
        for narrow in (False, True):
            assert 'run_control' in registry.allowed_tool_names('general', 'groq', text, narrow=narrow)
    assert 'run_control' not in registry.allowed_tool_names('tutor')
    executor = ActionExecutor(frozenset({'run_control'}), ToolCallGuardrailController(),
                              lambda name, args, text: RunControlTool().execute(args),
                              metadata_for=TOOL_CATALOG.get)
    assert 'estado consultado agora' in executor.execute('run_control', {'action': 'status'}, 'O que você executou?')
    assert 'não uma nova execução' in executor.execute('run_control', {'action': 'cancel'}, 'O que você executou?')


def test_cancellation_request_cannot_finish_with_only_a_status_lookup():
    from app.agent.loop_policy import missing_requested_steps

    steps = [{'name': 'run_control', 'status': 'succeeded', 'args': {'action': 'status'}}]
    message = 'Pode parar a espera que está em andamento nesta conversa. Cancele só essa espera e me diga o estado real.'
    assert 'run_control action=cancel' in missing_requested_steps(message, steps)[0]
    for text in ('Consulte o pedido, não cancele a espera.', 'O pedido foi cancelado?',
                 'Cancele meu compromisso de amanhã.', 'Qual o progresso da espera?'):
        assert missing_requested_steps(text, steps) == []
    for status in ('succeeded', 'failed'):
        attempted = steps + [{'name': 'run_control', 'status': status,
                               'args': {'action': 'cancel', 'run_id': 'run_test'}}]
        assert missing_requested_steps(message, attempted) == []
