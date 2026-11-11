import { useEffect, useState } from 'react'
import { autoSignIn, getEvoluteSettings } from '../utils/evoluteCloud'

export function CloudSessionStatus() {
  const [warning, setWarning] = useState('')
  useEffect(() => {
    let disposed = false
    let busy = false
    const restore = async () => {
      const settings = getEvoluteSettings()
      if (!settings.userEmail && !settings.supabaseRefreshToken) { setWarning(''); return }
      if (busy) return
      busy = true
      try {
        const result = await autoSignIn()
        const current = getEvoluteSettings()
        if (!disposed) setWarning(!current.userEmail && !current.supabaseRefreshToken || result.success ? '' : `Não foi possível reconectar sua conta. ${result.error || 'Verifique a conexão.'}`)
      } finally { busy = false }
    }
    void restore()
    const timer = window.setInterval(() => void restore(), 60000)
    const reconnect = () => void restore()
    window.addEventListener('online', reconnect)
    window.addEventListener('jarvis:auth-changed', reconnect)
    return () => { disposed = true; window.clearInterval(timer); window.removeEventListener('online', reconnect); window.removeEventListener('jarvis:auth-changed', reconnect) }
  }, [])
  if (!warning) return null
  return <div className="ws-cloud-warning" role="alert"><span>{warning}</span><button onClick={() => window.dispatchEvent(new Event('jarvis:open-settings'))}>Abrir Configurações</button></div>
}
