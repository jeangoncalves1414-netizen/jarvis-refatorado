from __future__ import annotations

from app.agent.action_executor import ActionExecutor
from app.agent.tool_guardrails import ToolCallGuardrailController
from app.agent.tools.base import ToolResult
from app.core.actions import ToolMetadata
from app.storage.action_store import ActionStore
from app.agent import effect_checks
import pytest


def test_native_function_style_execution_cannot_bypass_high_risk_proposal(tmp_path):
    calls: list[str] = []
    executor = ActionExecutor(
        frozenset({"browser_agent"}), ToolCallGuardrailController(),
        lambda name, args, user: calls.append(name) or ToolResult(True, "executado"),
        metadata_for=lambda _name: ToolMetadata(("browser",), "high", requires_confirmation=True),
        store=ActionStore(tmp_path / "journal.jsonl"), source="function:test",
    )
    response = executor.execute("browser_agent", {"goal": "abrir site"}, "abra")
    assert "exige confirmação" in response
    assert calls == []
    assert executor.last_action is not None
    assert executor.last_action.status == "awaiting_confirmation"


@pytest.mark.parametrize('effect,user_text,expected', [('confirmed', 'Abra Roblox', 1), ('unconfirmed', 'Abra Roblox', 3), ('confirmed', 'Abra Roblox três vezes', 3)])
def test_consecutive_openings_reuse_only_confirmed_receipts(tmp_path, monkeypatch, effect, user_text, expected):
    monkeypatch.setattr(effect_checks, 'capture_before', lambda *args: None)
    monkeypatch.setattr(effect_checks, 'check_effect', lambda *args: effect_checks.EffectCheck(effect, 'janela observada'))
    calls = []
    store = ActionStore(tmp_path / 'opens.sqlite3')
    executor = ActionExecutor(None, ToolCallGuardrailController(), lambda name, args, user: calls.append(args) or ToolResult(True, 'abertura solicitada'), metadata_for=lambda _: ToolMetadata(default_risk='observe'), store=store)
    ids = []
    for url in ['https://roblox.com', 'https://www.roblox.com/', 'https://roblox.com']:
        executor.execute('web_search', {'action': 'open_url', 'query': url}, user_text)
        ids.append(executor.last_action.id)
    assert len(calls) == len(set(ids)) == len(store.list()) == expected
    executor.execute('web_search', {'action': 'open_url', 'query': 'https://roblox.com/games?id=42'}, user_text)
    assert len(calls) == expected + 1


def test_complaint_never_reexecutes_an_action(tmp_path):
    calls = []
    executor = ActionExecutor(None, ToolCallGuardrailController(), lambda *args: calls.append(args), store=ActionStore(tmp_path / 'complaint.sqlite3'))
    message = executor.execute('web_search', {'action': 'open_url', 'query': 'https://roblox.com'}, 'o que está acontecendo por que você está abrindo Box três vezes')
    assert 'explicação' in message
    assert not calls and executor.last_action is None
