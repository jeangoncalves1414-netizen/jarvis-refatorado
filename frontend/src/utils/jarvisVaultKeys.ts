export const JARVIS_VAULT_KEY = '__jarvis_vault'
export const JARVIS_MEMORIES_KEY = 'jarvis-cloud-memories'
export const JARVIS_PROFILE_KEY = 'jarvis-cloud-profile'

export function getJarvisSystemPrompt(): string {
  const profile = typeof localStorage === 'undefined' ? '' : localStorage.getItem(JARVIS_PROFILE_KEY) || ''
  let memories: string[] = []
  try {
    memories = JSON.parse(localStorage.getItem(JARVIS_MEMORIES_KEY) || '[]')
  } catch {
    memories = []
  }
  const parts = [
    'Você é o Jarvis, assistente pessoal. Responda sempre em português do Brasil, de forma clara e direta.',
    profile.trim() ? `Perfil do usuário:\n${profile.trim().slice(0, 4000)}` : '',
    memories.length ? `Memórias persistentes:\n${memories.slice(0, 40).map(item => `- ${item}`).join('\n')}` : '',
  ]
  return parts.filter(Boolean).join('\n\n')
}

