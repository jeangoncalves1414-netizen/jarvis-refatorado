# Plan 004: Fix silent fetch errors in dashboard initialization

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 1861eae..HEAD -- frontend/src/App.tsx`
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

The dashboard initialization in `App.tsx` fires 13 fetch requests on mount with `.catch(() => undefined)` that silences all errors. When the backend is unavailable or returns errors, the dashboard loads with empty data and no error message. Users don't know if the issue is their data, their connection, or a server problem. Silent failures make debugging difficult and provide poor user experience.

## Current state

**File**: `frontend/src/App.tsx` — dashboard initialization useEffect

**Problem location** (lines 294-320):
```typescript
useEffect(() => {
  // ... 13 fetch requests like:
  fetch('/api/settings')
    .then(res => res.json())
    .then(data => { /* ... */ })
    .catch(() => undefined)  // Silent error swallowing
  // ... repeated 12 more times
}, [])
```

All fetch errors are silently ignored, returning `undefined` on failure.

**Repo conventions**:
- The codebase uses React state for error handling
- Error messages should be displayed to users
- No existing error boundary or toast system is evident

## Commands you will need

| Purpose   | Command                  | Expected on success |
|-----------|--------------------------|---------------------|
| Typecheck | `cd frontend && npx tsc --noEmit` | exit 0, no errors   |
| Build     | `cd frontend && npm run build` | exit 0              |

## Scope

**In scope**:
- `frontend/src/App.tsx` — add error state and replace silent catches with error handling
- Add error display UI to the dashboard

**Out of scope**:
- Creating a comprehensive error boundary system (deferred)
- Adding toast notification system (deferred)
- Other files with similar patterns (separate finding if needed)

## Git workflow

- Branch: `advisor/004-fix-silent-fetch-errors`
- Commit: `fix: add error handling for dashboard fetch requests`
- Do NOT push or open a PR unless instructed

## Steps

### Step 1: Add error state to App component

In `frontend/src/App.tsx`, add error state near the top of the component:
```typescript
const [dashboardError, setDashboardError] = useState<string | null>(null)
```

**Verify**: `cd frontend && npx tsc --noEmit` → exit 0, no errors

### Step 2: Replace silent catches with error handling

For each of the 13 fetch requests in the useEffect (lines 294-320), replace:
```typescript
.catch(() => undefined)
```

With:
```typescript
.catch(err => {
  console.error('Dashboard fetch error:', err)
  setDashboardError('Erro ao carregar dados do painel. Verifique a conexão.')
})
```

**Verify**: `cd frontend && npx tsc --noEmit` → exit 0, no errors

### Step 3: Add error display UI

In the dashboard JSX, add an error banner when `dashboardError` is set:
```typescript
{dashboardError && (
  <div style={{
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    background: '#ef4444',
    color: 'white',
    padding: '12px',
    textAlign: 'center',
    zIndex: 9999
  }}>
    {dashboardError}
    <button
      onClick={() => setDashboardError(null)}
      style={{
        marginLeft: '12px',
        background: 'white',
        color: '#ef4444',
        border: 'none',
        padding: '4px 12px',
        borderRadius: '4px',
        cursor: 'pointer'
      }}
    >
      Fechar
    </button>
  </div>
)}
```

Place this near the top of the JSX return, inside the main container.

**Verify**: `cd frontend && npx tsc --noEmit` → exit 0, no errors

### Step 4: Build to verify no runtime errors

**Verify**: `cd frontend && npm run build` → exit 0

## Test plan

- Manual test: Stop the backend server and reload the dashboard → error banner should appear
- Manual test: Restore backend and reload → dashboard should load normally
- Verify clicking "Fechar" dismisses the error banner

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `cd frontend && npx tsc --noEmit` exits 0
- [ ] `cd frontend && npm run build` exits 0
- [ ] `grep -n ".catch(() => undefined)" frontend/src/App.tsx` returns no matches
- [ ] Error state is added to the component
- [ ] Error display UI is added to the JSX
- [ ] No files outside `frontend/src/App.tsx` are modified (`git status`)
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- The code at lines 294-320 in `frontend/src/App.tsx` doesn't match the excerpts (drift detected)
- The typecheck fails after adding error state
- The build fails after changes
- You discover that a toast/notification system already exists (use it instead of inline banner)
- The number of fetch requests doesn't match 13 (report as scope expansion)

## Maintenance notes

- Consider migrating to a centralized error boundary or toast system in future
- Add retry logic for failed fetch requests in future
- Log errors to a monitoring service in production
