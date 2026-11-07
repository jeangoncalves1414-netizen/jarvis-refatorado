/**
 * useDirectChat — Mobile-only chat hook with full Desktop parity
 * Synchronized with PC settings: Oxxy, Groq, Gemini, Fish keys and Oxxy per-capability models.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import type { ChatMessage, ChatSession } from '../types'
import { getJarvisSystemPrompt } from '../utils/jarvisVaultKeys'

const SESSIONS_KEY = 'jarvis-direct-sessions'
const HISTORY_PREFIX = 'jarvis-direct-history-'
const ACTIVE_SESSION_KEY = 'jarvis-react-session'

const MOBILE_KEYS_STORAGE = 'jarvis-mobile-api-keys'
const MOBILE_PROVIDER_STORAGE = 'jarvis-mobile-provider'
const MOBILE_OXXY_MODELS_STORAGE = 'jarvis-mobile-oxyy-models'

export type DirectChatProvider = 'gemini' | 'groq' | 'oxyy'

// ── Mobile defaults ─────────────────────────────────────────────────────────
// Keys are deliberately empty. A mobile build must never ship the PC owner's
// provider credentials; the user can configure their own key in Settings.
export const DEFAULT_MOBILE_KEYS = {
  oxyy: '',
  groq: '',
  gemini: '',
  fish: '',
}

export const DEFAULT_OXXY_MODELS = {
  chat: 'codestral-2508',
  tts: 'tts-1-hd',
  tts_voice: 'alloy',
  stt: 'whisper-1',
  image: 'dall-e-3',
  video: 'veo-3',
  embedding: 'gemini-embedding-001',
}

// ── Getters / Setters ────────────────────────────────────────────────────────
export function getMobileApiKeys(): typeof DEFAULT_MOBILE_KEYS {
  const result = { ...DEFAULT_MOBILE_KEYS }
  try {
    const saved = localStorage.getItem(MOBILE_KEYS_STORAGE)
    if (saved) {
      const parsed = JSON.parse(saved)
      ;(Object.keys(DEFAULT_MOBILE_KEYS) as Array<keyof typeof DEFAULT_MOBILE_KEYS>).forEach(k => {
        if (parsed[k] && typeof parsed[k] === 'string' && parsed[k].trim().length > 0) {
          result[k] = parsed[k].trim()
        }
      })
    }
  } catch {}
  return result
}

export function setMobileApiKeys(keys: Record<string, string>) {
  localStorage.setItem(MOBILE_KEYS_STORAGE, JSON.stringify(keys))
}

export function getMobileProvider(): DirectChatProvider {
  const saved = localStorage.getItem(MOBILE_PROVIDER_STORAGE) as DirectChatProvider | null
  if (saved && (saved === 'gemini' || saved === 'groq' || saved === 'oxyy')) {
    return saved
  }
  const keys = getMobileApiKeys()
  if (keys.gemini && !keys.oxyy && !keys.groq) return 'gemini'
  if (keys.groq && !keys.oxyy) return 'groq'
  return 'oxyy'
}

export function setMobileProvider(v: DirectChatProvider) {
  localStorage.setItem(MOBILE_PROVIDER_STORAGE, v)
}

export function getMobileOxyyModels(): typeof DEFAULT_OXXY_MODELS {
  const result = { ...DEFAULT_OXXY_MODELS }
  try {
    const saved = localStorage.getItem(MOBILE_OXXY_MODELS_STORAGE)
    if (saved) {
      const parsed = JSON.parse(saved)
      ;(Object.keys(DEFAULT_OXXY_MODELS) as Array<keyof typeof DEFAULT_OXXY_MODELS>).forEach(k => {
        if (parsed[k] && typeof parsed[k] === 'string' && parsed[k].trim().length > 0) {
          result[k] = parsed[k].trim()
        }
      })
    }
  } catch {}
  return result
}

export function setMobileOxyyModels(models: Partial<typeof DEFAULT_OXXY_MODELS>) {
  const current = getMobileOxyyModels()
  localStorage.setItem(MOBILE_OXXY_MODELS_STORAGE, JSON.stringify({ ...current, ...models }))
}

// Helper to resolve an active key with rotation for multi-key strings (comma-separated)
let rotationIndex = 0
export function resolveActiveKey(provider: DirectChatProvider): string {
  const keys = getMobileApiKeys()
  const raw = keys[provider] || ''
  if (!raw) return ''
  const parts = raw.split(',').map(k => k.trim()).filter(Boolean)
  if (!parts.length) return ''
  const key = parts[rotationIndex % parts.length]
  rotationIndex++
  return key
}

// Helper to count available keys for a provider
export function countKeys(provider: DirectChatProvider): number {
  const keys = getMobileApiKeys()
  const raw = keys[provider] || ''
  if (!raw) return 0
  return raw.split(',').map(k => k.trim()).filter(Boolean).length
}

export function getMobileModelForCapability(capability: 'chat' | 'tts' | 'stt' | 'image' | 'video' | 'embedding' = 'chat'): string {
  const provider = getMobileProvider()
  console.log('[MobileModel] Provider:', provider, 'Capability:', capability)
  console.log('[MobileModel] All localStorage keys:', Object.keys(localStorage).filter(k => k.includes('jarvis-mobile')))

  if (provider === 'oxyy') {
    const oxyyModels = getMobileOxyyModels()
    const model = oxyyModels[capability] || DEFAULT_OXXY_MODELS[capability] || 'codestral-2508'
    console.log('[MobileModel] Using Oxyy model:', model)
    return model
  }

  // Check if provider-specific model is stored in localStorage (from sync)
  if (provider === 'groq') {
    const storedModel = localStorage.getItem('jarvis-mobile-groq-model')
    if (storedModel && storedModel.trim() && !storedModel.includes('gpt-oss')) {
      return storedModel
    }
    return 'llama-3.3-70b-versatile'
  }

  if (provider === 'gemini') {
    const storedModel = localStorage.getItem('jarvis-mobile-gemini-model')
    console.log('[MobileModel] Stored Gemini model from localStorage:', storedModel)
    if (storedModel && storedModel.trim()) {
      console.log('[MobileModel] Using synced Gemini model:', storedModel)
      return storedModel
    }
    console.log('[MobileModel] No synced Gemini model found, using default: gemini-2.5-flash')
    return 'gemini-2.5-flash'
  }

  if (provider === 'oxyy') {
    const storedModel = localStorage.getItem('jarvis-mobile-oxyy-model')
    console.log('[MobileModel] Stored Oxyy model from localStorage:', storedModel)
    if (storedModel && storedModel.trim()) {
      console.log('[MobileModel] Using synced Oxyy model:', storedModel)
      return storedModel
    }
    console.log('[MobileModel] No synced Oxyy model found, using default: gpt-4o-mini')
    return 'gpt-4o-mini'
  }

  console.log('[MobileModel] Unknown provider, using fallback model: openai/gpt-oss-120b')
  return 'openai/gpt-oss-120b'
}

export function getMobileGroqModel(): string {
  const model = localStorage.getItem('jarvis-mobile-groq-model')
  if (model && !model.includes('gpt-oss') && model.trim()) return model
  return 'llama-3.3-70b-versatile'
}

export function setMobileGroqModel(model: string): void {
  localStorage.setItem('jarvis-mobile-groq-model', model)
}

export function getMobileGeminiModel(): string {
  return localStorage.getItem('jarvis-mobile-gemini-model') || 'gemini-2.5-flash'
}

export function setMobileGeminiModel(model: string): void {
  localStorage.setItem('jarvis-mobile-gemini-model', model)
}

// ── Session Storage ──────────────────────────────────────────────────────────
function loadSessions(): ChatSession[] {
  try { return JSON.parse(localStorage.getItem(SESSIONS_KEY) || '[]') } catch { return [] }
}
function saveSessions(sessions: ChatSession[]) {
  try { localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions)) } catch {}
}
function loadHistory(id: string): ChatMessage[] {
  try { return JSON.parse(localStorage.getItem(HISTORY_PREFIX + id) || '[]') } catch { return [] }
}
function saveHistory(id: string, history: ChatMessage[]) {
  try { localStorage.setItem(HISTORY_PREFIX + id, JSON.stringify(history)) } catch {}
}

// ── Native Android Streaming Bridge ──────────────────────────────────────────
type StreamCallbacks = {
  onChunk: (chunk: string) => void
  onDone: () => void
  onError: (err: Error) => void
}

const activeNativeStreams = new Map<string, StreamCallbacks>()

if (typeof window !== 'undefined') {
  ;(window as any).__onNativeStreamChunk = (id: string, chunk: string) => {
    const cb = activeNativeStreams.get(id)
    if (cb) cb.onChunk(chunk)
  }
  ;(window as any).__onNativeStreamDone = (id: string) => {
    const cb = activeNativeStreams.get(id)
    if (cb) {
      cb.onDone()
      activeNativeStreams.delete(id)
    }
  }
  ;(window as any).__onNativeStreamError = (id: string, errorMsg: string) => {
    const cb = activeNativeStreams.get(id)
    if (cb) {
      cb.onError(new Error(errorMsg))
      activeNativeStreams.delete(id)
    }
  }
}

export function hasNativePostStream(): boolean {
  return typeof (window as any)?.Android?.nativePostStream === 'function'
}

export async function nativeDirectPost(url: string, headers: Record<string, string>, body: string): Promise<string> {
  if (hasNativePostStream()) {
    return new Promise<string>((resolve, reject) => {
      const reqId = 'post_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8)
      let full = ''
      activeNativeStreams.set(reqId, {
        onChunk: (chunk: string) => { full += chunk + '\n' },
        onDone: () => resolve(full),
        onError: (err: Error) => reject(err),
      })
      ;(window as any).Android.nativePostStream(reqId, url, JSON.stringify(headers), body)
    })
  }
  const res = await fetch(url, { method: 'POST', headers, body })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err?.error?.message || `HTTP ${res.status}`)
  }
  return res.text()
}

// ── Provider Streaming ────────────────────────────────────────────────────────
async function streamGemini(
  apiKey: string, model: string, history: ChatMessage[],
  onChunk: (text: string) => void, signal: AbortSignal,
): Promise<string> {
  // 1. Filtrar mensagens vazias e pegar janela recente (evita overflow de contexto/token)
  const clean = history.filter(m => m.content && m.content.trim().length > 0)
  const windowed = clean.slice(-20)

  // 2. Garantir estritamente alternância de turnos user/model para a API do Gemini
  const contents: { role: 'user' | 'model'; parts: { text: string }[] }[] = []
  for (const m of windowed) {
    const role = m.role === 'user' ? 'user' : 'model'
    if (contents.length === 0) {
      if (role !== 'user') continue // Primeiro turno deve ser sempre user
      contents.push({ role, parts: [{ text: m.content.trim() }] })
    } else {
      const prev = contents[contents.length - 1]
      if (prev.role === role) {
        prev.parts[0].text += '\n\n' + m.content.trim()
      } else {
        contents.push({ role, parts: [{ text: m.content.trim() }] })
      }
    }
  }

  // Fallback caso não haja turno de usuário
  if (contents.length === 0) {
    contents.push({ role: 'user', parts: [{ text: history[history.length - 1]?.content || 'Olá' }] })
  }

  const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${model}:streamGenerateContent?alt=sse&key=${apiKey}`
  const body = JSON.stringify({
    contents,
    generationConfig: { temperature: 0.7, maxOutputTokens: 8192 },
    systemInstruction: { parts: [{ text: getJarvisSystemPrompt() }] },
  })
  const headers = { 'Content-Type': 'application/json' }

  // 1. Prioriza ponte nativa se estiver dentro do app Android
  if (hasNativePostStream()) {
    return new Promise<string>((resolve, reject) => {
      const reqId = 'gem_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8)
      let full = ''

      const onAbort = () => {
        try { (window as any).Android?.abortNativeStream?.(reqId) } catch {}
        activeNativeStreams.delete(reqId)
        reject(new DOMException('Aborted', 'AbortError'))
      }

      if (signal.aborted) {
        return reject(new DOMException('Aborted', 'AbortError'))
      }

      signal.addEventListener('abort', onAbort, { once: true })

      activeNativeStreams.set(reqId, {
        onChunk: (line: string) => {
          if (!line.startsWith('data: ')) return
          const data = line.slice(6).trim()
          if (data === '[DONE]') return
          try {
            const json = JSON.parse(data)
            const chunk: string = json?.candidates?.[0]?.content?.parts?.[0]?.text ?? ''
            if (chunk) { full += chunk; onChunk(chunk) }
          } catch {}
        },
        onDone: () => {
          signal.removeEventListener('abort', onAbort)
          resolve(full)
        },
        onError: (err: Error) => {
          signal.removeEventListener('abort', onAbort)
          reject(err)
        },
      })

      ;(window as any).Android.nativePostStream(reqId, endpoint, JSON.stringify(headers), body)
    })
  }

  // 2. Fallback para fetch padrão do navegador
  const res = await fetch(endpoint, {
    method: 'POST',
    headers,
    body,
    signal,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err?.error?.message || `Gemini erro ${res.status}`)
  }
  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let full = '', buf = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const lines = buf.split('\n'); buf = lines.pop() ?? ''
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const data = line.slice(6).trim()
      if (data === '[DONE]') continue
      try {
        const json = JSON.parse(data)
        const chunk: string = json?.candidates?.[0]?.content?.parts?.[0]?.text ?? ''
        if (chunk) { full += chunk; onChunk(chunk) }
      } catch {}
    }
  }
  return full
}

async function streamOpenAICompatible(
  baseUrl: string, apiKey: string, model: string, history: ChatMessage[],
  onChunk: (text: string) => void, signal: AbortSignal,
): Promise<string> {
  const clean = history.filter(m => m.content && m.content.trim().length > 0)
  const windowed = clean.slice(-20)
  const messages = [
    { role: 'system', content: getJarvisSystemPrompt() },
    ...windowed.map(m => ({ role: m.role, content: m.content.trim() })),
  ]
  const endpoint = `${baseUrl}/chat/completions`
  const body = JSON.stringify({ model, messages, stream: true, temperature: 0.7, max_tokens: 4096 })
  const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${apiKey}` }

  // 1. Ponte nativa Android (ignora restrições de CORS e preflight 403 do Oxyy/Groq)
  if (hasNativePostStream()) {
    return new Promise<string>((resolve, reject) => {
      const reqId = 'oai_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8)
      let full = ''

      const onAbort = () => {
        try { (window as any).Android?.abortNativeStream?.(reqId) } catch {}
        activeNativeStreams.delete(reqId)
        reject(new DOMException('Aborted', 'AbortError'))
      }

      if (signal.aborted) {
        return reject(new DOMException('Aborted', 'AbortError'))
      }

      signal.addEventListener('abort', onAbort, { once: true })

      activeNativeStreams.set(reqId, {
        onChunk: (line: string) => {
          if (!line.startsWith('data: ')) return
          const data = line.slice(6).trim()
          if (data === '[DONE]') return
          try {
            const json = JSON.parse(data)
            const chunk: string = json?.choices?.[0]?.delta?.content ?? ''
            if (chunk) { full += chunk; onChunk(chunk) }
          } catch {}
        },
        onDone: () => {
          signal.removeEventListener('abort', onAbort)
          resolve(full)
        },
        onError: (err: Error) => {
          signal.removeEventListener('abort', onAbort)
          reject(err)
        },
      })

      ;(window as any).Android.nativePostStream(reqId, endpoint, JSON.stringify(headers), body)
    })
  }

  // 2. Fallback para fetch no navegador desktop
  const res = await fetch(endpoint, {
    method: 'POST',
    headers,
    body,
    signal,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err?.error?.message || `Erro ${res.status}`)
  }
  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let full = '', buf = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const lines = buf.split('\n'); buf = lines.pop() ?? ''
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const data = line.slice(6).trim()
      if (data === '[DONE]') continue
      try {
        const json = JSON.parse(data)
        const chunk: string = json?.choices?.[0]?.delta?.content ?? ''
        if (chunk) { full += chunk; onChunk(chunk) }
      } catch {}
    }
  }
  return full
}

async function callProvider(
  provider: DirectChatProvider, apiKey: string, model: string,
  history: ChatMessage[], onChunk: (text: string) => void, signal: AbortSignal,
): Promise<string> {
  try {
    if (provider === 'gemini') return await streamGemini(apiKey, model, history, onChunk, signal)
    const baseUrl = provider === 'oxyy' ? 'https://api.oxyy.ai/v1' : 'https://api.groq.com/openai/v1'
    return await streamOpenAICompatible(baseUrl, apiKey, model, history, onChunk, signal)
  } catch (err) {
    if ((err as Error).name === 'AbortError') throw err
    const geminiKey = resolveActiveKey('gemini')
    if (provider !== 'gemini' && geminiKey) {
      console.warn(`[DirectChat] Falha no provedor ${provider} (${(err as Error).message}), ativando fallback automático para Gemini...`)
      onChunk(`*(Conexão com ${provider.toUpperCase()} instável. Respondendo via Gemini...)*\n\n`)
      const geminiModel = getMobileGeminiModel()
      return await streamGemini(geminiKey, geminiModel, history, onChunk, signal)
    }
    throw err
  }
}

export function useDirectChat() {
  const [sessions, setSessions] = useState<ChatSession[]>(loadSessions)
  const [sessionId, setSessionId] = useState<string>(() => localStorage.getItem(ACTIVE_SESSION_KEY) || '')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [streamingReply, setStreamingReply] = useState('')
  const [loading, setLoading] = useState(false)
  const [answer, setAnswer] = useState('Ola. Estou pronto para ajudar.')
  const [chatError, setChatError] = useState('')
  const [query, setQuery] = useState('')
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (!sessionId) return
    const hist = loadHistory(sessionId)
    setMessages(hist)
    setAnswer(hist.at(-1)?.content || 'Sessao carregada.')
  }, [sessionId])

  const createSession = useCallback((title = 'Nova conversa') => {
    const id = crypto.randomUUID()
    const session: ChatSession = { id, title, type: 'chat' }
    const updated = [session, ...loadSessions()]
    saveSessions(updated); setSessions(updated)
    setSessionId(id); setMessages([])
    setAnswer('Nova conversa iniciada.'); setChatError('')
    localStorage.setItem(ACTIVE_SESSION_KEY, id)
    return id
  }, [])

  const selectSession = useCallback((id: string) => {
    abortRef.current?.abort(); setLoading(false); setStreamingReply(''); setChatError('')
    setSessionId(id); localStorage.setItem(ACTIVE_SESSION_KEY, id)
  }, [])

  const deleteSession = useCallback((id: string, confirmed = false) => {
    if (!confirmed && !window.confirm('Excluir esta conversa?')) return
    const updated = loadSessions().filter(s => s.id !== id)
    saveSessions(updated); setSessions(updated)
    try { localStorage.removeItem(HISTORY_PREFIX + id) } catch {}
    if (sessionId === id) {
      setSessionId(''); setMessages([]); localStorage.removeItem(ACTIVE_SESSION_KEY)
    }
  }, [sessionId])

  const exportSession = useCallback((id: string) => {
    const hist = loadHistory(id)
    if (!hist.length) return false
    let md = `# Chat Export\n\nData: ${new Date().toLocaleString('pt-BR')}\n\n---\n\n`
    hist.forEach(m => { md += `## ${m.role === 'user' ? 'Voce' : 'Jarvis'}\n\n${m.content}\n\n---\n\n` })
    const blob = new Blob([md], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `chat_${id.slice(0, 8)}.md`; a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    return true
  }, [])

  const copySession = useCallback((id: string) => {
    const hist = loadHistory(id)
    if (!hist.length) return false
    let md = `# Chat Export\n\nData: ${new Date().toLocaleString('pt-BR')}\n\n---\n\n`
    hist.forEach(m => { md += `## ${m.role === 'user' ? 'Voce' : 'Jarvis'}\n\n${m.content}\n\n---\n\n` })
    try {
      navigator.clipboard.writeText(md)
      return true
    } catch {
      return false
    }
  }, [])

  const sendText = useCallback(async (message: string, _mode = 'general'): Promise<string> => {
    if (!message.trim() || loading) return ''
    const provider = getMobileProvider()
    const apiKey = resolveActiveKey(provider)
    if (!apiKey) {
      const err = `Nenhuma chave de API configurada para o provedor ${provider.toUpperCase()}. Va em Configuracoes -> Mobile e insira sua chave.`
      setChatError(err); setAnswer(err); return ''
    }
    const model = getMobileModelForCapability('chat')
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    const userMsg: ChatMessage = { role: 'user', content: message }
    let activeId = sessionId
    if (!activeId) activeId = createSession(message.slice(0, 40))

    const prevMessages = messages
    const newHistory = [...prevMessages, userMsg]
    setMessages(newHistory); setLoading(true); setStreamingReply('Pensando...'); setChatError('')

    let reply = ''
    try {
      reply = await callProvider(provider, apiKey, model, newHistory, (chunk) => {
        setStreamingReply(prev => (prev === 'Pensando...' ? chunk : prev + chunk))
      }, controller.signal)

      const assistantMsg: ChatMessage = { role: 'assistant', content: reply }
      const finalHistory = [...newHistory, assistantMsg]
      setMessages(finalHistory); setAnswer(reply)
      saveHistory(activeId, finalHistory)

      const storedSessions = loadSessions()
      const idx = storedSessions.findIndex(s => s.id === activeId)
      if (idx >= 0 && storedSessions[idx].title === 'Nova conversa') {
        storedSessions[idx].title = message.slice(0, 40)
        saveSessions(storedSessions); setSessions([...storedSessions])
      }
    } catch (err) {
      if ((err as Error).name === 'AbortError') return ''
      const msg = err instanceof Error ? err.message : 'Erro ao contatar a API.'
      const errorMsg: ChatMessage = { role: 'assistant', content: `⚠️ Falha ao obter resposta: ${msg}` }
      const finalHistory = [...newHistory, errorMsg]
      setMessages(finalHistory)
      saveHistory(activeId, finalHistory)
      setChatError(msg)
      setAnswer(`Erro: ${msg}`)
    } finally {
      setStreamingReply(''); setLoading(false)
    }
    return reply
  }, [loading, messages, sessionId, createSession])

  return {
    sessions, sessionId, messages, answer, loading, streamingReply,
    liveSearch: null, liveReasoning: '', chatError, pendingScript: null, query,
    createSession, selectSession, deleteSession, exportSession, copySession, sendText,
    setAnswer, setChatError, setQuery,
    setPendingScript: () => {},
    sendVisionQuestion: async (prompt: string, _image: string, _cam?: string) => sendText(prompt),
    runPendingScript: async () => {},
  }
}

export function isMobileStandalone(): boolean {
  if (typeof window === 'undefined') return false
  return window.location.protocol === 'file:' || window.location.hostname === 'appassets.androidplatform.net'
}
