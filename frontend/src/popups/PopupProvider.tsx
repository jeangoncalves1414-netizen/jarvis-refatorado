import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, type ReactNode } from 'react'
import { parsePopupEnvelope } from './registry'
import { POPUP_SETTINGS_DEFAULTS, type PopupEntry, type PopupEnvelope, type PopupSettings } from './types'

// Fila e pilha dos popups (lote 6). Até `max_visible` na tela; os demais esperam em fila FIFO.
// Um popup com a mesma `key` de outro visível (ou na fila) atualiza aquele no lugar. `id` repetido
// (o mesmo popup chegando pelo WebSocket e pela resposta final) é descartado.

export type PopupState = { visible: PopupEntry[]; queue: PopupEntry[]; seen: string[]; maxVisible: number }

export type PopupAction =
  | { type: 'show'; popup: PopupEnvelope }
  | { type: 'dismiss'; id: string }
  | { type: 'pin'; id: string; pinned?: boolean }
  | { type: 'hold'; id: string; hold: boolean }
  | { type: 'clear' }
  | { type: 'configure'; maxVisible: number }

const SEEN_LIMIT = 200

export const initialPopupState: PopupState = { visible: [], queue: [], seen: [], maxVisible: POPUP_SETTINGS_DEFAULTS.max_visible }

const clampVisible = (value: number) => Math.max(1, Math.min(5, Math.round(Number.isFinite(value) ? value : POPUP_SETTINGS_DEFAULTS.max_visible)))

function promote(state: PopupState): PopupState {
  if (state.visible.length >= state.maxVisible || !state.queue.length) return state
  const room = state.maxVisible - state.visible.length
  return { ...state, visible: [...state.visible, ...state.queue.slice(0, room)], queue: state.queue.slice(room) }
}

function updateEntry(entry: PopupEntry, popup: PopupEnvelope): PopupEntry {
  return { ...entry, popup, revision: entry.revision + 1, pinned: entry.pinned || popup.pinned }
}

export function reducePopups(state: PopupState, action: PopupAction): PopupState {
  switch (action.type) {
    case 'show': {
      const { popup } = action
      if (state.seen.includes(popup.id)) return state
      const seen = [...state.seen, popup.id].slice(-SEEN_LIMIT)
      if (state.visible.some(entry => entry.popup.key === popup.key)) {
        return { ...state, seen, visible: state.visible.map(entry => entry.popup.key === popup.key ? updateEntry(entry, popup) : entry) }
      }
      if (state.queue.some(entry => entry.popup.key === popup.key)) {
        return { ...state, seen, queue: state.queue.map(entry => entry.popup.key === popup.key ? updateEntry(entry, popup) : entry) }
      }
      const entry: PopupEntry = { popup, revision: 0, pinned: popup.pinned, hold: false }
      if (state.visible.length < state.maxVisible) return { ...state, seen, visible: [...state.visible, entry] }
      return { ...state, seen, queue: [...state.queue, entry] }
    }
    case 'dismiss': {
      const visible = state.visible.filter(entry => entry.popup.id !== action.id)
      const queue = state.queue.filter(entry => entry.popup.id !== action.id)
      if (visible.length === state.visible.length && queue.length === state.queue.length) return state
      return promote({ ...state, visible, queue })
    }
    case 'pin':
      return { ...state, visible: state.visible.map(entry => entry.popup.id === action.id ? { ...entry, pinned: action.pinned ?? !entry.pinned } : entry) }
    case 'hold':
      return { ...state, visible: state.visible.map(entry => entry.popup.id === action.id ? { ...entry, hold: action.hold } : entry) }
    case 'clear':
      return { ...state, visible: [], queue: [] }
    case 'configure': {
      const maxVisible = clampVisible(action.maxVisible)
      if (maxVisible === state.maxVisible) return state
      // Se o limite caiu, os popups mais antigos voltam para o começo da fila.
      const overflow = Math.max(0, state.visible.length - maxVisible)
      const next = { ...state, maxVisible, visible: state.visible.slice(overflow), queue: [...state.visible.slice(0, overflow), ...state.queue] }
      return promote(next)
    }
  }
}

type PopupsApi = {
  visible: PopupEntry[]
  queued: number
  settings: PopupSettings
  // false: envelope ou dados inválidos (o popup não abre).
  show: (raw: unknown) => boolean
  dismiss: (id: string) => void
  pin: (id: string, pinned?: boolean) => void
  hold: (id: string, hold: boolean) => void
  clear: () => void
  configure: (settings: Partial<PopupSettings>) => void
}

const PopupsContext = createContext<PopupsApi | null>(null)

export function usePopups() {
  const api = useContext(PopupsContext)
  if (!api) throw new Error('usePopups precisa estar dentro de PopupProvider.')
  return api
}

function readSettings(raw: unknown): PopupSettings {
  const value = (raw && typeof raw === 'object' ? raw : {}) as Partial<Record<keyof PopupSettings, unknown>>
  const int = (input: unknown, low: number, high: number, fallback: number) => typeof input === 'number' && Number.isInteger(input) && input >= low && input <= high ? input : fallback
  return {
    enabled: typeof value.enabled === 'boolean' ? value.enabled : POPUP_SETTINGS_DEFAULTS.enabled,
    auto: typeof value.auto === 'boolean' ? value.auto : POPUP_SETTINGS_DEFAULTS.auto,
    ttl_seconds: int(value.ttl_seconds, 0, 120, POPUP_SETTINGS_DEFAULTS.ttl_seconds),
    max_visible: int(value.max_visible, 1, 5, POPUP_SETTINGS_DEFAULTS.max_visible),
  }
}

export function PopupProvider({ children, loadSettings = true }: { children: ReactNode; loadSettings?: boolean }) {
  const [state, dispatch] = useReducer(reducePopups, initialPopupState)
  const [settings, setSettings] = useReducer((previous: PopupSettings, patch: Partial<PopupSettings>) => readSettings({ ...previous, ...patch }), POPUP_SETTINGS_DEFAULTS)

  // Lê a configuração uma vez; falha mantém os padrões.
  useEffect(() => {
    if (!loadSettings) return
    let cancelled = false
    fetch('/api/settings/popups')
      .then(response => response.ok ? response.json() : null)
      .then(data => { if (!cancelled && data?.ok && data.settings) setSettings(readSettings(data.settings)) })
      .catch(() => undefined)
    return () => { cancelled = true }
  }, [loadSettings])

  useEffect(() => { dispatch({ type: 'configure', maxVisible: settings.max_visible }) }, [settings.max_visible])

  const show = useCallback((raw: unknown) => {
    const popup = parsePopupEnvelope(raw)
    if (!popup) return false
    dispatch({ type: 'show', popup })
    return true
  }, [])
  const dismiss = useCallback((id: string) => dispatch({ type: 'dismiss', id }), [])
  const pin = useCallback((id: string, pinned?: boolean) => dispatch({ type: 'pin', id, pinned }), [])
  const hold = useCallback((id: string, value: boolean) => dispatch({ type: 'hold', id, hold: value }), [])
  const clear = useCallback(() => dispatch({ type: 'clear' }), [])
  const configure = useCallback((patch: Partial<PopupSettings>) => setSettings(patch), [])

  const api = useMemo<PopupsApi>(() => ({ visible: state.visible, queued: state.queue.length, settings, show, dismiss, pin, hold, clear, configure }), [state.visible, state.queue.length, settings, show, dismiss, pin, hold, clear, configure])
  return <PopupsContext.Provider value={api}>{children}</PopupsContext.Provider>
}
