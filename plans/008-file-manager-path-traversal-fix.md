# Plan 008: Fix Path Traversal Vulnerability in FileManager

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the STOP conditions section occurs, stop and report
> back instead of improvising.
>
> **Drift check (run first)**: `git diff --stat HEAD -- app/domain/file_manager.py app/agent/tools/file_manager.py tests/`
> If any in-scope file changed since this plan was written, compare the
> Current state excerpts against the live code before proceeding.

## Status

- **Priority**: P0 (security vulnerability)
- **Effort**: M (roughly 1 day including tests)
- **Risk**: MED (moderate risk of breaking existing file access patterns)
- **Depends on**: none
- **Category**: security bug
- **Planned at**: commit `HEAD`, 2026-09-20
- **Execution Status**: DONE (previously implemented, all tests passing)

## Why this matters

The `FileManagerService` in `app/domain/file_manager.py` uses a weak path validation
that relies on `str.startswith()` to check if a resolved path is within the base
folder. This is vulnerable to:
- Symlink attacks (symlinks can escape the base folder)
- Relative path traversal using `../` sequences
- Case-sensitive bypasses on case-insensitive filesystems (Windows)
- Unicode normalization attacks

A malicious user could potentially access files outside the intended base folder,
leading to unauthorized file reads.

## Current state

### Repository and verification conventions

- Python backend under `app/`; no frontend changes required.
- Backend tests use pytest under `tests/`.
- Existing file manager tool follows the BaseTool pattern in `app/agent/tools/`.
- Security-critical code should have defensive programming and explicit validation.

### Evidence of the vulnerability

- `app/domain/file_manager.py:14-15` uses `str.startswith()` for path validation:
  ```python
  if not str(path).startswith(str(self.base_folder)):
      raise ValueError("Acesso a caminho fora do diretório base não permitido.")
  ```
- `app/domain/file_manager.py:22-23` repeats the same pattern for file reads
- `app/agent/tools/file_manager.py:38-63` calls the service without additional validation
- No tests exist for path traversal attacks in the current test suite
- The validation does not handle symlinks, case sensitivity, or relative path normalization

## Target design

Replace the weak `str.startswith()` validation with a robust path security check that:

1. Uses `path.resolve()` to normalize all paths (resolves symlinks and relative paths)
2. Uses strict containment check with `path.is_relative_to()` (Python 3.9+) or equivalent
3. Handles case sensitivity appropriately for the target OS
4. Adds explicit error messages that don't leak path information
5. Includes test coverage for common attack vectors

## Scope

**In scope (only these files may be modified by the executor):**

- `app/domain/file_manager.py` (core service with the vulnerability)
- `app/agent/tools/file_manager.py` (tool wrapper, for error handling improvements)
- `tests/test_file_manager_security.py` (new test file for security scenarios)

**Out of scope:**

- Changes to the BaseTool interface or other tools
- Frontend changes (not affected by this vulnerability)
- Adding new file manager features (only fixing security)
- Changing the base folder configuration mechanism

## Steps

### Step 1: Implement robust path validation in FileManagerService

1. Replace the `str.startswith()` validation in `list_directory()` and `read_file()` with:
   ```python
   # Use resolve() to normalize the path and resolve symlinks
   resolved_path = (self.base_folder / relative_path).resolve()
   
   # Check if the resolved path is actually within the base folder
   if not resolved_path.is_relative_to(self.base_folder):
       raise ValueError("Acesso não permitido: caminho fora do diretório autorizado.")
   ```
2. Add a helper method for path validation that can be reused:
   ```python
   def _validate_path(self, relative_path: str) -> Path:
       """Validates that a relative path stays within the base folder."""
       resolved_path = (self.base_folder / relative_path).resolve()
       if not resolved_path.is_relative_to(self.base_folder):
           raise ValueError("Acesso não permitido: caminho fora do diretório autorizado.")
       return resolved_path
   ```
3. Update both `list_directory()` and `read_file()` to use this helper.

**Verify**: `python -c "from app.domain.file_manager import FileManagerService; fm = FileManagerService('/tmp'); fm._validate_path('../etc/passwd')"` raises ValueError with the security message.

### Step 2: Add test coverage for path traversal attacks

1. Create `tests/test_file_manager_security.py` with tests for:
   - Basic `../` traversal attempts
   - Symlink attacks (create a symlink inside base folder pointing outside)
   - Absolute path attempts
   - Case sensitivity bypass on Windows
   - Unicode normalization attacks
   - Valid paths that should still work

2. Follow the existing test pattern from `tests/test_llm_provider.py` for fixtures and test structure.

**Verify**: `pytest tests/test_file_manager_security.py -v` passes all security tests.

### Step 3: Improve error messages in the tool wrapper

1. Update `app/agent/tools/file_manager.py` to catch security errors specifically:
   ```python
   except ValueError as e:
       if "não permitido" in str(e).lower():
           return ToolResult(ok=False, message="Erro de segurança: caminho não autorizado.")
       # other ValueError handling...
   ```

2. Ensure no path information leaks in error messages to the user.

**Verify**: Attempt to access `../../Windows/System32` through the tool returns a generic security error without path details.

### Step 4: Add integration test with the tool wrapper

1. Add a test that uses the `FileManagerTool` directly to ensure the security layer works end-to-end.
2. Test that valid operations still work correctly after the security fix.

**Verify**: Integration test passes and confirms both security and functionality.

## Test plan

- Create comprehensive security test suite covering all attack vectors
- Ensure backward compatibility with valid file operations
- Test on both Windows and Linux (if possible) for OS-specific path handling
- Run `pytest tests/test_file_manager_security.py -v` to verify all security tests pass
- Run existing file manager tests to ensure no regression

## Done criteria

- [ ] Path validation uses `resolve()` and `is_relative_to()` instead of `str.startswith()`
- [ ] All path traversal attack tests pass
- [ ] Valid file operations (list, read) still work correctly
- [ ] Error messages do not leak path information
- [ ] Test coverage includes symlink, relative path, and case-sensitivity attacks
- [ ] No files outside Scope are modified
- [ ] `python -m compileall -q app` passes

## STOP conditions

- If `path.is_relative_to()` is not available (Python < 3.9), stop and report for alternative implementation
- If the security fix breaks legitimate file access patterns that were working before, stop and investigate
- If symlinks are required for legitimate use cases, stop and discuss allowlisting approach
- If tests reveal additional security vulnerabilities beyond path traversal, stop and report separately

## Maintenance notes

- Path security is a fundamental concern; any future file operations should use the same validation pattern
- Consider adding an allowlist of safe subdirectories if the current approach is too restrictive
- Monitor for new Python pathlib methods that might provide better security validation
- Review this fix when adding new file-related features (search, move, delete operations)