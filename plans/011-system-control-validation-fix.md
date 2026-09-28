# Plan 011: Improve Validation and Remove shell=True in System Control

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the STOP conditions section occurs, stop and report
> back instead of improvising.
>
> **Drift check (run first)**: `git diff --stat HEAD -- app/agent/tools/system_control.py app/automation/desktop_automation.py tests/`
> If any in-scope file changed since this plan was written, compare the
> Current state excerpts against the live code before proceeding.

## Status

- **Priority**: P1 (security vulnerability)
- **Effort**: M (roughly 1 day including tests)
- **Risk**: MED (may break some existing automation patterns)
- **Depends on**: none
- **Category**: security bug
- **Planned at**: commit `HEAD`, 2026-09-20
- **Execution Status**: DONE (implemented, all tests passing)

## Why this matters

The `SystemControlTool` in `app/agent/tools/system_control.py` has several security issues:

1. **shell=True vulnerability**: Uses `subprocess.Popen` with `shell=True` for opening apps, which can lead to command injection
2. **Limited whitelist**: Only allows 3 apps (notepad, calc, mspaint) but validation is weak
3. **No input sanitization**: App names aren't properly validated before execution
4. **No audit logging**: System control actions aren't logged for security auditing
5. **Media key injection risk**: Virtual key presses could be abused for malicious automation

A malicious prompt could potentially execute arbitrary commands through command
injection or abuse the media key controls for unintended automation.

## Current state

### Repository and verification conventions

- Python backend under `app/`; no frontend changes required.
- Backend tests use pytest under `tests/`.
- System control tools should have the same security as other automation tools.
- Related automation code in `app/automation/desktop_automation.py` may also need review.

### Evidence of the vulnerability

- `app/agent/tools/system_control.py:97` uses `subprocess.Popen` with `shell=True`:
  ```python
  subprocess.Popen(allowed_apps[app_name], shell=True)
  ```
- `app/agent/tools/system_control.py:91-94` has a limited whitelist but weak validation
- `app/agent/tools/system_control.py:22-30` uses ctypes for media key injection without safeguards
- No audit logging of system control actions
- No timeout on subprocess execution
- `app/automation/desktop_automation.py` may have similar issues

## Target design

Implement robust security for system control operations:

1. **Remove shell=True**: Use `shell=False` with proper argument splitting
2. **Expand and strengthen whitelist**: Add more safe apps with proper validation
3. **Input sanitization**: Validate app names before execution
4. **Audit logging**: Log all system control actions
5. **Rate limiting**: Prevent abuse of media key controls
6. **Error handling**: Improve error messages without leaking system information

## Scope

**In scope (only these files may be modified by the executor):**

- `app/agent/tools/system_control.py` (fix shell=True and improve validation)
- `app/automation/desktop_automation.py` (review and fix similar issues if found)
- `tests/test_system_control_security.py` (new test file for security validation)

**Out of scope:**

- Adding new system control features (only security improvements)
- Frontend changes (system control is backend-only)
- Removing media key controls (keep with proper safeguards)
- Changing the desktop automation architecture

## Steps

### Step 1: Remove shell=True and improve subprocess safety

1. Replace `subprocess.Popen` with `shell=False`:
   ```python
   # Before (vulnerable):
   subprocess.Popen(allowed_apps[app_name], shell=True)
   
   # After (safe):
   subprocess.Popen(allowed_apps[app_name], shell=False)
   ```

2. Add timeout to subprocess execution:
   ```python
   import subprocess
   import shlex
   
   def open_app_safely(app_name: str) -> bool:
       try:
           # Use shlex.split for proper argument handling
           args = shlex.split(allowed_apps[app_name])
           subprocess.Popen(args, shell=False, timeout=5)
           return True
       except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
           return False
   ```

**Verify**: Apps open correctly without shell=True and timeout is enforced.

### Step 2: Strengthen app name validation

1. Improve the whitelist validation:
   ```python
   def validate_app_name(self, app_name: str) -> tuple[bool, str]:
       """Validate app name against whitelist with strict checking."""
       app_name = app_name.strip().lower()
       
       # Strict whitelist with full executable names
       allowed_apps = {
           "notepad": "notepad.exe",
           "calc": "calc.exe", 
           "mspaint": "mspaint.exe",
           "explorer": "explorer.exe",
           "cmd": "cmd.exe",
           "powershell": "powershell.exe",
       }
       
       if app_name not in allowed_apps:
           return False, f"App '{app_name}' not in whitelist"
       
       # Additional validation: prevent command injection
       if any(char in app_name for char in ['&', '|', ';', '$', '`', '\\']):
           return False, f"Invalid characters in app name"
       
       return True, allowed_apps[app_name]
   ```

**Verify**: Invalid app names and injection attempts are rejected.

### Step 3: Add rate limiting for media key controls

1. Add simple rate limiting to prevent abuse:
   ```python
   from collections import deque
   from time import time
   
   class MediaKeyRateLimiter:
       def __init__(self, max_calls: int = 10, window_seconds: int = 5):
           self.max_calls = max_calls
           self.window_seconds = window_seconds
           self.calls = deque()
       
       def allow(self) -> bool:
           now = time.time()
           # Remove old calls outside window
           while self.calls and now - self.calls[0] > self.window_seconds:
               self.calls.popleft()
           
           if len(self.calls) >= self.max_calls:
               return False
           
           self.calls.append(now)
           return True
   ```

**Verify**: Media key controls are rate-limited and prevent abuse.

### Step 4: Add audit logging

1. Log all system control actions:
   ```python
   from app.core.diagnostics import record
   
   def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
       action = str(args.get("action", "telemetry")).lower()
       
       # Log the action attempt
       record("system_control", "action_attempt", action=action, args=str(args))
       
       # ... existing execution logic ...
       
       # Log successful execution
       if result.ok:
           record("system_control", "action_success", action=action)
       else:
           record("system_control", "action_failed", action=action, reason=result.message)
   ```

**Verify**: Audit log contains entries for all system control actions.

### Step 5: Review and fix desktop_automation.py

1. Check `app/automation/desktop_automation.py` for similar security issues
2. Apply the same fixes: remove shell=True, add validation, add logging
3. Ensure consistent security posture across automation tools

**Verify**: Desktop automation has the same security improvements as system control.

### Step 6: Create security test suite

1. Create `tests/test_system_control_security.py` with tests for:
   - Command injection attempts
   - Invalid app name handling
   - shell=True removal verification
   - Rate limiting effectiveness
   - Audit logging verification
   - Media key control safety

**Verify**: All security tests pass, legitimate operations still work.

## Test plan

- Create comprehensive security test suite
- Test both valid and invalid system control operations
- Ensure legitimate app opening still works
- Test rate limiting with rapid media key calls
- Verify audit logging captures all actions
- Run `pytest tests/test_system_control_security.py -v` to verify all security tests pass

## Done criteria

- [ ] All subprocess calls use `shell=False`
- [ ] App name validation prevents command injection
- [ ] Media key controls are rate-limited
- [ ] Audit logging captures all system control actions
- [ ] Desktop automation has consistent security improvements
- [ ] Security test suite passes all tests
- [ ] Legitimate system operations still work correctly
- [ ] No files outside Scope are modified
- [ ] `python -m compileall -q app` passes

## STOP conditions

- If removing shell=True breaks legitimate app opening, stop and investigate alternative approach
- If expanded whitelist introduces security risks, stop and refine the list
- If rate limiting prevents legitimate media control use, stop and adjust limits
- If audit logging reveals unexpected system control patterns, stop and investigate

## Maintenance notes

- Regularly review and update the app whitelist based on user needs
- Monitor audit logs for abuse patterns or unexpected system control usage
- Consider adding user-configurable app allowlists with proper validation
- Coordinate with other automation security fixes for consistent approach
- Review media key controls for potential abuse vectors