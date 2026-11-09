import { createContext, Suspense, useCallback, useContext, useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent, type ReactNode } from 'react'
import { Maximize2, Minimize2, X } from 'lucide-react'
import { ErrorBoundary } from '../components/ErrorBoundary'
import type { OperationalState } from '../hooks/useOperationalSnapshot'
import { getWindowDef, type WindowDef } from './registry'

// Gerenciador de janelas do app: várias janelas, foco/z-order, arrastar, redimensionar, maximizar e
// fechar. Em larguras de celular (<= 640px) cada janela vira uma folha em tela cheia.

const MOBILE_QUERY = '(max-width: 640px)'
const MIN_WIDTH = 360
const MIN_HEIGHT = 280
const CASCADE = 28

type WindowState = {
  id: string
  params: unknown
  // Muda quando a janela é reaberta com novos parâmetros; força o conteúdo a ler os parâmetros de novo.
  nonce: number
  x: number
  y: number
  w: number
  h: number
  z: number
  maximized: boolean
}

type WindowsApi = {
  windows: WindowState[]
  focusedId: string | null
  // Retorna false se o id não está no registro ou se os parâmetros são inválidos.
  open: (id: string, rawParams?: unknown) => boolean
  close: (id: string) => void
  focus: (id: string) => void
  update: (id: string, patch: Partial<Pick<WindowState, 'x' | 'y' | 'w' | 'h' | 'maximized'>>) => void
}

const WindowsContext = createContext<WindowsApi | null>(null)

export function useWindows() {
  const api = useContext(WindowsContext)
  if (!api) throw new Error('useWindows precisa estar dentro de WindowProvider.')
  return api
}

const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value))

export function WindowProvider({ children }: { children: ReactNode }) {
  const [windows, setWindows] = useState<WindowState[]>([])
  const zRef = useRef(10)
  const nonceRef = useRef(0)

  const open = useCallback((id: string, rawParams?: unknown) => {
    const def = getWindowDef(id)
    if (!def) return false
    const params = def.parseParams(rawParams)
    if (params === null) return false
    const z = ++zRef.current
    const nonce = ++nonceRef.current
    setWindows(previous => {
      const existing = previous.find(item => item.id === id)
      if (existing) return previous.map(item => item.id === id ? { ...item, z, params: rawParams === undefined ? item.params : params, nonce: rawParams === undefined ? item.nonce : nonce } : item)
      const w = Math.min(def.width, window.innerWidth - 32)
      const h = Math.min(def.height, window.innerHeight - 32)
      const shift = previous.length * CASCADE
      return [...previous, {
        id, params, nonce, z, w, h, maximized: false,
        x: Math.max(8, Math.round((window.innerWidth - w) / 2) + shift),
        y: Math.max(8, Math.round((window.innerHeight - h) / 3) + shift),
      }]
    })
    return true
  }, [])

  const close = useCallback((id: string) => setWindows(previous => previous.filter(item => item.id !== id)), [])

  const focus = useCallback((id: string) => {
    setWindows(previous => {
      const top = previous.reduce((max, item) => Math.max(max, item.z), 0)
      const current = previous.find(item => item.id === id)
      if (!current || current.z === top) return previous
      return previous.map(item => item.id === id ? { ...item, z: ++zRef.current } : item)
    })
  }, [])

  const update = useCallback((id: string, patch: Partial<Pick<WindowState, 'x' | 'y' | 'w' | 'h' | 'maximized'>>) => {
    setWindows(previous => previous.map(item => item.id === id ? { ...item, ...patch } : item))
  }, [])

  const focusedId = useMemo(() => windows.length ? windows.reduce((a, b) => a.z > b.z ? a : b).id : null, [windows])
  const api = useMemo<WindowsApi>(() => ({ windows, focusedId, open, close, focus, update }), [windows, focusedId, open, close, focus, update])
  return <WindowsContext.Provider value={api}>{children}</WindowsContext.Provider>
}

function useMobileViewport() {
  const [mobile, setMobile] = useState(() => typeof window.matchMedia === 'function' && window.matchMedia(MOBILE_QUERY).matches)
  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return
    const query = window.matchMedia(MOBILE_QUERY)
    const onChange = () => setMobile(query.matches)
    onChange()
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])
  return mobile
}

  export function WindowHost({ operational, openRun }: { operational: OperationalState; openRun?: (id: string) => void }) {
    const { windows, focusedId, close, focus, update } = useWindows()
    const mobile = useMobileViewport()

    // Esc fecha a janela focada. Ignora o evento se um diálogo interno já o tratou ou se o foco está
    // em outra parte da interface (paleta, menu lateral).
    useEffect(() => {
      if (!focusedId) return
      const onKeyDown = (event: KeyboardEvent) => {
        if (event.key !== 'Escape' || event.defaultPrevented) return
        const active = document.activeElement
        const frame = document.querySelector(`[data-window-id="${focusedId}"]`)
        if (active && active !== document.body && !frame?.contains(active)) return
        close(focusedId)
      }
      document.addEventListener('keydown', onKeyDown)
      return () => document.removeEventListener('keydown', onKeyDown)
    }, [focusedId, close])

    if (!windows.length) return null
    return (
      <div className="ws-window-layer">
        {windows.map(state => {
          const def = getWindowDef(state.id)
          if (!def) return null
          return (
            <WindowFrame
              key={state.id}
              state={state}
              def={def}
              focused={state.id === focusedId}
              mobile={mobile}
              operational={operational}
              openRun={openRun}
              onFocus={() => focus(state.id)}
              onClose={() => close(state.id)}
              onChange={patch => update(state.id, patch)}
            />
          )
        })}
      </div>
    )
  }

  type FrameProps = {
    state: WindowState
    def: WindowDef<unknown>
    focused: boolean
    mobile: boolean
    operational: OperationalState
    openRun?: (id: string) => void
    onFocus: () => void
    onClose: () => void
    onChange: (patch: Partial<Pick<WindowState, 'x' | 'y' | 'w' | 'h' | 'maximized'>>) => void
  }

    function WindowFrame({ state, def, focused, mobile, operational, openRun, onFocus, onClose, onChange }: FrameProps) {
      const frame = useRef<HTMLDivElement>(null)
      const Content = def.component
      const Icon = def.icon
      const titleId = `ws-window-title-${state.id}`

      useEffect(() => { frame.current?.focus({ preventScroll: true }) }, [])
      useEffect(() => { if (focused && !frame.current?.contains(document.activeElement)) frame.current?.focus({ preventScroll: true }) }, [focused])

      const freeLayout = !mobile && !state.maximized

      const startDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
        if (!freeLayout || event.button !== 0 || (event.target as HTMLElement).closest('button')) return
        event.preventDefault()
        const target = event.currentTarget
        target.setPointerCapture(event.pointerId)
        const startX = event.clientX
        const startY = event.clientY
        const originX = state.x
        const originY = state.y
        const move = (moveEvent: PointerEvent) => onChange({
          x: clamp(originX + moveEvent.clientX - startX, 120 - state.w, window.innerWidth - 120),
          y: clamp(originY + moveEvent.clientY - startY, 0, window.innerHeight - 44),
        })
        const stop = () => {
          target.removeEventListener('pointermove', move)
          target.removeEventListener('pointerup', stop)
          target.removeEventListener('pointercancel', stop)
        }
        target.addEventListener('pointermove', move)
        target.addEventListener('pointerup', stop)
        target.addEventListener('pointercancel', stop)
      }

      const startResize = (edge: 'e' | 's' | 'se') => (event: ReactPointerEvent<HTMLDivElement>) => {
        if (!freeLayout || event.button !== 0) return
        event.preventDefault()
        event.stopPropagation()
        const target = event.currentTarget
        target.setPointerCapture(event.pointerId)
        const startX = event.clientX
        const startY = event.clientY
        const originW = state.w
        const originH = state.h
        const move = (moveEvent: PointerEvent) => onChange({
          ...(edge !== 's' ? { w: clamp(originW + moveEvent.clientX - startX, MIN_WIDTH, Math.max(MIN_WIDTH, window.innerWidth - state.x)) } : {}),
          ...(edge !== 'e' ? { h: clamp(originH + moveEvent.clientY - startY, MIN_HEIGHT, Math.max(MIN_HEIGHT, window.innerHeight - state.y)) } : {}),
        })
        const stop = () => {
          target.removeEventListener('pointermove', move)
          target.removeEventListener('pointerup', stop)
          target.removeEventListener('pointercancel', stop)
        }
        target.addEventListener('pointermove', move)
        target.addEventListener('pointerup', stop)
        target.addEventListener('pointercancel', stop)
      }

      const className = ['ws-window', focused ? 'focused' : '', mobile ? 'mobile' : '', state.maximized && !mobile ? 'maximized' : ''].filter(Boolean).join(' ')
      const style = freeLayout ? { left: state.x, top: state.y, width: state.w, height: state.h, zIndex: state.z } : { zIndex: state.z }

      return (
        <div
          ref={frame}
          className={className}
          style={style}
          role="dialog"
          aria-modal="false"
          aria-labelledby={titleId}
          data-window-id={state.id}
          tabIndex={-1}
          onPointerDownCapture={onFocus}
        >
          <div className="ws-window-titlebar" onPointerDown={startDrag} onDoubleClick={event => { if (!mobile && !(event.target as HTMLElement).closest('button')) onChange({ maximized: !state.maximized }) }}>
            <Icon size={15} aria-hidden="true" />
            <strong id={titleId}>{def.title}</strong>
            <span className="ws-window-spacer" />
            {!mobile && (
              <button type="button" className="ws-window-button" aria-label={state.maximized ? 'Restaurar janela' : 'Maximizar janela'} title={state.maximized ? 'Restaurar' : 'Maximizar'} onClick={() => onChange({ maximized: !state.maximized })}>
                {state.maximized ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
              </button>
            )}
            <button type="button" className="ws-window-button" aria-label="Fechar janela" title="Fechar (Esc)" onClick={onClose}><X size={15} /></button>
          </div>
          <div className="ws-window-body">
            <ErrorBoundary fallbackTitle="Não foi possível abrir esta janela.">
              <Suspense fallback={<p className="ws-window-loading">Carregando…</p>}>
                <Content key={state.nonce} params={state.params} operational={operational} openRun={openRun} />
              </Suspense>
            </ErrorBoundary>
          </div>
          {freeLayout && (
            <>
              <div className="ws-window-resize ws-window-resize-e" onPointerDown={startResize('e')} />
              <div className="ws-window-resize ws-window-resize-s" onPointerDown={startResize('s')} />
              <div className="ws-window-resize ws-window-resize-se" onPointerDown={startResize('se')} />
            </>
          )}
        </div>
      )
    }
