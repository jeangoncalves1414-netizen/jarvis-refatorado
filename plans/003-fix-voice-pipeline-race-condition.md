# Plan 003: Fix race condition in shared voice_pipeline class variable

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 1861eae..HEAD -- app/ui/panel/api/settings.py app/ui/panel/server.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: MED
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit 1861eae, 2025-01-15

## Why this matters

The voice pipeline is stored as a shared class variable (`PanelHandler.voice_pipeline`) that can be reassigned from multiple concurrent API requests. While a lock exists (`_pipeline_lock`), it's only used in one location (`server.py:2013`). Multiple concurrent requests in `settings.py` (lines 151, 177, 206, 225) reassign the pipeline without using the lock, creating a race condition. This can corrupt the shared pipeline state, causing undefined behavior or crashes in voice operations.

## Current state

**File**: `app/ui/panel/api/settings.py` — voice pipeline reload handlers

**Problem locations** (lines 151, 177, 206, 225):
```python
# Line 151 (and similar at 177, 206, 225)
handler.__class__.voice_pipeline = VoicePipeline(...)
```

These assignments happen without the lock that exists in `server.py`.

**Lock usage example** (server.py:2013):
```python
with PanelHandler._pipeline_lock:
    handler.__class__.voice_pipeline = VoicePipeline(...)
```

**Repo conventions**:
- The codebase uses threading locks for shared mutable state
- Pattern: `with PanelHandler._pipeline_lock:` when modifying the pipeline

## Commands you will need

| Purpose   | Command                  | Expected on success |
|-----------|--------------------------|---------------------|
| Lint      | `python -m py_compile app/ui/panel/api/settings.py` | exit 0              |
| Start     | `python -m app.main --server` | server starts successfully |

## Scope

**In scope**:
- `app/ui/panel/api/settings.py` — lines 151, 177, 206, 225 (wrap assignments with lock)

**Out of scope**:
- `app/ui/panel/server.py` — already uses lock correctly
- Any other files
- Changes to the lock itself or its scope

## Git workflow

- Branch: `advisor/003-fix-voice-pipeline-race`
- Commit: `fix: wrap voice_pipeline assignments with lock in settings.py`
- Do NOT push or open a PR unless instructed

## Steps

### Step 1: Wrap line 151 with lock

In `app/ui/panel/api/settings.py`, find line 151. Replace:
```python
handler.__class__.voice_pipeline = VoicePipeline(...)
```

With:
```python
with PanelHandler._pipeline_lock:
    handler.__class__.voice_pipeline = VoicePipeline(...)
```

**Verify**: `python -m py_compile app/ui/panel/api/settings.py` → exit 0

### Step 2: Wrap line 177 with lock

In `app/ui/panel/api/settings.py`, find line 177. Replace:
```python
handler.__class__.voice_pipeline = VoicePipeline(...)
```

With:
```python
with PanelHandler._pipeline_lock:
    handler.__class__.voice_pipeline = VoicePipeline(...)
```

**Verify**: `python -m py_compile app/ui/panel/api/settings.py` → exit 0

### Step 3: Wrap line 206 with lock

In `app/ui/panel/api/settings.py`, find line 206. Replace:
```python
handler.__class__.voice_pipeline = VoicePipeline(...)
```

With:
```python
with PanelHandler._pipeline_lock:
    handler.__class__.voice_pipeline = VoicePipeline(...)
```

**Verify**: `python -m py_compile app/ui/panel/api/settings.py` → exit 0

### Step 4: Wrap line 225 with lock

In `app/ui/panel/api/settings.py`, find line 225. Replace:
```python
handler.__class__.voice_pipeline = VoicePipeline(...)
```

With:
```python
with PanelHandler._pipeline_lock:
    handler.__class__.voice_pipeline = VoicePipeline(...)
```

**Verify**: `python -m py_compile app/ui/panel/api/settings.py` → exit 0

### Step 5: Verify server starts correctly

**Verify**: `python -m app.main --server` → server starts without errors (stop with Ctrl+C after verification)

## Test plan

- Manual test: Make concurrent voice settings changes and verify no corruption
- Verify voice operations still work after settings changes
- No automated tests exist for this concurrency scenario

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `python -m py_compile app/ui/panel/api/settings.py` exits 0
- [ ] `python -m app.main --server` starts successfully
- [ ] `grep -n "handler.__class__.voice_pipeline = VoicePipeline" app/ui/panel/api/settings.py` returns no matches (all should be wrapped)
- [ ] No files outside `app/ui/panel/api/settings.py` are modified (`git status`)
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- The code at lines 151, 177, 206, 225 in `app/ui/panel/api/settings.py` doesn't match the excerpts (drift detected)
- The Python compilation fails after adding locks
- The server fails to start after changes
- You discover that `_pipeline_lock` doesn't exist or is used differently
- You find other assignments to `voice_pipeline` not covered by this plan (report as scope expansion)

## Maintenance notes

- Any future assignments to `voice_pipeline` must use the lock
- Consider refactoring to an instance variable instead of class variable to eliminate shared state
- Review other shared class variables for similar race conditions
