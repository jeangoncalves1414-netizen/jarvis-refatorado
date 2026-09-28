# Plan 015: Fix Race Condition in Settings Class-Level State

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and expected result before moving to the
> next step. If anything in the STOP conditions section occurs, stop and report
> back instead of improvising.
>
> **Drift check (run first)**: `git diff --stat HEAD -- app/ui/panel/api/settings.py app/ui/panel/server.py tests/`
> If any in-scope file changed since this plan was written, compare the
> Current state excerpts against the live code before proceeding.

## Status

- **Priority**: P1 (race condition in concurrent API requests)
- **Effort**: M (roughly 1 day including tests)
- **Risk**: MEDIUM (requires refactoring class-level state to instance-level)
- **Depends on**: none
- **Category**: correctness bug + concurrency
- **Planned at**: commit `HEAD`, 2026-09-21

## Why this matters

The settings API handler modifies class-level state (`handler.__class__.voice_pipeline`) without thread synchronization. When multiple API requests arrive concurrently (e.g., updating TTS provider, STT provider, or Oxyy models simultaneously), this can cause:

1. **Race conditions**: Multiple requests overwriting the class-level pipeline
2. **Lost updates**: One request's pipeline configuration can be lost
3. **Inconsistent state**: The pipeline might be in a partially updated state
4. **Cascading failures**: Corrupted pipeline state affects all subsequent voice operations

Evidence:
- `app/ui/panel/api/settings.py:123` - `handler.__class__.voice_pipeline = VoicePipeline(...)` without lock
- `app/ui/panel/api/settings.py:149` - `handler.__class__.voice_pipeline = VoicePipeline(...)` without lock
- `app/ui/panel/api/settings.py:178` - `handler.__class__.voice_pipeline = VoicePipeline(...)` without lock
- HTTP server can handle multiple concurrent requests to `/api/settings/*` endpoints

## Current state

### app/ui/panel/api/settings.py

Lines 120-125 (updating routes):
```python
if tts.get("provider") or stt.get("provider"):
    try:
        from app.services.voice.pipeline import VoicePipeline
        handler.__class__.voice_pipeline = VoicePipeline(settings=handler.settings)  # BUG: Class-level assignment
    except Exception as exc:
        print(f"[Settings] Falha ao recarregar pipeline após atualização de rotas: {exc}")
```

Lines 147-151 (updating Oxyy models):
```python
try:
    from app.services.voice.pipeline import VoicePipeline
    handler.__class__.voice_pipeline = VoicePipeline(settings=settings)  # BUG: Class-level assignment
except Exception as exc:
    print(f"[Settings] Falha ao recarregar modelos de voz Oxyy: {exc}")
```

Lines 175-180 (updating TTS provider):
```python
try:
    handler.settings.tts_provider = str(provider).lower()
    from app.services.voice.pipeline import VoicePipeline
    handler.__class__.voice_pipeline = VoicePipeline(settings=handler.settings)  # BUG: Class-level assignment
except Exception as exc:
    print(f"[Settings] Falha ao recarregar TTS: {exc}")
```

### app/ui/panel/server.py

The server likely uses the class-level pipeline:
```python
# Somewhere in server.py, the pipeline is accessed via handler.voice_pipeline
# or self.__class__.voice_pipeline
```

## Step-by-step implementation

### Step 1: Investigate server.py to understand pipeline usage

**File**: `app/ui/panel/server.py`

Search for all references to `voice_pipeline`:
```powershell
cd "C:\Users\maria\Desktop\Jarvis"
Select-String -Path "app\ui\panel\server.py" -Pattern "voice_pipeline" -Context 2
```

**Expected**: Identify all places where the pipeline is accessed and whether it's class-level or instance-level.

**Verification**: Check output to understand the pattern.

### Step 2: Add instance-level voice_pipeline to PanelHandler

**File**: `app/ui/panel/server.py`

Find the PanelHandler class definition and add instance-level pipeline in __init__:

If class-level assignment exists:
```python
class PanelHandler:
    voice_pipeline = None  # Remove this class-level assignment
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.voice_pipeline = None  # Add instance-level assignment
        # ... other init code
```

If it's set elsewhere, add:
```python
def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.voice_pipeline = None
    # ... other init code
```

### Step 3: Update set_voice_pipeline to use instance-level

**File**: `app/ui/panel/server.py`

Find the set_voice_pipeline method and update it:

If it looks like:
```python
def set_voice_pipeline(self, pipeline):
    PanelHandler.voice_pipeline = pipeline  # Change this
```

Change to:
```python
def set_voice_pipeline(self, pipeline):
    self.voice_pipeline = pipeline  # Instance-level assignment
```

### Step 4: Update all references to use instance-level

**File**: `app/ui/panel/server.py`

Search for all `self.__class__.voice_pipeline` or `PanelHandler.voice_pipeline` and change to `self.voice_pipeline`.

**Example**:
```python
# Change this:
if self.__class__.voice_pipeline:
    self.__class__.voice_pipeline.speak(text)

# To this:
if self.voice_pipeline:
    self.voice_pipeline.speak(text)
```

### Step 5: Update settings.py to use instance-level

**File**: `app/ui/panel/api/settings.py`

Change all three occurrences of class-level assignment to instance-level:

Line 123:
```python
# Change this:
handler.__class__.voice_pipeline = VoicePipeline(settings=handler.settings)

# To this:
handler.voice_pipeline = VoicePipeline(settings=handler.settings)
```

Line 149:
```python
# Change this:
handler.__class__.voice_pipeline = VoicePipeline(settings=settings)

# To this:
handler.voice_pipeline = VoicePipeline(settings=settings)
```

Line 178:
```python
# Change this:
handler.__class__.voice_pipeline = VoicePipeline(settings=handler.settings)

# To this:
handler.voice_pipeline = VoicePipeline(settings=handler.settings)
```

### Step 6: Add lock for thread-safe pipeline updates

**File**: `app/ui/panel/server.py`

Add lock to PanelHandler:

```python
import threading

class PanelHandler:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.voice_pipeline = None
        self._pipeline_lock = threading.Lock()  # Add lock for pipeline updates
        # ... other init code
```

Update set_voice_pipeline:
```python
def set_voice_pipeline(self, pipeline):
    with self._pipeline_lock:
        self.voice_pipeline = pipeline
```

### Step 7: Update settings.py to use lock

**File**: `app/ui/panel/api/settings.py`

Wrap all pipeline updates with the lock:

Line 120-125:
```python
if tts.get("provider") or stt.get("provider"):
    try:
        from app.services.voice.pipeline import VoicePipeline
        with handler._pipeline_lock:
            handler.voice_pipeline = VoicePipeline(settings=handler.settings)
    except Exception as exc:
        print(f"[Settings] Falha ao recarregar pipeline após atualização de rotas: {exc}")
```

Line 147-151:
```python
try:
    from app.services.voice.pipeline import VoicePipeline
    with handler._pipeline_lock:
        handler.voice_pipeline = VoicePipeline(settings=settings)
except Exception as exc:
    print(f"[Settings] Falha ao recarregar modelos de voz Oxyy: {exc}")
```

Line 175-180:
```python
try:
    handler.settings.tts_provider = str(provider).lower()
    from app.services.voice.pipeline import VoicePipeline
    with handler._pipeline_lock:
        handler.voice_pipeline = VoicePipeline(settings=handler.settings)
except Exception as exc:
    print(f"[Settings] Falha ao recarregar TTS: {exc}")
```

### Step 8: Add test for concurrent settings updates

**File**: `tests/test_settings_thread_safety.py` (new file)

Create test to verify thread safety:
```python
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.ui.panel.server import PanelHandler
from app.config import Settings


class TestSettingsThreadSafety:
    """Test thread safety of settings updates."""
    
    def test_concurrent_pipeline_updates(self):
        """Test that concurrent pipeline updates don't cause race conditions."""
        handler = PanelHandler()
        handler.settings = Settings()
        
        # Initialize pipeline
        from app.services.voice.pipeline import VoicePipeline
        handler.voice_pipeline = VoicePipeline(settings=handler.settings)
        
        def update_tts(provider: str):
            handler.settings.tts_provider = provider
            from app.services.voice.pipeline import VoicePipeline
            with handler._pipeline_lock:
                handler.voice_pipeline = VoicePipeline(settings=handler.settings)
            return True
        
        def update_stt(provider: str):
            handler.settings.stt_provider = provider
            from app.services.voice.pipeline import VoicePipeline
            with handler._pipeline_lock:
                handler.voice_pipeline = VoicePipeline(settings=handler.settings)
            return True
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for i in range(5):
                futures.append(executor.submit(update_tts, f"provider_{i}"))
                futures.append(executor.submit(update_stt, f"provider_{i}"))
            results = [f.result() for f in futures]
        
        # All should succeed
        assert all(results)
        # Pipeline should be in a valid state
        assert handler.voice_pipeline is not None
    
    def test_pipeline_lock_prevents_races(self):
        """Test that the lock actually prevents concurrent access."""
        handler = PanelHandler()
        handler.settings = Settings()
        handler._pipeline_lock = threading.Lock()
        
        # Initialize pipeline
        from app.services.voice.pipeline import VoicePipeline
        handler.voice_pipeline = VoicePipeline(settings=handler.settings)
        
        call_count = 0
        lock_held_count = 0
        
        def try_update():
            nonlocal call_count, lock_held_count
            call_count += 1
            if handler._pipeline_lock.locked():
                lock_held_count += 1
            with handler._pipeline_lock:
                handler.voice_pipeline = VoicePipeline(settings=handler.settings)
            return True
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(try_update) for _ in range(20)]
            results = [f.result() for f in futures]
        
        # All should succeed
        assert all(results)
        # Lock was held at least some of the time
        assert lock_held_count > 0
```

**Verification**:
- Command: `python -m pytest tests/test_settings_thread_safety.py -v`
- Expected: All tests pass

## Done criteria

- [ ] Class-level `voice_pipeline` removed from PanelHandler
- [ ] Instance-level `voice_pipeline` added to PanelHandler.__init__
- [ ] `set_voice_pipeline` updated to use instance-level
- [ ] All references to pipeline changed to instance-level
- [ ] `_pipeline_lock` added to PanelHandler
- [ ] All pipeline updates in settings.py wrapped with lock
- [ ] Thread safety tests created
- [ ] All tests pass
- [ ] `python -m compileall -q app` passes
- [ ] Manual test: Voice pipeline still works after settings updates

## Stop conditions

- If removing class-level pipeline breaks existing code that depends on it, STOP and add fallback support.
- If the lock causes deadlocks in practice (e.g., voice operation tries to acquire lock while settings update holds it), STOP and reconsider the locking strategy.
- If the server uses multiple handler instances and they need to share the pipeline, STOP and keep class-level but add proper locking.

## Maintenance notes

The voice pipeline is now instance-level with thread-safe updates. When adding new settings that modify the pipeline:

1. Always acquire `handler._pipeline_lock` before updating
2. Use `with handler._pipeline_lock:` context manager
3. Keep the critical section as short as possible
4. Don't call blocking operations while holding the lock

Future changes should consider whether to use a singleton pattern with proper locking if the pipeline needs to be shared across all handler instances.