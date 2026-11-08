export const JARVIS_VAULT_KEY = '__jarvis_vault'
export const JARVIS_MEMORIES_KEY = 'jarvis-cloud-memories'
export const JARVIS_PROFILE_KEY = 'jarvis-cloud-profile'
/** Cópia local do perfil do agente (nome, estilo, frase de ativação) usada pelo chat direto. */
export const JARVIS_AGENT_PROFILE_KEY = 'jarvis-agent-profile'

export type AgentProfile = {
  name: string
  style: string
  wake_phrase: string
  wake_phrase_custom: boolean
}

export const DEFAULT_AGENT_NAME = 'Assistente'
export const DEFAULT_AGENT_STYLE = 'Neutro, cordial e conciso. Responda em português do Brasil, com frases curtas e diretas. Trate o usuário pelo nome quando souber, sem títulos ou apelidos.'

export function deriveWakePhrase(name: string): string {
  return `ei ${name}`.toLowerCase().split(/\s+/).filter(Boolean).join(' ')
}

export const DEFAULT_AGENT_PROFILE: AgentProfile = {
  name: DEFAULT_AGENT_NAME,
  style: DEFAULT_AGENT_STYLE,
  wake_phrase: deriveWakePhrase(DEFAULT_AGENT_NAME),
  wake_phrase_custom: false,
}

export function getStoredAgentProfile(): AgentProfile {
  if (typeof localStorage === 'undefined') return DEFAULT_AGENT_PROFILE
  try {
    const raw = JSON.parse(localStorage.getItem(JARVIS_AGENT_PROFILE_KEY) || 'null')
    const name = typeof raw?.name === 'string' ? raw.name.trim().slice(0, 40) : ''
    if (!name) return DEFAULT_AGENT_PROFILE
    const style = typeof raw.style === 'string' && raw.style.trim() ? raw.style.trim().slice(0, 2000) : DEFAULT_AGENT_STYLE
    const custom = typeof raw.wake_phrase === 'string' && Boolean(raw.wake_phrase.trim()) && raw.wake_phrase_custom === true
    return { name, style, wake_phrase: custom ? raw.wake_phrase.trim() : deriveWakePhrase(name), wake_phrase_custom: custom }
  } catch {
    return DEFAULT_AGENT_PROFILE
  }
}

export function setStoredAgentProfile(profile: AgentProfile): void {
  if (typeof localStorage === 'undefined') return
  localStorage.setItem(JARVIS_AGENT_PROFILE_KEY, JSON.stringify(profile))
}

export function getJarvisSystemPrompt(): string {
  const profile = typeof localStorage === 'undefined' ? '' : localStorage.getItem(JARVIS_PROFILE_KEY) || ''
  const agent = getStoredAgentProfile()
  let memories: string[] = []
  try {
    memories = JSON.parse(localStorage.getItem(JARVIS_MEMORIES_KEY) || '[]')
  } catch {
    memories = []
  }
  const parts = [
    `Você é ${agent.name}, assistente pessoal. Responda sempre em português do Brasil, de forma clara e direta.`,
    `Estilo: ${agent.style}`,
    profile.trim() ? `Perfil do usuário:\n${profile.trim().slice(0, 4000)}` : '',
    memories.length ? `Memórias persistentes:\n${memories.slice(0, 40).map(item => `- ${item}`).join('\n')}` : '',
  ]
  return parts.filter(Boolean).join('\n\n')
}
