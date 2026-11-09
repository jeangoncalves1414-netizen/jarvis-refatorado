import { Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence } from 'framer-motion'
import { ErrorBoundary } from '../components/ErrorBoundary'
import { PopupFrame } from './motion'
import { usePopups } from './PopupProvider'
import { getPopupDef } from './registry'
import type { PopupEntry } from './types'

// Camada fixa e não modal dos popups: canto inferior direito no desktop, topo no celular.
// Cliques fora dos cartões passam direto para o app (pointer-events só nos cartões).

export function PopupHost() {
  const { visible, queued, dismiss, pin, hold } = usePopups()
  return (
    <div className="ws-popup-layer" aria-live="polite" aria-label="Popups do agente">
      <AnimatePresence initial={false}>
        {visible.map(entry => (
          // A chave do React é a do popup: atualizar pela mesma chave mantém o cartão no lugar.
          <PopupItem key={entry.popup.key} entry={entry} onDismiss={dismiss} onPin={pin} onHold={hold} />
        ))}
      </AnimatePresence>
      {queued > 0 && <p className="ws-popup-queue" role="status">+{queued} na fila</p>}
    </div>
  )
}

type ItemProps = {
  entry: PopupEntry
  onDismiss: (id: string) => void
  onPin: (id: string, pinned?: boolean) => void
  onHold: (id: string, hold: boolean) => void
}

function PopupItem({ entry, onDismiss, onPin, onHold }: ItemProps) {
  const { popup, revision, pinned, hold } = entry
  const def = getPopupDef(popup.template)
  const ttl = popup.ttl_ms
  const expiring = ttl > 0 && !pinned && !hold
  const [entered, setEntered] = useState(false)
  const [paused, setPaused] = useState(false)
  const remaining = useRef(ttl)

  // Atualização pela mesma chave recomeça a contagem.
  useEffect(() => { remaining.current = ttl }, [revision, ttl])

  // O tempo só conta com o popup já animado e pausa com mouse ou foco.
  useEffect(() => {
    if (!expiring || !entered || paused) return
    const startedAt = performance.now()
    const timer = window.setTimeout(() => onDismiss(popup.id), Math.max(0, remaining.current))
    return () => {
      window.clearTimeout(timer)
      remaining.current -= performance.now() - startedAt
    }
  }, [expiring, entered, paused, revision, popup.id, onDismiss])

  const setHold = useCallback((value: boolean) => onHold(popup.id, value), [onHold, popup.id])
  if (!def) return null
  const Content = def.component
  return (
    <PopupFrame
      id={popup.id}
      title={popup.title || def.title}
      icon={def.icon}
      pinned={pinned}
      tone={def.tone?.(popup.data)}
      ttl={expiring ? { ms: ttl, running: entered && !paused, revision } : null}
      onPin={() => onPin(popup.id)}
      onClose={() => onDismiss(popup.id)}
      onEntered={() => setEntered(true)}
      onPause={setPaused}
    >
      <ErrorBoundary fallbackTitle="Não foi possível mostrar este popup.">
        <Suspense fallback={<p className="ws-popup-loading">Carregando…</p>}>
          <Content popup={popup} revision={revision} setHold={setHold} />
        </Suspense>
      </ErrorBoundary>
    </PopupFrame>
  )
}
