from __future__ import annotations

import pytest

from app.agent.tools.script_runner import (
    ScriptRunnerTool,
    _validate_python_code,
    _validate_powershell_code,
    DANGEROUS_PYTHON_PATTERNS,
    DANGEROUS_POWERSHELL_PATTERNS,
    MAX_CODE_LENGTH,
)


class TestScriptRunnerSecurity:
    """Test suite for script runner security and validation."""
    
    def test_validate_python_code_basic(self):
        """Test that basic valid Python code passes validation."""
        code = """
def hello():
    print("Hello, World!")
    
hello()
"""
        is_valid, error = _validate_python_code(code)
        assert is_valid is True
        assert error == ""
    
    def test_validate_python_code_syntax_error(self):
        """Test that Python code with syntax errors is rejected."""
        code = """
def hello(
    print("Hello")
"""
        is_valid, error = _validate_python_code(code)
        assert is_valid is False
        assert "sintaxe" in error.lower()
    
    def test_validate_python_code_too_long(self):
        """Test that overly long Python code is rejected."""
        code = "print('test')\n" * 5000  # Exceeds MAX_CODE_LENGTH
        is_valid, error = _validate_python_code(code)
        assert is_valid is False
        assert "muito longo" in error.lower()
    
    def test_validate_python_code_with_import(self):
        """Test that __import__ is blocked."""
        code = "__import__('os').system('malicious')"
        is_valid, error = _validate_python_code(code)
        assert is_valid is False
        assert "perigoso" in error.lower()
    
    def test_validate_python_code_with_eval(self):
        """Test that eval is blocked."""
        code = "eval('print(1)')"
        is_valid, error = _validate_python_code(code)
        assert is_valid is False
        assert "perigoso" in error.lower()
    
    def test_validate_python_code_with_exec(self):
        """Test that exec is blocked."""
        code = "exec('print(1)')"
        is_valid, error = _validate_python_code(code)
        assert is_valid is False
        assert "perigoso" in error.lower()
    
    def test_validate_python_code_with_compile(self):
        """Test that compile is blocked."""
        code = "compile('print(1)', '<string>', 'exec')"
        is_valid, error = _validate_python_code(code)
        assert is_valid is False
        assert "perigoso" in error.lower()
    
    def test_validate_python_code_with_open(self):
        """Test that open is blocked."""
        code = "open('/etc/passwd').read()"
        is_valid, error = _validate_python_code(code)
        assert is_valid is False
        assert "perigoso" in error.lower()
    
    def test_validate_python_code_with_subprocess(self):
        """Test that subprocess is blocked."""
        code = "import subprocess; subprocess.run(['ls'])"
        is_valid, error = _validate_python_code(code)
        assert is_valid is False
        assert "perigoso" in error.lower()
    
    def test_validate_python_code_with_os_system(self):
        """Test that os.system is blocked."""
        code = "import os; os.system('ls')"
        is_valid, error = _validate_python_code(code)
        assert is_valid is False
        assert "perigoso" in error.lower()
    
    def test_validate_python_code_with_globals(self):
        """Test that globals() is blocked."""
        code = "globals()"
        is_valid, error = _validate_python_code(code)
        assert is_valid is False
        assert "perigoso" in error.lower()
    
    def test_validate_python_code_with_dunder_class(self):
        """Test that __class__ access is blocked."""
        code = "().__class__"
        is_valid, error = _validate_python_code(code)
        assert is_valid is False
        assert "perigoso" in error.lower()
    
    def test_validate_python_code_with_getattr(self):
        """Test that getattr is blocked."""
        code = "getattr('', '__class__')"
        is_valid, error = _validate_python_code(code)
        assert is_valid is False
        assert "perigoso" in error.lower()
    
    def test_validate_powershell_code_basic(self):
        """Test that basic valid PowerShell code passes validation."""
        code = "Write-Host 'Hello, World!'"
        is_valid, error = _validate_powershell_code(code)
        assert is_valid is True
        assert error == ""
    
    def test_validate_powershell_code_too_long(self):
        """Test that overly long PowerShell code is rejected."""
        code = "Write-Host 'test'\n" * 5000  # Exceeds MAX_CODE_LENGTH
        is_valid, error = _validate_powershell_code(code)
        assert is_valid is False
        assert "muito longo" in error.lower()
    
    def test_validate_powershell_code_with_invoke_expression(self):
        """Test that Invoke-Expression is blocked."""
        code = "Invoke-Expression 'Get-Process'"
        is_valid, error = _validate_powershell_code(code)
        assert is_valid is False
        assert "perigoso" in error.lower()
    
    def test_validate_powershell_code_with_iex(self):
        """Test that iex alias is blocked."""
        code = "iex 'Get-Process'"
        is_valid, error = _validate_powershell_code(code)
        assert is_valid is False
        assert "perigoso" in error.lower()
    
    def test_validate_powershell_code_with_invoke_command(self):
        """Test that Invoke-Command is blocked."""
        code = "Invoke-Command -ScriptBlock {Get-Process}"
        is_valid, error = _validate_powershell_code(code)
        assert is_valid is False
        assert "perigoso" in error.lower()
    
    def test_validate_powershell_code_with_start_process(self):
        """Test that Start-Process is blocked."""
        code = "Start-Process notepad.exe"
        is_valid, error = _validate_powershell_code(code)
        assert is_valid is False
        assert "perigoso" in error.lower()
    
    def test_validate_powershell_code_with_wscript_shell(self):
        """Test that WScript.Shell is blocked."""
        code = "New-Object -ComObject WScript.Shell"
        is_valid, error = _validate_powershell_code(code)
        assert is_valid is False
        assert "perigoso" in error.lower()
    
    def test_validate_powershell_code_with_new_object_process(self):
        """Test that New-Object System.Diagnostics.Process is blocked."""
        code = "New-Object System.Diagnostics.Process"
        is_valid, error = _validate_powershell_code(code)
        assert is_valid is False
        assert "perigoso" in error.lower()
    
    def test_validate_powershell_code_with_add_type(self):
        """Test that Add-Type is blocked."""
        code = "Add-Type -TypeDefinition '...'"
        is_valid, error = _validate_powershell_code(code)
        assert is_valid is False
        assert "perigoso" in error.lower()
    
    def test_validate_powershell_code_with_invoke_webrequest(self):
        """Test that Invoke-WebRequest is blocked."""
        code = "Invoke-WebRequest http://example.com"
        is_valid, error = _validate_powershell_code(code)
        assert is_valid is False
        assert "perigoso" in error.lower()
    
    def test_validate_powershell_code_with_registry_access(self):
        """Test that registry access is blocked."""
        code = "Get-ItemProperty -Path 'HKLM:\\Software'"
        is_valid, error = _validate_powershell_code(code)
        assert is_valid is False
        assert "perigoso" in error.lower()
    
    def test_validate_powershell_code_with_get_credential(self):
        """Test that Get-Credential is blocked."""
        code = "Get-Credential"
        is_valid, error = _validate_powershell_code(code)
        assert is_valid is False
        assert "perigoso" in error.lower()
    
    def test_validate_powershell_code_with_stop_process(self):
        """Test that Stop-Process is blocked."""
        code = "Stop-Process -Name notepad"
        is_valid, error = _validate_powershell_code(code)
        assert is_valid is False
        assert "perigoso" in error.lower()
    
    def test_script_runner_tool_validates_python(self):
        """Test that ScriptRunnerTool validates Python code."""
        tool = ScriptRunnerTool()
        
        # Valid code should pass
        result = tool.execute({
            "language": "python",
            "code": "print('Hello')",
            "description": "Test script"
        })
        assert result.ok is True
        assert result.data["needs_confirmation"] is True
        
        # Dangerous code should be rejected
        result = tool.execute({
            "language": "python",
            "code": "__import__('os').system('ls')",
            "description": "Malicious script"
        })
        assert result.ok is False
        assert "perigoso" in result.message.lower()
    
    def test_script_runner_tool_validates_powershell(self):
        """Test that ScriptRunnerTool validates PowerShell code."""
        tool = ScriptRunnerTool()
        
        # Valid code should pass
        result = tool.execute({
            "language": "powershell",
            "code": "Write-Host 'Hello'",
            "description": "Test script"
        })
        assert result.ok is True
        assert result.data["needs_confirmation"] is True
        
        # Dangerous code should be rejected
        result = tool.execute({
            "language": "powershell",
            "code": "Invoke-Expression 'Get-Process'",
            "description": "Malicious script"
        })
        assert result.ok is False
        assert "perigoso" in result.message.lower()
    
    def test_script_runner_tool_rejects_empty_code(self):
        """Test that empty code is rejected."""
        tool = ScriptRunnerTool()
        
        result = tool.execute({
            "language": "python",
            "code": "",
            "description": "Empty script"
        })
        assert result.ok is False
        assert "vazio" in result.message.lower()
    
    def test_script_runner_tool_rejects_invalid_language(self):
        """Test that invalid language is rejected."""
        tool = ScriptRunnerTool()
        
        result = tool.execute({
            "language": "bash",
            "code": "echo 'test'",
            "description": "Bash script"
        })
        assert result.ok is False
        assert "não suportada" in result.message.lower()
    
    def test_dangerous_patterns_lists_are_not_empty(self):
        """Test that dangerous pattern lists are not empty."""
        assert len(DANGEROUS_PYTHON_PATTERNS) > 0
        assert len(DANGEROUS_POWERSHELL_PATTERNS) > 0
    
    def test_max_code_length_is_reasonable(self):
        """Test that MAX_CODE_LENGTH is set to a reasonable value."""
        assert MAX_CODE_LENGTH > 0
        assert MAX_CODE_LENGTH <= 50000  # Should not be excessive