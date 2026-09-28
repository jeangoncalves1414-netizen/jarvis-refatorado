# Plan 001: Fix unsafe non-null assertion on nullable response body

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 1861eae..HEAD -- frontend/src/hooks/useDirectChat.ts`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit 1861eae, 2025-01-15

## Why this matters

The streaming chat handler uses non-null assertion (`!`) on `res.body` after checking `res.ok` but without verifying that the response actually has a body. If the response has no body (e.g., 204 No Content or certain error responses), the code will crash at runtime with "Cannot read properties of null". This causes silent failures in chat functionality when the API returns valid ok status but no body, making debugging difficult and providing poor user experience.

## Current state

**File**: `frontend/src/hooks/useDirectChat.ts` — streaming chat response handler

**Problem locations** (lines 198 and 238):
```typescript
// Line 198
const reader = res.body!.getReader()

// Line 238 (similar pattern)
const reader = res.body!.getReader()
```

The code checks `if (res.ok)` but not `if (res.body)` before using the non-null assertion. According to the Fetch API specification, a response can have `ok: true` but `body: null` (e.g., 204 No Content).

**Repo conventions**:
- Error handling in this codebase typically uses try-catch with early returns
- No specific pattern for null checks, but defensive programming is standard

## Commands you will need

| Purpose   | Command                  | Expected on success |
|-----------|--------------------------|---------------------|
| Typecheck | `cd frontend && npx tsc --noEmit` | exit 0, no errors   |
| Build     | `cd frontend && npm run build` | exit 0              |

## Scope

**In scope**:
- `frontend/src/hooks/useDirectChat.ts` — lines 198 and 238

**Out of scope**:
- Any other files
- Any changes to the public API or response handling logic

## Git workflow

- Branch: `advisor/001-fix-non-null-assertion`
- Commit: `fix: add null check before accessing response body in useDirectChat`
- Do NOT push or open a PR unless instructed

## Steps

### Step 1: Add null check before first reader access

In `frontend/src/hooks/useDirectChat.ts`, find line 198. Replace:
```typescript
const reader = res.body!.getReader()
```

With:
```typescript
if (!res.body) {
  throw new Error('Response has no body')
}
const reader = res.body.getReader()
```

**Verify**: `cd frontend && npx tsc --noEmit` → exit 0, no errors

### Step 2: Add null check before second reader access

In `frontend/src/hooks/useDirectChat.ts`, find line 238. Replace:
```typescript
const reader = res.body!.getReader()
```

With:
```typescript
if (!res.body) {
  throw new Error('Response has no body')
}
const reader = res.body.getReader()
```

**Verify**: `cd frontend && npx tsc --noEmit` → exit 0, no errors

### Step 3: Build to verify no runtime errors

**Verify**: `cd frontend && npm run build` → exit 0

## Test plan

- Manual test: Trigger a chat response and verify streaming works normally
- Edge case: Simulate a 204 No Content response to verify the error is thrown appropriately
- No automated tests exist for this hook; manual verification is sufficient

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `cd frontend && npx tsc --noEmit` exits 0
- [ ] `cd frontend && npm run build` exits 0
- [ ] `grep -n "res.body!" frontend/src/hooks/useDirectChat.ts` returns no matches
- [ ] No files outside `frontend/src/hooks/useDirectChat.ts` are modified (`git status`)
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- The code at lines 198 and 238 in `frontend/src/hooks/useDirectChat.ts` doesn't match the excerpts (drift detected)
- The typecheck fails after adding the null checks
- The build fails after changes
- You discover that `res.body` is already guaranteed to be non-null by the caller (this would invalidate the finding)

## Maintenance notes

- If the streaming logic is refactored to use a shared reader extraction function, ensure the null check is preserved
- Review any future additions of `res.body!` in the codebase for similar issues
