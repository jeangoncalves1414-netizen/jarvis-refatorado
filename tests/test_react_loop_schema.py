"""Tests for ReAct loop schema compaction with fields preservation."""
import pytest
from app.agent.react_loop import _compact_schema
from app.agent.tools.registry import ToolRegistry


def test_compact_schema_preserves_object_descriptions():
    """_compact_schema adds descriptions for object params."""
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["create", "list"]},
            "fields": {
                "type": "object",
                "description": "Campos: name, start_time, days_of_week para hábito"
            },
            "simple": {"type": "string"}
        }
    }
    
    compact = _compact_schema(parameters)
    assert "action" in compact
    assert compact["action"] == "string (create|list)"
    assert "fields" in compact
    assert " — " in compact["fields"]
    assert "Campos" in compact["fields"]
    assert "simple" in compact
    assert " — " not in compact["simple"]  # No description


def test_personal_records_parameters_have_fields_description():
    """personal_records tool has fields parameter with habit-related description."""
    registry = ToolRegistry()
    tool = registry.get_tool("personal_records")
    if not tool:
        pytest.skip("personal_records not registered")
    
    params = tool.parameters
    fields_spec = params.get("properties", {}).get("fields", {})
    assert fields_spec.get("type") == "object"
    assert "description" in fields_spec
    # Description should mention habits
    desc = fields_spec["description"].lower()
    assert "habit" in desc or "hábito" in desc
    
    # Compact schema should preserve this
    compact = _compact_schema(params)
    assert "fields" in compact
    assert "object" in compact["fields"]
