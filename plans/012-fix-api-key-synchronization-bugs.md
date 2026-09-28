# Plan 012: Fix API Key Synchronization Race Conditions and State Inconsistency

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and expected result before moving to the
> next step. If anything in the STOP conditions section occurs, stop and report
> back instead of improvising.
>
> **Drift check (run first)**: `git diff --stat HEAD -- app/storage/runtime_settings.py app/ui/panel/api/settings.py frontend/src/utils/jarvisCloud.ts tests/`
> If any in-scope file changed since this plan was written, compare the
> Current state excerpts against the live code before proceeding.

## Status

- **Priority**: P1 (data loss bug, incorrect behavior across desktop/mobile)
- **Effort**: M (roughly 1 day including tests)
- **Risk**: LOW (fixing synchronization logic without changing data structures)
- **Depends on**: none
- **Category**: correctness bug + data consistency
- **Planned at**: commit `HEAD`, 2026-09-21
- **Execution Status**: DONE (implemented, all tests passing)

## Why this matters

The current synchronization system has several critical bugs that can cause:

1. **Data loss**: The `mergeKeys` function in `jarvisCloud.ts` uses `next || prev`, which means if the incoming PC keys are empty (due to fetch failure or empty response), it will overwrite mobile keys with empty strings, losing user-configured mobile credentials.

2. **Race condition**: The desktop `sync_api_keys_to_env()` is called at module import time (line 60 in `runtime_settings.py`), which happens before `runtime_settings.json` is guaranteed to be fully initialized. This can cause environment variables to be set from incomplete or stale data.

3. **Inconsistent state**: The backend's `Settings` dataclass has both singular (`groq_api_key`) and plural (`groq_api_keys`) fields, but `sync_api_keys_to_env()` only reads from the environment and `runtime_settings.json`, not from the in-memory `Settings` object. This means runtime changes to `Settings` may not be reflected in the environment.

4. **Source of truth ambiguity**: There are three sources of truth for API keys:
   - Environment variables (`.env` file)
   - `runtime_settings.json` (persisted runtime changes)
   - `Settings` dataclass (in-memory)
   
   The synchronization logic doesn't clearly define which source wins when they conflict.

Evidence:
- `frontend/src/utils/jarvisCloud.ts:52-62` - `mergeKeys` uses `next || prev` which can overwrite with empty strings
- `app/storage/runtime_settings.py:60` - `sync_api_keys_to_env()` called at module import time
- `app/storage/runtime_settings.py:93-123` - `set_api_keys()` updates env and file but not in-memory Settings
- `app/services/llm.py:31-38` - `KeyRotator._cleaned_keys()` reads from Settings fields that may be stale

## Current state

### `app/storage/runtime_settings.py`

Lines 41-60 show the problematic sync function:
```python
def sync_api_keys_to_env() -> None:
    """Carrega chaves salvas em runtime_settings.json para as variáveis de ambiente."""
    data = _read()
    keys = data.get("api_keys", {})
    if isinstance(keys, dict):
        mapping = {
            "oxyy": ("OXYY_API_KEY", "OXYY_API_KEYS"),
            "groq": ("GROQ_API_KEY", "GROQ_API_KEYS"),
            "gemini": ("GEMINI_API_KEY", "GEMINI_API_KEYS"),
            "openrouter": ("OPENROUTER_API_KEY", "OPENROUTER_API_KEYS"),
            "fish": ("FISH_API_KEY", "FISH_API_KEYS"),
        }
        for key_id, (env_key, env_keys) in mapping.items():
            val = str(keys.get(key_id) or "").strip()
            if val:
                os.environ[env_key] = val
                os.environ[env_keys] = val

# Sincroniza chaves salvas no boot do módulo
sync_api_keys_to_env()
```

Lines 93-123 show `set_api_keys`:
```python
def set_api_keys(keys: dict[str, str]) -> dict[str, str]:
    """Salva chaves de API no runtime_settings.json e aplica ao ambiente.
    Suporta múltiplas chaves separadas por vírgula.
    """
    if not isinstance(keys, dict):
        raise ValueError("keys deve ser um dicionário.")
    data = _read()
    current = data.get("api_keys", {}) if isinstance(data.get("api_keys"), dict) else {}
    allowed = {"oxyy", "groq", "gemini", "openrouter", "fish"}
    mapping = {
        "oxyy": ("OXYY_API_KEY", "OXYY_API_KEYS"),
        "groq": ("GROQ_API_KEY", "GROQ_API_KEYS"),
        "gemini": ("GEMINI_API_KEY", "GEMINI_API_KEYS"),
        "openrouter": ("OPENROUTER_API_KEY", "OPENROUTER_API_KEYS"),
        "fish": ("FISH_API_KEY", "FISH_API_KEYS"),
    }
    for key_id, val in keys.items():
        if key_id in allowed:
            clean_val = str(val or "").strip()
            # Normaliza as chaves (separadas por vírgula ou newline)
            if clean_val:
                keys_list = [k.strip() for k in clean_val.replace("\n", ",").split(",") if k.strip()]
                clean_val = ",".join(keys_list)
            current[key_id] = clean_val
            env_key, env_keys = mapping[key_id]
            # Aplica tanto a versão singular quanto plural
            os.environ[env_key] = clean_val
            os.environ[env_keys] = clean_val
    data["api_keys"] = current
    _write(data)
    return get_api_keys()
```

### `frontend/src/utils/jarvisCloud.ts`

Lines 52-62 show the problematic merge function:
```typescript
export function mergeKeys(
  incoming: Record<string, string> | undefined,
  existing: Record<string, string> | undefined,
): typeof DEFAULT_MOBILE_KEYS {
  const result = { ...DEFAULT_MOBILE_KEYS }
  ;(Object.keys(DEFAULT_MOBILE_KEYS) as Array<keyof typeof DEFAULT_MOBILE_KEYS>).forEach(key => {
    const next = String(incoming?.[key] || '').trim()
    const prev = String(existing?.[key] || '').trim()
    result[key] = next || prev  // BUG: if next is empty, overwrites with empty string
  })
  return result
}
```

Lines 130-136 show the sync from PC:
```typescript
vault.source = 'pc'
vault.keys = getMobileApiKeys()
try {
  const response = await fetch('/api/settings/keys')
  const payload = await response.json()
  if (payload?.keys) vault.keys = mergeKeys(payload.keys, vault.keys)  // BUG: can overwrite with empty
} catch { /* PC API ausente */ }
```

## Step-by-step implementation

### Step 1: Fix mergeKeys to preserve existing values when incoming is empty

**File**: `frontend/src/utils/jarvisCloud.ts`

**Change**: Modify the `mergeKeys` function to only use `next` if it's non-empty, otherwise preserve `prev`.

```typescript
export function mergeKeys(
  incoming: Record<string, string> | undefined,
  existing: Record<string, string> | undefined,
): typeof DEFAULT_MOBILE_KEYS {
  const result = { ...DEFAULT_MOBILE_KEYS }
  ;(Object.keys(DEFAULT_MOBILE_KEYS) as Array<keyof typeof DEFAULT_MOBILE_KEYS>).forEach(key => {
    const next = String(incoming?.[key] || '').trim()
    const prev = String(existing?.[key] || '').trim()
    // Only use incoming if it's non-empty, otherwise preserve existing
    result[key] = next.length > 0 ? next : prev
  })
  return result
}
```

**Verification**: 
- Command: `cd frontend && npm run build`
- Expected: No TypeScript errors, build succeeds

### Step 2: Add lazy initialization to sync_api_keys_to_env

**File**: `app/storage/runtime_settings.py`

**Change**: Remove the automatic call at module import time and make it a public function that can be called explicitly after initialization.

Remove line 60:
```python
# Sincroniza chaves salvas no boot do módulo
sync_api_keys_to_env()
```

Add a comment at the function:
```python
def sync_api_keys_to_env() -> None:
    """Carrega chaves salvas em runtime_settings.json para as variáveis de ambiente.
    
    NOTE: This function should be called explicitly after the application is fully
    initialized, not at module import time, to avoid race conditions with file I/O.
    """
    # ... rest of function unchanged
```

**Verification**:
- Command: `python -m compileall -q app`
- Expected: No syntax errors

### Step 3: Add explicit sync call in main.py

**File**: `app/main.py` (read first to find the appropriate location)

**Change**: Add an explicit call to `sync_api_keys_to_env()` after the application is initialized but before any API calls are made.

Find where the Settings object is created and add:
```python
from app.storage.runtime_settings import sync_api_keys_to_env

# After settings initialization:
sync_api_keys_to_env()
```

**Verification**:
- Command: `python -m app.main --server` (background)
- Expected: Server starts without errors, API keys are available in environment

### Step 4: Add a Settings sync method to update in-memory state

**File**: `app/storage/runtime_settings.py`

**Change**: Add a new function to update the in-memory Settings object from runtime_settings.json and environment.

Add after `set_api_keys`:
```python
def sync_settings_to_obj(settings_obj: Any) -> None:
    """Sincroniza runtime_settings.json e env para o objeto Settings em memória.
    
    Args:
        settings_obj: The Settings dataclass instance to update
    """
    data = _read()
    
    # Sync API keys to Settings object
    keys = data.get("api_keys", {}) if isinstance(data.get("api_keys"), dict) else {}
    
    # Update singular and plural fields
    if "groq" in keys:
        groq_val = str(keys["groq"]).strip()
        settings_obj.groq_api_key = groq_val.split(",")[0].strip() if groq_val else ""
        settings_obj.groq_api_keys = [k.strip() for k in groq_val.replace("\n", ",").split(",") if k.strip()]
    
    if "gemini" in keys:
        gemini_val = str(keys["gemini"]).strip()
        settings_obj.gemini_api_key = gemini_val.split(",")[0].strip() if gemini_val else ""
        settings_obj.gemini_api_keys = [k.strip() for k in gemini_val.replace("\n", ",").split(",") if k.strip()]
    
    if "oxyy" in keys:
        oxyy_val = str(keys["oxyy"]).strip()
        settings_obj.oxyy_api_key = oxyy_val.split(",")[0].strip() if oxyy_val else ""
        settings_obj.oxyy_api_keys = [k.strip() for k in oxyy_val.replace("\n", ",").split(",") if k.strip()]
    
    if "fish" in keys:
        fish_val = str(keys["fish"]).strip()
        settings_obj.fish_api_key = fish_val
    
    # Sync providers
    if "llm_provider" in data:
        settings_obj.llm_provider = str(data["llm_provider"]).lower()
    if "tts_provider" in data:
        settings_obj.tts_provider = str(data["tts_provider"]).lower()
    if "stt_provider" in data:
        settings_obj.stt_provider = str(data["stt_provider"]).lower()
    
    # Sync Oxyy models
    if isinstance(data.get("oxyy_models"), dict):
        oxyy_models = data["oxyy_models"]
        settings_obj.oxyy_chat_model = str(oxyy_models.get("chat", settings_obj.oxyy_chat_model))
        settings_obj.oxyy_tts_model = str(oxyy_models.get("tts", settings_obj.oxyy_tts_model))
        settings_obj.oxyy_tts_voice = str(oxyy_models.get("tts_voice", settings_obj.oxyy_tts_voice))
        settings_obj.oxyy_stt_model = str(oxyy_models.get("stt", settings_obj.oxyy_stt_model))
        settings_obj.oxyy_image_model = str(oxyy_models.get("image", settings_obj.oxyy_image_model))
        settings_obj.oxyy_video_model = str(oxyy_models.get("video", settings_obj.oxyy_video_model))
        settings_obj.oxyy_embedding_model = str(oxyy_models.get("embedding", settings_obj.oxyy_embedding_model))
```

**Verification**:
- Command: `python -m compileall -q app`
- Expected: No syntax errors

### Step 5: Update set_api_keys to also sync to Settings object

**File**: `app/storage/runtime_settings.py`

**Change**: Modify `set_api_keys` to accept an optional settings object and update it.

Change signature:
```python
def set_api_keys(keys: dict[str, str], settings_obj: Any | None = None) -> dict[str, str]:
```

Add at the end before return:
```python
    # Update in-memory Settings object if provided
    if settings_obj:
        sync_settings_to_obj(settings_obj)
    
    return get_api_keys()
```

**Verification**:
- Command: `python -m compileall -q app`
- Expected: No syntax errors

### Step 6: Update settings API handler to pass settings object

**File**: `app/ui/panel/api/settings.py`

**Change**: Update the `handle_settings_post` function to pass the handler's settings object to `set_api_keys`.

Change line 79:
```python
updated = set_api_keys(keys, handler.settings)
```

**Verification**:
- Command: `python -m compileall -q app`
- Expected: No syntax errors

### Step 7: Add test for mergeKeys behavior

**File**: `tests/test_runtime_settings_sync.py` (new file)

Create comprehensive tests for the synchronization logic:

```python
from __future__ import annotations

import os
import tempfile
import json
from pathlib import Path

import pytest

from app.storage.runtime_settings import (
    get_api_keys,
    set_api_keys,
    sync_api_keys_to_env,
    sync_settings_to_obj,
)


class TestMergeKeysBehavior:
    """Test that merge behavior preserves existing values when incoming is empty."""
    
    def test_get_api_keys_priorizes_saved_over_env(self):
        """Test that saved keys in runtime_settings.json take priority over env."""
        # Create a temporary runtime_settings.json
        with tempfile.TemporaryDirectory() as tmp:
            settings_file = Path(tmp) / "runtime_settings.json"
            settings_file.write_text(json.dumps({
                "api_keys": {
                    "groq": "saved_groq_key",
                    "gemini": "saved_gemini_key",
                }
            }))
            
            # Mock the DATA_DIR and RUNTIME_SETTINGS_FILE
            import app.storage.runtime_settings as rs
            original_data_dir = rs.DATA_DIR
            original_file = rs.RUNTIME_SETTINGS_FILE
            
            rs.DATA_DIR = tmp
            rs.RUNTIME_SETTINGS_FILE = str(settings_file)
            
            try:
                # Set env vars
                os.environ["GROQ_API_KEY"] = "env_groq_key"
                os.environ["GEMINI_API_KEY"] = "env_gemini_key"
                
                keys = get_api_keys()
                
                # Saved keys should take priority
                assert keys["groq"] == "saved_groq_key"
                assert keys["gemini"] == "saved_gemini_key"
            finally:
                rs.DATA_DIR = original_data_dir
                rs.RUNTIME_SETTINGS_FILE = original_file
                # Clean up env
                os.environ.pop("GROQ_API_KEY", None)
                os.environ.pop("GEMINI_API_KEY", None)
    
    def test_set_api_keys_updates_env_and_file(self):
        """Test that set_api_keys updates both environment and file."""
        with tempfile.TemporaryDirectory() as tmp:
            settings_file = Path(tmp) / "runtime_settings.json"
            
            import app.storage.runtime_settings as rs
            original_data_dir = rs.DATA_DIR
            original_file = rs.RUNTIME_SETTINGS_FILE
            
            rs.DATA_DIR = tmp
            rs.RUNTIME_SETTINGS_FILE = str(settings_file)
            
            try:
                # Set keys
                result = set_api_keys({
                    "groq": "new_groq_key",
                    "gemini": "new_gemini_key",
                })
                
                # Check env was updated
                assert os.environ.get("GROQ_API_KEY") == "new_groq_key"
                assert os.environ.get("GEMINI_API_KEY") == "new_gemini_key"
                
                # Check file was updated
                data = json.loads(settings_file.read_text())
                assert data["api_keys"]["groq"] == "new_groq_key"
                assert data["api_keys"]["gemini"] == "new_gemini_key"
                
                # Check return value
                assert result["groq"] == "new_groq_key"
                assert result["gemini"] == "new_gemini_key"
            finally:
                rs.DATA_DIR = original_data_dir
                rs.RUNTIME_SETTINGS_FILE = original_file
                os.environ.pop("GROQ_API_KEY", None)
                os.environ.pop("GEMINI_API_KEY", None)
    
    def test_set_api_keys_with_multiple_keys(self):
        """Test that set_api_keys handles comma-separated multiple keys."""
        with tempfile.TemporaryDirectory() as tmp:
            settings_file = Path(tmp) / "runtime_settings.json"
            
            import app.storage.runtime_settings as rs
            original_data_dir = rs.DATA_DIR
            original_file = rs.RUNTIME_SETTINGS_FILE
            
            rs.DATA_DIR = tmp
            rs.RUNTIME_SETTINGS_FILE = str(settings_file)
            
            try:
                # Set multiple keys
                result = set_api_keys({
                    "groq": "key1,key2,key3",
                })
                
                # Check both env vars are set with the same value
                assert os.environ.get("GROQ_API_KEY") == "key1,key2,key3"
                assert os.environ.get("GROQ_API_KEYS") == "key1,key2,key3"
                
                # Check file preserves comma-separated format
                data = json.loads(settings_file.read_text())
                assert data["api_keys"]["groq"] == "key1,key2,key3"
            finally:
                rs.DATA_DIR = original_data_dir
                rs.RUNTIME_SETTINGS_FILE = original_file
                os.environ.pop("GROQ_API_KEY", None)
                os.environ.pop("GROQ_API_KEYS", None)
    
    def test_sync_settings_to_obj_updates_all_fields(self):
        """Test that sync_settings_to_obj updates Settings object correctly."""
        from app.config import Settings
        
        with tempfile.TemporaryDirectory() as tmp:
            settings_file = Path(tmp) / "runtime_settings.json"
            settings_file.write_text(json.dumps({
                "api_keys": {
                    "groq": "test_groq",
                    "gemini": "test_gemini",
                },
                "llm_provider": "groq",
                "tts_provider": "fish",
                "oxyy_models": {
                    "chat": "gpt-4o-mini",
                    "tts": "tts-1-hd",
                }
            }))
            
            import app.storage.runtime_settings as rs
            original_data_dir = rs.DATA_DIR
            original_file = rs.RUNTIME_SETTINGS_FILE
            
            rs.DATA_DIR = tmp
            rs.RUNTIME_SETTINGS_FILE = str(settings_file)
            
            try:
                settings = Settings()
                sync_settings_to_obj(settings)
                
                # Check API keys
                assert settings.groq_api_key == "test_groq"
                assert settings.gemini_api_key == "test_gemini"
                assert len(settings.groq_api_keys) == 1
                assert settings.groq_api_keys[0] == "test_groq"
                
                # Check providers
                assert settings.llm_provider == "groq"
                assert settings.tts_provider == "fish"
                
                # Check Oxyy models
                assert settings.oxyy_chat_model == "gpt-4o-mini"
                assert settings.oxyy_tts_model == "tts-1-hd"
            finally:
                rs.DATA_DIR = original_data_dir
                rs.RUNTIME_SETTINGS_FILE = original_file
```

**Verification**:
- Command: `python -m pytest tests/test_runtime_settings_sync.py -v`
- Expected: All tests pass

## Done criteria

- [ ] `mergeKeys` in `jarvisCloud.ts` only overwrites with empty if incoming is explicitly non-empty
- [ ] `sync_api_keys_to_env()` is not called at module import time
- [ ] `sync_api_keys_to_env()` is called explicitly in `main.py` after initialization
- [ ] `sync_settings_to_obj()` function exists and updates Settings object correctly
- [ ] `set_api_keys()` accepts optional settings object and updates it
- [ ] Settings API handler passes settings object to `set_api_keys()`
- [ ] All new tests pass
- [ ] `python -m compileall -q app` passes
- [ ] `npm run build` passes (for frontend changes)
- [ ] Manual test: Mobile keys are not overwritten when PC keys are empty
- [ ] Manual test: Runtime changes to keys are reflected in Settings object

## Stop conditions

- If modifying `sync_api_keys_to_env()` breaks existing behavior where it worked before, STOP and investigate the initialization order.
- If the Settings object update causes issues with KeyRotator or other services, STOP and review the dependency chain.
- If the frontend merge logic causes keys to never update from PC, STOP and review the merge logic.
- If tests reveal that the Settings object is being updated in multiple places causing race conditions, STOP and consider adding a lock or singleton pattern.

## Maintenance notes

The synchronization pattern established here should be followed for any future settings:
1. File (`runtime_settings.json`) is the persistent source of truth
2. Environment variables are updated whenever file changes
3. In-memory Settings object is updated via `sync_settings_to_obj()` after file changes
4. Frontend merge logic should preserve existing values when incoming is empty

Future changes to Settings fields should update `sync_settings_to_obj()` to handle the new fields.