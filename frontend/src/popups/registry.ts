import { lazy, type ComponentType, type LazyExoticComponent } from 'react'
import { CalendarClock, Droplets, Info, ListChecks, ListTodo, MapPinned, NotebookPen, type LucideIcon } from 'lucide-react'
import { parseBbox, parsePlace, type PlaceBbox, type PlaceProvider, type PlaceResult } from '../utils/places'
import type { PopupEnvelope, PopupOrigin } from './types'

// Registro dos modelos de popup. Espelho de app/agent/popups.py (POPUP_TEMPLATES): mesmos ids.
// O backend monta `data` a partir dos serviços; aqui `parseData` confere de novo o formato e um
// popup com dado inválido não abre.

export const POPUP_INFO = 'info'
export const POPUP_HABIT_LIST = 'habit_list'
export const POPUP_SCHEDULE = 'schedule'
export const POPUP_WATER = 'water'
export const POPUP_LIVE_NOTES = 'live_notes'
export const POPUP_TASK_LIST = 'task_list'
export const POPUP_PLACES = 'places'

export type InfoPopupData = { title: string; lines: string[]; tone: 'info' | 'ok' | 'warn' }

export type HabitPopupItem = {
  id: string
  name: string
  category: string
  routine_block: string
  start_time: string
  days_of_week: string[]
  completed_today: boolean
  streak: number
}
export type HabitListPopupData = { filter: 'today' | 'all'; items: HabitPopupItem[]; completed: number; total: number; highlight_ids: string[] }

export type ScheduleEvent = { id: string; title: string; start: string; reminder_at: string | null }
export type SchedulePopupData = { date: string; events: ScheduleEvent[] }

export type WaterPopupData = { date: string; current_ml: number; previous_ml: number; target_ml: number; percentage: number }

export type NoteFormat = 'text' | 'bullets' | 'checklist'
export type LiveNotesPopupData = { draft_id: string; title: string; format: NoteFormat; dictate: boolean; content: string }

export type TaskPopupItem = { id: string; title: string; priority: number; due_date: string; completed: boolean }
export type TaskListPopupData = { filter: 'pending' | 'all'; items: TaskPopupItem[]; pending: number; total: number }

export type PopupPlace = PlaceResult & { id: string }
export type PlacesPopupData = { query: string; near: string; provider: PlaceProvider; results: PopupPlace[]; bbox: PlaceBbox | null; attribution: string; notice: string }

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

const MAX_ITEMS = 50
const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/
const ISO_MINUTE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/
const isText = (value: unknown, max: number): value is string => typeof value === 'string' && value.length <= max
const isCount = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value) && value >= 0
const isTextList = (value: unknown, maxItems: number, max: number): value is string[] => Array.isArray(value) && value.length <= maxItems && value.every(item => isText(item, max))

function parseHabitItem(raw: unknown): HabitPopupItem | null {
  if (!isRecord(raw)) return null
  const { id, name, category, routine_block, start_time, days_of_week, completed_today, streak } = raw
  if (!isText(id, 80) || !id || !isText(name, 120) || !isText(category, 120) || !isText(routine_block, 20) || !isText(start_time, 10)) return null
  if (!isTextList(days_of_week, 7, 10) || typeof completed_today !== 'boolean' || !isCount(streak)) return null
  return { id, name, category, routine_block, start_time, days_of_week, completed_today, streak }
}

function parseHabitList(raw: unknown): HabitListPopupData | null {
  if (!isRecord(raw) || (raw.filter !== 'today' && raw.filter !== 'all')) return null
  if (!Array.isArray(raw.items) || raw.items.length > MAX_ITEMS) return null
  const items = raw.items.map(parseHabitItem)
  if (items.some(item => item === null)) return null
  if (!isCount(raw.completed) || !isCount(raw.total) || !isTextList(raw.highlight_ids, MAX_ITEMS, 80)) return null
  return { filter: raw.filter, items: items as HabitPopupItem[], completed: raw.completed, total: raw.total, highlight_ids: raw.highlight_ids }
}

function parseSchedule(raw: unknown): SchedulePopupData | null {
  if (!isRecord(raw) || !isText(raw.date, 10) || !ISO_DAY.test(raw.date)) return null
  if (!Array.isArray(raw.events) || raw.events.length > MAX_ITEMS) return null
  const events: ScheduleEvent[] = []
  for (const item of raw.events) {
    if (!isRecord(item) || !isText(item.id, 80) || !item.id || !isText(item.title, 120) || !isText(item.start, 32) || !ISO_MINUTE.test(item.start)) return null
    const reminder = item.reminder_at ?? null
    if (reminder !== null && (!isText(reminder, 32) || !ISO_MINUTE.test(reminder))) return null
    events.push({ id: item.id, title: item.title, start: item.start, reminder_at: reminder })
  }
  return { date: raw.date, events }
}

function parseWater(raw: unknown): WaterPopupData | null {
  if (!isRecord(raw) || !isText(raw.date, 10) || !ISO_DAY.test(raw.date)) return null
  const { current_ml, previous_ml, target_ml, percentage } = raw
  if (!isCount(current_ml) || !isCount(previous_ml) || !isCount(target_ml) || !isCount(percentage)) return null
  return { date: raw.date, current_ml, previous_ml, target_ml, percentage }
}

function parseLiveNotes(raw: unknown): LiveNotesPopupData | null {
  if (!isRecord(raw) || !isText(raw.draft_id, 32) || !/^[a-z0-9]{8,32}$/.test(raw.draft_id)) return null
  if (!isText(raw.title, 80) || (raw.format !== 'text' && raw.format !== 'bullets' && raw.format !== 'checklist')) return null
  if (typeof raw.dictate !== 'boolean' || !isText(raw.content, 20_000)) return null
  return { draft_id: raw.draft_id, title: raw.title, format: raw.format, dictate: raw.dictate, content: raw.content }
}

const habitListDef: PopupDef<HabitListPopupData> = {
  id: POPUP_HABIT_LIST,
  title: 'Hábitos',
  icon: ListChecks,
  parseData: parseHabitList,
  component: lazy(() => import('./templates/HabitListPopup').then(module => ({ default: module.HabitListPopup }))),
}

const scheduleDef: PopupDef<SchedulePopupData> = {
  id: POPUP_SCHEDULE,
  title: 'Agenda',
  icon: CalendarClock,
  parseData: parseSchedule,
  component: lazy(() => import('./templates/SchedulePopup').then(module => ({ default: module.SchedulePopup }))),
}

const waterDef: PopupDef<WaterPopupData> = {
  id: POPUP_WATER,
  title: 'Água de hoje',
  icon: Droplets,
  parseData: parseWater,
  tone: data => data.target_ml > 0 && data.current_ml >= data.target_ml ? 'ok' : undefined,
  component: lazy(() => import('./templates/WaterPopup').then(module => ({ default: module.WaterPopup }))),
}

const liveNotesDef: PopupDef<LiveNotesPopupData> = {
  id: POPUP_LIVE_NOTES,
  title: 'Anotação ao vivo',
  icon: NotebookPen,
  parseData: parseLiveNotes,
  component: lazy(() => import('./templates/LiveNotesPopup').then(module => ({ default: module.LiveNotesPopup }))),
}

function parseTaskList(raw: unknown): TaskListPopupData | null {
  if (!isRecord(raw) || (raw.filter !== 'pending' && raw.filter !== 'all')) return null
  if (!Array.isArray(raw.items) || raw.items.length > MAX_ITEMS) return null
  const items: TaskPopupItem[] = []
  for (const item of raw.items) {
    if (!isRecord(item) || !isText(item.id, 80) || !item.id || !isText(item.title, 200) || !isText(item.due_date, 10)) return null
    if (typeof item.priority !== 'number' || !Number.isInteger(item.priority) || item.priority < 1 || item.priority > 4 || typeof item.completed !== 'boolean') return null
    items.push({ id: item.id, title: item.title, priority: item.priority, due_date: item.due_date, completed: item.completed })
  }
  if (!isCount(raw.pending) || !isCount(raw.total)) return null
  return { filter: raw.filter, items, pending: raw.pending, total: raw.total }
}

function parsePlaces(raw: unknown): PlacesPopupData | null {
  if (!isRecord(raw) || !isText(raw.query, 120) || !raw.query || !isText(raw.near, 80)) return null
  if (raw.provider !== 'osm' && raw.provider !== 'google') return null
  if (!Array.isArray(raw.results) || raw.results.length > 8) return null
  const results: PopupPlace[] = []
  for (const item of raw.results) {
    const place = parsePlace(item)
    if (!place || !place.id) return null
    results.push(place as PopupPlace)
  }
  const bbox = parseBbox(raw.bbox)
  if (bbox === undefined || !isText(raw.attribution, 120) || !isText(raw.notice, 300)) return null
  return { query: raw.query, near: raw.near, provider: raw.provider, results, bbox, attribution: raw.attribution, notice: raw.notice }
}

const taskListDef: PopupDef<TaskListPopupData> = {
  id: POPUP_TASK_LIST,
  title: 'Tarefas',
  icon: ListTodo,
  parseData: parseTaskList,
  component: lazy(() => import('./templates/TaskListPopup').then(module => ({ default: module.TaskListPopup }))),
}

const placesDef: PopupDef<PlacesPopupData> = {
  id: POPUP_PLACES,
  title: 'Lugares',
  icon: MapPinned,
  parseData: parsePlaces,
  component: lazy(() => import('./templates/PlacesPopup').then(module => ({ default: module.PlacesPopup }))),
}

export const popupRegistry: Record<string, PopupDef<any>> = {
  [POPUP_INFO]: infoDef,
  [POPUP_HABIT_LIST]: habitListDef,
  [POPUP_SCHEDULE]: scheduleDef,
  [POPUP_WATER]: waterDef,
  [POPUP_LIVE_NOTES]: liveNotesDef,
  [POPUP_TASK_LIST]: taskListDef,
  [POPUP_PLACES]: placesDef,
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
