// Funções puras da sincronização com a nuvem (sem localStorage, rede ou imports).
// Regras: nunca trocar valor preenchido por vazio, nunca perder campo que só um
// dispositivo conhece e, no mesmo campo, vence o carimbo de data mais recente.

export type StampedField = { v: unknown; ts: number }
export type StampedFields = Record<string, StampedField>
export type StampState = Record<string, { fp: string; ts: number }>

export function isEmptyValue(value: unknown): boolean {
  if (value === null || value === undefined) return true
  if (typeof value === 'string') return value.trim() === ''
  if (Array.isArray(value)) return value.length === 0
  if (typeof value === 'object') return Object.keys(value as object).length === 0
  return false
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

export function stableStringify(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(',')}]`
  if (isPlainObject(value)) {
    return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${stableStringify(value[key])}`).join(',')}}`
  }
  return JSON.stringify(value) ?? 'null'
}

/** Impressão digital curta (não criptográfica) para detectar mudança de valor. */
export function fingerprint(text: string): string {
  let a = 5381
  let b = 52711
  for (let index = 0; index < text.length; index += 1) {
    const code = text.charCodeAt(index)
    a = ((a << 5) + a + code) | 0
    b = ((b << 5) ^ (b >>> 2) ^ code) | 0
  }
  return `${text.length.toString(36)}-${(a >>> 0).toString(36)}-${(b >>> 0).toString(36)}`
}

/** Mescla campo a campo: vazio não vence preenchido; no conflito vence o carimbo maior (empate: local). */
export function mergeStampedFields(local: StampedFields = {}, remote: StampedFields = {}): StampedFields {
  const merged: StampedFields = {}
  const valid = (entry: unknown): entry is StampedField =>
    isPlainObject(entry) && 'v' in entry && typeof entry.ts === 'number' && Number.isFinite(entry.ts)
  for (const path of new Set([...Object.keys(local || {}), ...Object.keys(remote || {})])) {
    const left = valid(local?.[path]) ? local[path] : undefined
    const right = valid(remote?.[path]) ? remote[path] : undefined
    if (!left && !right) continue
    let winner: StampedField
    if (!left) winner = right as StampedField
    else if (!right) winner = left
    else {
      const leftEmpty = isEmptyValue(left.v)
      const rightEmpty = isEmptyValue(right.v)
      if (leftEmpty && !rightEmpty) winner = right
      else if (rightEmpty && !leftEmpty) winner = left
      else if (stableStringify(left.v) === stableStringify(right.v)) winner = left.ts >= right.ts ? left : right
      else winner = right.ts > left.ts ? right : left
    }
    merged[path] = { v: winner.v, ts: winner.ts }
  }
  return merged
}

function itemId(item: unknown): string | null {
  if (!isPlainObject(item)) return null
  const id = item.id
  return typeof id === 'string' || typeof id === 'number' ? String(id) : null
}

function mergeArrays(local: unknown[], remote: unknown[], localTs: number, remoteTs: number): unknown[] {
  const result = new Map<string, unknown>()
  const order: string[] = []
  const add = (marker: string, item: unknown, remoteSide: boolean) => {
    const existing = result.get(marker)
    if (existing === undefined && !result.has(marker)) {
      result.set(marker, item)
      order.push(marker)
      return
    }
    if (!remoteSide || marker.startsWith('json:')) return
    const left = (existing as Record<string, unknown>).updatedAt
    const right = (item as Record<string, unknown>).updatedAt
    const remoteNewer = typeof left === 'number' && typeof right === 'number' ? right > left : remoteTs > localTs
    if (remoteNewer) result.set(marker, item)
  }
  for (const item of local) add(itemId(item) !== null ? `id:${itemId(item)}` : `json:${stableStringify(item)}`, item, false)
  for (const item of remote) add(itemId(item) !== null ? `id:${itemId(item)}` : `json:${stableStringify(item)}`, item, true)
  return order.map(marker => result.get(marker))
}

/** Mescla uma seção do cofre: união de listas por id, chave a chave nos objetos, carimbo nos valores simples. */
export function mergeSection(local: unknown, remote: unknown, localTs: number, remoteTs: number): unknown {
  const localEmpty = isEmptyValue(local)
  const remoteEmpty = isEmptyValue(remote)
  if (localEmpty && remoteEmpty) return local ?? remote
  if (localEmpty) return remote
  if (remoteEmpty) return local
  if (Array.isArray(local) && Array.isArray(remote)) return mergeArrays(local, remote, localTs, remoteTs)
  if (isPlainObject(local) && isPlainObject(remote)) {
    const out: Record<string, unknown> = {}
    for (const key of new Set([...Object.keys(local), ...Object.keys(remote)])) {
      if (key in local && key in remote) out[key] = mergeSection(local[key], remote[key], localTs, remoteTs)
      else out[key] = key in local ? local[key] : remote[key]
    }
    return out
  }
  if (stableStringify(local) === stableStringify(remote)) return local
  return remoteTs > localTs ? remote : local
}

/**
 * Carimbo de um campo local: mantém o anterior se o valor não mudou, usa "agora" se mudou.
 * Valor vazio ou igual ao padrão visto pela primeira vez recebe 0 (nunca vence um valor real).
 */
export function stampValue(state: StampState, name: string, value: unknown, now: number, defaultValue?: unknown): number {
  const serialized = stableStringify(value)
  const fp = fingerprint(serialized)
  const previous = state[name]
  if (previous && previous.fp === fp) return previous.ts
  const isDefault = defaultValue !== undefined && serialized === stableStringify(defaultValue)
  const ts = !previous && (isEmptyValue(value) || isDefault) ? 0 : now
  state[name] = { fp, ts }
  return ts
}

export function recordStamp(state: StampState, name: string, value: unknown, ts: number): void {
  state[name] = { fp: fingerprint(stableStringify(value)), ts }
}

// ============ Máscara de segredos ============

export function maskSecret(value: string): string {
  const text = String(value || '').trim()
  if (!text) return ''
  return text.length > 4 ? `•••• ${text.slice(-4)}` : '••••'
}

/** Lista de chaves separadas por vírgula ou quebra de linha, mostrando só os 4 últimos caracteres de cada. */
export function maskKeyList(value: string): string {
  return String(value || '')
    .split(/[,\n]/)
    .map(part => part.trim())
    .filter(Boolean)
    .map(maskSecret)
    .join(', ')
}

const SECRET_NAME = /key|token|secret|password|senha|authorization|apikey/i
const SECRET_SHAPE = /^(sk-|AIza|gsk_|Bearer\s|eyJ)/

/** Cópia segura para log: oculta campos com nome de segredo e textos com formato de chave. */
export function redactForLog(value: unknown, depth = 0): unknown {
  if (depth > 4) return '[…]'
  if (typeof value === 'string') return SECRET_SHAPE.test(value) ? maskSecret(value) : value.length > 200 ? `${value.slice(0, 40)}…` : value
  if (Array.isArray(value)) return value.slice(0, 20).map(item => redactForLog(item, depth + 1))
  if (isPlainObject(value)) {
    const out: Record<string, unknown> = {}
    for (const [key, item] of Object.entries(value)) {
      out[key] = SECRET_NAME.test(key) && !isEmptyValue(item) ? '[oculto]' : redactForLog(item, depth + 1)
    }
    return out
  }
  return value
}
