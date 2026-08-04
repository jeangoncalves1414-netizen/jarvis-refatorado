import { useState } from 'react'

export type DiffOp = {
  type: 'context' | 'remove' | 'add'
  text: string
}

function calculateDiff(oldText: string, newText: string): DiffOp[] {
  const a = oldText.split('\n')
  const b = newText.split('\n')
  const m = a.length
  const n = b.length

  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array<number>(n + 1).fill(0))

  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      if (a[i] === b[j]) dp[i][j] = dp[i + 1][j + 1] + 1
      else dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }

  const ops: DiffOp[] = []
  let i = 0
  let j = 0

  while (i < m && j < n) {
    if (a[i] === b[j]) {
      ops.push({ type: 'context', text: a[i] })
      i++
      j++
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      ops.push({ type: 'remove', text: a[i] })
      i++
    } else {
      ops.push({ type: 'add', text: b[j] })
      j++
    }
  }

  while (i < m) {
    ops.push({ type: 'remove', text: a[i] })
    i++
  }
  while (j < n) {
    ops.push({ type: 'add', text: b[j] })
    j++
  }

  return ops
}

export type EditToolProps = {
  filename?: string
  oldCode?: string
  newCode?: string
  diffOps?: DiffOp[]
  title?: string
  onApprove?: () => void
  onReject?: () => void
  isApproved?: boolean
  isRejected?: boolean
}

export function EditTool({
  filename = 'script.py',
  oldCode = '',
  newCode = '',
  diffOps: providedDiffOps,
  title = 'Proposta de Modificação de Código',
  onApprove,
  onReject,
  isApproved = false,
  isRejected = false,
}: EditToolProps) {
  const [status, setStatus] = useState<'pending' | 'approved' | 'rejected'>(
    isApproved ? 'approved' : isRejected ? 'rejected' : 'pending'
  )

  const ops = providedDiffOps || calculateDiff(oldCode, newCode)
  const addedCount = ops.filter((o) => o.type === 'add').length
  const removedCount = ops.filter((o) => o.type === 'remove').length

  const handleApprove = () => {
    setStatus('approved')
    onApprove?.()
  }

  const handleReject = () => {
    setStatus('rejected')
    onReject?.()
  }

  return (
    <div className="et-container">
      {/* Header */}
      <div className="et-header">
        <div className="et-header-left">
          <span className="et-icon">⚡</span>
          <span className="et-title">{title}</span>
          <code className="et-filename">{filename}</code>
        </div>
        <div className="et-stats">
          {addedCount > 0 && <span className="et-stat-add">+{addedCount}</span>}
          {removedCount > 0 && <span className="et-stat-rm">-{removedCount}</span>}
        </div>
      </div>

      {/* Diff Code View */}
      <div className="et-diff-view">
        <div className="et-code-table">
          {ops.map((op, idx) => (
            <div
              key={idx}
              className={`et-diff-line et-line-${op.type}`}
            >
              <span className="et-line-prefix">
                {op.type === 'add' ? '+' : op.type === 'remove' ? '-' : ' '}
              </span>
              <span className="et-line-content">{op.text || ' '}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Approval Footer */}
      <div className="et-footer">
        {status === 'pending' ? (
          <>
            <span className="et-status-pending">Aguardando confirmação de execução…</span>
            <div className="et-actions">
              <button type="button" onClick={handleReject} className="et-btn-reject">
                Rejeitar
              </button>
              <button type="button" onClick={handleApprove} className="et-btn-approve">
                ✓ Executar Código
              </button>
            </div>
          </>
        ) : status === 'approved' ? (
          <div className="et-status-approved">
            <span>✓ Execução Autorizada pelo Usuário</span>
          </div>
        ) : (
          <div className="et-status-rejected">
            <span>✕ Execução Cancelada</span>
          </div>
        )}
      </div>
    </div>
  )
}
