# Plan 013: Replace Native window.confirm() with Custom Confirmation Dialog

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and expected result before moving to the
> next step. If anything in the STOP conditions section occurs, stop and report
> back instead of improvising.
>
> **Drift check (run first)**: `git diff --stat HEAD -- frontend/src evolute/src tests/`
> If any in-scope file changed since this plan was written, compare the
> Current state excerpts against the live code before proceeding.

## Status

- **Priority**: P2 (UX consistency, not a security or data loss issue)
- **Effort**: M (roughly 1 day including component creation and replacement)
- **Risk**: LOW (replacing native dialogs with custom component)
- **Depends on**: none
- **Category**: tech debt + UX consistency
- **Planned at**: commit `HEAD`, 2026-09-21

## Why this matters

The current codebase uses `window.confirm()` for confirmation dialogs in 6 places across desktop and mobile interfaces. This causes:

1. **Inconsistent UX**: Native browser/OS alerts don't match Jarvis's design system
2. **Poor mobile experience**: Android WebView shows native Android alerts that break immersion
3. **No customization**: Cannot style, brand, or add additional context to native dialogs
4. **Fragmented approach**: StudyDialog exists but is domain-specific, not reusable

Evidence:
- `frontend/src/hooks/useDirectChat.ts:264` - `window.confirm('Excluir esta conversa?')`
- `frontend/src/App.tsx:372` - `window.confirm('Remover da memória semântica...')`
- `frontend/src/App.tsx:414` - `window.confirm('Remover esta tarefa?')`
- `frontend/src/hooks/useChat.ts:209` - `window.confirm('Excluir esta conversa?...')`
- `frontend/src/pages/MemoriesPage.tsx:52` - `window.confirm('Apagar todas as memórias...')`
- `evolute/src/components/ErrorBoundary.tsx:33` - `window.confirm('Deseja limpar os dados...')`

The project already has a custom dialog pattern in `StudyDialog.tsx` that can be adapted.

## Current state

### Native confirm() usage examples

**frontend/src/hooks/useDirectChat.ts:264**
```typescript
const deleteSession = useCallback((id: string) => {
  if (!window.confirm('Excluir esta conversa?')) return
  const updated = loadSessions().filter(s => s.id !== id)
  // ...
}, [])
```

**frontend/src/App.tsx:372**
```typescript
const clearTechnicalMemories = async () => {
  if (!window.confirm('Remover da memória semântica os erros técnicos antigos? Isso não remove conversas normais.')) return
  const response = await fetch('/api/memories/cleanup', { method: 'POST' })
  // ...
}
```

### Existing custom dialog pattern

**frontend/src/components/study/StudyDialog.tsx**
```typescript
export function StudyDialog({ open, title, description, kind = 'confirm', initialValue = '', initialColor = COLORS[0], confirmLabel = 'Confirmar', onClose, onSubmit }: StudyDialogProps) {
  const [value, setValue] = useState(initialValue)
  const [color, setColor] = useState(initialColor)
  useEffect(() => { if (open) { setValue(initialValue); setColor(initialColor) } }, [open, initialValue, initialColor])
  if (!open) return null
  return <div className="study-dialog-backdrop" role="presentation" onMouseDown={event => { if (event.currentTarget === event.target) onClose() }}>
    <div className="study-dialog" role="dialog" aria-modal="true" aria-labelledby="study-dialog-title">
      <div className="study-dialog-icon">{kind === 'category' ? '✦' : kind === 'text' ? '✎' : '!'}</div>
      <div className="study-dialog-copy"><h3 id="study-dialog-title">{title}</h3>{description && <p>{description}</p>}</div>
      {kind !== 'confirm' && <input autoFocus className="study-dialog-input" value={value} onChange={event => setValue(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && value.trim()) onSubmit(value.trim(), kind === 'category' ? color : undefined); if (event.key === 'Escape') onClose() }} placeholder={kind === 'category' ? 'Nome da categoria' : 'Nome da sessão'} />}
      {kind === 'category' && <div className="study-color-palette" aria-label="Paleta de cores">{COLORS.map(item => <button key={item} type="button" aria-label={`Usar cor ${item}`} className={color === item ? 'selected' : ''} style={{ backgroundColor: item }} onClick={() => setColor(item)} />)}</div>}
      <div className="study-dialog-actions"><button type="button" className="study-dialog-cancel" onClick={onClose}>Cancelar</button><button type="button" className="study-dialog-submit" disabled={kind !== 'confirm' && !value.trim()} onClick={() => onSubmit(value.trim(), kind === 'category' ? color : undefined)}>{confirmLabel}</button></div>
    </div>
  </div>
}
```

## Step-by-step implementation

### Step 1: Create generic ConfirmDialog component

**File**: `frontend/src/components/ConfirmDialog.tsx` (new file)

Create a reusable confirmation dialog component following the StudyDialog pattern but simplified for confirmations:

```typescript
import { useEffect } from 'react'

type ConfirmDialogProps = {
  open: boolean
  title: string
  message?: string
  confirmLabel?: string
  cancelLabel?: string
  variant?: 'danger' | 'warning' | 'info'
  onClose: () => void
  onConfirm: () => void
}

export function ConfirmDialog({ 
  open, 
  title, 
  message, 
  confirmLabel = 'Confirmar', 
  cancelLabel = 'Cancelar',
  variant = 'info',
  onClose, 
  onConfirm 
}: ConfirmDialogProps) {
  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && open) {
        onClose()
      }
    }
    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [open, onClose])

  if (!open) return null

  const variantIcon = {
    danger: '⚠',
    warning: '⚠',
    info: 'i'
  }[variant]

  const variantClass = `confirm-dialog-${variant}`

  return (
    <div className="confirm-dialog-backdrop" role="presentation" onMouseDown={event => {
      if (event.currentTarget === event.target) onClose()
    }}>
      <div className={`confirm-dialog ${variantClass}`} role="dialog" aria-modal="true" aria-labelledby="confirm-dialog-title">
        <div className="confirm-dialog-icon">{variantIcon}</div>
        <div className="confirm-dialog-content">
          <h3 id="confirm-dialog-title">{title}</h3>
          {message && <p>{message}</p>}
        </div>
        <div className="confirm-dialog-actions">
          <button type="button" className="confirm-dialog-cancel" onClick={onClose}>
            {cancelLabel}
          </button>
          <button 
            type="button" 
            className={`confirm-dialog-confirm ${variantClass}`}
            onClick={() => {
              onConfirm()
              onClose()
            }}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
```

**Verification**: 
- Command: `cd frontend && npm run build`
- Expected: No TypeScript errors

### Step 2: Add CSS styles for ConfirmDialog

**File**: `frontend/src/index.css` (or appropriate CSS file)

Add styles following the StudyDialog pattern:

```css
.confirm-dialog-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
}

.confirm-dialog {
  background: #1a1a2e;
  border: 1px solid #3b3b5c;
  border-radius: 12px;
  padding: 1.5rem;
  max-width: 400px;
  width: 100%;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.5);
  animation: dialogFadeIn 0.2s ease-out;
}

@keyframes dialogFadeIn {
  from {
    opacity: 0;
    transform: scale(0.95);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.confirm-dialog-icon {
  font-size: 2rem;
  margin-bottom: 1rem;
  text-align: center;
}

.confirm-dialog-content h3 {
  margin: 0 0 0.5rem 0;
  font-size: 1.25rem;
  color: #fff;
}

.confirm-dialog-content p {
  margin: 0;
  color: #a0a0b0;
  line-height: 1.5;
}

.confirm-dialog-actions {
  display: flex;
  gap: 0.75rem;
  margin-top: 1.5rem;
  justify-content: flex-end;
}

.confirm-dialog-cancel,
.confirm-dialog-confirm {
  padding: 0.5rem 1rem;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 500;
  transition: all 0.15s ease;
}

.confirm-dialog-cancel {
  background: #2a2a4a;
  color: #e0e0e0;
}

.confirm-dialog-cancel:hover {
  background: #3a3a5a;
}

.confirm-dialog-confirm {
  background: #60a5fa;
  color: #fff;
}

.confirm-dialog-confirm:hover {
  background: #3b82f6;
}

.confirm-dialog-danger {
  background: #ef4444;
}

.confirm-dialog-danger:hover {
  background: #dc2626;
}

.confirm-dialog-warning {
  background: #f59e0b;
  color: #fff;
}

.confirm-dialog-warning:hover {
  background: #d97706;
}
```

**Verification**:
- Command: `cd frontend && npm run build`
- Expected: No CSS errors, build succeeds

### Step 3: Replace window.confirm in useDirectChat.ts

**File**: `frontend/src/hooks/useDirectChat.ts`

Add state for dialog at component level:
```typescript
const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null)
```

Replace the deleteSession callback:
```typescript
const deleteSession = useCallback((id: string) => {
  setDeleteTargetId(id)
  setDeleteConfirmOpen(true)
}, [])

const handleDeleteConfirm = useCallback(() => {
  if (!deleteTargetId) return
  const updated = loadSessions().filter(s => s.id !== deleteTargetId)
  saveSessions(updated); setSessions(updated)
  try { localStorage.removeItem(HISTORY_PREFIX + deleteTargetId) } catch {}
  if (sessionId === deleteTargetId) {
    setSessionId(''); setMessages([]); localStorage.removeItem(ACTIVE_SESSION_KEY)
  }
  setDeleteConfirmOpen(false)
  setDeleteTargetId(null)
}, [deleteTargetId, sessionId])

const handleDeleteCancel = useCallback(() => {
  setDeleteConfirmOpen(false)
  setDeleteTargetId(null)
}, [])
```

Add the dialog component in the return statement (after existing JSX):
```typescript
<ConfirmDialog
  open={deleteConfirmOpen}
  title="Excluir conversa"
  message="Tem certeza que deseja excluir esta conversa? Esta ação não pode ser desfeita."
  variant="danger"
  confirmLabel="Excluir"
  cancelLabel="Cancelar"
  onClose={handleDeleteCancel}
  onConfirm={handleDeleteConfirm}
/>
```

**Verification**:
- Command: `cd frontend && npm run build`
- Expected: No TypeScript errors

### Step 4: Replace window.confirm in useChat.ts

**File**: `frontend/src/hooks/useChat.ts`

Follow the same pattern as Step 3:
1. Add state for dialog
2. Modify deleteSession to open dialog instead of using window.confirm
3. Add handleDeleteConfirm and handleDeleteCancel
4. Add ConfirmDialog component to return

**Verification**:
- Command: `cd frontend && npm run build`
- Expected: No TypeScript errors

### Step 5: Replace window.confirm in App.tsx (2 occurrences)

**File**: `frontend/src/App.tsx`

There are 2 confirmations:
1. Line 372: clearTechnicalMemories
2. Line 414: deleteTask

For each, follow the same pattern:
1. Add state for each dialog
2. Modify the function to open dialog
3. Add confirm/cancel handlers
4. Add ConfirmDialog components

**Verification**:
- Command: `cd frontend && npm run build`
- Expected: No TypeScript errors

### Step 6: Replace window.confirm in MemoriesPage.tsx

**File**: `frontend/src/pages/MemoriesPage.tsx`

Follow the same pattern for clearProfile (line 52).

**Verification**:
- Command: `cd frontend && npm run build`
- Expected: No TypeScript errors

### Step 7: Replace window.confirm in evolute ErrorBoundary.tsx

**File**: `evolute/src/components/ErrorBoundary.tsx`

Follow the same pattern for handleResetCache (line 33).

**Verification**:
- Command: `cd evolute && npm run build` (if evolute has build command)
- Expected: No TypeScript errors

### Step 8: Add tests for ConfirmDialog

**File**: `frontend/src/components/__tests__/ConfirmDialog.test.tsx` (new file)

Create basic tests:
```typescript
import { render, screen, fireEvent } from '@testing-library/react'
import { ConfirmDialog } from '../ConfirmDialog'

describe('ConfirmDialog', () => {
  it('renders when open', () => {
    render(
      <ConfirmDialog
        open={true}
        title="Test Title"
        message="Test message"
        onClose={() => {}}
        onConfirm={() => {}}
      />
    )
    expect(screen.getByText('Test Title')).toBeInTheDocument()
    expect(screen.getByText('Test message')).toBeInTheDocument()
  })

  it('does not render when closed', () => {
    render(
      <ConfirmDialog
        open={false}
        title="Test Title"
        onClose={() => {}}
        onConfirm={() => {}}
      />
    )
    expect(screen.queryByText('Test Title')).not.toBeInTheDocument()
  })

  it('calls onConfirm when confirm button clicked', () => {
    const onConfirm = jest.fn()
    const onClose = jest.fn()
    render(
      <ConfirmDialog
        open={true}
        title="Test Title"
        onClose={onClose}
        onConfirm={onConfirm}
      />
    )
    fireEvent.click(screen.getByText('Confirmar'))
    expect(onConfirm).toHaveBeenCalled()
    expect(onClose).toHaveBeenCalled()
  })

  it('calls onClose when cancel button clicked', () => {
    const onClose = jest.fn()
    render(
      <ConfirmDialog
        open={true}
        title="Test Title"
        onClose={onClose}
        onConfirm={() => {}}
      />
    )
    fireEvent.click(screen.getByText('Cancelar'))
    expect(onClose).toHaveBeenCalled()
  })

  it('closes on Escape key', () => {
    const onClose = jest.fn()
    render(
      <ConfirmDialog
        open={true}
        title="Test Title"
        onClose={onClose}
        onConfirm={() => {}}
      />
    )
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onClose).toHaveBeenCalled()
  })
})
```

**Verification**:
- Command: `cd frontend && npm test -- ConfirmDialog.test.tsx` (if test setup exists)
- Expected: All tests pass

## Done criteria

- [ ] ConfirmDialog component created with proper TypeScript types
- [ ] CSS styles added for all variants (danger, warning, info)
- [ ] All 6 window.confirm() calls replaced with ConfirmDialog
- [ ] useDirectChat.ts uses custom dialog for session deletion
- [ ] useChat.ts uses custom dialog for session deletion
- [ ] App.tsx uses custom dialog for both confirmations
- [ ] MemoriesPage.tsx uses custom dialog for profile clear
- [ ] evolute ErrorBoundary.tsx uses custom dialog for cache clear
- [ ] Tests created for ConfirmDialog component
- [ ] `npm run build` passes for frontend
- [ ] Manual test: Dialog opens and closes correctly on desktop
- [ ] Manual test: Dialog works on mobile (no native alert)

## Stop conditions

- If the CSS doesn't match the existing design system, STOP and review StudyDialog styles more closely.
- If replacing window.confirm breaks existing functionality (e.g., delete doesn't work), STOP and debug the state management.
- If the evolute build command doesn't exist or fails differently, STOP and document the limitation.
- If the new dialog causes focus/keyboard accessibility issues, STOP and add proper ARIA attributes and focus management.

## Maintenance notes

Future confirmation dialogs should use ConfirmDialog instead of window.confirm(). The component supports:
- Custom labels for confirm/cancel buttons
- Variant styling (danger for destructive actions, warning for caution, info for neutral)
- Keyboard support (Escape to close)
- Click-outside to close

When adding new confirmations, follow the pattern established in Step 3:
1. Add state for dialog open/close
2. Add state for any data needed in the confirm handler
3. Modify action to open dialog instead of executing immediately
4. Add confirm handler that executes the action
5. Add cancel handler that closes dialog
6. Render ConfirmDialog with appropriate props