import { useEffect, useId, useRef } from 'react'

type ConfirmDialogProps = {
  title: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  danger?: boolean
  busy?: boolean
  onConfirm: () => void
  onCancel: () => void
}

// Diálogo de confirmação do app (substitui window.confirm). Desenhado para ficar sobre o conteúdo do
// pai posicionado (janela ou página). Esc e clique fora cancelam; o foco inicial fica em "Cancelar".
export function ConfirmDialog({ title, message, confirmLabel = 'Confirmar', cancelLabel = 'Cancelar', danger = false, busy = false, onConfirm, onCancel }: ConfirmDialogProps) {
  const cancelButton = useRef<HTMLButtonElement>(null)
  const titleId = useId()
  const messageId = useId()
  useEffect(() => { cancelButton.current?.focus() }, [])
  return (
    <div className="ws-confirm-backdrop" onClick={event => { if (event.target === event.currentTarget && !busy) onCancel() }}>
      <div
        className="ws-confirm"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={messageId}
        onKeyDown={event => {
          if (event.key !== 'Escape') return
          event.preventDefault()
          event.stopPropagation()
          if (!busy) onCancel()
        }}
      >
        <h3 id={titleId}>{title}</h3>
        <p id={messageId}>{message}</p>
        <div className="ws-confirm-actions">
          <button type="button" ref={cancelButton} className="ws-button" disabled={busy} onClick={onCancel}>{cancelLabel}</button>
          <button type="button" className={`ws-button ${danger ? 'danger' : 'primary'}`} disabled={busy} onClick={onConfirm}>{busy ? 'Aguarde…' : confirmLabel}</button>
        </div>
      </div>
    </div>
  )
}
