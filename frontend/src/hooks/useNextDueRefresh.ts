import { useEffect, useRef, useState } from 'react'

// Quando a fila está vazia mas há um cartão em aprendizado vencendo hoje, mostra quantos minutos
// faltam e recarrega a fila no horário em que ele vence.
export function useNextDueRefresh(nextDueAt: string | null | undefined, active: boolean, refresh: () => unknown) {
  const refreshRef = useRef(refresh)
  refreshRef.current = refresh
  const [now, setNow] = useState(() => Date.now())
  const dueTime = nextDueAt ? Date.parse(nextDueAt) : NaN
  const enabled = active && Number.isFinite(dueTime)

  useEffect(() => {
    if (!enabled) return
    setNow(Date.now())
    const delay = Math.min(Math.max(0, dueTime - Date.now()) + 1000, 24 * 60 * 60 * 1000)
    const timeout = window.setTimeout(() => {
      Promise.resolve(refreshRef.current()).catch(() => undefined)
    }, delay)
    const ticker = window.setInterval(() => setNow(Date.now()), 30_000)
    return () => {
      window.clearTimeout(timeout)
      window.clearInterval(ticker)
    }
  }, [enabled, dueTime])

  if (!enabled) return null
  return Math.max(1, Math.ceil((dueTime - now) / 60000))
}
