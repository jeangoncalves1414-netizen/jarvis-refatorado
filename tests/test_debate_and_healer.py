"""
Unit tests for MultiModelDebateEngine and TerminalAutoHealer.
"""
import pytest
from app.services.model_debate import MultiModelDebateEngine, DebateResult
from app.services.terminal_healer import TerminalAutoHealer, HealFixProposal
from app.agent.swarm import APIKeyRotator, AgentSwarmManager


# ── 1. MultiModelDebateEngine Tests ──────────────────────────────────────────

def test_multi_model_debate_consensus():
    engine = MultiModelDebateEngine(max_rounds=2)

    def proposer(prob: str) -> str:
        return "def add(a, b):\n    return a + b"

    def critic(prob: str, code: str) -> str:
        return "Código correto e sem falhas."

    def synthesizer(prob: str, code: str, critique: str) -> str:
        return code

    result = engine.run_debate("Crie uma função de soma em Python.", proposer, critic, synthesizer)
    assert result.ok
    assert result.consensus_reached
    assert "add" in result.final_solution
    assert result.rounds_executed == 1


def test_multi_model_debate_refinement():
    engine = MultiModelDebateEngine(max_rounds=2)

    def proposer(prob: str) -> str:
        return "def divide(a, b):\n    return a / b"

    def critic(prob: str, code: str) -> str:
        return "Atenção: divisão por zero não tratada!"

    def synthesizer(prob: str, code: str, critique: str) -> str:
        return "def divide(a, b):\n    if b == 0: return None\n    return a / b"

    result = engine.run_debate("Crie uma função de divisão segura.", proposer, critic, synthesizer)
    assert result.ok
    assert "if b == 0:" in result.final_solution


# ── 2. TerminalAutoHealer Tests ──────────────────────────────────────────────

def test_terminal_healer_module_not_found():
    healer = TerminalAutoHealer()
    res = healer.diagnose_and_fix("python script.py", "ModuleNotFoundError: No module named 'requests'")
    assert res.ok
    assert res.error_type == "Dependência Python Ausente"
    assert "pip install requests" in res.suggested_command
    assert res.can_auto_apply


def test_terminal_healer_permission_denied():
    healer = TerminalAutoHealer()
    res = healer.diagnose_and_fix("python script.py", "PermissionError: [Errno 13] Permission denied: '/var/data'")
    assert res.ok
    assert "Permissão" in res.error_type


# ── 3. APIKeyRotator Tests ───────────────────────────────────────────────────

def test_api_key_rotator(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEYS", "key_alpha,key_beta,key_gamma")
    rotator = APIKeyRotator("GEMINI_API_KEY")
    assert len(rotator.keys) == 3
    assert rotator.get_next_key() == "key_alpha"
    assert rotator.get_next_key() == "key_beta"
    assert rotator.get_next_key() == "key_gamma"
    assert rotator.get_next_key() == "key_alpha"
