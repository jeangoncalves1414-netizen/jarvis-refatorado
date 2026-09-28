# Plan 010: Sanitize Input and Add Rate Limiting to Desktop Search

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the STOP conditions section occurs, stop and report
> back instead of improvising.
>
> **Drift check (run first)**: `git diff --stat HEAD -- app/agent/tools/desktop_search.py tests/`
> If any in-scope file changed since this plan was written, compare the
> Current state excerpts against the live code before proceeding.

## Status

- **Priority**: P1 (security and reliability issue)
- **Effort**: M (roughly 1 day including tests)
- **Risk**: LOW (minimal risk to existing functionality)
- **Depends on**: none
- **Category**: security bug + reliability
- **Planned at**: commit `HEAD`, 2026-09-20
- **Execution Status**: DONE (implemented, all tests passing)

## Why this matters

The `DesktopSearchTool` in `app/agent/tools/desktop_search.py` performs file system
searches without proper input sanitization, creating several issues:

1. **DoS vulnerability**: Long or malicious queries can cause excessive filesystem traversal
2. **Path traversal risk**: Query terms aren't validated, could potentially access unintended directories
3. **No rate limiting**: Tool can be called repeatedly, potentially overwhelming the filesystem
4. **No result limiting by size**: Large directories could cause memory issues
5. **No input validation**: Empty or malformed queries aren't properly handled

A malicious prompt could cause the assistant to search indefinitely or access
inappropriate directories.

## Current state

### Repository and verification conventions

- Python backend under `app/`; no frontend changes required.
- Backend tests use pytest under `tests/`.
- Search tools should have input validation and resource limits.

### Evidence of the vulnerability

- `app/agent/tools/desktop_search.py:42-44` processes query terms without validation:
  ```python
  query_terms = [q.lower() for q in query.strip().split() if len(q) >= 2]
  category = category.lower().strip()
  ```
- `app/agent/tools/desktop_search.py:49-87` performs `os.walk()` without depth limits
- `app/agent/tools/desktop_search.py:83` has a basic result limit but no directory depth limit
- No timeout on filesystem operations
- No rate limiting on tool calls
- No validation that search locations actually exist before walking

## Target design

Add defensive programming layers to the search tool:

1. **Input sanitization**: Validate and sanitize query terms and categories
2. **Resource limits**: Add depth limits, timeout, and size limits
3. **Rate limiting**: Implement per-session rate limiting for search operations
4. **Path validation**: Ensure search locations are safe and accessible
5. **Error handling**: Graceful degradation on filesystem errors

## Scope

**In scope (only these files may be modified by the executor):**

- `app/agent/tools/desktop_search.py` (add validation and limits)
- `tests/test_desktop_search_security.py` (new test file for security scenarios)

**Out of scope:**

- Changing the search algorithm or adding new search features
- Frontend changes (search is backend-only)
- Adding new search locations (only secure existing ones)
- Performance optimizations beyond basic resource limits

## Steps

### Step 1: Add input validation and sanitization

1. Add input validation in the `run()` method:
   ```python
   def run(self, query: str = "", category: str = "", max_results: int = 15, **kwargs: Any) -> dict[str, Any]:
       # Validate query length and content
       if len(query) > 200:
           return {"success": False, "error": "Query too long (max 200 characters)"}
       
       # Validate max_results
       if not (1 <= max_results <= 100):
           return {"success": False, "error": "max_results must be between 1 and 100"}
       
       # Sanitize query terms
       query_terms = [q.lower() for q in query.strip().split() if len(q) >= 2 and len(q) <= 50]
       if len(query_terms) > 10:
           return {"success": False, "error": "Too many search terms (max 10)"}
       
       # Validate category
       category = category.lower().strip()
       if category and category not in CATEGORIES:
           return {"success": False, "error": f"Invalid category: {category}"}
   ```

**Verify**: Tool rejects queries longer than 200 characters and invalid categories.

### Step 2: Add resource limits and timeout

1. Add depth limits and timeout to filesystem operations:
   ```python
   import time
   from typing import Any
   
   MAX_DEPTH = 5  # Limit directory traversal depth
   MAX_FILES_PER_DIR = 100  # Limit files per directory
   SEARCH_TIMEOUT = 10  # seconds
   
   def run(self, query: str = "", category: str = "", max_results: int = 15, **kwargs: Any) -> dict[str, Any]:
       start_time = time.time()
       matches: list[dict[str, Any]] = []
       
       for base_path in SEARCH_LOCATIONS:
           if time.time() - start_time > SEARCH_TIMEOUT:
               break
           
           if not base_path.exists():
               continue
           
           for root, dirs, files in os.walk(base_path):
               # Check depth limit
               rel_depth = len(Path(root).relative_to(base_path).parts)
               if rel_depth > MAX_DEPTH:
                   dirs[:] = []  # Don't descend further
                   continue
               
               # Limit files per directory
               if len(files) > MAX_FILES_PER_DIR:
                   files = files[:MAX_FILES_PER_DIR]
               
               # ... rest of search logic
   ```

**Verify**: Search respects depth limits and timeout even on large directory trees.

### Step 3: Add path validation for search locations

1. Validate that search locations are safe and accessible:
   ```python
   def _validate_search_location(self, path: Path) -> bool:
       """Ensure search location is safe and accessible."""
       try:
           # Check if path is within user home or project dir
       if not (path.is_relative_to(HOME_DIR) or path.is_relative_to(_PROJECT_DIR)):
           return False
           
           # Check if path exists and is readable
           if not path.exists() or not path.is_dir():
               return False
           
           return True
       except (OSError, PermissionError):
           return False
   ```

**Verify**: Tool refuses to search locations outside approved directories.

### Step 4: Create security test suite

1. Create `tests/test_desktop_search_security.py` with tests for:
   - Query length validation
   - Category validation
   - Directory depth limits
   - Timeout enforcement
   - Path traversal attempts
   - Empty/malformed query handling
   - Large directory handling

**Verify**: All security tests pass, valid searches still work correctly.

## Test plan

- Create comprehensive security test suite
- Test both valid and invalid inputs
- Ensure legitimate search queries still work correctly
- Test timeout and resource limiting with large directories
- Run `pytest tests/test_desktop_search_security.py -v` to verify all security tests pass

## Done criteria

- [ ] Input validation rejects malformed or excessive queries
- [ ] Resource limits (depth, timeout, file count) are enforced
- [ ] Search locations are validated before traversal
- [ ] Security test suite passes all tests
- [ ] Valid search queries still work correctly
- [ ] No files outside Scope are modified
- [ ] `python -m compileall -q app` passes

## STOP conditions

- If resource limits break legitimate search use cases, stop and adjust limits
- If path validation prevents searching approved user directories, stop and fix validation logic
- If timeout mechanism is unreliable on Windows, stop and use alternative approach
- If tests reveal additional vulnerabilities beyond input sanitization, stop and report separately

## Maintenance notes

- Monitor search performance and adjust limits based on real-world usage
- Review and update search locations periodically for safety
- Consider adding user-configurable search locations with validation
- Coordinate with file manager security fixes for consistent path handling