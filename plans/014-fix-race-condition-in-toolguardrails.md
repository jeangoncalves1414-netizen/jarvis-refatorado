# Plan 014: Fix Race Condition in ToolGuardrails

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and expected result before moving to the
> next step. If anything in the STOP conditions section occurs, stop and report
> back instead of improvising.
>
> **Drift check (run first)**: `git diff --stat HEAD -- app/core/guardrails.py tests/`
> If any in-scope file changed since this plan was written, compare the
> Current state excerpts against the live code before proceeding.

## Status

- **Priority**: P1 (race condition in multi-threaded environment)
- **Effort**: M (roughly 0.5 day including tests)
- **Risk**: LOW (adding locks to dictionaries is safe)
- **Depends on**: none
- **Category**: correctness bug + concurrency
- **Planned at**: commit `HEAD`, 2026-09-21

## Why this matters

The `ToolGuardrails` class uses unprotected dictionaries `_calls` and `_results` that are modified in `before_call` and `after_call` without thread synchronization. If the same guardrail instance is used by multiple threads (e.g., in `agent.swarm.py` which uses `concurrent.futures.ThreadPoolExecutor`), this can cause:

1. **Race conditions**: Multiple threads modifying the same dictionary simultaneously
2. **Lost updates**: Increment operations overwriting each other
3. **Inconsistent state**: Guardrail decisions based on stale or corrupted counter values
4. **Unpredictable behavior**: Repetition limits and no-progress detection may fail randomly

Evidence:
- `app/core/guardrails.py:20-21` - Unprotected dictionaries `_calls` and `_results`
- `app/core/guardrails.py:28` - `self._calls[key] = self._calls.get(key, 0) + 1` without lock
- `app/core/guardrails.py:35` - `self._results[key] = self._results.get(key, 0) + 1` without lock
- `app/agent/swarm.py:89-95` - Uses `concurrent.futures.ThreadPoolExecutor` which creates multiple threads

## Current state

### app/core/guardrails.py

Lines 14-57 show the problematic code:
```python
class ToolGuardrails:
    """Proteção contra loops e repetições."""
    
    def __init__(self, repeat_limit: int = 3, no_progress_limit: int = 3):
        self.repeat_limit = repeat_limit
        self.no_progress_limit = no_progress_limit
        self._calls: dict[str, int] = {}
        self._results: dict[tuple[str, str], int] = {}  # BUG: No lock protection
    
    def before_call(self, tool: str, args: Mapping[str, Any]) -> GuardrailDecision:
        """Verifica antes de executar ferramenta."""
        key = self._key(tool, args)
        if self._calls.get(key, 0) >= self.repeat_limit:
            return GuardrailDecision(False, f"Repetição bloqueada: {tool}")
        self._calls[key] = self._calls.get(key, 0) + 1  # BUG: Race condition
        return Guardrail(True)
    
    def after_call(self, tool: str, args: Mapping[str, Any], result: Any) -> GuardrailDecision:
        """Verifica após executar ferramenta."""
        text = self._normalize(result)
        key = (tool, text)
        self._results[key] = self._results.get(key, 0) + 1  # BUG: Race condition
        # ...
```

### Usage in multi-threaded context

**app/agent/swarm.py:89-95**
```python
with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(tasks), 5)) as executor:
    future_to_task = {executor.submit(_worker, task): task for task in tasks}
    for future in concurrent.futures.as_completed(future_to_task):
        try:
            res = future.result()
            results.append(res)
        except Exception as exc:
            results.append({"ok": False, "error": str(exc)})
```

If the orchestrator uses ToolGuardrails and the swarm executes tools in parallel, the guardrail state will be accessed concurrently.

## Step-by-step implementation

### Step 1: Add threading.Lock to ToolGuardrails

**File**: `app/core/guardrails.py`

Add import at top:
```python
import threading
```

Add lock in __init__:
```python
def __init__(self, repeat_limit: int = 3, no_progress_limit: int = 3):
    self.repeat_limit = repeat_limit
    self.no_progress_limit = no_progress_limit
    self._calls: dict[str, int] = {}
    self._results: dict[tuple[str, str], int] = {}
    self._lock = threading.Lock()  # Added for thread safety
```

### Step 2: Protect before_call with lock

**File**: `app/core/guardrails.py`

Modify before_call method:
```python
def before_call(self, tool: str, args: Mapping[str, Any]) -> GuardrailDecision:
    """Verifica antes de executar ferramenta."""
    key = self._key(tool, args)
    with self._lock:
        if self._calls.get(key, 0) >= self.repeat_limit:
            return GuardrailDecision(False, f"Repetição bloqueada: {tool}")
        self._calls[key] = self._calls.get(key, 0) + 1
    return GuardrailDecision(True)
```

### Step 3: Protect after_call with lock

**File**: `app/core/guardrails.py`

Modify after_call method:
```python
def after_call(self, tool: str, args: Mapping[str, Any], result: Any) -> GuardrailDecision:
    """Verifica após executar ferramenta."""
    text = self._normalize(result)
    key = (tool, text)
    with self._lock:
        self._results[key] = self._results.get(key, 0) + 1
        
        if self._results[key] >= self.no_progress_limit and self._is_no_progress(text):
            return GuardrailDecision(False, f"Sem progresso: {tool}")
    return GuardrailDecision(True)
```

### Step 4: Protect reset with lock

**File**: `app/core/guardrails.py`

Modify reset method:
```python
def reset(self) -> None:
    """Reseta contadores."""
    with self._lock:
        self._calls.clear()
        self._results.clear()
```

### Step 5: Add test for thread safety

**File**: `tests/test_guardrails_thread_safety.py` (new file)

Create test to verify thread safety:
```python
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.core.guardrails import ToolGuardrails


class TestGuardrailsThreadSafety:
    """Test thread safety of ToolGuardrails."""
    
    def test_concurrent_before_call(self):
        """Test that concurrent before_call calls don't cause race conditions."""
        guardrails = ToolGuardrails(repeat_limit=100, no_progress_limit=100)
        
        def make_call(tool: str, idx: int):
            for _ in range(50):
                decision = guardrails.before_call(tool, {"idx": idx})
                if not decision.allow:
                    return False
            return True
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_call, "test_tool", i) for i in range(10)]
            results = [f.result() for f in futures]
        
        # All should succeed (no false positives)
        assert all(results)
    
    def test_concurrent_after_call(self):
        """Test that concurrent after_call calls don't cause race conditions."""
        guardrails = ToolGuardrails(repeat_limit=100, no_progress_limit=100)
        
        def make_call(tool: str, idx: int):
            for _ in range(50):
                guardrails.before_call(tool, {"idx": idx})
                guardrails.after_call(tool, {"idx": idx}, f"result_{idx}")
            return True
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_call, "test_tool", i) for i in range(10)]
            results = [f.result() for f in futures]
        
        # All should succeed
        assert all(results)
    
    def test_repeat_limit_with_concurrent_calls(self):
        """Test that repeat limit is enforced correctly under concurrent load."""
        guardrails = ToolGuardrails(repeat_limit=5, no_progress_limit=100)
        
        def make_call(tool: str, idx: int):
            for _ in range(10):
                decision = guardrails.before_call(tool, {"idx": idx})
                if not decision.allow:
                    return False
            return True
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_call, "test_tool", i) for i in range(3)]
            results = [f.result() for f in futures]
        
        # At least some should be blocked due to repeat limit
        # (with 3 threads * 10 calls each = 30 calls, limit is 5 per key)
        # This test verifies the limit is actually enforced, not that all fail
        assert not all(results)
    
    def test_reset_during_concurrent_calls(self):
        """Test that reset works correctly while calls are happening."""
        guardrails = ToolGuardrails(repeat_limit=100, no_progress_limit=100)
        
        def make_calls(tool: str, idx: int):
            for _ in range(20):
                guardrails.before_call(tool, {"idx": idx})
                if idx == 0 and guardrails._calls.get(guardrails._key(tool, {"idx": 0}), 0) == 10:
                    guardrails.reset()
            return True
        
        with ThreadPoolExecutor(max_workers=5) executor:
            futures = [executor.submit(make_calls, "test_tool", i) for i in range(5)]
            results = [f.result() for f in futures]
        
        # All should succeed
        assert all(results)
```

**Verification**:
- Command: `python -m pytest tests/test_guardrails_thread_safety.py -v`
- Expected: All tests pass

## Done criteria

- [ ] `threading.Lock` added to ToolGuardrails.__init__
- [ ] `before_call` protected with lock
- [ ] `after_call` protected with lock
- [ ] `reset` protected with lock
- [ ] Thread safety tests created
- [ ] All tests pass
- [ ] `python -m compileall -q app` passes
- [ ] Manual test: No errors when running with concurrent.futures

## Stop conditions

- If adding locks causes performance degradation in single-threaded use, STOP and consider lock-free alternatives.
- If the reset() method being locked causes deadlocks in practice, STOP and remove lock from reset() only.
- If tests reveal that the locking is still insufficient (e.g., key() method not thread-safe), STOP and add more comprehensive protection.

## Maintenance notes

The ToolGuardrails class is now thread-safe. When adding new methods that access `_calls` or `_results`, they must:
1. Acquire `self._lock` before accessing/modifying these dictionaries
2. Release the lock as soon as possible (use `with self._lock:` context manager)
3. Avoid holding the lock while calling external code that might block

Future changes should consider whether to use `threading.local()` for thread-local guardrails instead of a shared instance if lock contention becomes an issue.