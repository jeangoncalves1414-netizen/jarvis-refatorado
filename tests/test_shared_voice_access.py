from types import SimpleNamespace

import pytest

from app.agent.orchestrator import AgentOrchestrator, AgentPlan
from app.services import identity, identity_access as policy, identity_context as evidence, public_conversation
from app.services.llm import LLMService
from app.storage import session_store as store


@pytest.fixture
def people(isolated_lote6_data):
    owner = identity.IdentityService.enroll_admin('Jean', 'password123')['profile']
    guest = identity.IdentityService.enroll_profile('Ana', 'user', 'password123')['profile']
    return owner, guest


def proof(profile, method='voice'):
    return evidence.issue({'matched': True, 'profile': profile}, method=method)


def test_text_uses_full_history_without_biometric_token(people):
    agent = AgentOrchestrator.__new__(AgentOrchestrator)
    agent.llm_service = None
    store.save_turn('s', 'old', 'Meu projeto se chama Orion.', 'Anotado.', timestamp=1)
    seen = []
    def dispatch(text, sid, mode, history, *args):
        seen.extend(history)
        return AgentPlan(intent='general', summary='Orion', actions=[])
    agent._dispatch_request = dispatch
    result = agent.handle_request('Como se chama?', session_id='s', origin='chat')
    assert result.summary == 'Orion' and not result.context.get('identity_restricted')
    assert 'Orion' in str(seen)
    assert len(store.get_session_history('s')) == 4


def test_voice_owner_then_unknown_cannot_reuse_owner_context(people):
    owner, _ = people
    store.save_turn('s', 'private', 'Meu segredo pessoal', 'Informação privada.', timestamp=1)
    agent = AgentOrchestrator.__new__(AgentOrchestrator)
    seen = []
    agent.llm_service = SimpleNamespace(build_contents=LLMService.build_contents,
        generate=lambda contents, **kw: seen.append(str(contents) + str(kw)) or SimpleNamespace(text='Conversa pública.'))
    agent._dispatch_request = lambda *a: AgentPlan(intent='general', summary='Informação privada.', actions=[])
    first = agent.handle_request('Lembre meu segredo', session_id='s', origin='voice', identity_token=proof(owner))
    assert not first.context.get('identity_restricted')
    second = agent.handle_request('Repita a resposta anterior', session_id='s', origin='voice')
    assert second.context['identity_restricted']
    assert 'segredo' not in ''.join(seen) and 'Informação privada' not in ''.join(seen)
    public_conversation.respond(agent.llm_service, 'Continue a conversa pública', 's')
    assert 'Conversa pública.' in seen[-1]


def test_face_cannot_authorize_voice_and_legacy_private_grant_is_ignored(people):
    owner, guest = people
    face = evidence.consume(proof(owner, 'face'))
    assert policy.access(face, origin='voice') == (False, None)
    data = identity._read()
    data['profiles'][1]['permissions'] = ['assistant_private']
    identity._write(data)
    assert not policy.access(evidence.consume(proof(guest)), origin='voice')[0]
    merged = evidence.merge_turns([proof(owner, 'face')])
    assert not policy.access(evidence.consume(merged['evidence_token']), origin='voice')[0]


def test_permission_levels_never_grant_personal_data(people):
    _, guest = people
    for level in ['visitor', 'user', 'delegate']:
        profile = policy.set_permission({'profile_id': guest['id'], 'admin_password': 'password123', 'level': level})['profile']
        verified = evidence.consume(proof(profile))
        allowed, actual = policy.access(verified, origin='voice')
        assert not allowed and policy.command_level(actual) == level
        assert policy.command_allowed(actual, 'timer', {'action': 'set_timer'}) == (level != 'visitor')
        assert policy.command_allowed(actual, 'system_control', {'action': 'set_brightness'}) == (level == 'delegate')
        for name in ['memory', 'vault_search', 'file_manager', 'script_runner', 'browser', 'calendar']:
            assert not policy.command_allowed(actual, name, {})
        assert not policy.command_allowed(actual, 'timer', {'action': 'list'})
        assert not policy.command_allowed(actual, 'system_control', {'action': 'open_app', 'app_name': 'cmd'})
        assert not policy.command_allowed(actual, 'realtime', {'action': 'get_weather'})


def test_delegate_commands_execute_with_no_owner_context_and_revocation(people):
    from app.agent.tools.base import ToolResult
    from app.core.actions import ToolMetadata
    _, guest = people
    guest = policy.set_permission({'profile_id': guest['id'], 'admin_password': 'password123', 'level': 'delegate'})['profile']
    calls = []
    tool = SimpleNamespace(description='fixture', parameters={'properties': {'action': {}, 'app_name': {}}})
    registry = SimpleNamespace(get_tool=lambda name: tool if name == 'system_control' else None,
        get_tool_metadata=lambda _: ToolMetadata(('system_control',), 'observe'),
        execute_tool=lambda name, args, **kw: calls.append((name, args, kw)) or ToolResult(True, 'Brilho ajustado.'))
    def model(**kw):
        assert 'OWNER_SECRET' not in str(kw['messages']) + kw['system_instruction']
        assert len(kw['tools']) == 1
        assert 'list_processes' not in kw['tools'][0]['parameters']['properties']['action']['enum']
        kw['on_function_call']('memory', {'action': 'list'})
        kw['on_function_call']('system_control', {'action': 'set_brightness', 'level': 40})
        policy.set_permission({'profile_id': guest['id'], 'admin_password': 'password123', 'level': 'visitor'})
        kw['on_function_call']('system_control', {'action': 'set_brightness', 'level': 50})
        return 'Tudo feito'
    store.save_session_history('s', [{'role': 'user', 'content': 'OWNER_SECRET'}])
    agent = AgentOrchestrator.__new__(AgentOrchestrator)
    agent.llm_service = SimpleNamespace(chat_with_functions_stream=model)
    agent.registry = registry
    result = agent.handle_request('Ajuste o brilho', session_id='s', origin='voice', identity_token=proof(guest))
    assert result.context['identity_restricted'] and 'Brilho ajustado' in result.summary
    assert len(calls) == 1 and calls[0][1]['level'] == 40
    assert 'semantic_memory' not in calls[0][2]['context']


def test_original_history_stays_saved_after_compacted_turn(people):
    from app.services import context_compaction as compact
    rows = [{'role': 'user' if i % 2 == 0 else 'assistant', 'content': f'{i}: ' + 'x' * 700} for i in range(20)]
    store.save_session_history('s', rows)
    agent = AgentOrchestrator.__new__(AgentOrchestrator)
    agent.llm_service = SimpleNamespace(ask=lambda *a, **k: 'Objetivo: terminar projeto.')
    observed = []
    agent._dispatch_request = lambda text, sid, mode, history, *args: observed.extend(history) or AgentPlan(intent='general', summary='Continuando.', actions=[])
    agent.handle_request('Continue', session_id='s', origin='chat')
    assert len(observed) == 7 and 'Objetivo' in observed[0]['content']
    persisted = store.get_session_history('s')
    assert persisted[:20] == rows and len(persisted) == 22
    result = agent.handle_request('Qual foi minha primeira mensagem?', session_id='s', origin='chat')
    assert rows[0]['content'] in result.summary
