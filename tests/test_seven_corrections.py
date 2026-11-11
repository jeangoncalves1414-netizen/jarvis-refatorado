"""Regressões das correções de tools, mídia, verificação, pesquisa e saúde."""
import json

import pytest

from app.agent import effect_checks
from app.agent.action_executor import ActionExecutor
from app.agent.tool_guardrails import ToolCallGuardrailController
from app.agent.tools.base import ToolResult
from app.agent.tools.catalog import TOOL_CATALOG
from app.agent.tools.registry import ToolRegistry
from app.agent.tools.script_runner import ScriptRunnerTool
from app.agent.tools.video_intent import is_video_analysis_request
from app.agent.tools import web_search
from app.storage.action_store import ActionStore


@pytest.mark.parametrize('text,analysis', [
    ('resuma https://youtu.be/abc', True), ('abra https://youtu.be/abc', False),
    ('reproduza https://www.youtube.com/watch?v=abc', False),
    ('analise C:/Videos/a.mp4', True), ('abra C:/Videos/a.mp4', False),
    ('https://youtube.com/watch?v=abc', True), ('https://notyoutube.com/watch', False),
    ('https://youtube.com.evil.test/watch', False),
])
def test_video_action_respects_intent(text, analysis):
    assert is_video_analysis_request(text) is analysis


def test_marker_is_normalized_before_policy_and_receipt(tmp_path, monkeypatch):
    registry = ToolRegistry(base_folder=str(tmp_path))
    store = ActionStore(tmp_path / 'actions.sqlite3')
    monkeypatch.setattr(effect_checks, 'enabled', True)
    executor = ActionExecutor(frozenset({'file_manager'}), ToolCallGuardrailController(),
        lambda name, args, user: registry.execute_tool(name, args, {'user_line': user}),
        metadata_for=registry.get_tool_metadata, store=store)
    name, args = registry.resolve_marker('fs', 'mkdir:nova', 'crie a pasta nova')
    executor.execute(name, args, 'crie a pasta nova')
    assert executor.last_action.status == 'awaiting_confirmation'
    store.transition(executor.last_action.id, 'authorized')
    executor.execute_authorized(executor.last_action.id, name, args, 'crie a pasta nova')
    action = store.get(executor.last_action.id)
    assert name == 'file_manager' and args == {'action': 'mkdir', 'path': 'nova'}
    assert action.risk == 'high' and action.effect_status == 'confirmed'
    assert store.last_verified().id == action.id
    assert (tmp_path / 'nova').is_dir()
    assert registry.resolve_marker('file', r'read:C:\Docs\a.txt', '')[1]['path'] == r'C:\Docs\a.txt'


def test_local_video_marker_uses_local_analysis(tmp_path):
    registry = ToolRegistry(base_folder=str(tmp_path))
    name, args = registry.resolve_marker('video', 'C:/Videos/a.mp4', 'analise o vídeo')
    assert name == 'video_analyst' and args['action'] == 'analyze_local_video'
    assert args['file_path'] == 'C:/Videos/a.mp4'


def test_script_executes_once_after_kernel_approval(tmp_path, monkeypatch):
    store = ActionStore(tmp_path / 'journal.sqlite3')
    tool = ScriptRunnerTool()
    results = []
    def execute(name, args, user):
        result = tool.execute(args)
        results.append(result)
        return result
    executor = ActionExecutor(frozenset({'script_runner'}), ToolCallGuardrailController(), execute, metadata_for=TOOL_CATALOG.get, store=store)
    args = {'language': 'python', 'code': 'print(2 + 2)', 'description': 'calcular quatro'}
    assert 'exige confirmação' in executor.execute('script_runner', args, '')
    assert results == []
    action_id = executor.last_action.id
    store.transition(action_id, 'authorized')
    monkeypatch.setattr(effect_checks, 'enabled', True)
    message = executor.execute_authorized(action_id, 'script_runner', args, '')
    assert 'código de saída 0' in message and '__SCRIPT_CONFIRM__' not in message
    assert results[0].data['receipt']['effect_status'] == 'confirmed'
    with pytest.raises(ValueError):
        executor.execute_authorized(action_id, 'script_runner', args, '')
    assert len(results) == 1


def test_script_args_cannot_forge_kernel_authorization():
    result = ScriptRunnerTool().execute({'code': 'print(4)', 'authorized': True, 'confirmed': True})
    assert result.data['needs_confirmation'] is True


def test_folder_missing_and_timer_without_registration_are_unconfirmed(monkeypatch, tmp_path):
    monkeypatch.setattr(effect_checks, 'enabled', True)
    monkeypatch.setattr('app.agent.tools.timer.list_active_timers', lambda: [])
    for name, args, data in [
        ('file_manager', {'action': 'mkdir'}, {'path': str(tmp_path / 'missing')}),
        ('timer', {'action': 'set_timer'}, {'label': 'teste', 'fire_at': '2030-01-01'}),
    ]:
        assert effect_checks.check_effect(name, args, ToolResult(True, 'ok', data)).status == 'unconfirmed'


def test_research_preserves_dates_and_labels_failed_reads(monkeypatch):
    result = web_search._normalise_result({'title': 'Relatório', 'href': 'https://example.org/report', 'body': 'O estudo encontrou uma redução de 20%.', 'date': '2026-11-09'})
    monkeypatch.setattr(web_search, '_search', lambda *a: [result])
    monkeypatch.setattr(web_search, '_page_details', lambda url: {'excerpt': '', 'read_status': 'unavailable'})
    answer = web_search.WebSearchTool().execute({'action': 'research', 'query': 'estudo redução'})
    assert '2026-11-09' in answer.message and '[Relatório](https://example.org/report)' in answer.message
    assert 'página não verificada' in answer.message
    assert answer.data['steps'][-1]['detail'] == '0 de 1 fontes lidas'
    assert web_search._is_informative_result({'url': 'https://spacex.com/news', 'title': 'Lançamento', 'snippet': 'Texto'})


def test_generic_search_cannot_claim_factual_synthesis(monkeypatch):
    monkeypatch.setattr(web_search, '_search', lambda *a: [{'url': 'https://instagram.com/person', 'title': 'Perfil', 'snippet': 'Fotos'}])
    result = web_search.WebSearchTool().execute({'action': 'search', 'query': 'notícias da pessoa'})
    assert 'Evidência insuficiente' in result.message
    assert result.data['evidence_status'] == 'insufficient'


def test_page_reads_publication_metadata_and_article(monkeypatch):
    import io
    document = b'<html><meta property="article:published_time" content="2026-11-09"><nav>Menu</nav><article><p>Texto do estudo.</p></article></html>'
    monkeypatch.setattr(web_search.urllib.request, 'urlopen', lambda *a, **k: io.BytesIO(document))
    result = web_search._page_details('https://example.org/report')
    assert result == {'excerpt': 'Texto do estudo.', 'read_status': 'read', 'published_at': '2026-11-09'}


def test_health_exposes_actual_tools_and_no_mcp_credentials(tmp_path, monkeypatch):
    from app.ui.panel.api import mission_control
    store = ActionStore(tmp_path / 'journal.sqlite3')
    monkeypatch.setattr(mission_control, 'action_store', store)
    monkeypatch.setattr('app.agent.tools.registry.registry.tools', {'file_manager': object()})
    monkeypatch.setattr('app.mcp.manager.mcp_manager.list_servers', lambda: [{'id': 'test', 'name': 'Teste', 'status': 'offline', 'tools_count': 0, 'env': {'TOKEN': 'secret-value'}, 'command': 'secret-value', 'error': 'secret-value'}])
    details = mission_control.build_health_details()
    assert details['tools'] == ['file_manager']
    assert details['last_verified_action'] is None
    assert 'secret-value' not in json.dumps(details)
