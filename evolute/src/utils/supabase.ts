import { ApiSettings } from '../types';

export interface CloudSnapshot {
  data: Record<string, unknown>;
  revision: number;
}

interface AuthSession {
  access_token: string;
  refresh_token: string;
}

function baseUrl(settings: ApiSettings): string {
  return String(settings.supabaseUrl || '').trim().replace(/\/$/, '');
}

function headers(settings: ApiSettings, token = settings.supabaseAccessToken): HeadersInit {
  const key = String(settings.supabasePublishableKey || '').trim();
  return {
    'Content-Type': 'application/json',
    apikey: key,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export function isSupabaseConfigured(settings: ApiSettings): boolean {
  return Boolean(baseUrl(settings) && settings.supabasePublishableKey && settings.supabaseAccessToken);
}

async function authenticate(settings: ApiSettings, email: string, password: string, signup = false): Promise<ApiSettings> {
  const url = baseUrl(settings);
  const key = String(settings.supabasePublishableKey || '').trim();
  if (!url || !key) throw new Error('Informe a URL e a chave publicável do projeto Supabase.');
  const response = await fetch(`${url}/auth/v1/${signup ? 'signup' : 'token?grant_type=password'}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', apikey: key },
    body: JSON.stringify({ email: email.trim(), password }),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.msg || payload.error_description || 'Não foi possível autenticar no Supabase.');
  const session: AuthSession | undefined = payload.session || payload;
  if (!session?.access_token) {
    throw new Error('Conta criada. Confirme o e-mail e entre para ativar a sincronização.');
  }
  return { ...settings, supabaseAccessToken: session.access_token, supabaseRefreshToken: session.refresh_token || '' };
}

export const signInToSupabase = (settings: ApiSettings, email: string, password: string) => authenticate(settings, email, password);
export const signUpToSupabase = (settings: ApiSettings, email: string, password: string) => authenticate(settings, email, password, true);

export async function refreshAccessToken(settings: ApiSettings): Promise<ApiSettings | null> {
  const refresh = settings.supabaseRefreshToken;
  const url = baseUrl(settings);
  const key = String(settings.supabasePublishableKey || '').trim();
  if (!refresh || !url || !key) return null;

  try {
    const response = await fetch(`${url}/auth/v1/token?grant_type=refresh_token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', apikey: key },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload.access_token) return null;

    const nextSettings: ApiSettings = {
      ...settings,
      supabaseAccessToken: payload.access_token,
      supabaseRefreshToken: payload.refresh_token || refresh,
    };
    try {
      const stored = JSON.parse(localStorage.getItem('lifeos_api_settings') || '{}');
      localStorage.setItem('lifeos_api_settings', JSON.stringify({
        ...stored,
        supabaseAccessToken: payload.access_token,
        supabaseRefreshToken: payload.refresh_token || refresh,
      }));
    } catch { /* ignore */ }
    return nextSettings;
  } catch {
    return null;
  }
}

export async function pullSupabaseSnapshot(settings: ApiSettings): Promise<CloudSnapshot | null> {
  if (!isSupabaseConfigured(settings)) return null;
  let activeSettings = settings;
  let response = await fetch(`${baseUrl(activeSettings)}/rest/v1/evolute_snapshots?select=data,revision`, {
    headers: headers(activeSettings),
  });

  if (response.status === 401 && activeSettings.supabaseRefreshToken) {
    const refreshed = await refreshAccessToken(activeSettings);
    if (refreshed) {
      activeSettings = refreshed;
      response = await fetch(`${baseUrl(activeSettings)}/rest/v1/evolute_snapshots?select=data,revision`, {
        headers: headers(activeSettings),
      });
    }
  }

  if (!response.ok) throw new Error('Não foi possível ler a nuvem do Evolução.');
  const rows = await response.json();
  const row = Array.isArray(rows) ? rows[0] : null;
  return row && typeof row.data === 'object'
    ? { data: row.data, revision: Number(row.revision || 0) }
    : null;
}

export async function pushSupabaseSnapshot(settings: ApiSettings, data: Record<string, unknown>, baseRevision: number): Promise<{ revision: number; conflict: boolean }> {
  if (!isSupabaseConfigured(settings)) throw new Error('Supabase não está conectado.');
  let activeSettings = settings;
  let response = await fetch(`${baseUrl(activeSettings)}/rest/v1/rpc/sync_evolute_snapshot`, {
    method: 'POST',
    headers: headers(activeSettings),
    body: JSON.stringify({ p_data: data, p_base_revision: baseRevision }),
  });

  if (response.status === 401 && activeSettings.supabaseRefreshToken) {
    const refreshed = await refreshAccessToken(activeSettings);
    if (refreshed) {
      activeSettings = refreshed;
      response = await fetch(`${baseUrl(activeSettings)}/rest/v1/rpc/sync_evolute_snapshot`, {
        method: 'POST',
        headers: headers(activeSettings),
        body: JSON.stringify({ p_data: data, p_base_revision: baseRevision }),
      });
    }
  }

  if (!response.ok) throw new Error('Não foi possível salvar a evolução na nuvem.');
  const rows = await response.json();
  const row = Array.isArray(rows) ? rows[0] : rows;
  return { revision: Number(row?.revision || baseRevision), conflict: Boolean(row?.conflict) };
}
