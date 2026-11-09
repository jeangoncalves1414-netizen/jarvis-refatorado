import { lazy, type ComponentType, type LazyExoticComponent } from 'react'
import { Info, type LucideIcon } from 'lucide-react'
import type { PopupEnvelope, PopupOrigin } from './types'

// Registro dos modelos de popup. Espelho de app/agent/popups.py (POPUP_TEMPLATES): mesmos ids.
// O backend monta `data` a partir dos serviços; aqui `parseData` confere de novo o formato e um
// popup com dado inválido não abre.

export const POPUP_INFO = 'info'

export type InfoPopupData = { title: string; lines: string[]; tone: 'info' | 'ok' | 'warn' }

export type PopupComponentProps<D> = {
  popup: PopupEnvelope<D>
  revision: number
  // Popup ativo (ex.: ditado) pede para não expirar.
  setHold: (hold: boolean) => void
}

export type PopupDef<D = unknown> = {
  id: string
  title: string
  icon: LucideIcon
  parseData: (raw: unknown) => D | null
  // Cor da moldura a partir dos dados (opcional).
  tone?: (data: D) => string | undefined
  component: LazyExoticComponent<ComponentType<PopupComponentProps<D>>>
}

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value)

function parseInfo(raw: unknown): InfoPopupData | null {
  if (!isRecord(raw) || typeof raw.title !== 'string' || raw.title.length > 60) return null
  const lines = raw.lines === undefined ? [] : raw.lines
  if (!Array.isArray(lines) || lines.length > 6 || lines.some(line => typeof line !== 'string' || line.length > 120)) return null
  const tone = raw.tone === undefined ? 'info' : raw.tone
  if (tone !== 'info' && tone !== 'ok' && tone !== 'warn') return null
  return { title: raw.title, lines: lines as string[], tone }
}

const infoDef: PopupDef<InfoPopupData> = {
  id: POPUP_INFO,
  title: 'Aviso',
  icon: Info,
  parseData: parseInfo,
  tone: data => data.tone,
  component: lazy(() => import('./templates/InfoPopup').then(module => ({ default: module.InfoPopup }))),
}

export const popupRegistry: Record<string, PopupDef<any>> = {
  [POPUP_INFO]: infoDef,
}

export function getPopupDef(id: string): PopupDef<unknown> | undefined {
  return Object.prototype.hasOwnProperty.call(popupRegistry, id) ? popupRegistry[id] : undefined
}

const ORIGINS: PopupOrigin[] = ['chat', 'voice', 'command']

/** Confere o envelope e os dados do modelo. Devolve null se algo não bater. */
export function parsePopupEnvelope(raw: unknown): PopupEnvelope | null {
  if (!isRecord(raw)) return null
  const { id, key, template, version, title, origin, created_at, ttl_ms, pinned, animate } = raw
  if (typeof id !== 'string' || !id.startsWith('pop_') || id.length > 80) return null
  if (typeof key !== 'string' || !key || key.length > 160) return null
  if (typeof template !== 'string' || version !== 1) return null
  const def = getPopupDef(template)
  if (!def) return null
  const data = def.parseData(raw.data)
  if (data === null) return null
  return {
    id,
    key,
    template,
    version: 1,
    title: typeof title === 'string' && title.trim() ? title.slice(0, 80) : def.title,
    origin: ORIGINS.includes(origin as PopupOrigin) ? origin as PopupOrigin : 'chat',
    created_at: typeof created_at === 'number' ? created_at : Date.now() / 1000,
    ttl_ms: typeof ttl_ms === 'number' && Number.isFinite(ttl_ms) && ttl_ms >= 0 ? Math.min(ttl_ms, 600_000) : 8000,
    pinned: pinned === true,
    data,
    animate: isRecord(animate) ? animate : {},
  }
}

/** Popups que vieram no contexto da resposta final (context.ui_popups). */
export function extractPopups(context: unknown): unknown[] {
  const list = (context as { ui_popups?: unknown } | null | undefined)?.ui_popups
  return Array.isArray(list) ? list : []
}
