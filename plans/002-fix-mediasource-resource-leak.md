# Plan 002: Fix MediaSource resource leak by adding cleanup

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 1861eae..HEAD -- frontend/src/hooks/useMediaAssistant.ts`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit 1861eae, 2025-01-15

## Why this matters

The `createStreamingAudio` function in `useMediaAssistant.ts` adds event listeners to a MediaSource object and creates a Blob URL, but never removes the listeners or revokes the URL. Each call to this function accumulates listeners and URLs without cleanup, causing memory leaks during long-running sessions or repeated TTS calls. This can lead to performance degradation and eventual resource exhaustion.

## Current state

**File**: `frontend/src/hooks/useMediaAssistant.ts` — streaming audio creation

**Problem locations** (lines 62-92):
```typescript
// Line 62: Blob URL created
const url = URL.createObjectURL(blob)

// Lines 65, 74, 88: Event listeners added
mediaSource.addEventListener('sourceopen', handleSourceOpen)
mediaSource.addEventListener('sourceended', handleSourceEnded)
mediaSource.addEventListener('error', handleError)

// URL returned but never revoked
return url
```

The function returns the URL but provides no cleanup mechanism. Callers in the codebase do not revoke the URL or remove listeners, leading to accumulation.

**Repo conventions**:
- The codebase uses cleanup functions in hooks (useEffect cleanup pattern)
- Event listeners should be removed when no longer needed
- Blob URLs should be revoked after use

## Commands you will need

| Purpose   | Command                  | Expected on success |
|-----------|--------------------------|---------------------|
| Typecheck | `cd frontend && npx tsc --noEmit` | exit 0, no errors   |
| Build     | `cd frontend && npm run build` | exit 0              |

## Scope

**In scope**:
- `frontend/src/hooks/useMediaAssistant.ts` — modify `createStreamingAudio` function to return cleanup function
- All callers of `createStreamingAudio` in the same file to use the cleanup function

**Out of scope**:
- Other files that might use similar patterns (separate finding if needed)
- Changes to the MediaSource logic itself

## Git workflow

- Branch: `advisor/002-fix-mediasource-leak`
- Commit: `fix: add cleanup for MediaSource event listeners and Blob URLs`
- Do NOT push or open a PR unless instructed

## Steps

### Step 1: Modify createStreamingAudio to return cleanup function

In `frontend/src/hooks/useMediaAssistant.ts`, find the `createStreamingAudio` function. Change the return type from `string` to `{ url: string; cleanup: () => void }`.

After the event listeners are added (around line 88), add:
```typescript
const cleanup = () => {
  mediaSource.removeEventListener('sourceopen', handleSourceOpen)
  mediaSource.removeEventListener('sourceended', handleSourceEnded)
  mediaSource.removeEventListener('error', handleError)
  URL.revokeObjectURL(url)
}

return { url, cleanup }
```

**Verify**: `cd frontend && npx tsc --noEmit` → exit 0, no errors

### Step 2: Update all callers to use cleanup

Find all callers of `createStreamingAudio` in the file. For each caller:

1. Change `const url = createStreamingAudio(...)` to `const { url, cleanup } = createStreamingAudio(...)`
2. Add `cleanup()` call in the finally block or when the audio is no longer needed

Example pattern:
```typescript
try {
  const { url, cleanup } = createStreamingAudio(...)
  // ... use url
} finally {
  cleanup()
}
```

**Verify**: `cd frontend && npx tsc --noEmit` → exit 0, no errors

### Step 3: Build to verify no runtime errors

**Verify**: `cd frontend && npm run build` → exit 0

## Test plan

- Manual test: Trigger TTS audio multiple times and verify no memory accumulation
- Verify audio still plays correctly with cleanup
- Check browser DevTools Memory tab to confirm no leak after repeated calls

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `cd frontend && npx tsc --noEmit` exits 0
- [ ] `cd frontend && npm run build` exits 0
- [ ] `grep -n "return url" frontend/src/hooks/useMediaAssistant.ts` returns no matches (should return object)
- [ ] All callers of `createStreamingAudio` use the cleanup function
- [ ] No files outside `frontend/src/hooks/useMediaAssistant.ts` are modified (`git status`)
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- The code at lines 62-92 in `frontend/src/hooks/useMediaAssistant.ts` doesn't match the excerpts (drift detected)
- The typecheck fails after adding the cleanup function
- The build fails after changes
- You discover that cleanup is already handled elsewhere (this would invalidate the finding)
- There are callers in other files that would need updating (report this as scope expansion)

## Maintenance notes

- Any future uses of MediaSource should follow this cleanup pattern
- Consider adding a custom hook for MediaSource management to encapsulate this pattern
- Review other blob URL usages in the codebase for similar leaks
