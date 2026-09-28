from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from app.agent.tools.system_control import SystemControlTool, ALLOWED_APPS


class TestSystemControlSecurity:
    """Test suite for system control security and validation."""
    
    def test_validate_app_name_with_allowed_app(self):
        """Test that allowed app names are validated correctly."""
        tool = SystemControlTool()
        
        for app_name, exe_name in ALLOWED_APPS.items():
            result = tool._validate_app_name(app_name)
            assert result == exe_name
    
    def test_validate_app_name_case_insensitive(self):
        """Test that app name validation is case-insensitive."""
        tool = SystemControlTool()
        
        assert tool._validate_app_name("NOTEPAD") == "notepad.exe"
        assert tool._validate_app_name("CALC") == "calc.exe"
        assert tool._validate_app_name("NoTePaD") == "notepad.exe"
    
    def test_validate_app_name_with_whitespace(self):
        """Test that app name validation handles whitespace."""
        tool = SystemControlTool()
        
        assert tool._validate_app_name("  notepad  ") == "notepad.exe"
        assert tool._validate_app_name("\tcalc\t") == "calc.exe"
    
    def test_validate_app_name_with_disallowed_app(self):
        """Test that disallowed app names are rejected."""
        tool = SystemControlTool()
        
        assert tool._validate_app_name("malicious.exe") is None
        assert tool._validate_app_name("powershell") is None
        assert tool._validate_app_name("cmd /c") is None
        assert tool._validate_app_name("notepad.exe & malicious") is None
    
    def test_validate_app_name_with_empty_string(self):
        """Test that empty app names are rejected."""
        tool = SystemControlTool()
        
        assert tool._validate_app_name("") is None
        assert tool._validate_app_name("   ") is None
        assert tool._validate_app_name(None) is None
    
    def test_validate_app_name_with_special_characters(self):
        """Test that app names with special characters are rejected."""
        tool = SystemControlTool()
        
        assert tool._validate_app_name("notepad; malicious") is None
        assert tool._validate_app_name("notepad && calc") is None
        assert tool._validate_app_name("notepad|calc") is None
        assert tool._validate_app_name("notepad > output.txt") is None
    
    @patch('subprocess.Popen')
    def test_open_app_with_allowed_app(self, mock_popen):
        """Test that allowed apps can be opened."""
        tool = SystemControlTool()
        mock_popen.return_value = MagicMock()
        
        result = tool.execute({"action": "open_app", "app_name": "notepad"})
        
        assert result.ok is True
        assert "iniciado com sucesso" in result.message.lower()
        mock_popen.assert_called_once_with("notepad.exe", shell=False)
    
    @patch('subprocess.Popen')
    def test_open_app_with_disallowed_app(self, mock_popen):
        """Test that disallowed apps are rejected."""
        tool = SystemControlTool()
        
        result = tool.execute({"action": "open_app", "app_name": "malicious"})
        
        assert result.ok is False
        assert "não é permitido" in result.message.lower()
        mock_popen.assert_not_called()
    
    @patch('subprocess.Popen')
    def test_open_app_without_shell_true(self, mock_popen):
        """Test that shell=True is not used when opening apps."""
        tool = SystemControlTool()
        mock_popen.return_value = MagicMock()
        
        result = tool.execute({"action": "open_app", "app_name": "calc"})
        
        assert result.ok is True
        # Verify shell=False is used
        call_args = mock_popen.call_args
        assert call_args[1].get('shell') is False
    
    @patch('subprocess.Popen')
    def test_open_app_with_command_injection_attempt(self, mock_popen):
        """Test that command injection attempts are blocked."""
        tool = SystemControlTool()
        
        # Try various injection patterns
        injection_attempts = [
            "notepad && malicious",
            "notepad; calc",
            "notepad | powershell",
            "notepad > output.txt",
            "notepad < input.txt",
        ]
        
        for attempt in injection_attempts:
            result = tool.execute({"action": "open_app", "app_name": attempt})
            assert result.ok is False, f"Injection attempt not blocked: {attempt}"
        
        mock_popen.assert_not_called()
    
    @patch('subprocess.Popen')
    def test_open_app_with_nonexistent_app(self, mock_popen):
        """Test that nonexistent apps are handled gracefully."""
        tool = SystemControlTool()
        mock_popen.side_effect = FileNotFoundError()
        
        result = tool.execute({"action": "open_app", "app_name": "notepad"})
        
        assert result.ok is False
        assert "não encontrado" in result.message.lower()
    
    def test_open_app_with_empty_app_name(self):
        """Test that empty app names are rejected."""
        tool = SystemControlTool()
        
        result = tool.execute({"action": "open_app", "app_name": ""})
        
        assert result.ok is False
        assert "não é permitido" in result.message.lower()
    
    def test_unknown_action_is_rejected(self):
        """Test that unknown actions are rejected."""
        tool = SystemControlTool()
        
        result = tool.execute({"action": "malicious_action"})
        
        assert result.ok is False
        assert "desconhecida" in result.message.lower()
    
    @patch('app.agent.tools.system_control._press_media_key')
    def test_media_actions_still_work(self, mock_press):
        """Test that media control actions still work correctly."""
        tool = SystemControlTool()
        
        media_actions = [
            "media_play_pause",
            "media_next",
            "media_prev",
            "volume_up",
            "volume_down",
            "volume_mute",
        ]
        
        for action in media_actions:
            result = tool.execute({"action": action})
            assert result.ok is True, f"Media action failed: {action}"
            mock_press.assert_called()
            mock_press.reset_mock()
    
    def test_telemetry_action_still_works(self):
        """Test that telemetry action still works correctly."""
        tool = SystemControlTool()
        
        result = tool.execute({"action": "telemetry"})
        
        assert result.ok is True
        assert "cpu" in result.message.lower()
        assert "ram" in result.message.lower()
    
    def test_list_processes_action_still_works(self):
        """Test that list_processes action still works correctly."""
        tool = SystemControlTool()
        
        result = tool.execute({"action": "list_processes"})
        
        assert result.ok is True
        assert "processos" in result.message.lower() or "aplicativos" in result.message.lower()
    
    def test_alternative_media_action_names(self):
        """Test that alternative media action names work."""
        tool = SystemControlTool()
        
        with patch('app.agent.tools.system_control._press_media_key') as mock_press:
            # Test alternative names
            result = tool.execute({"action": "play"})
            assert result.ok is True
            
            result = tool.execute({"action": "pause"})
            assert result.ok is True
            
            result = tool.execute({"action": "next"})
            assert result.ok is True
            
            result = tool.execute({"action": "prev"})
            assert result.ok is True