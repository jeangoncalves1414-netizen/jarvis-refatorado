from __future__ import annotations

from app.agent.tools.catalog import TOOL_CATALOG, metadata_for
from app.core.actions import ToolMetadata


def test_catalog_has_explicit_policy_for_privileged_builtin_tools():
    for name in ("file_manager", "browser_agent", "whatsapp", "script_runner", "hacker_mode", "mobile_adb"):
        metadata = TOOL_CATALOG[name]
        assert metadata.default_risk in {"high", "critical"}
        assert metadata.requires_confirmation is True


def test_unknown_tool_keeps_its_own_metadata():
    fallback = ToolMetadata(("plugin",), "low")
    assert metadata_for("future_plugin", fallback) is fallback
