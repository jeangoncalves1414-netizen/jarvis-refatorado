import { panelRequest } from './panelApi'
import { broadcastSyncEvent } from './syncChannel'

export type Change = { store: string; key: string; before: any; after: any }
export type PersonalReceipt = { id: string; message: string; tool: string; created: number; undone: number; success: number; changes: Change[]; can_undo: boolean }
export type PersonalPreferences = { blocks: string[]; reduced_motion: boolean; review: 'off' | 'daily' | 'weekly' }
export const PERSONAL_CHANGED = 'jarvis:personal-changed'
export const PERSONAL_OPEN = 'jarvis:personal-open'
let pendingOpen: any = null
export function openOrganizer(detail: unknown) {
  pendingOpen = detail
  window.dispatchEvent(new Event(PERSONAL_OPEN))
}
export function consumeOrganizerOpen() { const detail = pendingOpen; pendingOpen = null; return detail }

export async function personalRequest(payload: Record<string, unknown>, operationId = crypto.randomUUID()) {
  const result = await panelRequest<any>('/api/personal', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...payload, operation_id: operationId }) })
  if (!['list', 'summary', 'history', 'preferences_get', 'bulk_preview'].includes(String(payload.action))) {
    window.dispatchEvent(new Event(PERSONAL_CHANGED))
    window.dispatchEvent(new Event('jarvis:finance-changed'))
    window.dispatchEvent(new Event('jarvis:notes-changed'))
    broadcastSyncEvent('HABIT_UPDATED')
  }
  return result
}

export function changeTitle(change: Change) {
  const row = change.after ?? change.before
  if (change.store === 'notes') return change.key.split('/').pop() || 'Anotação'
  if (change.store === 'personal_records') {
    try { const body = JSON.parse(row?.body || '{}'); return body.title || body.account || 'Preferências' } catch { return 'Registro' }
  }
  if (change.store === 'lifeos') return change.key === 'lifeos_workout_sessions' ? 'Sessões de treino' : change.key === 'lifeos_workouts' ? 'Exercícios do treino' : change.key.startsWith('lifeos_hlog_') ? 'Progresso dos hábitos' : 'Vida pessoal'
  return row?.title || row?.name || row?.description || (change.store === 'habit_logs' ? 'Progresso do hábito' : 'Registro vinculado')
}
