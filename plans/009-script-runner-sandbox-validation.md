# Plan 009: Add Sandbox and Validation to Script Runner

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the STOP conditions section occurs, stop and report
> back instead of improvising.
>
> **Drift check (run first)**: `git diff --stat HEAD -- app/agent/tools/script_runner.py app/ui/panel/api/script.py tests/`
> If any in-scope file changed since this plan was written, compare the
> Current state excerpts against the live code before proceeding.

## Status

- **Priority**: P0 (critical security vulnerability)
- **Effort**: L (roughly 2-3 days including comprehensive validation)
- **Risk**: HIGH (may break existing automation workflows)
- **Depends on**: none
- **Category**: security bug
- **Planned at**: commit `HEAD`, 2026-09-20
- **Execution Status**: DONE (implemented, all tests passing)

## Why this matters

The `ScriptRunnerTool` in `app/agent/tools/script_runner.py` allows execution of arbitrary
Python and PowerShell code with only UI confirmation as a safeguard. This presents several
critical security risks:

1. **No code validation**: The tool doesn't analyze the code before execution
2. **No sandbox**: Code runs with full system privileges
3. **No resource limits**: Could execute DoS attacks (infinite loops, resource exhaustion)
4. **No audit trail**: Limited logging of what was actually executed
5. **No allowlist/blocklist**: Any command can be executed

A malicious prompt or compromised LLM could execute destructive commands (delete files,
steal credentials, install malware) with just a user's UI confirmation.

## Current state

### Repository and verification conventions

- Python backend under `app/`; minimal frontend changes required.
- Backend tests use pytest under `tests/`.
- Script execution should have the same security posture as other system control tools.
- The tool follows the BaseTool pattern with confirmation flow.

### Evidence of the vulnerability

- `app/agent/tools/script_runner.py:56-83` simply wraps code in JSON and returns it for execution
- No validation of code content, dangerous patterns, or resource usage
- No timeout or resource limits
- No audit logging of executed code
- The confirmation mechanism is purely UI-based, not a security boundary
- No existing tests for script execution security

## Target design

Implement a layered security approach for script execution:

1. **Static analysis**: Parse and validate code before execution (detect dangerous patterns)
2. **Resource limits**: Enforce timeouts, memory limits, and execution restrictions
3. **Sandbox execution**: Run in restricted environment where possible
4. **Audit logging**: Log all execution attempts with code hashes and results
5. **Allowlist patterns**: Define safe patterns for common automation tasks
6. **Blocklist patterns**: Explicitly block dangerous operations

## Scope

**In scope (only these files may be modified by the executor):**

- `app/agent/tools/script_runner.py` (add validation layer)
- `app/ui/panel/api/script.py` (if exists, otherwise create proper execution endpoint)
- `tests/test_script_runner_security.py` (new test file for security validation)
- `app/services/script_validator.py` (new validation service)

**Out of scope:**

- Complete sandbox implementation (full containerization)
- Frontend UI changes (confirmation UI is adequate)
- Removing the confirmation mechanism (keep user approval)
- Adding new script languages (only secure existing Python/PowerShell)

## Steps

### Step 1: Create script validation service

1. Create `app/services/script_validator.py` with:
   - Static code analysis for dangerous patterns
   - AST parsing for Python to detect imports and operations
   - PowerShell command analysis
   - Allowlist/blocklist configuration
   - Code hashing for audit trail

2. Implement dangerous pattern detection:
   ```python
   DANGEROUS_PATTERNS = {
       'python': [
           r'os\.system\s*\(',
           r'subprocess\.call\s*\(',
           r'eval\s*\(',
           r'exec\s*\(',
           r'__import__\s*\(',
           r'open\s*\([^)]*\s*[\'"]\s*w',  # write mode
       ],
       'powershell': [
           r'Remove-Item',
           r'Delete-Item',
           r'Invoke-Expression',
           r'Invoke-Command',
           r'Set-ExecutionPolicy',
       ]
   }
   ```

**Verify**: Validation service rejects code with `os.system("rm -rf /")` and `Remove-Item -Recurse`.

### Step 2: Add validation layer to ScriptRunnerTool

1. Update `app/agent/tools/script_runner.py` to call validation before returning confirmation request:
   ```python
   from app.services.script_validator import ScriptValidator
   
   def execute(self, args: dict, context: dict | None = None) -> ToolResult:
       # existing validation...
       
       # Add security validation
       validator = ScriptValidator()
       validation_result = validator.validate(language, code)
       
       if not validation_result.is_safe:
           return ToolResult(
               ok=False,
               message=f"Código rejeitado por segurança: {validation_result.reason}"
           )
       
       # Return confirmation request with security metadata
       payload = json.dumps({
           "needs_confirmation": True,
           "language": language,
           "code": code,
           "description": description,
           "security_score": validation_result.score,
           "detected_patterns": validation_result.detected_patterns,
       }, ensure_ascii=False)
   ```

**Verify**: Tool returns rejection for dangerous code and confirmation for safe code.

### Step 3: Implement resource limits and timeout

1. Add execution timeout mechanism:
   ```python
   import signal
   from concurrent.futures import ThreadPoolExecutor, TimeoutError
   
   def execute_with_timeout(code, timeout_seconds=30):
       with ThreadPoolExecutor() as executor:
           future = executor.submit(exec_code, code)
           try:
               return future.result(timeout=timeout_seconds)
           except TimeoutError:
               return "Timeout: script execution exceeded time limit"
   ```

2. Add memory limits where possible (process memory monitoring).

**Verify**: Scripts that hang are terminated after timeout and don't consume infinite resources.

### Step 4: Create comprehensive security test suite

1. Create `tests/test_script_runner_security.py` with tests for:
   - Dangerous pattern detection (file deletion, system commands)
   - Safe code execution (simple calculations, file reads)
   - Timeout enforcement (infinite loops)
   - Code injection attempts
   - AST parsing validation
   - PowerShell command validation

2. Test edge cases and bypass attempts.

**Verify**: All security tests pass, dangerous code is rejected, safe code executes correctly.

### Step 5: Add audit logging

1. Log all script execution attempts with:
   - Code hash (SHA-256)
   - Timestamp
   - User/agent that requested execution
   - Validation result
   - Execution result
   - Resource usage

2. Store logs in `data/script_audit.log` with proper rotation.

**Verify**: Audit log contains entries for all execution attempts with proper metadata.

## Test plan

- Create comprehensive security test suite covering all attack vectors
- Test both Python and PowerShell validation
- Ensure safe automation scripts still work (file operations, simple calculations)
- Test timeout and resource limiting
- Verify audit logging functionality
- Run `pytest tests/test_script_runner_security.py -v` to verify all security tests pass

## Done criteria

- [ ] Script validation service detects dangerous patterns in both Python and PowerShell
- [ ] ScriptRunnerTool rejects dangerous code before confirmation
- [ ] Safe code can still be executed with user confirmation
- [ ] Execution timeout is enforced (default 30 seconds)
- [ ] Audit logging captures all execution attempts
- [ ] Security test suite passes all tests
- [ ] No files outside Scope are modified
- [ ] `python -m compileall -q app` passes

## STOP conditions

- If validation breaks all existing automation scripts, stop and refine allowlist
- If timeout mechanism cannot be implemented reliably, stop and use alternative approach
- If audit logging reveals unexpected execution patterns, stop and investigate
- If security validation adds unacceptable latency to legitimate use cases, stop and optimize

## Maintenance notes

- Regularly update dangerous pattern lists based on new security research
- Monitor audit logs for emerging attack patterns
- Consider adding user-specific allowlists for trusted automation workflows
- Review and update timeout limits based on legitimate automation needs
- Coordinate with other security plans (control plane, system control) for consistent security posture