import { useEffect, useState } from 'react'
import { panelRequest } from '../../utils/panelApi'

export function ContextMaintenance({ sessionId }: { sessionId: string }) {
  const [running, setRunning] = useState(false)
  useEffect(() => {
    let live = true
    setRunning(false)
    if (!sessionId) return
    const poll = () => void panelRequest<{ running: boolean }>(`/api/sessions/${encodeURIComponent(sessionId)}/context-status`)
      .then(data => { if (live) setRunning(data.running) }).catch(() => {})
    poll()
    const timer = window.setInterval(poll, 1500)
    return () => { live = false; clearInterval(timer) }
  }, [sessionId])
  return running ? <div role="status" aria-live="polite">Compactando o contexto após a conversa. Esta manutenção não pode ser cancelada; o histórico completo permanece salvo.</div> : null
}
