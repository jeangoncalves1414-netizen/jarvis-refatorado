"""Tests for personal_records batch habit creation and read-only field handling."""
import pytest
from app.agent.tools.registry import ToolRegistry


pytestmark = pytest.mark.usefixtures('isolated_lote6_data')


def test_batch_habit_creation_in_one_receipt():
    """Batch of 3 habits created in one personal_records call."""
    registry = ToolRegistry()
    tool = registry.get_tool("personal_records")
    
    result = tool.execute({
        "action": "create",
        "kind": "habit",
        "fields": {
            "habits": [
                {"name": "Ler 20 minutos", "start_time": "21:00"},
                {"name": "Meditar 10 minutos", "start_time": "07:00"},
                {"name": "Escrever diário", "start_time": "22:00"},
            ]
        }
    })
    
    assert result.ok, result.message
    assert len(result.data.get("habit_ids", [])) == 3
    assert "3 hábito(s) criado(s)" in result.message or "Já existiam" in result.message


def test_readonly_fields_ignored_with_warning():
    """List keys (id, color, icon, created_at, etc.) are ignored with warning."""
    registry = ToolRegistry()
    tool = registry.get_tool("personal_records")
    
    result = tool.execute({
        "action": "create",
        "kind": "habit",
        "fields": {
            "habits": [
                {
                    "name": "Teste com campos somente leitura",
                    "start_time": "08:00",
                    "id": "should_be_ignored",
                    "color": "#ff0000",
                    "icon": "🔥",
                    "created_at": 123456,
                    "current_streak": 999,
                }
            ]
        }
    })
    
    assert result.ok
    assert "Ignorei campos somente leitura" in result.message
    ignored = result.data.get("ignored_fields", [])
    assert "id" in ignored or "color" in ignored or "icon" in ignored


def test_unknown_field_error_lists_accepted_fields():
    """Unknown field generates error listing accepted fields for habit."""
    registry = ToolRegistry()
    tool = registry.get_tool("personal_records")
    
    result = tool.execute({
        "action": "create",
        "kind": "habit",
        "fields": {
            "name": "Teste",
            "unknown_field_xyz": "value",
        }
    })
    
    assert not result.ok
    assert "Campos não reconhecidos" in result.message
    assert "unknown_field_xyz" in result.message
    assert "Aceitos para habit" in result.message


def test_repeated_batch_is_idempotent():
    """Repeating the same batch creation returns existing habits."""
    registry = ToolRegistry()
    tool = registry.get_tool("personal_records")
    
    batch = {
        "action": "create",
        "kind": "habit",
        "fields": {
            "habits": [
                {"name": "Idempotente A", "start_time": "09:00"},
                {"name": "Idempotente B", "start_time": "10:00"},
            ]
        }
    }
    
    # First call
    result1 = tool.execute(batch)
    assert result1.ok
    ids1 = result1.data.get("habit_ids", [])
    
    # Second call (should return existing)
    result2 = tool.execute(batch)
    assert result2.ok
    assert "Já existiam" in result2.message
    ids2 = result2.data.get("habit_ids", [])
    assert set(ids1) == set(ids2)


def test_reopen_habit_unchecks_today():
    """Reopen action on habit unchecks today's completion."""
    registry = ToolRegistry()
    pr_tool = registry.get_tool("personal_records")
    
    # Create and check a habit
    create_result = pr_tool.execute({
        "action": "create",
        "kind": "habit",
        "fields": {"name": "Reopen Test", "start_time": "08:00"}
    })
    assert create_result.ok
    habit_id = create_result.data["habit_ids"][0]
    
    # Check it
    from app.services.habits import HabitService
    HabitService.check_in(habit_id)
    habit = HabitService.get_habit(habit_id)
    assert habit["completed_today"] is True
    
    # Reopen via personal_records
    reopen_result = pr_tool.execute({
        "action": "reopen",
        "kind": "habit",
        "record_id": habit_id,
        "fields": {}
    })
    assert reopen_result.ok
    
    # Verify unchecked
    habit_after = HabitService.get_habit(habit_id)
    assert habit_after["completed_today"] is False


def test_real_payload_from_report_works():
    """Real payload example from report should work."""
    registry = ToolRegistry()
    tool = registry.get_tool("personal_records")
    
    # Simulated payload with title instead of name (should auto-map)
    result = tool.execute({
        "action": "create",
        "kind": "habit",
        "fields": {
            "habits": [
                {"title": "Estudar inglês 30min", "start_time": "19:00", "days_of_week": ["mon", "wed", "fri"]},
                {"title": "Fazer flexões", "start_time": "07:30"},
            ]
        }
    })
    
    assert result.ok
    assert len(result.data.get("habit_ids", [])) >= 2
