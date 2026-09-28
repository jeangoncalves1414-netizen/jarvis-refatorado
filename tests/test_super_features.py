"""
Unit tests for the 5 super features:
1. SmartLLMRouter
2. RealTimeStreamManager
3. DiagramCopilotService
4. CommandInspector
"""
import pytest
from app.services.llm_router import SmartLLMRouter, TaskCategory
from app.services.voice.realtime_stream import RealTimeStreamManager
from app.services.diagram_copilot import DiagramCopilotService
from app.services.command_inspector import CommandInspector, RiskLevel


# ── 1. SmartLLMRouter Tests ──────────────────────────────────────────────────

def test_smart_llm_router_classification():
    router = SmartLLMRouter()

    # Code classification
    cat_code = router.classify_prompt("Como refatorar uma função em python?")
    assert cat_code == TaskCategory.CODE_REFLEXION

    # Vision classification
    cat_vision = router.classify_prompt("O que tem nesta imagem?", has_image=True)
    assert cat_vision == TaskCategory.VISION_MULTIMODAL

    # Quick chat classification
    cat_chat = router.classify_prompt("Oi Jarvis, tudo bem?")
    assert cat_chat == TaskCategory.QUICK_CHAT


def test_smart_llm_router_failover():
    router = SmartLLMRouter()
    route = router.route("Qual a diferença entre REST e GraphQL?")
    assert route.primary_provider in ("gemini", "groq")

    # Simulate Gemini error
    router.mark_provider_error("gemini")
    assert not router.is_provider_healthy("gemini")


# ── 2. RealTimeStreamManager Tests ───────────────────────────────────────────

def test_realtime_stream_manager():
    mgr = RealTimeStreamManager()
    mgr.register_session("session_ws_1", websocket=None)

    # Telemetry should be available
    telem = mgr.get_session_telemetry("session_ws_1")
    assert telem["ok"]
    assert telem["session_id"] == "session_ws_1"

    mgr.unregister_session("session_ws_1")


# ── 3. DiagramCopilotService Tests ───────────────────────────────────────────

def test_diagram_copilot_flowchart():
    steps = [
        ("Cliente", "Solicitação HTTP", "Servidor"),
        ("Servidor", "Consulta Banco", "BancoDeDados"),
        ("BancoDeDados", "Retorna Dados", "Servidor"),
    ]
    res = DiagramCopilotService.generate_flowchart("Fluxo de Dados", steps)
    assert res.ok
    assert "graph TD" in res.mermaid_code
    assert "Cliente" in res.mermaid_code
    assert "Servidor" in res.mermaid_code


def test_diagram_copilot_sequence():
    interactions = [
        ("User", "Login", "AuthService"),
        ("AuthService", "Validate JWT", "DB"),
    ]
    res = DiagramCopilotService.generate_sequence("Sequência Login", interactions)
    assert res.ok
    assert "sequenceDiagram" in res.mermaid_code
    assert "AuthService" in res.mermaid_code


# ── 4. CommandInspector Tests ────────────────────────────────────────────────

def test_command_inspector_safe():
    inspector = CommandInspector()
    audit = inspector.inspect("echo 'Hello World'")
    assert audit.risk_level == RiskLevel.SAFE
    assert audit.risk_score == 0
    assert audit.can_auto_execute


def test_command_inspector_high_risk():
    inspector = CommandInspector()
    audit = inspector.inspect("rm -rf /var/log/system.log")
    assert audit.risk_score > 30
    assert audit.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL)

    preview = inspector.generate_dry_run_preview("rm -rf /var/log/system.log")
    assert "Análise de Segurança do Comando" in preview
    assert "/var/log/system.log" in preview
