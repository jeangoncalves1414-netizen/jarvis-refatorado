// Registro de água: se o backend não confirmar, o valor fica guardado como rascunho neste aparelho
// e é reenviado depois. Nada é somado na tela sem confirmação do servidor.

const WATER_DRAFTS_KEY = 'jarvis-water-drafts'
const MAX_DRAFTS = 50

export type WaterDraft = { id: string; ml: number; at: number }

export type WaterResult = {
  ok: boolean
  error?: string
  // Resposta do backend quando confirmou (total do dia, popup montado etc.).
  data?: { ok?: boolean; total_ml?: number; added_ml?: number; popup?: unknown } & Record<string, unknown>
}

export function loadWaterDrafts(): WaterDraft[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(WATER_DRAFTS_KEY) || '[]')
    if (!Array.isArray(parsed)) return []
    return parsed.filter((item): item is WaterDraft => item && typeof item.id === 'string' && Number.isFinite(item.ml) && item.ml > 0)
  } catch {
    return []
  }
}

function saveWaterDrafts(drafts: WaterDraft[]): void {
  try {
    if (drafts.length) localStorage.setItem(WATER_DRAFTS_KEY, JSON.stringify(drafts.slice(-MAX_DRAFTS)))
    else localStorage.removeItem(WATER_DRAFTS_KEY)
  } catch { /* armazenamento cheio ou bloqueado: o erro já foi mostrado */ }
}

export function addWaterDraft(ml: number): WaterDraft {
  const draft: WaterDraft = { id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`, ml, at: Date.now() }
  saveWaterDrafts([...loadWaterDrafts(), draft])
  return draft
}

export function removeWaterDraft(id: string): void {
  saveWaterDrafts(loadWaterDrafts().filter(item => item.id !== id))
}

/** Envia um registro de água e devolve o erro real quando o backend não confirma. */
export async function postWater(ml: number): Promise<WaterResult> {
  try {
    const response = await fetch('/api/evolute/water/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ amount_ml: ml }),
    })
    const data = await response.json().catch(() => null)
    if (!response.ok || data?.ok === false) {
      const detail = typeof data?.error === 'string' && data.error ? data.error : `o servidor respondeu ${response.status}`
      return { ok: false, error: detail }
    }
    return { ok: true, data: data ?? undefined }
  } catch (error) {
    return { ok: false, error: error instanceof Error && error.message ? error.message : 'sem conexão com o Jarvis' }
  }
}

/** Reenvia os rascunhos em ordem; para no primeiro que falhar. Devolve quantos foram confirmados e quantos faltam. */
export async function flushWaterDrafts(): Promise<{ sent: number; sentMl: number; pending: number; error?: string }> {
  let sent = 0
  let sentMl = 0
  for (const draft of loadWaterDrafts()) {
    const result = await postWater(draft.ml)
    if (!result.ok) return { sent, sentMl, pending: loadWaterDrafts().length, error: result.error }
    removeWaterDraft(draft.id)
    sent += 1
    sentMl += draft.ml
  }
  return { sent, sentMl, pending: loadWaterDrafts().length }
}
