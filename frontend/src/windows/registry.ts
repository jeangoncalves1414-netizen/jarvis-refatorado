import { lazy, type ComponentType, type LazyExoticComponent } from 'react'
import { MapPinned, MonitorCog, Wallet, type LucideIcon } from 'lucide-react'
import type { OperationalState } from '../hooks/useOperationalSnapshot'

// Registro de janelas do app. O agente (ferramenta open_window) e os comandos só escolhem ids
// daqui e preenchem parâmetros validados; nunca geram interface. O espelho no backend, com as
// mesmas regras de validação, está em app/agent/tools/open_window.py.

export const WINDOW_FINANCE = 'finance'

export type FinanceWindowParams = {
  type?: 'expense' | 'income'
  category?: string
  period?: 'week' | 'month' | 'all'
  amount?: number
  description?: string
  date?: string
}

export const WINDOW_PC_CONTROLS = 'pc-controls'

// A janela de controles do PC não recebe parâmetros: o agente só pede que ela abra.
export type PcControlsWindowParams = Record<string, never>

export const WINDOW_PLACES = 'places'

// Busca de lugares com mapa: query/near só preenchem o campo e disparam a busca ao abrir.
export type PlacesWindowParams = { query?: string; near?: string }

export type WindowParamsMap = { [WINDOW_FINANCE]: FinanceWindowParams; [WINDOW_PC_CONTROLS]: PcControlsWindowParams; [WINDOW_PLACES]: PlacesWindowParams }
export type WindowId = keyof WindowParamsMap

export type WindowComponentProps<P> = { params: P; operational: OperationalState }

export type WindowDef<P = unknown> = {
  id: string
  title: string
  icon: LucideIcon
  width: number
  height: number
  // Retorna os parâmetros limpos ou null se algo for inválido (chave desconhecida, tipo errado).
  parseParams: (raw: unknown) => P | null
  component: LazyExoticComponent<ComponentType<WindowComponentProps<P>>>
}

type ParamChecks = Record<string, (value: unknown) => unknown>

function parseWith(checks: ParamChecks) {
  return (raw: unknown) => {
    if (raw === undefined || raw === null) return {}
    if (typeof raw !== 'object' || Array.isArray(raw)) return null
    const clean: Record<string, unknown> = {}
    for (const [key, value] of Object.entries(raw as Record<string, unknown>)) {
      const check = checks[key]
      if (!check) return null
      const parsed = check(value)
      if (parsed === undefined) return null
      clean[key] = parsed
    }
    return clean
  }
}

const text = (limit: number) => (value: unknown) => typeof value === 'string' && value.trim().length <= limit ? value.trim() : undefined
const choice = (...options: string[]) => (value: unknown) => typeof value === 'string' && options.includes(value.trim().toLowerCase()) ? value.trim().toLowerCase() : undefined
const positive = (value: unknown) => typeof value === 'number' && Number.isFinite(value) && value > 0 && value <= 1_000_000_000 ? value : undefined
const isoDate = (value: unknown) => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value.trim()) && !Number.isNaN(Date.parse(value.trim())) ? value.trim() : undefined

const financeDef: WindowDef<FinanceWindowParams> = {
  id: WINDOW_FINANCE,
  title: 'Finanças',
  icon: Wallet,
  width: 760,
  height: 640,
  parseParams: parseWith({
    type: choice('expense', 'income'),
    category: text(60),
    period: choice('week', 'month', 'all'),
    amount: positive,
    description: text(300),
    date: isoDate,
  }) as WindowDef<FinanceWindowParams>['parseParams'],
  component: lazy(() => import('./FinanceWindow').then(module => ({ default: module.FinanceWindow }))),
}

const pcControlsDef: WindowDef<PcControlsWindowParams> = {
  id: WINDOW_PC_CONTROLS,
  title: 'Controles do PC',
  icon: MonitorCog,
  width: 460,
  height: 560,
  parseParams: parseWith({}) as WindowDef<PcControlsWindowParams>['parseParams'],
  component: lazy(() => import('./PcControlsWindow').then(module => ({ default: module.PcControlsWindow }))),
}

const placesDef: WindowDef<PlacesWindowParams> = {
  id: WINDOW_PLACES,
  title: 'Lugares',
  icon: MapPinned,
  width: 760,
  height: 620,
  parseParams: parseWith({ query: text(120), near: text(80) }) as WindowDef<PlacesWindowParams>['parseParams'],
  component: lazy(() => import('./PlacesWindow').then(module => ({ default: module.PlacesWindow }))),
}

export const windowRegistry: { [K in WindowId]: WindowDef<WindowParamsMap[K]> } = {
  [WINDOW_FINANCE]: financeDef,
  [WINDOW_PC_CONTROLS]: pcControlsDef,
  [WINDOW_PLACES]: placesDef,
}

export function getWindowDef(id: string): WindowDef<unknown> | undefined {
  return Object.prototype.hasOwnProperty.call(windowRegistry, id) ? (windowRegistry[id as WindowId] as WindowDef<unknown>) : undefined
}

export function isManagedWindow(id: string) {
  return getWindowDef(id) !== undefined
}

export type WindowOpenRequest = { windowId: string; params: unknown }

// Lê o pedido de janela que a ferramenta open_window devolve no contexto da resposta do chat
// (WebSocket "complete" ou POST /api/chat): context.tool_results.open_window.data.ui_window.
export function extractWindowRequest(context: unknown): WindowOpenRequest | null {
  const result = (context as { tool_results?: { open_window?: { ok?: unknown; data?: { ui_window?: { window_id?: unknown; params?: unknown } } } } } | null | undefined)?.tool_results?.open_window
  const request = result?.ok === true ? result.data?.ui_window : undefined
  if (!request || typeof request.window_id !== 'string') return null
  return { windowId: request.window_id, params: request.params }
}
