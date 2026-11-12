import pytest

from app.agent.orchestrator import AgentPlan
from app.agent.run_tracking import track_run
from app.storage import session_store as sessions


def test_failed_turn_survives_reload(isolated_conversation_journal):
    @track_run
    def turn(text, session_id):
        return AgentPlan(intent="error", summary="Provedor indisponível.", actions=[])

    result = turn("Olá", "s")
    rows = sessions.get_session_history("s")
    assert [r["content"] for r in rows] == ["Olá", "Provedor indisponível."]
    assert all(r["run_id"] == result.context["run_id"] for r in rows)
    assert rows[-1]["failed"]


def test_exception_is_saved_without_exception_secrets(isolated_conversation_journal):
    @track_run
    def turn(text, session_id):
        raise RuntimeError("secret-token")

    with pytest.raises(RuntimeError):
        turn("Execute", "s")
    rows = sessions.get_session_history("s")
    assert len(rows) == 2 and rows[-1]["failed"]
    assert "secret-token" not in str(rows)


def test_client_copy_and_repeated_backend_save_do_not_duplicate():
    client = [{"role": "user", "content": "Olá"}, {"role": "assistant", "content": "Oi", "run_id": "r1"}]
    sessions.save_session_history("s", client)
    sessions.save_turn("s", "r1", "Olá", "Oi", timestamp=1)
    sessions.save_turn("s", "r1", "Olá", "Oi", timestamp=1)
    sessions.save_session_history("s", client)
    assert len(sessions.get_session_history("s")) == 2
    # Repetir a mesma pergunta em outro turno é válido.
    sessions.save_turn("s", "r2", "Olá", "Oi", timestamp=2)
    sessions.save_session_history("s", client)
    assert len(sessions.get_session_history("s")) == 4
    sessions.save_session_history("s", [])
    assert len(sessions.get_session_history("s")) == 4
