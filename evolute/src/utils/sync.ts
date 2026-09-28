import { isSupabaseConfigured, pullSupabaseSnapshot, pushSupabaseSnapshot } from './supabase';

const SYNC_TIMESTAMP_KEY = 'lifeos_last_sync_timestamp';
const CLOUD_REVISION_KEY = 'lifeos_cloud_revision';
const DEVICE_PRIVATE_KEYS = new Set(['lifeos_api_settings', SYNC_TIMESTAMP_KEY, CLOUD_REVISION_KEY]);

interface SyncConnection {
  endpoint: string;
  token: string;
}

function connection(): SyncConnection {
  try {
    const raw = localStorage.getItem('lifeos_api_settings');
    const settings = raw ? JSON.parse(raw) : {};
    const endpoint = String(settings.syncEndpoint || '').trim().replace(/\/$/, '');
    return { endpoint, token: String(settings.syncToken || '').trim() };
  } catch {
    return { endpoint: '', token: '' };
  }
}

function syncUrl(): string {
  const { endpoint } = connection();
  return endpoint ? `${endpoint}/api/evolute/sync` : '/api/sync';
}

function syncHeaders(): HeadersInit {
  const { token } = connection();
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {})
  };
}

function settings() {
  try {
    return JSON.parse(localStorage.getItem('lifeos_api_settings') || '{}');
  } catch {
    return {};
  }
}

export interface SyncResult {
  success: boolean;
  message: string;
  updatedAt?: number;
}

/**
 * Fires a synthetic event on window so React components can react to
 * localStorage changes made by sync (cross-tab storage events don't fire
 * for same-tab writes).
 */
function dispatchStorageRefreshEvent(): void {
  try {
    window.dispatchEvent(new Event('jarvis-sync-applied'));
  } catch { /* ignore */ }
}

/**
 * Applies a parsed vault object to localStorage, writing ALL known Life OS keys.
 */
function applyVaultToLocalStorage(vault: Record<string, any>): void {
  // Versioned arrays
  if (Array.isArray(vault.habits)) {
    const habitsData = vault.habits.map((h: any) => h.data || h).filter(Boolean);
    localStorage.setItem('lifeos_habits', JSON.stringify(habitsData));
    localStorage.setItem('jarvis-habits', JSON.stringify(habitsData));
  }
  if (Array.isArray(vault.training)) {
    const trainingData = vault.training.map((t: any) => t.data || t).filter(Boolean);
    localStorage.setItem('lifeos_workouts', JSON.stringify(trainingData));
  }

  // Simple arrays
  if (Array.isArray(vault.studyLogs)) localStorage.setItem('lifeos_study_logs', JSON.stringify(vault.studyLogs));
  if (Array.isArray(vault.viceLogs)) localStorage.setItem('lifeos_vice_logs', JSON.stringify(vault.viceLogs));
  if (Array.isArray(vault.readingLogs)) localStorage.setItem('lifeos_reading_logs', JSON.stringify(vault.readingLogs));
  if (Array.isArray(vault.cognitive)) localStorage.setItem('lifeos_cognitive', JSON.stringify(vault.cognitive));
  if (Array.isArray(vault.subjects)) localStorage.setItem('lifeos_subjects', JSON.stringify(vault.subjects));
  if (Array.isArray(vault.summaries)) localStorage.setItem('lifeos_summaries', JSON.stringify(vault.summaries));
  if (Array.isArray(vault.flashcards)) localStorage.setItem('lifeos_flashcards', JSON.stringify(vault.flashcards));

  // Per-day log maps
  if (vault.habitLogs && typeof vault.habitLogs === 'object') {
    for (const [k, v] of Object.entries(vault.habitLogs)) {
      try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* ignore */ }
    }
  }
  if (vault.mentalLogs && typeof vault.mentalLogs === 'object') {
    for (const [k, v] of Object.entries(vault.mentalLogs)) {
      try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* ignore */ }
    }
  }
  if (vault.waterLogs && typeof vault.waterLogs === 'object') {
    for (const [k, v] of Object.entries(vault.waterLogs)) {
      try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* ignore */ }
    }
  }

  // extraData: books, quotes, vices, simulations, workout_split, weight_logs, body_photos,
  //            victories per day, mental per day, water per day, infinite_notes, etc.
  if (vault.extraData && typeof vault.extraData === 'object') {
    for (const [k, v] of Object.entries(vault.extraData)) {
      try {
        if (typeof v === 'string') {
          localStorage.setItem(k, v);
        } else if (v !== null && v !== undefined) {
          localStorage.setItem(k, JSON.stringify(v));
        }
      } catch { /* ignore */ }
    }
  }
}

/**
 * Puxa dados atualizados do servidor caso a versão no servidor seja mais recente.
 * Usado na inicialização do Life OS ou ao recarregar a tela.
 */
export async function pullLatestFromServer(): Promise<boolean> {
  try {
    const currentSettings = settings();
    if (isSupabaseConfigured(currentSettings)) {
      const snapshot = await pullSupabaseSnapshot(currentSettings);
      if (!snapshot) return false;
      const localRevision = Number(localStorage.getItem(CLOUD_REVISION_KEY) || '0');
      if (snapshot.revision <= localRevision) return false;

      // Known keys that must strictly be arrays (never plain objects)
      const arrayKeys = new Set([
        'lifeos_habits', 'lifeos_workouts', 'lifeos_study_logs', 'lifeos_reading_logs',
        'lifeos_vice_logs', 'lifeos_cognitive', 'lifeos_subjects', 'lifeos_summaries',
        'lifeos_flashcards', 'lifeos_simulations', 'lifeos_weight_logs', 'lifeos_body_photos',
        'lifeos_books', 'lifeos_quotes', 'lifeos_vices', 'lifeos_workout_split'
      ]);

      // 1. Unpack Jarvis vault (primary source – most complete)
      const rawVault = snapshot.data.__jarvis_vault || snapshot.data.jarvis_vault;
      if (rawVault && typeof rawVault === 'object') {
        applyVaultToLocalStorage(rawVault as Record<string, any>);
      }

      // 2. Apply remaining top-level snapshot keys (flat fallback keys)
      for (const [k, v] of Object.entries(snapshot.data)) {
        if (DEVICE_PRIVATE_KEYS.has(k) || k === '__jarvis_vault' || k === 'jarvis_vault') continue;
        if (arrayKeys.has(k)) {
          if (Array.isArray(v)) {
            localStorage.setItem(k, JSON.stringify(v));
          } else if (typeof v === 'string') {
            try {
              const p = JSON.parse(v);
              if (Array.isArray(p)) localStorage.setItem(k, v);
            } catch { /* ignore corrupted */ }
          }
          // If v is a plain object {}, do NOT overwrite the local array!
        } else {
          localStorage.setItem(k, typeof v === 'string' ? v : JSON.stringify(v));
        }
      }

      localStorage.setItem(CLOUD_REVISION_KEY, String(snapshot.revision));
      dispatchStorageRefreshEvent();
      return true;
    }

    // Fallback: local network server sync
    const res = await fetch(syncUrl(), { headers: syncHeaders() });
    if (!res.ok) return false;
    const body = await res.json();
    if (!body || !body.data) return false;

    const serverTime = body.updatedAt || 0;
    const localTime = Number(localStorage.getItem(SYNC_TIMESTAMP_KEY) || '0');

    if (serverTime > localTime) {
      const serverData = body.data;
      for (const [k, v] of Object.entries(serverData)) {
        if (DEVICE_PRIVATE_KEYS.has(k)) continue;
        if (typeof v === 'string') {
          localStorage.setItem(k, v);
        } else {
          localStorage.setItem(k, JSON.stringify(v));
        }
      }
      localStorage.setItem(SYNC_TIMESTAMP_KEY, String(serverTime));
      dispatchStorageRefreshEvent();
      return true;
    }
    return false;
  } catch {
    // Modo offline resiliente: continua com os dados locais
    return false;
  }
}

let syncDebounceTimer: any = null;

/**
 * Dispara envio dos dados locais para o servidor com debounce de 1,2s.
 * Evita chamadas excessivas durante digitação rápida.
 */
export function pushToServerDebounced(): void {
  if (syncDebounceTimer) clearTimeout(syncDebounceTimer);
  syncDebounceTimer = setTimeout(() => {
    pushAllToServer();
  }, 1200);
}

/**
 * Envia todos os dados armazenados localmente para o backend salvar.
 */
export async function pushAllToServer(): Promise<boolean> {
  try {
    const payload: Record<string, any> = {};
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith('lifeos_') && !DEVICE_PRIVATE_KEYS.has(key)) {
        const val = localStorage.getItem(key);
        if (val !== null) {
          try {
            payload[key] = JSON.parse(val);
          } catch {
            payload[key] = val;
          }
        }
      }
    }

    const baseUpdatedAt = Number(localStorage.getItem(SYNC_TIMESTAMP_KEY) || '0');
    const now = Date.now();
    localStorage.setItem(SYNC_TIMESTAMP_KEY, String(now));

    const currentSettings = settings();
    if (isSupabaseConfigured(currentSettings)) {
      const existing = await pullSupabaseSnapshot(currentSettings);
      const mergedPayload = { ...(existing?.data || {}), ...payload };
      const result = await pushSupabaseSnapshot(
        currentSettings,
        mergedPayload,
        Number(localStorage.getItem(CLOUD_REVISION_KEY) || '0'),
      );
      if (result.conflict) {
        localStorage.setItem(`lifeos_sync_conflict_${Date.now()}`, JSON.stringify(payload));
        return false;
      }
      localStorage.setItem(CLOUD_REVISION_KEY, String(result.revision));
      return true;
    }

    const res = await fetch('/api/sync', {
      method: 'POST',
      headers: syncHeaders(),
      body: JSON.stringify({ data: payload, updatedAt: now, baseUpdatedAt })
    });
    if (res.ok) return true;

    // Conflitos nunca descartam a cópia local silenciosamente.
    if (res.status === 409) {
      localStorage.setItem(`lifeos_sync_conflict_${Date.now()}`, JSON.stringify(payload));
    }
    return false;
  } catch {
    // Falha silenciosa em caso de ausência de rede (offline-first)
    return false;
  }
}
