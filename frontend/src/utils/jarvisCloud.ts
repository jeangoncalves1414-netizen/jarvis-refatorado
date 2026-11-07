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

export { JARVIS_MEMORIES_KEY, JARVIS_PROFILE_KEY, JARVIS_VAULT_KEY }

const CLOUD_REVISION_KEY = 'lifeos_cloud_revision'
const LOCAL_LAST_SYNC_KEY = 'jarvis_local_last_sync'
const LOCAL_FIELD_TIMESTAMPS_KEY = 'jarvis_field_timestamps'
const SYNC_LOCK_KEY = 'jarvis_sync_lock'
const BACKUP_VAULT_KEY = 'jarvis_backup_vault'

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

// ============ SYNC LOCK ============
// Impede modificações durante sincronização

function acquireSyncLock(): boolean {
  const lock = localStorage.getItem(SYNC_LOCK_KEY)
  if (lock) {
    const lockTime = Number(lock)
    // Lock expira após 30 segundos (caso de crash)
    if (Date.now() - lockTime < 30000) {
      console.log('[JarvisCloud] Sync lock already acquired, skipping')
      return false
    }
  }
  localStorage.setItem(SYNC_LOCK_KEY, String(Date.now()))
  console.log('[JarvisCloud] Sync lock acquired')
  return true
}

function releaseSyncLock(): void {
  localStorage.removeItem(SYNC_LOCK_KEY)
  console.log('[JarvisCloud] Sync lock released')
}

// ============ BACKUP ============
// Backup automático antes de sync

function createBackup(vault: JarvisVault): void {
  localStorage.setItem(BACKUP_VAULT_KEY, JSON.stringify(vault))
  console.log('[JarvisCloud] Backup created')
}

function restoreBackup(): JarvisVault | null {
  try {
    const backup = localStorage.getItem(BACKUP_VAULT_KEY)
    if (backup) {
      console.log('[JarvisCloud] Backup restored')
      return JSON.parse(backup)
    }
  } catch (e) {
    console.error('[JarvisCloud] Failed to restore backup:', e)
  }
  return null
}

// ============ ITEM-LEVEL MERGE ============
// Merge item por item, não array inteiro

function mergeVersionedArrays<T>(
  local: VersionedItem<T>[],
  remote: VersionedItem<T>[],
  localTs: number,
  remoteTs: number
): VersionedItem<T>[] {
  const merged = new Map<string, VersionedItem<T>>()
  
  // Indexar por ID
  local.forEach(item => merged.set(item.id, item))
  remote.forEach(item => {
    const existing = merged.get(item.id)
    if (!existing) {
      // Item novo no remote
      merged.set(item.id, item)
    } else {
      // Merge item por item baseado em updatedAt
      if (item.updatedAt > existing.updatedAt) {
        merged.set(item.id, item)
      }
      // Se mesmo timestamp, prefere não-deletado
      else if (item.updatedAt === existing.updatedAt && !item.deleted) {
        merged.set(item.id, item)
      }
    }
  })
  
  // Remover itens deletados
  const result = Array.from(merged.values()).filter(item => !item.deleted)
  console.log(`[JarvisCloud] Merged ${result.length} items (local: ${local.length}, remote: ${remote.length})`)
  return result
}

// ============ THREE-WAY MERGE ============
// Merge determinístico: base + local + remote

function mergeVaults(
  base: JarvisVault,
  local: JarvisVault,
  remote: JarvisVault
): JarvisVault {
  console.log('[JarvisCloud] Starting three-way merge...')
  console.log('[JarvisCloud] Base version:', base.version)
  console.log('[JarvisCloud] Local version:', local.version)
  console.log('[JarvisCloud] Remote version:', remote.version)
  
  const now = Date.now()
  const merged: JarvisVault = {
    ...emptyVault(),
    ...base,
    ...local,
    ...remote,
    updatedAt: now,
    version: Math.max(base.version || 0, local.version || 0, remote.version || 0) + 1,
    fieldTimestamps: {},
  }
  
  // Merge de campos simples (last-write-wins por timestamp)
  const mergeField = <T>(
    field: keyof JarvisVault,
    localValue: T,
    remoteValue: T,
    localTs: number,
    remoteTs: number
  ): T => {
    const localHasData = Array.isArray(localValue) ? localValue.length > 0 : localValue !== null && localValue !== undefined && localValue !== ''
    const remoteHasData = Array.isArray(remoteValue) ? remoteValue.length > 0 : remoteValue !== null && remoteValue !== undefined && remoteValue !== ''
    
    // Se local tem dados e remote não, usa local
    if (localHasData && !remoteHasData) {
      console.log(`[JarvisCloud] Field ${String(field)}: using local (has data, remote empty)`)
      return localValue
    }
    // Se remote tem dados e local não, usa remote
    if (!localHasData && remoteHasData) {
      console.log(`[JarvisCloud] Field ${String(field)}: using remote (has data, local empty)`)
      return remoteValue
    }
    // Se ambos têm dados, usa timestamp
    if (localHasData && remoteHasData) {
      const useLocal = (localTs || 0) >= (remoteTs || 0)
      console.log(`[JarvisCloud] Field ${String(field)}: using ${useLocal ? 'local' : 'remote'} (timestamp)`)
      return useLocal ? localValue : remoteValue
    }
    // Se nenhum tem dados, usa local
    console.log(`[JarvisCloud] Field ${String(field)}: using local (both empty)`)
    return localValue
  }
  
  const localTs = local.fieldTimestamps || {}
  const remoteTs = remote.fieldTimestamps || {}
  
  // Merge de campos simples
  // Para 'keys': verificar se realmente tem valores preenchidos (não apenas defaults vazios)
  const localKeysHaveValue = keysHaveValue(local.keys)
  const remoteKeysHaveValue = keysHaveValue(remote.keys)
  if (!localKeysHaveValue && remoteKeysHaveValue) {
    // Local só tem padrões vazios, remote tem chaves reais → usar remote
    console.log('[JarvisCloud] Keys: using remote (local is default/empty, remote has real keys)')
    merged.keys = remote.keys
  } else if (localKeysHaveValue && !remoteKeysHaveValue) {
    merged.keys = local.keys
    console.log('[JarvisCloud] Keys: using local (remote is empty)')
  } else {
    // Ambos têm ou ambos não têm → resolver por timestamp
    merged.keys = mergeField('keys', local.keys, remote.keys, localTs.keys || 0, remoteTs.keys || 0)
  }
  merged.provider = mergeField('provider', local.provider, remote.provider, localTs.provider || 0, remoteTs.provider || 0)
  merged.oxyyModels = mergeField('oxyyModels', local.oxyyModels, remote.oxyyModels, localTs.oxyyModels || 0, remoteTs.oxyyModels || 0)
  merged.providerModels = mergeField('providerModels', local.providerModels, remote.providerModels, localTs.providerModels || 0, remoteTs.providerModels || 0)
  merged.memories = mergeField('memories', local.memories, remote.memories, localTs.memories || 0, remoteTs.memories || 0)
  merged.profile = mergeField('profile', local.profile, remote.profile, localTs.profile || 0, remoteTs.profile || 0)
  merged.dashboard = mergeField('dashboard', local.dashboard, remote.dashboard, localTs.dashboard || 0, remoteTs.dashboard || 0)
  merged.proactive = mergeField('proactive', local.proactive, remote.proactive, localTs.proactive || 0, remoteTs.proactive || 0)
  merged.climate = mergeField('climate', local.climate, remote.climate, localTs.climate || 0, remoteTs.climate || 0)
  merged.finance = mergeField('finance', local.finance, remote.finance, localTs.finance || 0, remoteTs.finance || 0)
  
  // Merge de dados do Life OS (deep merge para objetos)
  const deepMerge = (local: any, remote: any): any => {
    // If either side is not a plain object, prefer the non-null side
    const localIsObj = local !== null && local !== undefined && typeof local === 'object' && !Array.isArray(local)
    const remoteIsObj = remote !== null && remote !== undefined && typeof remote === 'object' && !Array.isArray(remote)
    if (!localIsObj || !remoteIsObj) {
      // For primitives: prefer remote if it has a value, else keep local
      if (remote !== null && remote !== undefined) return remote
      return local
    }
    const result = { ...local }
    Object.keys(remote).forEach(key => {
      result[key] = deepMerge(local[key], remote[key])
    })
    return result
  }
  
  merged.habitLogs = deepMerge(local.habitLogs || {}, remote.habitLogs || {})
  merged.mentalLogs = deepMerge(local.mentalLogs || {}, remote.mentalLogs || {})
  merged.waterLogs = deepMerge(local.waterLogs || {}, remote.waterLogs || {})
  merged.viceLogs = deepMerge(local.viceLogs || {}, remote.viceLogs || {})
  merged.studyLogs = deepMerge(local.studyLogs || {}, remote.studyLogs || {})
  merged.readingLogs = deepMerge(local.readingLogs || {}, remote.readingLogs || {})
  merged.cognitive = deepMerge(local.cognitive || {}, remote.cognitive || {})
  merged.subjects = deepMerge(local.subjects || {}, remote.subjects || {})
  merged.summaries = deepMerge(local.summaries || {}, remote.summaries || {})
  merged.flashcards = deepMerge(local.flashcards || {}, remote.flashcards || {})
  merged.extraData = deepMerge(local.extraData || {}, remote.extraData || {})
  
  // Merge de arrays versionados (item por item)
  if (local.habits || remote.habits) {
    merged.habits = mergeVersionedArrays(
      local.habits || [],
      remote.habits || [],
      localTs.habits || 0,
      remoteTs.habits || 0
    )
    console.log(`[JarvisCloud] Merged habits: ${merged.habits?.length || 0} items`)
  }
  
  if (local.training || remote.training) {
    merged.training = mergeVersionedArrays(
      local.training || [],
      remote.training || [],
      localTs.training || 0,
      remoteTs.training || 0
    )
    console.log(`[JarvisCloud] Merged training: ${merged.training?.length || 0} items`)
  }
  
  // Atualizar timestamps de campos
  merged.fieldTimestamps = {
    keys: Math.max(localTs.keys || 0, remoteTs.keys || 0, now),
    provider: Math.max(localTs.provider || 0, remoteTs.provider || 0, now),
    oxyyModels: Math.max(localTs.oxyyModels || 0, remoteTs.oxyyModels || 0, now),
    providerModels: Math.max(localTs.providerModels || 0, remoteTs.providerModels || 0, now),
    memories: Math.max(localTs.memories || 0, remoteTs.memories || 0, now),
    profile: Math.max(localTs.profile || 0, remoteTs.profile || 0, now),
    habits: Math.max(localTs.habits || 0, remoteTs.habits || 0, now),
    training: Math.max(localTs.training || 0, remoteTs.training || 0, now),
    dashboard: Math.max(localTs.dashboard || 0, remoteTs.dashboard || 0, now),
    proactive: Math.max(localTs.proactive || 0, remoteTs.proactive || 0, now),
    climate: Math.max(localTs.climate || 0, remoteTs.climate || 0, now),
    finance: Math.max(localTs.finance || 0, remoteTs.finance || 0, now),
    habitLogs: Math.max(localTs.habitLogs || 0, remoteTs.habitLogs || 0, now),
    mentalLogs: Math.max(localTs.mentalLogs || 0, remoteTs.mentalLogs || 0, now),
    waterLogs: Math.max(localTs.waterLogs || 0, remoteTs.waterLogs || 0, now),
    viceLogs: Math.max(localTs.viceLogs || 0, remoteTs.viceLogs || 0, now),
    studyLogs: Math.max(localTs.studyLogs || 0, remoteTs.studyLogs || 0, now),
    readingLogs: Math.max(localTs.readingLogs || 0, remoteTs.readingLogs || 0, now),
    cognitive: Math.max(localTs.cognitive || 0, remoteTs.cognitive || 0, now),
    subjects: Math.max(localTs.subjects || 0, remoteTs.subjects || 0, now),
    summaries: Math.max(localTs.summaries || 0, remoteTs.summaries || 0, now),
    flashcards: Math.max(localTs.flashcards || 0, remoteTs.flashcards || 0, now),
    extraData: Math.max(localTs.extraData || 0, remoteTs.extraData || 0, now),
  }
  
  console.log('[JarvisCloud] Three-way merge complete, version:', merged.version)
  return merged
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
  console.log('[JarvisCloud] Pulling snapshot from cloud...')
  console.log('[JarvisCloud] Supabase URL:', baseUrl(settings))
  // Supabase usa RLS (Row Level Security) para filtrar por usuário automaticamente
  // Não precisamos filtrar por user_id manualmente
  const url = `${baseUrl(settings)}/rest/v1/evolute_snapshots?select=data,revision&order=revision.desc&limit=1`
  console.log('[JarvisCloud] Request URL:', url)
  const response = await fetch(url, {
    headers: headers(settings),
  })
  console.log('[JarvisCloud] Response status:', response.status)
  console.log('[JarvisCloud] Response ok:', response.ok)
  if (!response.ok) {
    const errorText = await response.text()
    console.error('[JarvisCloud] Error response:', errorText)
    throw new Error(`Não foi possível ler a nuvem. Status: ${response.status}`)
  }
  const rows = await response.json()
  console.log('[JarvisCloud] Response rows:', rows)
  const row = Array.isArray(rows) ? rows[0] : null
  if (!row || typeof row.data !== 'object') {
    console.log('[JarvisCloud] No valid snapshot found in cloud')
    return null
  }
  console.log('[JarvisCloud] Snapshot found, revision:', row.revision)
  console.log('[JarvisCloud] Snapshot data keys:', Object.keys(row.data || {}))
  return { data: row.data as Record<string, unknown>, revision: Number(row.revision || 0) }
}

async function pushSnapshot(data: Record<string, unknown>, baseRevision: number, settings = getEvoluteSettings()) {
  console.log('[JarvisCloud] Pushing snapshot to cloud...')
  console.log('[JarvisCloud] Data keys being pushed:', Object.keys(data))
  console.log('[JarvisCloud] Base revision:', baseRevision)
  const response = await fetch(`${baseUrl(settings)}/rest/v1/rpc/sync_evolute_snapshot`, {
    method: 'POST',
    headers: headers(settings),
    body: JSON.stringify({ p_data: data, p_base_revision: baseRevision }),
  })
  if (!response.ok) throw new Error('Não foi possível salvar na nuvem.')
  const rows = await response.json()
  console.log('[JarvisCloud] Push response:', rows)
  const result = Array.isArray(rows) ? rows[0] : rows
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
    console.log('[JarvisCloud] Vault read from snapshot, version:', vault.version)
    return vault
  } catch (e) {
    console.error('[JarvisCloud] Failed to read vault from snapshot:', e)
    return null
  }
}

// ============ COLLECT DATA ============

export async function collectJarvisVaultFromThisDevice(): Promise<JarvisVault> {
  const now = Date.now()
  const vault: JarvisVault = emptyVault()
  
  // Coletar dados básicos
  vault.keys = getMobileApiKeys()
  if (!isMobileStandalone()) {
    try {
      const [keysRes, settingsRes] = await Promise.all([
        fetch('/api/settings/keys').then(r => r.json()).catch(() => null),
        fetch('/api/settings').then(r => r.json()).catch(() => null),
      ])
      if (keysRes && keysRes.keys && keysHaveValue(keysRes.keys)) {
        vault.keys = { ...vault.keys, ...keysRes.keys }
        setMobileApiKeys(vault.keys)
      }
      if (settingsRes) {
        if (settingsRes.llm_provider) {
          vault.provider = settingsRes.llm_provider
          setMobileProvider(settingsRes.llm_provider)
        }
        if (settingsRes.oxyy_models) {
          vault.oxyyModels = { ...vault.oxyyModels, ...settingsRes.oxyy_models }
          setMobileOxyyModels(vault.oxyyModels)
        }
      }
    } catch (e) {
      console.warn('[JarvisCloud] Falha ao coletar dados do backend local no PC:', e)
    }
  }
  vault.fieldTimestamps!.keys = now
  
  if (!vault.provider) {
    vault.provider = getMobileProvider()
  }
  vault.fieldTimestamps!.provider = now
  
  if (!vault.oxyyModels || Object.keys(vault.oxyyModels).length === 0) {
    vault.oxyyModels = getMobileOxyyModels()
  }
  vault.fieldTimestamps!.oxyyModels = now
  
  // Coletar provider models do localStorage
  const groqModel = localStorage.getItem('jarvis-mobile-groq-model')
  const geminiModel = localStorage.getItem('jarvis-mobile-gemini-model')
  const oxyyModel = localStorage.getItem('jarvis-mobile-oxyy-model')
  if (groqModel) vault.providerModels.groq = groqModel
  if (geminiModel) vault.providerModels.gemini = geminiModel
  if (oxyyModel) vault.providerModels.oxyy = oxyyModel
  vault.fieldTimestamps!.providerModels = now
  
  try { vault.memories = JSON.parse(localStorage.getItem(JARVIS_MEMORIES_KEY) || '[]') } catch { vault.memories = [] }
  vault.fieldTimestamps!.memories = now
  
  vault.profile = localStorage.getItem(JARVIS_PROFILE_KEY) || ''
  vault.fieldTimestamps!.profile = now
  
  // Coletar hábitos com versionamento
  console.log('[JarvisCloud] Checking localStorage for habits...')
  console.log('[JarvisCloud] All localStorage keys:', Object.keys(localStorage))
  const habitsRaw = localStorage.getItem('lifeos_habits') || localStorage.getItem('jarvis-habits')
  console.log('[JarvisCloud] Raw habits from localStorage:', habitsRaw)
  console.log('[JarvisCloud] Using key:', habitsRaw ? (localStorage.getItem('lifeos_habits') ? 'lifeos_habits' : 'jarvis-habits') : 'none')
  try {
    const habits = JSON.parse(habitsRaw || '[]') as any[]
    // Converter para versioned items
    vault.habits = habits.map(h => ({
      id: h.id || `h_${Date.now()}_${Math.random()}`,
      data: h,
      updatedAt: h.updatedAt || h.createdAt || Date.now(),
      deleted: false,
    }))
    console.log('[JarvisCloud] Habits count:', vault.habits?.length || 0)
  } catch { vault.habits = [] }
  vault.fieldTimestamps!.habits = now
  
  // Coletar treino com versionamento
  const trainingRaw = localStorage.getItem('lifeos_workouts') || localStorage.getItem('jarvis-training')
  console.log('[JarvisCloud] Raw training from localStorage:', trainingRaw)
  console.log('[JarvisCloud] Using training key:', trainingRaw ? (localStorage.getItem('lifeos_workouts') ? 'lifeos_workouts' : 'jarvis-training') : 'none')
  try {
    const training = JSON.parse(trainingRaw || '[]') as any[]
    vault.training = training.map(t => ({
      id: t.id || `t_${Date.now()}_${Math.random()}`,
      data: t,
      updatedAt: t.updatedAt || t.createdAt || Date.now(),
      deleted: false,
    }))
    console.log('[JarvisCloud] Training count:', vault.training?.length || 0)
  } catch { vault.training = [] }
  vault.fieldTimestamps!.training = now
  
  // Coletar outros dados
  try { vault.dashboard = JSON.parse(localStorage.getItem('jarvis-dashboard') || '{}') } catch { vault.dashboard = {} }
  vault.fieldTimestamps!.dashboard = now
  
  try { vault.proactive = JSON.parse(localStorage.getItem('jarvis-proactive') || '{}') } catch { vault.proactive = {} }
  vault.fieldTimestamps!.proactive = now
  
  try { vault.climate = JSON.parse(localStorage.getItem('jarvis-climate') || '{}') } catch { vault.climate = {} }
  vault.fieldTimestamps!.climate = now
  
  const financeRaw = localStorage.getItem('jarvis-finance') || localStorage.getItem('lifeos_finance')
  try { vault.finance = JSON.parse(financeRaw || '{}') } catch { vault.finance = {} }
  vault.fieldTimestamps!.finance = now
  
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
  vault.fieldTimestamps!.habitLogs = now
  vault.fieldTimestamps!.mentalLogs = now
  vault.fieldTimestamps!.waterLogs = now
  
  // Coletar outros dados do Life OS
  try {
    const viceLogs = JSON.parse(localStorage.getItem('lifeos_vice_logs') || '[]')
    vault.viceLogs = Array.isArray(viceLogs) ? viceLogs : []
  } catch { vault.viceLogs = [] }
  vault.fieldTimestamps!.viceLogs = now
  
  try {
    const studyLogs = JSON.parse(localStorage.getItem('lifeos_study_logs') || '[]')
    vault.studyLogs = Array.isArray(studyLogs) ? studyLogs : []
  } catch { vault.studyLogs = [] }
  vault.fieldTimestamps!.studyLogs = now
  
  try {
    const readingLogs = JSON.parse(localStorage.getItem('lifeos_reading_logs') || '[]')
    vault.readingLogs = Array.isArray(readingLogs) ? readingLogs : []
  } catch { vault.readingLogs = [] }
  vault.fieldTimestamps!.readingLogs = now
  
  try {
    const cognitive = JSON.parse(localStorage.getItem('lifeos_cognitive') || '[]')
    vault.cognitive = Array.isArray(cognitive) ? cognitive : []
  } catch { vault.cognitive = [] }
  vault.fieldTimestamps!.cognitive = now
  
  try {
    const subjects = JSON.parse(localStorage.getItem('lifeos_subjects') || '[]')
    vault.subjects = Array.isArray(subjects) ? subjects : []
  } catch { vault.subjects = [] }
  vault.fieldTimestamps!.subjects = now
  
  try {
    const summaries = JSON.parse(localStorage.getItem('lifeos_summaries') || '[]')
    vault.summaries = Array.isArray(summaries) ? summaries : []
  } catch { vault.summaries = [] }
  vault.fieldTimestamps!.summaries = now
  
  try {
    const flashcards = JSON.parse(localStorage.getItem('lifeos_flashcards') || '[]')
    vault.flashcards = Array.isArray(flashcards) ? flashcards : []
  } catch { vault.flashcards = [] }
  vault.fieldTimestamps!.flashcards = now
  
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
  vault.fieldTimestamps!.extraData = now
  
  vault.source = isMobileStandalone() ? 'mobile' : 'pc'
  vault.updatedAt = now
  vault.version = (vault.version || 0) + 1
  
  return vault
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
  console.log('[JarvisCloud] Applying vault locally:', vault)
  const now = Date.now()
  sanitizeVaultArrays(vault)
  
  setMobileApiKeys(vault.keys)
  setLocalFieldTimestamp('keys', now)
  
  setMobileProvider(vault.provider || 'oxyy')
  setLocalFieldTimestamp('provider', now)
  
  setMobileOxyyModels(vault.oxyyModels || DEFAULT_OXXY_MODELS)
  setLocalFieldTimestamp('oxyyModels', now)
  
  // Apply provider models
  if (vault.providerModels) {
    console.log('[JarvisCloud] Applying provider models:', vault.providerModels)
    if (vault.providerModels.groq) {
      localStorage.setItem('jarvis-mobile-groq-model', vault.providerModels.groq)
      console.log('[JarvisCloud] Set groq model:', vault.providerModels.groq)
    }
    if (vault.providerModels.gemini) {
      localStorage.setItem('jarvis-mobile-gemini-model', vault.providerModels.gemini)
      console.log('[JarvisCloud] Set gemini model:', vault.providerModels.gemini)
    }
    if (vault.providerModels.oxyy) {
      localStorage.setItem('jarvis-mobile-oxyy-model', vault.providerModels.oxyy)
      console.log('[JarvisCloud] Set oxyy model:', vault.providerModels.oxyy)
    }
    setLocalFieldTimestamp('providerModels', now)
  }
  
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
    console.log('[JarvisCloud] No habitLogs in vault or invalid type, keeping local')
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
  
  console.log('[JarvisCloud] Vault applied locally')
}

// ============ PUSH/PULL OPERATIONS ============

export async function pushJarvisVault(incoming = collectJarvisVaultFromThisDevice()): Promise<JarvisVault> {
  if (!acquireSyncLock()) {
    throw new Error('Sincronização em andamento. Aguarde.')
  }
  
  try {
    const local = await incoming
    console.log('[JarvisCloud] Starting push, local version:', local.version)
    
    // Criar backup antes de sync
    createBackup(local)
    
    const snapshot = await pullSnapshot()
    const cloudVault = readVaultFromSnapshot(snapshot?.data)
    
    // Se não há snapshot na nuvem, criar um novo
    if (!snapshot || !cloudVault) {
      console.log('[JarvisCloud] No snapshot in cloud, creating new one with local data')
      const data = buildCloudSnapshotPayload(snapshot?.data, local)
      const result = await pushSnapshot(data, 0)
      if (result.conflict) {
        throw new Error('Conflito ao criar snapshot na nuvem. Tente novamente.')
      }
      localStorage.setItem(CLOUD_REVISION_KEY, String(result.revision))
      applyJarvisVaultLocally(local)
      return local
    }
    
    // Three-way merge: base (cloud) + local + remote (cloud)
    console.log('[JarvisCloud] Performing three-way merge...')
    const merged = mergeVaults(cloudVault, local, cloudVault)
    
    const data = buildCloudSnapshotPayload(snapshot?.data, merged)
    const baseRevision = snapshot?.revision || Number(localStorage.getItem(CLOUD_REVISION_KEY) || '0')
    const result = await pushSnapshot(data, baseRevision)
    
    if (result.conflict) {
      console.log('[JarvisCloud] Conflict detected, pulling latest and retrying...')
      // Em caso de conflito, baixar latest e tentar novamente
      const latestSnapshot = await pullSnapshot()
      const latestVault = readVaultFromSnapshot(latestSnapshot?.data)
      if (latestVault) {
        const retryMerged = mergeVaults(latestVault, local, latestVault)
        const retryData = buildCloudSnapshotPayload(latestSnapshot?.data, retryMerged)
        const retryResult = await pushSnapshot(retryData, latestSnapshot?.revision || 0)
        if (retryResult.conflict) {
          throw new Error('Conflito persistente. Tente novamente mais tarde.')
        }
        localStorage.setItem(CLOUD_REVISION_KEY, String(retryResult.revision))
        applyJarvisVaultLocally(retryMerged)
        return retryMerged
      }
    }
    
    localStorage.setItem(CLOUD_REVISION_KEY, String(result.revision))
    applyJarvisVaultLocally(merged)
    return merged
  } catch (e) {
    console.error('[JarvisCloud] Push failed:', e)
    // Restaurar backup em caso de erro
    const backup = restoreBackup()
    if (backup) {
      console.log('[JarvisCloud] Restored from backup after error')
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
    console.log('[JarvisCloud] Starting download from cloud...')
    const local = await collectJarvisVaultFromThisDevice()
    console.log('[JarvisCloud] Local vault collected, version:', local.version)
    
    // Criar backup
    createBackup(local)
    
    const snapshot = await pullSnapshot()
    const cloudVault = readVaultFromSnapshot(snapshot?.data)
    
    if (!snapshot || !cloudVault) {
      console.log('[JarvisCloud] No snapshot in cloud')
      throw new Error('Ainda não há dados na nuvem. Use "Salvar na nuvem" primeiro.')
    }
    
    console.log('[JarvisCloud] Vault pulled from cloud:', cloudVault)
    console.log('[JarvisCloud] Vault habits count:', cloudVault.habits?.length || 0)
    
    // Three-way merge: base (cloud) + local + remote (cloud)
    const merged = mergeVaults(cloudVault, local, cloudVault)
    
    applyJarvisVaultLocally(merged)
    return merged
  } catch (e) {
    console.error('[JarvisCloud] Download failed:', e)
    const backup = restoreBackup()
    if (backup) {
      console.log('[JarvisCloud] Restored from backup after error')
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
    console.log('[JarvisCloud] Not connected to cloud, skipping auto-sync')
    return
  }
  
  // Renovar token se expirado
  if (isTokenExpired()) {
    console.log('[JarvisCloud] Token expired, refreshing...')
    await refreshAccessToken()
  }
  
  const lastSync = getLocalLastSync()
  const now = Date.now()
  const oneHour = 60 * 60 * 1000
  
  // Auto-sync apenas se passou mais de 1 hora
  if (now - lastSync < oneHour) {
    console.log('[JarvisCloud] Auto-sync skipped (synced recently)')
    return
  }
  
  try {
    console.log('[JarvisCloud] Starting auto-sync...')
    await downloadJarvisVault()
    console.log('[JarvisCloud] Auto-sync complete')
  } catch (e) {
    console.error('[JarvisCloud] Auto-sync failed:', e)
    // Não lançar erro em auto-sync
  }
}

export async function syncJarvisAfterLogin(role: 'pc' | 'mobile'): Promise<string> {
  try {
    if (role === 'mobile') {
      const vault = await downloadJarvisVault()
      const count = Object.values(vault.keys || {}).filter(value => value && typeof value === 'string' && value.trim()).length
      return `Chaves e memórias baixadas (${count} provedor(es), ${vault.memories?.length || 0} memórias). Rotação por vírgula igual ao PC.`
    }
    const collected = await collectJarvisVaultFromThisDevice()
    if (!keysHaveValue(collected.keys)) {
      return 'Conta conectada. Este PC ainda não tem chaves para enviar.'
    }
    const vault = await pushJarvisVault(Promise.resolve(collected))
    return `Jarvis do PC enviado à nuvem (${Object.values(vault.keys || {}).filter(value => value && typeof value === 'string' && value.trim()).length} provedor(es)). No celular, entre com a mesma conta.`
  } catch (error) {
    console.error('[JarvisCloud] Erro na sincronização:', error)
    if (error instanceof Error) {
      throw error
    }
    throw new Error('Erro desconhecido na sincronização.')
  }
}

