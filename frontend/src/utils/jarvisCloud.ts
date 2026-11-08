import {
  DEFAULT_OXXY_MODELS,
  DEFAULT_MOBILE_KEYS,
  getMobileApiKeys,
  getMobileOxyyModels,
  getMobileProvider,
  isMobileStandalone,
  setMobileApiKeys,
  setMobileOxyyModels,
  setMobileProvider,
  type DirectChatProvider,
} from '../hooks/useDirectChat'
import {
  DEFAULT_SUPABASE_KEY,
  DEFAULT_SUPABASE_URL,
  getEvoluteSettings,
  isEvoluteCloudConnected,
  refreshAccessToken,
  isTokenExpired,
  type EvoluteSettings,
} from './evoluteCloud'
import { JARVIS_MEMORIES_KEY, JARVIS_PROFILE_KEY, JARVIS_VAULT_KEY } from './jarvisVaultKeys'
import {
  fingerprint,
  mergeSection,
  mergeStampedFields,
  recordStamp,
  redactForLog,
  stampValue,
  type StampedFields,
  type StampState,
} from './syncMerge'

export { JARVIS_MEMORIES_KEY, JARVIS_PROFILE_KEY, JARVIS_VAULT_KEY }

const CLOUD_REVISION_KEY = 'lifeos_cloud_revision'
const LOCAL_LAST_SYNC_KEY = 'jarvis_local_last_sync'
const LOCAL_FIELD_TIMESTAMPS_KEY = 'jarvis_field_timestamps'
const LOCAL_STAMP_STATE_KEY = 'jarvis_stamp_state'
const SYNC_LOCK_KEY = 'jarvis_sync_lock'
const BACKUP_VAULT_KEY = 'jarvis_backup_vault'
const MOBILE_KEYS_STORAGE = 'jarvis-mobile-api-keys'
const MOBILE_PROVIDER_STORAGE = 'jarvis-mobile-provider'
const KEY_IDS = ['oxyy', 'groq', 'gemini', 'openrouter', 'fish'] as const
const PROVIDER_MODEL_STORAGE: Record<string, string> = {
  groq: 'jarvis-mobile-groq-model',
  gemini: 'jarvis-mobile-gemini-model',
  oxyy: 'jarvis-mobile-oxyy-model',
}

// Log seguro: passa tudo por redactForLog e nunca recebe o vault, linhas da nuvem ou URLs.
function log(message: string, detail?: unknown): void {
  if (detail === undefined) console.log(`[JarvisCloud] ${message}`)
  else console.log(`[JarvisCloud] ${message}`, redactForLog(detail))
}

function loadStampState(): StampState {
  try {
    const parsed = JSON.parse(localStorage.getItem(LOCAL_STAMP_STATE_KEY) || '{}')
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

function saveStampState(state: StampState): void {
  try { localStorage.setItem(LOCAL_STAMP_STATE_KEY, JSON.stringify(state)) } catch { /* ignore */ }
}

function readRawMobileKeys(): Record<string, string> {
  const result: Record<string, string> = {}
  try {
    const parsed = JSON.parse(localStorage.getItem(MOBILE_KEYS_STORAGE) || '{}')
    for (const id of KEY_IDS) {
      const value = parsed?.[id]
      result[id] = typeof value === 'string' ? value.trim() : ''
    }
  } catch {
    for (const id of KEY_IDS) result[id] = ''
  }
  return result
}

// ============ NOVA ARQUITETURA DE SINCRONIZAÇÃO ============
// Baseado em: Obsidian Sync, Simplenote, Notion
// Padrão: Three-way merge com versionamento por item

// Timestamps por campo para sincronização inteligente
export type FieldTimestamps = {
  keys?: number
  provider?: number
  oxyyModels?: number
  providerModels?: number
  memories?: number
  profile?: number
  habits?: number
  training?: number
  dashboard?: number
  proactive?: number
  climate?: number
  finance?: number
  habitLogs?: number
  mentalLogs?: number
  waterLogs?: number
  viceLogs?: number
  studyLogs?: number
  readingLogs?: number
  cognitive?: number
  subjects?: number
  summaries?: number
  flashcards?: number
  extraData?: number
  [section: string]: number | undefined
}

// Item versionado (para arrays como hábitos)
export type VersionedItem<T> = {
  id: string
  data: T
  updatedAt: number
  deleted?: boolean
}

// Vault com versionamento granular
export type JarvisVault = {
  keys: typeof DEFAULT_MOBILE_KEYS
  provider: DirectChatProvider
  oxyyModels: typeof DEFAULT_OXXY_MODELS
  providerModels: Record<string, string> // groq_model, gemini_model, etc.
  memories: string[]
  profile: string
  habits?: VersionedItem<any>[]  // Hábitos versionados individualmente
  training?: VersionedItem<any>[]  // Treinos versionados
  dashboard?: any  // Dados do dashboard
  proactive?: any  // Configurações proativas
  climate?: any  // Dados de clima
  finance?: any  // Dados financeiros
  // Life OS data
  habitLogs?: Record<string, any>  // Logs de hábitos por dia (lifeos_hlog_YYYY-MM-DD)
  mentalLogs?: Record<string, any>  // Logs mentais por dia
  waterLogs?: Record<string, any>  // Logs de água por dia
  viceLogs?: any  // Logs de vícios
  studyLogs?: any  // Logs de estudo
  readingLogs?: any  // Logs de leitura
  cognitive?: any  // Dados cognitivos
  subjects?: any  // Assuntos
  summaries?: any  // Resumos
  flashcards?: any  // Flashcards
  // Outros dados localStorage dinâmicos
  extraData?: Record<string, any>  // Quaisquer outros dados do localStorage
  // Campos de configuração com carimbo por campo (api_keys.groq, llm_provider, oxyy_models.chat...).
  // É a fonte da mesclagem; keys/provider/oxyyModels/providerModels continuam sendo gravados
  // para o APK antigo ler.
  fields?: StampedFields
  // Snapshot do backend do PC (configurações completas, perfil do agente, memórias, notas,
  // tarefas, metas, hábitos e finanças). Dispositivos sem backend apenas o repassam.
  backend?: Record<string, any>
  updatedAt: number
  source: 'pc' | 'mobile'
  fieldTimestamps?: FieldTimestamps
  version: number  // Versão do vault inteiro (para conflict detection)
}

function emptyVault(): JarvisVault {
  return {
    keys: { ...DEFAULT_MOBILE_KEYS },
    provider: 'oxyy',
    oxyyModels: { ...DEFAULT_OXXY_MODELS },
    providerModels: {},
    memories: [],
    profile: '',
    updatedAt: 0,
    source: isMobileStandalone() ? 'mobile' : 'pc',
    fieldTimestamps: {},
    version: 0,
  }
}

export function keysHaveValue(keys?: Record<string, string> | null): boolean {
  return Object.values(keys || {}).some(value => String(value || '').trim().length > 0)
}

// ============ CAMPOS DE CONFIGURAÇÃO (carimbo por campo) ============

/** Campos de configuração deste dispositivo (localStorage), com carimbo por mudança de valor. */
function collectLocalSettingsFields(state: StampState, now: number): StampedFields {
  const fields: StampedFields = {}
  const put = (path: string, value: unknown, defaultValue?: unknown) => {
    fields[path] = { v: value, ts: stampValue(state, path, value, now, defaultValue) }
  }
  const keys = readRawMobileKeys()
  for (const id of KEY_IDS) put(`api_keys.${id}`, keys[id])
  put('llm_provider', localStorage.getItem(MOBILE_PROVIDER_STORAGE) || '')
  const models = getMobileOxyyModels() as Record<string, string>
  for (const [name, value] of Object.entries(models)) {
    put(`oxyy_models.${name}`, value, (DEFAULT_OXXY_MODELS as Record<string, string>)[name])
  }
  for (const [provider, storageKey] of Object.entries(PROVIDER_MODEL_STORAGE)) {
    put(`provider_models.${provider}`, localStorage.getItem(storageKey) || '')
  }
  return fields
}

/** Vaults gravados antes dos campos carimbados: deriva os campos das chaves antigas. */
function fieldsFromLegacyVault(vault: JarvisVault): StampedFields {
  const fields: StampedFields = {}
  const ts = (name: string) => Number(vault.fieldTimestamps?.[name] || vault.updatedAt || 0)
  for (const [id, value] of Object.entries(vault.keys || {})) fields[`api_keys.${id}`] = { v: value, ts: ts('keys') }
  if (vault.provider) fields.llm_provider = { v: vault.provider, ts: ts('provider') }
  for (const [name, value] of Object.entries(vault.oxyyModels || {})) fields[`oxyy_models.${name}`] = { v: value, ts: ts('oxyyModels') }
  for (const [name, value] of Object.entries(vault.providerModels || {})) fields[`provider_models.${name}`] = { v: value, ts: ts('providerModels') }
  return fields
}

function vaultFields(vault: JarvisVault): StampedFields {
  return mergeStampedFields(fieldsFromLegacyVault(vault), vault.fields || {})
}

function fieldValue(fields: StampedFields, path: string): string {
  const value = fields[path]?.v
  return typeof value === 'string' ? value : ''
}

/** Preenche as chaves antigas (APK) a partir dos campos mesclados. */
function applyFieldsToLegacy(vault: JarvisVault): void {
  const fields = vault.fields || {}
  const keys: Record<string, string> = { ...DEFAULT_MOBILE_KEYS }
  for (const id of KEY_IDS) {
    const value = fieldValue(fields, `api_keys.${id}`)
    if (value || id in DEFAULT_MOBILE_KEYS) keys[id] = value
  }
  vault.keys = keys as typeof DEFAULT_MOBILE_KEYS
  const provider = fieldValue(fields, 'llm_provider')
  vault.provider = (provider === 'gemini' || provider === 'groq' || provider === 'oxyy' ? provider : 'oxyy') as DirectChatProvider
  const models: Record<string, string> = { ...DEFAULT_OXXY_MODELS }
  const providerModels: Record<string, string> = {}
  for (const [path, entry] of Object.entries(fields)) {
    if (path.startsWith('oxyy_models.') && typeof entry.v === 'string' && entry.v) models[path.slice('oxyy_models.'.length)] = entry.v
    if (path.startsWith('provider_models.') && typeof entry.v === 'string' && entry.v) providerModels[path.slice('provider_models.'.length)] = entry.v
  }
  vault.oxyyModels = models as typeof DEFAULT_OXXY_MODELS
  vault.providerModels = providerModels
}

// ============ SYNC LOCK ============
// Impede modificações durante sincronização

function acquireSyncLock(): boolean {
  const lock = localStorage.getItem(SYNC_LOCK_KEY)
  if (lock) {
    const lockTime = Number(lock)
    // Lock expira após 30 segundos (caso de crash)
    if (Date.now() - lockTime < 30000) {
      log('Sincronização já em andamento, ignorando')
      return false
    }
  }
  localStorage.setItem(SYNC_LOCK_KEY, String(Date.now()))
  return true
}

function releaseSyncLock(): void {
  localStorage.removeItem(SYNC_LOCK_KEY)
}

// ============ BACKUP ============
// Backup automático antes de sync

function createBackup(vault: JarvisVault): void {
  try { localStorage.setItem(BACKUP_VAULT_KEY, JSON.stringify(vault)) } catch { log('Backup local não coube no armazenamento') }
}

function restoreBackup(): JarvisVault | null {
  try {
    const backup = localStorage.getItem(BACKUP_VAULT_KEY)
    if (backup) return JSON.parse(backup)
  } catch {
    log('Falha ao ler o backup local')
  }
  return null
}

// ============ ITEM-LEVEL MERGE ============
// Merge item por item, não array inteiro

function mergeVersionedArrays<T>(
  local: VersionedItem<T>[],
  remote: VersionedItem<T>[],
): VersionedItem<T>[] {
  const merged = new Map<string, VersionedItem<T>>()

  local.forEach(item => merged.set(item.id, item))
  remote.forEach(item => {
    const existing = merged.get(item.id)
    if (!existing) {
      merged.set(item.id, item)
    } else if (item.updatedAt > existing.updatedAt) {
      merged.set(item.id, item)
    } else if (item.updatedAt === existing.updatedAt && !item.deleted && existing.deleted) {
      // Mesmo carimbo: prefere o não-deletado
      merged.set(item.id, item)
    }
  })

  return Array.from(merged.values()).filter(item => !item.deleted)
}

// ============ MERGE CAMPO A CAMPO ============
// Regras: vazio nunca vence preenchido; campo que só um lado conhece é preservado;
// no mesmo campo vence o carimbo mais recente (empate: este dispositivo).

const MERGED_SECTIONS = [
  'memories', 'profile', 'dashboard', 'proactive', 'climate', 'finance',
  'habitLogs', 'mentalLogs', 'waterLogs', 'viceLogs', 'studyLogs', 'readingLogs',
  'cognitive', 'subjects', 'summaries', 'flashcards', 'extraData',
] as const

export function mergeVaults(local: JarvisVault, remote: JarvisVault): JarvisVault {
  log(`Mesclando cofres (local v${local.version || 0}, nuvem v${remote.version || 0})`)

  const now = Date.now()
  const localTs = local.fieldTimestamps || {}
  const remoteTs = remote.fieldTimestamps || {}
  const merged: JarvisVault = {
    ...emptyVault(),
    ...remote,
    ...local,
    updatedAt: now,
    version: Math.max(local.version || 0, remote.version || 0) + 1,
    fieldTimestamps: {},
  }

  // Configurações (chaves de API, provedor, modelos): campo a campo.
  merged.fields = mergeStampedFields(vaultFields(local), vaultFields(remote))
  applyFieldsToLegacy(merged)

  // Seções com dados do usuário.
  for (const section of MERGED_SECTIONS) {
    const lts = Number(localTs[section] || 0)
    const rts = Number(remoteTs[section] || 0)
    ;(merged as Record<string, unknown>)[section] = mergeSection(
      (local as Record<string, unknown>)[section],
      (remote as Record<string, unknown>)[section],
      lts,
      rts,
    )
    merged.fieldTimestamps![section] = Math.max(lts, rts)
  }

  // Arrays versionados (item por item)
  if (local.habits || remote.habits) {
    merged.habits = mergeVersionedArrays(local.habits || [], remote.habits || [])
    merged.fieldTimestamps!.habits = Math.max(localTs.habits || 0, remoteTs.habits || 0)
  }
  if (local.training || remote.training) {
    merged.training = mergeVersionedArrays(local.training || [], remote.training || [])
    merged.fieldTimestamps!.training = Math.max(localTs.training || 0, remoteTs.training || 0)
  }

  // Carimbos antigos (APK): maior carimbo dos campos de cada grupo.
  const maxTs = (prefix: string) =>
    Math.max(0, ...Object.entries(merged.fields || {}).filter(([path]) => path.startsWith(prefix)).map(([, entry]) => entry.ts))
  merged.fieldTimestamps!.keys = maxTs('api_keys.')
  merged.fieldTimestamps!.provider = maxTs('llm_provider')
  merged.fieldTimestamps!.oxyyModels = maxTs('oxyy_models.')
  merged.fieldTimestamps!.providerModels = maxTs('provider_models.')

  // O snapshot do backend é mesclado pelo servidor (ver syncBackend); aqui só não perdemos nenhum lado.
  merged.backend = local.backend ?? remote.backend

  log(`Mesclagem concluída (v${merged.version})`)
  return merged
}

// ============ BACKEND (PC) ============
// O backend do PC guarda configurações completas, perfil do agente, memórias, notas,
// tarefas, metas, hábitos e finanças. Quem mescla é o servidor (app/storage/backend_sync.py).

function settingsFieldsForBackend(fields: StampedFields): StampedFields {
  const result: StampedFields = {}
  for (const [path, entry] of Object.entries(fields)) {
    if (path.startsWith('api_keys.') || path === 'llm_provider' || path.startsWith('oxyy_models.')) result[path] = entry
  }
  return result
}

async function fetchBackendSnapshot(): Promise<Record<string, any> | undefined> {
  if (isMobileStandalone()) return undefined
  try {
    const response = await fetch('/api/settings/sync-snapshot')
    if (!response.ok) return undefined
    const data = await response.json()
    return data?.ok && data.snapshot && typeof data.snapshot === 'object' ? data.snapshot : undefined
  } catch {
    log('Backend local indisponível; os dados dele ficam fora desta sincronização')
    return undefined
  }
}

/** Mescla o snapshot da nuvem com o backend local e grava o resultado nele. Devolve o snapshot final. */
async function syncBackend(merged: JarvisVault, cloudBackend?: Record<string, any>): Promise<void> {
  if (isMobileStandalone()) {
    merged.backend = cloudBackend ?? merged.backend
    return
  }
  try {
    const snapshot = {
      ...(cloudBackend || {}),
      settings: mergeStampedFields(cloudBackend?.settings || {}, settingsFieldsForBackend(merged.fields || {})),
    }
    const response = await fetch('/api/settings/sync-merge', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ snapshot }),
    })
    const data = await response.json().catch(() => null)
    if (!response.ok || !data?.ok || !data.snapshot) throw new Error(`status ${response.status}`)
    merged.backend = data.snapshot
    merged.fields = mergeStampedFields(merged.fields || {}, settingsFieldsForBackend(data.snapshot.settings || {}))
    applyFieldsToLegacy(merged)
    log('Backend local mesclado', data.summary)
  } catch (error) {
    // Sem backend: preserva o que já está na nuvem em vez de sobrescrevê-lo com dados parciais.
    merged.backend = cloudBackend ?? merged.backend
    log(`Não foi possível mesclar com o backend local (${error instanceof Error ? error.message : 'erro'})`)
  }
}

// ============ HELPER FUNCTIONS ============

function getLocalFieldTimestamps(): FieldTimestamps {
  try {
    const raw = localStorage.getItem(LOCAL_FIELD_TIMESTAMPS_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

function setLocalFieldTimestamp(field: keyof FieldTimestamps, timestamp: number = Date.now()): void {
  const current = getLocalFieldTimestamps()
  current[field] = timestamp
  localStorage.setItem(LOCAL_FIELD_TIMESTAMPS_KEY, JSON.stringify(current))
}

function getLocalLastSync(): number {
  try {
    return Number(localStorage.getItem(LOCAL_LAST_SYNC_KEY) || '0')
  } catch {
    return 0
  }
}

function setLocalLastSync(timestamp: number = Date.now()): void {
  localStorage.setItem(LOCAL_LAST_SYNC_KEY, String(timestamp))
}

// ============ SUPABASE HELPERS ============

function baseUrl(settings = getEvoluteSettings()): string {
  return settings.supabaseUrl || DEFAULT_SUPABASE_URL
}

function headers(settings = getEvoluteSettings()): HeadersInit {
  const token = settings.supabaseAccessToken
  return {
    'apikey': settings.supabasePublishableKey || DEFAULT_SUPABASE_KEY,
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  }
}

async function pullSnapshot(settings = getEvoluteSettings()) {
  log('Lendo o snapshot da nuvem...')
  // Supabase usa RLS (Row Level Security) para filtrar por usuário automaticamente
  // Não precisamos filtrar por user_id manualmente
  const response = await fetch(`${baseUrl(settings)}/rest/v1/evolute_snapshots?select=data,revision&order=revision.desc&limit=1`, {
    headers: headers(settings),
  })
  if (!response.ok) {
    // Nunca registrar o corpo da resposta: pode ecoar cabeçalhos ou dados do snapshot.
    log(`Falha ao ler a nuvem (status ${response.status})`)
    throw new Error(`Não foi possível ler a nuvem. Status: ${response.status}`)
  }
  const rows = await response.json()
  const row = Array.isArray(rows) ? rows[0] : null
  if (!row || typeof row.data !== 'object') {
    log('Nenhum snapshot válido na nuvem')
    return null
  }
  log(`Snapshot encontrado (revisão ${Number(row.revision || 0)}, ${Object.keys(row.data || {}).length} chaves)`)
  return { data: row.data as Record<string, unknown>, revision: Number(row.revision || 0) }
}

async function pushSnapshot(data: Record<string, unknown>, baseRevision: number, settings = getEvoluteSettings()) {
  log(`Enviando snapshot à nuvem (${Object.keys(data).length} chaves, revisão base ${baseRevision})`)
  const response = await fetch(`${baseUrl(settings)}/rest/v1/rpc/sync_evolute_snapshot`, {
    method: 'POST',
    headers: headers(settings),
    body: JSON.stringify({ p_data: data, p_base_revision: baseRevision }),
  })
  if (!response.ok) throw new Error('Não foi possível salvar na nuvem.')
  const rows = await response.json()
  const result = Array.isArray(rows) ? rows[0] : rows
  log(`Resposta da nuvem: revisão ${Number(result?.revision || 0)}, conflito ${Boolean(result?.conflict)}`)
  return { revision: Number(result?.revision || 0), conflict: Boolean(result?.conflict) }
}

// Sanitize localStorage corrupted keys (e.g. '{}' stored instead of '[]')
export function cleanCorruptedLocalStorage(): void {
  const arrayKeys = [
    'lifeos_habits', 'lifeos_workouts', 'lifeos_study_logs', 'lifeos_reading_logs',
    'lifeos_vice_logs', 'lifeos_cognitive', 'lifeos_subjects', 'lifeos_summaries',
    'lifeos_flashcards', 'lifeos_simulations', 'lifeos_weight_logs', 'lifeos_body_photos',
    'lifeos_books', 'lifeos_quotes', 'lifeos_vices', 'lifeos_workout_split'
  ]
  try {
    for (const key of arrayKeys) {
      const val = localStorage.getItem(key)
      if (val === '{}' || val === 'null') {
        localStorage.setItem(key, '[]')
      } else if (val) {
        try {
          const parsed = JSON.parse(val)
          if (typeof parsed === 'object' && !Array.isArray(parsed)) {
            localStorage.setItem(key, '[]')
          }
        } catch {
          localStorage.setItem(key, '[]')
        }
      }
    }
  } catch { /* ignore */ }
}

// Run immediately
cleanCorruptedLocalStorage()

function sanitizeVaultArrays(vault: JarvisVault): JarvisVault {
  if (!Array.isArray(vault.habits)) vault.habits = []
  if (!Array.isArray(vault.training)) vault.training = []
  if (!Array.isArray(vault.viceLogs)) vault.viceLogs = []
  if (!Array.isArray(vault.studyLogs)) vault.studyLogs = []
  if (!Array.isArray(vault.readingLogs)) vault.readingLogs = []
  if (!Array.isArray(vault.cognitive)) vault.cognitive = []
  if (!Array.isArray(vault.subjects)) vault.subjects = []
  if (!Array.isArray(vault.summaries)) vault.summaries = []
  if (!Array.isArray(vault.flashcards)) vault.flashcards = []
  return vault
}

function readVaultFromSnapshot(data: Record<string, unknown> | undefined): JarvisVault | null {
  if (!data) return null
  try {
    const vaultRaw = data[JARVIS_VAULT_KEY]
    if (!vaultRaw || typeof vaultRaw !== 'object') return null
    const vault = sanitizeVaultArrays(vaultRaw as JarvisVault)
    log(`Cofre lido do snapshot (versão ${vault.version})`)
    return vault
  } catch {
    log('Falha ao ler o cofre do snapshot')
    return null
  }
}

// ============ COLLECT DATA ============

export async function collectJarvisVaultFromThisDevice(): Promise<JarvisVault> {
  const now = Date.now()
  const vault: JarvisVault = emptyVault()
  const state = loadStampState()

  // Configurações deste dispositivo (localStorage) somadas às do backend do PC, campo a campo.
  // Nunca se sobrescreve um campo preenchido por um vazio: a regra vive em mergeStampedFields.
  vault.backend = await fetchBackendSnapshot()
  vault.fields = mergeStampedFields(
    collectLocalSettingsFields(state, now),
    settingsFieldsForBackend(vault.backend?.settings || {}),
  )
  applyFieldsToLegacy(vault)

  fillSectionsFromLocalStorage(vault)
  stampSections(vault, state, now)
  saveStampState(state)

  vault.source = isMobileStandalone() ? 'mobile' : 'pc'
  vault.updatedAt = now
  vault.version = (vault.version || 0) + 1

  return vault
}

/** Carimba cada seção só quando o conteúdo muda; assim o carimbo reflete a edição real. */
function stampSections(vault: JarvisVault, state: StampState, now: number): void {
  vault.fieldTimestamps = vault.fieldTimestamps || {}
  for (const section of [...MERGED_SECTIONS, 'habits', 'training'] as const) {
    vault.fieldTimestamps[section] = stampValue(state, `section.${section}`, (vault as Record<string, unknown>)[section], now)
  }
}

function fillSectionsFromLocalStorage(vault: JarvisVault): void {
  try { vault.memories = JSON.parse(localStorage.getItem(JARVIS_MEMORIES_KEY) || '[]') } catch { vault.memories = [] }
  vault.profile = localStorage.getItem(JARVIS_PROFILE_KEY) || ''
  // Coletar hábitos com versionamento
  const habitsRaw = localStorage.getItem('lifeos_habits') || localStorage.getItem('jarvis-habits')
  try {
    const habits = JSON.parse(habitsRaw || '[]') as any[]
    // Converter para versioned items
    vault.habits = habits.map(h => ({
      id: h.id || `h_${fingerprint(JSON.stringify(h))}`,
      data: h,
      updatedAt: h.updatedAt || h.createdAt || 0,
      deleted: false,
    }))
  } catch { vault.habits = [] }
  // Coletar treino com versionamento
  const trainingRaw = localStorage.getItem('lifeos_workouts') || localStorage.getItem('jarvis-training')
  try {
    const training = JSON.parse(trainingRaw || '[]') as any[]
    vault.training = training.map(t => ({
      id: t.id || `t_${fingerprint(JSON.stringify(t))}`,
      data: t,
      updatedAt: t.updatedAt || t.createdAt || 0,
      deleted: false,
    }))
  } catch { vault.training = [] }
  // Coletar outros dados
  try { vault.dashboard = JSON.parse(localStorage.getItem('jarvis-dashboard') || '{}') } catch { vault.dashboard = {} }
  try { vault.proactive = JSON.parse(localStorage.getItem('jarvis-proactive') || '{}') } catch { vault.proactive = {} }
  try { vault.climate = JSON.parse(localStorage.getItem('jarvis-climate') || '{}') } catch { vault.climate = {} }
  const financeRaw = localStorage.getItem('jarvis-finance') || localStorage.getItem('lifeos_finance')
  try { vault.finance = JSON.parse(financeRaw || '{}') } catch { vault.finance = {} }
  // Coletar dados do Life OS (logs por dia e outros dados)
  const lifeosPrefixes = ['lifeos_hlog_', 'lifeos_mental_', 'lifeos_water_']
  vault.habitLogs = {}
  vault.mentalLogs = {}
  vault.waterLogs = {}
  
  Object.keys(localStorage).forEach(key => {
    if (key.startsWith('lifeos_hlog_')) {
      try {
        const value = JSON.parse(localStorage.getItem(key) || '{}')
        if (typeof value === 'object') {
          vault.habitLogs![key] = value
        }
      } catch { vault.habitLogs![key] = {} }
    } else if (key.startsWith('lifeos_mental_')) {
      try {
        const value = JSON.parse(localStorage.getItem(key) || '{}')
        if (typeof value === 'object') {
          vault.mentalLogs![key] = value
        }
      } catch { vault.mentalLogs![key] = {} }
    } else if (key.startsWith('lifeos_water_')) {
      try {
        const value = JSON.parse(localStorage.getItem(key) || '{}')
        if (typeof value === 'object') {
          vault.waterLogs![key] = value
        }
      } catch { vault.waterLogs![key] = {} }
    }
  })
  // Coletar outros dados do Life OS
  try {
    const viceLogs = JSON.parse(localStorage.getItem('lifeos_vice_logs') || '[]')
    vault.viceLogs = Array.isArray(viceLogs) ? viceLogs : []
  } catch { vault.viceLogs = [] }
  try {
    const studyLogs = JSON.parse(localStorage.getItem('lifeos_study_logs') || '[]')
    vault.studyLogs = Array.isArray(studyLogs) ? studyLogs : []
  } catch { vault.studyLogs = [] }
  try {
    const readingLogs = JSON.parse(localStorage.getItem('lifeos_reading_logs') || '[]')
    vault.readingLogs = Array.isArray(readingLogs) ? readingLogs : []
  } catch { vault.readingLogs = [] }
  try {
    const cognitive = JSON.parse(localStorage.getItem('lifeos_cognitive') || '[]')
    vault.cognitive = Array.isArray(cognitive) ? cognitive : []
  } catch { vault.cognitive = [] }
  try {
    const subjects = JSON.parse(localStorage.getItem('lifeos_subjects') || '[]')
    vault.subjects = Array.isArray(subjects) ? subjects : []
  } catch { vault.subjects = [] }
  try {
    const summaries = JSON.parse(localStorage.getItem('lifeos_summaries') || '[]')
    vault.summaries = Array.isArray(summaries) ? summaries : []
  } catch { vault.summaries = [] }
  try {
    const flashcards = JSON.parse(localStorage.getItem('lifeos_flashcards') || '[]')
    vault.flashcards = Array.isArray(flashcards) ? flashcards : []
  } catch { vault.flashcards = [] }
  // Coletar dados adicionais do Life OS que ficam em extraData
  vault.extraData = {}

  // Chaves de array adicionais
  const extraArrayKeys = [
    'lifeos_simulations', 'lifeos_weight_logs', 'lifeos_body_photos',
    'lifeos_books', 'lifeos_quotes', 'lifeos_vices', 'lifeos_workout_split',
  ]
  for (const key of extraArrayKeys) {
    try {
      const raw = localStorage.getItem(key)
      if (raw) {
        const parsed = JSON.parse(raw)
        vault.extraData![key] = Array.isArray(parsed) ? parsed : []
      } else {
        vault.extraData![key] = []
      }
    } catch { vault.extraData![key] = [] }
  }

  // Chaves simples (string/number)
  const extraStringKeys = ['lifeos_infinite_notes']
  for (const key of extraStringKeys) {
    try {
      const raw = localStorage.getItem(key)
      if (raw !== null) vault.extraData![key] = raw
    } catch { /* ignore */ }
  }

  // Coletar victories por dia (prefixo lifeos_victories_)
  // Coletar water por dia (prefixo lifeos_water_) — não cobertos pelo waterLogs
  // Coletar mental logs por dia (prefixo lifeos_mental_) — agora em extraData também
  Object.keys(localStorage).forEach(key => {
    if (
      key.startsWith('lifeos_victories_') ||
      key.startsWith('lifeos_mental_') ||
      key.startsWith('lifeos_water_')
    ) {
      try {
        const raw = localStorage.getItem(key)
        if (raw !== null) {
          try { vault.extraData![key] = JSON.parse(raw) } catch { vault.extraData![key] = raw }
        }
      } catch { /* ignore */ }
    }
  })

  // Outros prefixos lifeos_ não coletados
  const alreadyCollected = new Set([
    'jarvis-react-session', 'jarvis-direct-sessions', 'jarvis-active-screen',
    'jarvis-chat-sidebar-open', 'jarvis_field_timestamps', 'jarvis_local_last_sync',
    'jarvis_sync_lock', 'jarvis_backup_vault', 'lifeos_cloud_revision', 'lifeos_last_sync_timestamp',
    'lifeos_api_settings', '__jarvis_vault',
    'jarvis-mobile-api-keys', 'jarvis-mobile-groq-model', 'jarvis-mobile-gemini-model',
    'jarvis-mobile-oxyy-models', 'jarvis-mobile-oxyy-model', 'jarvis-mobile-provider',
    'jarvis-cloud-memories', 'jarvis-cloud-profile', 'jarvis-habits', 'lifeos_habits',
    'jarvis-training', 'lifeos_workouts', 'jarvis-dashboard', 'jarvis-proactive',
    'jarvis-climate', 'jarvis-finance', 'lifeos_finance',
    'lifeos_vice_logs', 'lifeos_study_logs', 'lifeos_reading_logs', 'lifeos_cognitive',
    'lifeos_subjects', 'lifeos_summaries', 'lifeos_flashcards',
    ...extraArrayKeys, ...extraStringKeys,
  ])

  Object.keys(localStorage).forEach(key => {
    const isExcluded = alreadyCollected.has(key) ||
                       key.startsWith('lifeos_hlog_') ||
                       key.startsWith('lifeos_mental_') ||
                       key.startsWith('lifeos_water_') ||
                       key.startsWith('lifeos_victories_')
    if (!isExcluded && key.startsWith('lifeos_')) {
      try {
        const raw = localStorage.getItem(key)
        if (raw !== null) {
          try { vault.extraData![key] = JSON.parse(raw) } catch { vault.extraData![key] = raw }
        }
      } catch { /* ignore */ }
    }
  })
}

function buildCloudSnapshotPayload(existingData: Record<string, unknown> | undefined, vault: JarvisVault): Record<string, unknown> {
  const sanitized = sanitizeVaultArrays(vault)
  const habitsData = (Array.isArray(sanitized.habits) ? sanitized.habits : [])
    .map((h: any) => (h && typeof h === 'object' && 'data' in h && h.data ? h.data : h))
    .filter((h: any) => h && typeof h === 'object' && h.id)
  const trainingData = (Array.isArray(sanitized.training) ? sanitized.training : [])
    .map((t: any) => (t && typeof t === 'object' && 'data' in t && t.data ? t.data : t))
    .filter((t: any) => t && typeof t === 'object' && t.id)

  return {
    ...(existingData || {}),
    [JARVIS_VAULT_KEY]: sanitized,
    lifeos_habits: habitsData,
    lifeos_workouts: trainingData,
    lifeos_study_logs: Array.isArray(sanitized.studyLogs) ? sanitized.studyLogs : [],
    lifeos_vice_logs: Array.isArray(sanitized.viceLogs) ? sanitized.viceLogs : [],
    lifeos_reading_logs: Array.isArray(sanitized.readingLogs) ? sanitized.readingLogs : [],
    lifeos_cognitive: Array.isArray(sanitized.cognitive) ? sanitized.cognitive : [],
    lifeos_subjects: Array.isArray(sanitized.subjects) ? sanitized.subjects : [],
    lifeos_summaries: Array.isArray(sanitized.summaries) ? sanitized.summaries : [],
    lifeos_flashcards: Array.isArray(sanitized.flashcards) ? sanitized.flashcards : [],
  }
}

// ============ APPLY DATA LOCALLY ============

export function applyJarvisVaultLocally(vault: JarvisVault) {
  log(`Aplicando o cofre localmente (versão ${vault.version || 0})`)
  const now = Date.now()
  sanitizeVaultArrays(vault)
  const fields = vaultFields(vault)
  vault.fields = fields

  // Chaves: grava as que o cofre conhece e mantém as locais que ele não conhece (nunca apaga por vazio).
  const keys = readRawMobileKeys()
  for (const id of KEY_IDS) {
    const value = fieldValue(fields, `api_keys.${id}`)
    if (value) keys[id] = value
  }
  setMobileApiKeys(keys)
  setLocalFieldTimestamp('keys', now)

  const provider = fieldValue(fields, 'llm_provider')
  if (provider === 'gemini' || provider === 'groq' || provider === 'oxyy') setMobileProvider(provider)
  setLocalFieldTimestamp('provider', now)

  const oxyyModels: Record<string, string> = {}
  for (const [path, entry] of Object.entries(fields)) {
    if (path.startsWith('oxyy_models.') && typeof entry.v === 'string' && entry.v) oxyyModels[path.slice('oxyy_models.'.length)] = entry.v
  }
  if (Object.keys(oxyyModels).length) setMobileOxyyModels(oxyyModels)
  setLocalFieldTimestamp('oxyyModels', now)

  for (const [name, storageKey] of Object.entries(PROVIDER_MODEL_STORAGE)) {
    const value = fieldValue(fields, `provider_models.${name}`)
    if (value) localStorage.setItem(storageKey, value)
  }
  setLocalFieldTimestamp('providerModels', now)

  localStorage.setItem(JARVIS_MEMORIES_KEY, JSON.stringify(vault.memories || []))
  setLocalFieldTimestamp('memories', now)

  localStorage.setItem(JARVIS_PROFILE_KEY, vault.profile || '')
  setLocalFieldTimestamp('profile', now)

  // Aplicar hábitos (des-versionar de forma segura)
  if (vault.habits) {
    const rawHabits = Array.isArray(vault.habits) ? vault.habits : []
    const habitsData = rawHabits
      .map((h: any) => (h && typeof h === 'object' && 'data' in h && h.data ? h.data : h))
      .filter((h: any) => h && typeof h === 'object' && h.id)
    localStorage.setItem('jarvis-habits', JSON.stringify(habitsData))
    localStorage.setItem('lifeos_habits', JSON.stringify(habitsData))
    setLocalFieldTimestamp('habits', now)
  }
  
  // Aplicar treino (des-versionar de forma segura)
  if (vault.training) {
    const rawTraining = Array.isArray(vault.training) ? vault.training : []
    const trainingData = rawTraining
      .map((t: any) => (t && typeof t === 'object' && 'data' in t && t.data ? t.data : t))
      .filter((t: any) => t && typeof t === 'object' && t.id)
    localStorage.setItem('jarvis-training', JSON.stringify(trainingData))
    localStorage.setItem('lifeos_workouts', JSON.stringify(trainingData))
    setLocalFieldTimestamp('training', now)
  }
  
  if (vault.dashboard) {
    localStorage.setItem('jarvis-dashboard', JSON.stringify(vault.dashboard))
    setLocalFieldTimestamp('dashboard', now)
  }
  
  if (vault.proactive) {
    localStorage.setItem('jarvis-proactive', JSON.stringify(vault.proactive))
    setLocalFieldTimestamp('proactive', now)
  }
  
  if (vault.climate) {
    localStorage.setItem('jarvis-climate', JSON.stringify(vault.climate))
    setLocalFieldTimestamp('climate', now)
  }
  
  if (vault.finance) {
    localStorage.setItem('jarvis-finance', JSON.stringify(vault.finance))
    localStorage.setItem('lifeos_finance', JSON.stringify(vault.finance))
    setLocalFieldTimestamp('finance', now)
  }
  
  // Aplicar logs do Life OS
  if (vault.habitLogs && typeof vault.habitLogs === 'object') {
    Object.entries(vault.habitLogs).forEach(([key, value]) => {
      try {
        localStorage.setItem(key, JSON.stringify(value))
      } catch { /* ignore */ }
    })
    setLocalFieldTimestamp('habitLogs', now)
  } else {
    log('Cofre sem habitLogs válidos; mantendo os locais')
  }
  
  if (vault.mentalLogs && typeof vault.mentalLogs === 'object') {
    Object.entries(vault.mentalLogs).forEach(([key, value]) => {
      try {
        localStorage.setItem(key, JSON.stringify(value))
      } catch { /* ignore */ }
    })
    setLocalFieldTimestamp('mentalLogs', now)
  }
  
  if (vault.waterLogs && typeof vault.waterLogs === 'object') {
    Object.entries(vault.waterLogs).forEach(([key, value]) => {
      try {
        localStorage.setItem(key, JSON.stringify(value))
      } catch { /* ignore */ }
    })
    setLocalFieldTimestamp('waterLogs', now)
  }
  
  if (Array.isArray(vault.viceLogs)) {
    localStorage.setItem('lifeos_vice_logs', JSON.stringify(vault.viceLogs))
    setLocalFieldTimestamp('viceLogs', now)
  }
  
  if (Array.isArray(vault.studyLogs)) {
    localStorage.setItem('lifeos_study_logs', JSON.stringify(vault.studyLogs))
    setLocalFieldTimestamp('studyLogs', now)
  }
  
  if (Array.isArray(vault.readingLogs)) {
    localStorage.setItem('lifeos_reading_logs', JSON.stringify(vault.readingLogs))
    setLocalFieldTimestamp('readingLogs', now)
  }
  
  if (Array.isArray(vault.cognitive)) {
    localStorage.setItem('lifeos_cognitive', JSON.stringify(vault.cognitive))
    setLocalFieldTimestamp('cognitive', now)
  }
  
  if (Array.isArray(vault.subjects)) {
    localStorage.setItem('lifeos_subjects', JSON.stringify(vault.subjects))
    setLocalFieldTimestamp('subjects', now)
  }
  
  if (Array.isArray(vault.summaries)) {
    localStorage.setItem('lifeos_summaries', JSON.stringify(vault.summaries))
    setLocalFieldTimestamp('summaries', now)
  }
  
  if (Array.isArray(vault.flashcards)) {
    localStorage.setItem('lifeos_flashcards', JSON.stringify(vault.flashcards))
    setLocalFieldTimestamp('flashcards', now)
  }
  
  if (vault.extraData && typeof vault.extraData === 'object') {
    Object.entries(vault.extraData).forEach(([key, value]) => {
      try {
        // value can be already-parsed (object/array) or a raw string
        if (typeof value === 'string') {
          localStorage.setItem(key, value)
        } else {
          localStorage.setItem(key, JSON.stringify(value))
        }
      } catch { /* ignore */ }
    })
    setLocalFieldTimestamp('extraData', now)
  }
  
  // Limpar qualquer chave de array que possa estar corrompida como {}
  cleanCorruptedLocalStorage()
  
  localStorage.setItem(CLOUD_REVISION_KEY, String(vault.version || 0))
  setLocalLastSync(now)
  
  // Notificar o app React para recarregar o estado do localStorage
  try {
    window.dispatchEvent(new Event('jarvis-sync-applied'))
  } catch { /* ignore */ }
  
  recordAppliedStamps(vault, now)
  log('Cofre aplicado localmente')
}

/** Depois de gravar no localStorage, guarda os carimbos do cofre para a próxima coleta reconhecê-los. */
function recordAppliedStamps(vault: JarvisVault, now: number): void {
  const state = loadStampState()
  for (const [path, entry] of Object.entries(vault.fields || {})) recordStamp(state, path, entry.v, entry.ts)
  const current = emptyVault()
  fillSectionsFromLocalStorage(current)
  for (const section of [...MERGED_SECTIONS, 'habits', 'training'] as const) {
    const ts = Number(vault.fieldTimestamps?.[section] || 0) || now
    recordStamp(state, `section.${section}`, (current as Record<string, unknown>)[section], ts)
  }
  saveStampState(state)
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'erro desconhecido'
}

// ============ PUSH/PULL OPERATIONS ============

export async function pushJarvisVault(incoming = collectJarvisVaultFromThisDevice()): Promise<JarvisVault> {
  if (!acquireSyncLock()) {
    throw new Error('Sincronização em andamento. Aguarde.')
  }

  try {
    const local = await incoming
    log(`Iniciando envio (versão local ${local.version})`)

    // Criar backup antes de sync
    createBackup(local)

    // Mesclagem campo a campo com o que já está na nuvem; em conflito de revisão, baixa a mais recente e repete.
    let snapshot = await pullSnapshot()
    for (let attempt = 0; attempt < 3; attempt += 1) {
      const cloudVault = readVaultFromSnapshot(snapshot?.data)
      const merged = cloudVault ? mergeVaults(local, cloudVault) : local
      await syncBackend(merged, cloudVault?.backend)
      const data = buildCloudSnapshotPayload(snapshot?.data, merged)
      const result = await pushSnapshot(data, snapshot ? snapshot.revision : 0)
      if (!result.conflict) {
        localStorage.setItem(CLOUD_REVISION_KEY, String(result.revision))
        applyJarvisVaultLocally(merged)
        return merged
      }
      log('Conflito de revisão; baixando a versão mais recente e tentando de novo')
      snapshot = await pullSnapshot()
    }
    throw new Error('Conflito persistente. Tente novamente mais tarde.')
  } catch (e) {
    log(`Falha no envio: ${errorMessage(e)}`)
    // Restaurar backup em caso de erro
    const backup = restoreBackup()
    if (backup) {
      log('Backup local restaurado após o erro')
      applyJarvisVaultLocally(backup)
    }
    throw e
  } finally {
    releaseSyncLock()
  }
}

export async function downloadJarvisVault(): Promise<JarvisVault> {
  if (!acquireSyncLock()) {
    throw new Error('Sincronização em andamento. Aguarde.')
  }

  try {
    log('Iniciando download da nuvem')
    const local = await collectJarvisVaultFromThisDevice()

    // Criar backup
    createBackup(local)

    const snapshot = await pullSnapshot()
    const cloudVault = readVaultFromSnapshot(snapshot?.data)

    if (!snapshot || !cloudVault) {
      throw new Error('Ainda não há dados na nuvem. Use "Salvar na nuvem" primeiro.')
    }

    const merged = mergeVaults(local, cloudVault)
    await syncBackend(merged, cloudVault.backend)

    applyJarvisVaultLocally(merged)
    return merged
  } catch (e) {
    log(`Falha no download: ${errorMessage(e)}`)
    const backup = restoreBackup()
    if (backup) {
      log('Backup local restaurado após o erro')
      applyJarvisVaultLocally(backup)
    }
    throw e
  } finally {
    releaseSyncLock()
  }
}

// ============ AUTO-SYNC ============

export async function autoSyncOnOpen(): Promise<void> {
  if (!isEvoluteCloudConnected()) {
    log('Sem conexão com a nuvem; sincronização automática ignorada')
    return
  }

  // Renovar token se expirado
  if (isTokenExpired()) {
    log('Token expirado; renovando')
    await refreshAccessToken()
  }

  const lastSync = getLocalLastSync()
  const now = Date.now()
  const oneHour = 60 * 60 * 1000

  // Auto-sync apenas se passou mais de 1 hora
  if (now - lastSync < oneHour) {
    log('Sincronização automática ignorada (sincronizado há pouco)')
    return
  }

  try {
    log('Iniciando sincronização automática')
    await downloadJarvisVault()
    log('Sincronização automática concluída')
  } catch (e) {
    log(`Sincronização automática falhou: ${errorMessage(e)}`)
    // Não lançar erro em auto-sync
  }
}

function countConfiguredProviders(vault: JarvisVault): number {
  return Object.values(vault.keys || {}).filter(value => value && typeof value === 'string' && value.trim()).length
}

export async function syncJarvisAfterLogin(role: 'pc' | 'mobile'): Promise<string> {
  try {
    if (role === 'mobile') {
      const vault = await downloadJarvisVault()
      return `Chaves e memórias baixadas (${countConfiguredProviders(vault)} provedor(es), ${vault.memories?.length || 0} memórias). Rotação por vírgula igual ao PC.`
    }
    // O envio sempre mescla com a nuvem antes de gravar: dados de outro dispositivo não são sobrescritos.
    const vault = await pushJarvisVault()
    return `Jarvis do PC sincronizado com a nuvem (${countConfiguredProviders(vault)} provedor(es) com chave). No celular, entre com a mesma conta.`
  } catch (error) {
    log(`Erro na sincronização: ${errorMessage(error)}`)
    if (error instanceof Error) {
      throw error
    }
    throw new Error('Erro desconhecido na sincronização.')
  }
}
