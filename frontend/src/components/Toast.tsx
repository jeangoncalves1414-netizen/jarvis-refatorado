import { useEffect } from 'react'

type ToastProps = {
  message: string
  onDismiss: () => void
  durationMs?: number
}

export function Toast({ message, onDismiss, durationMs = 4000 }: ToastProps) {
  useEffect(() => {
    if (!message) return
    const timer = window.setTimeout(onDismiss, durationMs)
    return () => window.clearTimeout(timer)
  }, [message, durationMs, onDismiss])

  if (!message) return null

  return (
    <div className="toast-container" role="status" aria-live="polite">
      <div className="toast-card">
        <span className="toast-dot" aria-hidden="true" />
        <p>{message}</p>
        <button type="button" className="toast-close" onClick={onDismiss} aria-label="Fechar aviso">
          ×
        </button>
      </div>
    </div>
  )
}
