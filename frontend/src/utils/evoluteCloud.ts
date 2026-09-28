/** Shared Evolução sync settings — same localStorage key as the Life OS app. */
export const EVOLUTE_SETTINGS_KEY = 'lifeos_api_settings'

export const DEFAULT_SUPABASE_URL = 'https://rhfqrgptnpviplxplcbo.supabase.co'
export const DEFAULT_SUPABASE_KEY = 'sb_publishable__dLqOSYJpM5WfGArFbVyYw_OFdak85E'

export type EvoluteSettings = {
  syncEndpoint?: string
  syncToken?: string
  supabaseUrl?: string
  supabasePublishableKey?: string
  supabaseAccessToken?: string
  supabaseRefreshToken?: string
  supabaseExpiresAt?: number  // Timestamp de expiração do access token
  userEmail?: string  // Email do usuário para persistência
}

export function getEvoluteSettings(): EvoluteSettings {
  try {
    const raw = localStorage.getItem(EVOLUTE_SETTINGS_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

export function saveEvoluteSettings(patch: Partial<EvoluteSettings>): EvoluteSettings {
  const current = getEvoluteSettings()
  const next = { ...current, ...patch }
  localStorage.setItem(EVOLUTE_SETTINGS_KEY, JSON.stringify(next))
  return next
}

export function isEvoluteCloudConnected(settings = getEvoluteSettings()): boolean {
  return Boolean(
    settings.supabaseUrl &&
    settings.supabasePublishableKey &&
    settings.supabaseAccessToken
  )
}

async function supabaseAuth(
  settings: EvoluteSettings,
  email: string,
  password: string,
  signup: boolean
): Promise<EvoluteSettings> {
  const url = String(settings.supabaseUrl || DEFAULT_SUPABASE_URL).trim().replace(/\/$/, '')
  const key = String(settings.supabasePublishableKey || DEFAULT_SUPABASE_KEY).trim()
  if (!url || !key) throw new Error('Supabase não configurado.')

  console.log(`[SupabaseAuth] ${signup ? 'Criando conta' : 'Entrando'} com e-mail: ${email.trim()}`)

  const response = await fetch(`${url}/auth/v1/${signup ? 'signup' : 'token?grant_type=password'}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', apikey: key },
    body: JSON.stringify({ email: email.trim(), password }),
  })
  const payload = await response.json().catch(() => ({}))
  console.log(`[SupabaseAuth] Response status: ${response.status}`, payload)

  if (!response.ok) {
    const errorMsg = payload.msg || payload.error_description || payload.error || 'Falha ao autenticar no Supabase.'
    console.error(`[SupabaseAuth] Erro: ${errorMsg}`, payload)
    throw new Error(`${signup ? 'Erro ao criar conta' : 'Erro ao entrar'}: ${errorMsg}`)
  }
  const session = payload.session || payload
  if (!session?.access_token) {
    console.error(`[SupabaseAuth] Sem access_token. Payload:`, payload)
    if (signup) {
      // Signup sem access_token pode significar que precisa confirmação de email
      // ou que o Supabase está configurado para não retornar session no signup
      if (payload.weak_password) {
        throw new Error('Senha muito fraca. Use uma senha mais forte.')
      }
      if (payload.email_already_exists) {
        throw new Error('Este e-mail já está cadastrado. Tente entrar com sua senha.')
      }
      throw new Error('Conta criada, mas o Supabase não retornou sessão. Entre com sua senha para ativar a sincronização.')
    }
    throw new Error('Falha na autenticação: token de acesso não recebido.')
  }
  console.log(`[SupabaseAuth] Sucesso. Token obtido.`)
  // Calcula expiração (tokens do Supabase expiram em 1 hora por padrão)
  const expiresAt = Date.now() + (session.expires_in || 3600) * 1000
  return saveEvoluteSettings({
    supabaseUrl: url,
    supabasePublishableKey: key,
    supabaseAccessToken: session.access_token,
    supabaseRefreshToken: session.refresh_token || '',
    supabaseExpiresAt: expiresAt,
    userEmail: email.trim(),
  })
}

export const signInEvoluteCloud = (email: string, password: string, settings = getEvoluteSettings()) =>
  supabaseAuth(settings, email, password, false)

export const signUpEvoluteCloud = (email: string, password: string, settings = getEvoluteSettings()) =>
  supabaseAuth(settings, email, password, true)

// Verifica se o token está expirado ou prestes a expirar (5 minutos de margem)
export function isTokenExpired(settings = getEvoluteSettings()): boolean {
  if (!settings.supabaseExpiresAt) return true
  const now = Date.now()
  const expiresAt = settings.supabaseExpiresAt
  // Considera expirado se faltar menos de 5 minutos
  return now >= (expiresAt - 5 * 60 * 1000)
}

// Renova o token usando o refresh token
export async function refreshAccessToken(settings = getEvoluteSettings()): Promise<EvoluteSettings> {
  if (!settings.supabaseRefreshToken || !settings.supabaseUrl || !settings.supabasePublishableKey) {
    throw new Error('Refresh token não disponível. Faça login novamente.')
  }

  const url = String(settings.supabaseUrl).trim().replace(/\/$/, '')
  const key = String(settings.supabasePublishableKey).trim()

  console.log('[SupabaseAuth] Renovando access token...')

  const response = await fetch(`${url}/auth/v1/token?grant_type=refresh_token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', apikey: key },
    body: JSON.stringify({ refresh_token: settings.supabaseRefreshToken }),
  })

  const payload = await response.json().catch(() => ({}))
  console.log('[SupabaseAuth] Refresh response status:', response.status)

  if (!response.ok || !payload.access_token) {
    console.error('[SupabaseAuth] Falha ao renovar token:', payload)
    // Limpa tokens expirados
    saveEvoluteSettings({
      supabaseAccessToken: '',
      supabaseRefreshToken: '',
      supabaseExpiresAt: 0,
    })
    throw new Error('Sessão expirada. Faça login novamente.')
  }

  const expiresAt = Date.now() + (payload.expires_in || 3600) * 1000
  console.log('[SupabaseAuth] Token renovado com sucesso.')

  return saveEvoluteSettings({
    supabaseAccessToken: payload.access_token,
    supabaseRefreshToken: payload.refresh_token || settings.supabaseRefreshToken,
    supabaseExpiresAt: expiresAt,
  })
}

// Tenta fazer login automático se houver credenciais salvas
export async function autoSignIn(): Promise<{ success: boolean; error?: string }> {
  const settings = getEvoluteSettings()
  if (!settings.userEmail || !settings.supabaseRefreshToken) {
    return { success: false, error: 'Nenhuma sessão salva encontrada.' }
  }

  try {
    // Se o access token ainda é válido, usa ele
    if (!isTokenExpired(settings) && settings.supabaseAccessToken) {
      console.log('[SupabaseAuth] Sessão válida encontrada.')
      return { success: true }
    }

    // Tenta renovar o token
    await refreshAccessToken(settings)
    console.log('[SupabaseAuth] Login automático realizado com sucesso.')
    return { success: true }
  } catch (error) {
    console.error('[SupabaseAuth] Falha no login automático:', error)
    return { success: false, error: error instanceof Error ? error.message : 'Falha no login automático.' }
  }
}

// Logout - limpa a sessão
export function signOutEvoluteCloud(): void {
  saveEvoluteSettings({
    supabaseAccessToken: '',
    supabaseRefreshToken: '',
    supabaseExpiresAt: 0,
    userEmail: '',
  })
  console.log('[SupabaseAuth] Logout realizado.')
}
