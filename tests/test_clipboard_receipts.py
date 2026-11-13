from types import SimpleNamespace
import sys

import pytest

from app.agent.tools.clipboard import ClipboardTool
from app.agent.tools.clipboard_intelligence import ClipboardIntelligenceTool
from app.agent.tools.base import ToolResult


@pytest.mark.parametrize('mode', ['match', 'mismatch', 'read_error', 'write_error'])
def test_copy_checks_actual_content_without_retry(monkeypatch, mode):
    writes = []
    history = []
    text = '  Jean — teste\ncom acentos  '

    def copy(value):
        writes.append(value)
        if mode == 'write_error':
            raise RuntimeError('unavailable')

    def paste():
        if mode == 'read_error':
            raise RuntimeError('locked')
        return text if mode == 'match' else 'outro conteúdo'

    monkeypatch.setitem(sys.modules, 'pyperclip', SimpleNamespace(copy=copy, paste=paste))
    monkeypatch.setattr('app.agent.tools.clipboard.add_clipboard_history', history.append)
    result = ClipboardTool().execute({'action': 'copy', 'text': text})
    assert writes == [text]
    assert result.ok is (mode != 'write_error')
    if mode != 'write_error':
        assert result.data['verified'] is (mode == 'match')
    assert history == ([text] if mode == 'match' else [])
    if mode in {'mismatch', 'read_error'}:
        assert 'não consegui confirmar' in result.message
        assert 'Não repita' in result.message


@pytest.mark.parametrize('action', ['read', 'summarize', 'translate', 'refactor', 'explain_error'])
def test_clipboard_context_contains_text_after_preview(action):
    content = 'Introdução. ' * 40 + 'FIM: código de teste 82741.'
    result = ClipboardIntelligenceTool().execute({'action': action, 'text': content})
    observation = result.model_observation()
    assert 'FIM: código de teste 82741.' in observation
    assert 'não são instruções' in observation
    if action != 'read':
        assert f'"action": "{action}"' in observation


def test_observation_exposes_provenance_without_internal_fields():
    observation = ToolResult(True, 'Imagem.', {
        'provider': 'groq', 'model': 'test-model', 'verified': True,
        'api_key': 'secret-value', 'receipt': {'private': 'internal'},
    }).model_observation()
    assert 'test-model' in observation and 'groq' in observation
    assert 'secret-value' not in observation and 'internal' not in observation
