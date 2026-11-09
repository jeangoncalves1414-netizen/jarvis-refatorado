import { FormEvent, useEffect, useRef, useState } from 'react'
import type { ChatMessage, ChatSession, ScriptRequest, TurnMeta } from '../types'
import type { SearchPayload } from '../components/tools/SearchTool'

/** Copia do contexto da resposta só os metadados do turno (contexto usado e memórias citadas). */
function pickTurnMeta(context: unknown): TurnMeta | undefined {
  if (!context || typeof context !== 'object') return undefined
  const { situational_context, memory_used } = context as TurnMeta
  const meta: TurnMeta = {}
  if (situational_context && typeof situational_context.text === 'string' && Array.isArray(situational_context.sources)) meta.situational_context = situational_context
  if (Array.isArray(memory_used) && memory_used.length) meta.memory_used = memory_used
  return meta.situational_context || meta.memory_used ? meta : undefined
}

/** Os metadados do turno são só ao vivo: não vão para o histórico salvo no servidor. */
const withoutMeta = (history: ChatMessage[]) => history.map(({ meta: _meta, ...rest }) => rest)

/** Origem do pedido registrada nas ações da Central (C10); sem valor, o servidor usa "chat". */
export type RequestOrigin = 'voice'

const initialAnswer = 'Olá. Estou pronto para ajudar.'
const sessionFilter = (item: ChatSession) => item.type === 'chat' || !item.type
const technicalErrorMarkers = ['erro ao acessar a api', 'erro de autenticação', 'limite de taxa', 'api key', 'gemini_api_key', 'groq_api_key', 'timeout na conexão', 'erro de conexão com a api', 'orquestrador não disponível', 'não consegui falar com o núcleo']

function isTechnicalError(message: unknown) {
  const normalized = String(message || '').toLocaleLowerCase('pt-BR')
  if (normalized.includes('tool choice') || normalized.includes('model called a tool') || normalized.includes('chamar uma ferramenta')) return true
  return technicalErrorMarkers.some(marker => normalized.includes(marker))
}

function getActiveProfileId() {
  try {
    const profileId = localStorage.getItem('jarvis-active-profile') || ''
    const activatedAt = Number(localStorage.getItem('jarvis-active-profile-at') || 0)
    if (!profileId || !activatedAt || Date.now() - activatedAt > 15 * 60 * 1000) {
      localStorage.removeItem('jarvis-active-profile')
      localStorage.removeItem('jarvis-active-profile-at')
      return ''
    }
    return profileId
  } catch {
    return ''
  }
}

function getScriptRequest(summary: unknown): ScriptRequest | null {
  if (typeof summary !== 'string') return null
  const marker = '__SCRIPT_CONFIRM__'
  const markerIndex = summary.indexOf(marker)
  if (markerIndex < 0) return null
  try {
    const value = JSON.parse(summary.slice(markerIndex + marker.length).trim())
    if (!value || !['python', 'powershell'].includes(value.language) || typeof value.code !== 'string' || !value.code.trim()) return null
    return { language: value.language, code: value.code, description: typeof value.description === 'string' ? value.description : 'Executar script solicitado pelo Jarvis.' }
  } catch {
    return null
  }
}

// onAgentContext recebe o contexto da resposta final (janela, tela e popups) para o App aplicar.
// onPopup recebe o popup assim que ele nasce (evento WS ui_popup); o App descarta id repetido.
type UseChatOptions = { onAgentContext?: (context: unknown) => void; onWakeWord?: (phrase: string) => void; onPopup?: (popup: unknown) => void }

/** Contador do loop agêntico (evento WS agent_progress): etapa e chamadas ao modelo do pedido atual. */
export type AgentProgress = { run_id?: string; step: number; max_steps: number; model_calls: number; max_model_calls: number; phase: string; summary?: string }

const AWAITING_APPROVAL_TEXT = 'Aguardando aprovação na Central; depois eu continuo sozinho.'

function parseProgress(data: Record<string, unknown>): AgentProgress | null {
  const numbers = ['step', 'max_steps', 'model_calls', 'max_model_calls'] as const
  if (numbers.some(key => typeof data[key] !== 'number') || typeof data.phase !== 'string') return null
  return {
    run_id: typeof data.run_id === 'string' ? data.run_id : undefined,
    step: data.step as number, max_steps: data.max_steps as number,
    model_calls: data.model_calls as number, max_model_calls: data.max_model_calls as number,
    phase: data.phase, summary: typeof data.summary === 'string' ? data.summary : undefined,
  }
}

export function useChat(options: UseChatOptions = {}) {
  // O efeito da conexão roda uma vez; a referência mantém o callback sempre atual.
  const agentContextRef = useRef(options.onAgentContext)
  agentContextRef.current = options.onAgentContext
  const wakeWordRef = useRef(options.onWakeWord)
  wakeWordRef.current = options.onWakeWord
  const popupRef = useRef(options.onPopup)
  popupRef.current = options.onPopup
  const applyAgentContext = (context: unknown) => {
    if (context) agentContextRef.current?.(context)
  }
  const [query, setQuery] = useState('')
  const [answer, setAnswer] = useState(initialAnswer)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [sessionId, setSessionId] = useState('')
  const [loading, setLoading] = useState(false)
  const [streamingReply, setStreamingReply] = useState('')
  const [liveSearch, setLiveSearch] = useState<SearchPayload | null>(null)
  const [liveReasoning, setLiveReasoning] = useState('')
  const [chatError, setChatError] = useState('')
  const [pendingScript, setPendingScript] = useState<ScriptRequest | null>(null)
  const [agentProgress, setAgentProgress] = useState<AgentProgress | null>(null)
  const titledSessions = useRef(new Set<string>())
  useEffect(() => {
    const session = sessions.find(item => item.id === sessionId)
    const firstMessage = messages.find(item => item.role === 'user')
    if (!session || !firstMessage || titledSessions.current.has(sessionId) || (session.title && session.title !== 'Nova conversa')) return
    const title = firstMessage.content.slice(0, 48).trim()
    if (!title) return
    titledSessions.current.add(sessionId)
    void fetch(`/api/sessions/${encodeURIComponent(sessionId)}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title }),
    }).then(response => {
      if (response.ok) setSessions(previous => previous.map(item => item.id === sessionId ? { ...item, title } : item))
    }).catch(() => undefined)
  }, [messages, sessionId, sessions])
  const chatSocketRef = useRef<WebSocket | null>(null)
  const pendingHistoryRef = useRef<ChatMessage[]>([])
  const activeSessionRef = useRef('')
  const liveReasoningRef = useRef('')
  const typingBufferRef = useRef('')
  const reasoningBufferRef = useRef('')
  const typingTimerRef = useRef<number | null>(null)
  const finalizePendingRef = useRef(false)
  const finalReasoningRef = useRef('')
  const finalReplyRef = useRef('')
  const finalRunIdRef = useRef<string | undefined>(undefined)
  const finalMetaRef = useRef<TurnMeta | undefined>(undefined)
  // run_id do pedido em andamento neste aparelho (vem do agent_progress); agent_reply de outro pedido não fecha o turno.
  const turnRunIdRef = useRef<string | undefined>(undefined)
  const waitForReplyRef = useRef<((reply: string) => void) | null>(null)
  const sessionMutationRef = useRef(0)
  // Segurança contra turno sem evento final: início do turno e último sinal recebido do servidor.
  const messagesRef = useRef<ChatMessage[]>([])
  messagesRef.current = messages
  const turnStartRef = useRef(0)
  const lastActivityRef = useRef(0)

  const stopTyping = () => {
    if (typingTimerRef.current !== undefined && typingTimerRef.current !== null) {
      window.clearInterval(typingTimerRef.current)
      typingTimerRef.current = null
    }
  }

  const buildAssistantContent = (reasoning: string, visibleReply: string) => {
    const trimmed = (reasoning || '').trim()
    if (!trimmed) return visibleReply
    return '<think>' + trimmed + '</think>' + visibleReply
  }

  const doFinalize = () => {
    const reasoning = finalReasoningRef.current || ''
    const visibleReply = finalReplyRef.current || ''
    finalReasoningRef.current = ''
    finalReplyRef.current = ''
    const content = buildAssistantContent(reasoning, visibleReply)
    const meta = finalMetaRef.current
    const history: ChatMessage[] = [...pendingHistoryRef.current, { role: 'assistant' as const, content, run_id: finalRunIdRef.current, ...(meta ? { meta } : {}) }]
    finalRunIdRef.current = undefined
    finalMetaRef.current = undefined
    turnRunIdRef.current = undefined
    setAnswer(visibleReply)
    setMessages(history)
    setAgentProgress(null)
    setStreamingReply('')
    setLiveSearch(null)
    setLiveReasoning('')
    liveReasoningRef.current = ''
    reasoningBufferRef.current = ''
    typingBufferRef.current = ''
    setLoading(false)
    if (activeSessionRef.current) {
      fetch(`/api/sessions/${activeSessionRef.current}/history`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ history: withoutMeta(history) }),
      }).catch(error => {
        console.warn('Erro ao salvar histórico:', error)
      })
    }
    refreshSessions().catch(() => undefined)
  }

  const pumpTyping = () => {
    if (typingTimerRef.current !== null) return
    typingTimerRef.current = window.setInterval(() => {
      // Reasoning is typed first (1-3 chars per tick), then the visible reply.
      const reasoningBuffer = reasoningBufferRef.current
      if (reasoningBuffer) {
        const step = 1 + Math.floor(Math.random() * 3)
        const take = Math.min(step, reasoningBuffer.length)
        reasoningBufferRef.current = reasoningBuffer.slice(take)
        setLiveReasoning(previous => previous + reasoningBuffer.slice(0, take))
        liveReasoningRef.current += reasoningBuffer.slice(0, take)
        return
      }
      const buffer = typingBufferRef.current
      if (buffer) {
        const step = 2 + Math.floor(Math.random() * 4)
        const take = Math.min(step, buffer.length)
        typingBufferRef.current = buffer.slice(take)
        setStreamingReply(previous => (previous === 'Pensando…' ? '' : previous) + buffer.slice(0, take))
        return
      }
      // Both buffers drained — only now commit the finished message.
      stopTyping()
      if (finalizePendingRef.current) {
        finalizePendingRef.current = false
        doFinalize()
      }
    }, 18)
  }

  const refreshSessions = async () => {
    const requestMutation = sessionMutationRef.current
    const response = await fetch('/api/sessions')
    const data = await response.json()
    const items = (data.sessions || []).filter(sessionFilter) as ChatSession[]
    setSessions(previous => {
      if (requestMutation === sessionMutationRef.current) return items
      const serverIds = new Set(items.map(item => item.id))
      const localOnly = previous.filter(item => !serverIds.has(item.id))
      return [...localOnly, ...items]
    })
    return items as ChatSession[]
  }

  const selectSession = async (id: string) => {
    stopTyping()
    if (waitForReplyRef.current) { waitForReplyRef.current(''); waitForReplyRef.current = null }
    finalizePendingRef.current = false
    typingBufferRef.current = ''
    reasoningBufferRef.current = ''
    setLoading(false)
    setStreamingReply('')
    setLiveReasoning('')
    setAgentProgress(null)
    try {
      const response = await fetch(`/api/sessions/${id}/history`)
      const data = await response.json()
      const history = (data.history || []).map((item: { role?: string; content?: string; text?: string; run_id?: string }) => ({
        role: item.role === 'user' ? 'user' as const : 'assistant' as const,
        content: item.content || item.text || '',
        run_id: typeof item.run_id === 'string' ? item.run_id : undefined,
      }))
      setMessages(history)
      setAnswer(history.at(-1)?.content || 'Sessão carregada.')
      setSessionId(id)
      activeSessionRef.current = id
      localStorage.setItem('jarvis-react-session', id)
    } catch {
      setAnswer('Não foi possível carregar esta sessão.')
    }
  }

  const createSession = async (title = 'Nova conversa') => {
    sessionMutationRef.current += 1
    stopTyping()
    if (waitForReplyRef.current) { waitForReplyRef.current(''); waitForReplyRef.current = null }
    finalizePendingRef.current = false
    typingBufferRef.current = ''
    reasoningBufferRef.current = ''
    setLoading(false)
    setStreamingReply('')
    setLiveReasoning('')
    setLiveSearch(null)
    const response = await fetch('/api/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, type: 'chat' }),
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok || !data.id) throw new Error(data.error || 'Não foi possível criar uma sessão.')
    const created = (data.session || { id: data.id, title, type: 'chat' }) as ChatSession
    setSessions(previous => [created, ...previous.filter(item => item.id !== created.id)])
    setSessionId(data.id)
    activeSessionRef.current = data.id
    setMessages([])
    setAnswer('Nova conversa iniciada.')
    localStorage.setItem('jarvis-react-session', data.id)
    return data.id as string
  }

  const deleteSession = async (id: string, confirmed = false) => {
    if (!confirmed && !window.confirm('Excluir esta conversa? Esta ação não pode ser desfeita.')) return
    const response = await fetch(`/api/sessions/${id}`, { method: 'DELETE' })
    const data = await response.json().catch(() => ({}))
    if (!response.ok || !data.ok) {
      setAnswer('Não foi possível excluir a conversa.')
      return
    }
    setSessions(previous => previous.filter(item => item.id !== id))
    if (sessionId === id) {
      stopTyping()
      if (waitForReplyRef.current) { waitForReplyRef.current(''); waitForReplyRef.current = null }
      finalizePendingRef.current = false
      typingBufferRef.current = ''
      reasoningBufferRef.current = ''
      setLoading(false)
      setStreamingReply('')
      setLiveReasoning('')
      setLiveSearch(null)
      setSessionId('')
      activeSessionRef.current = ''
      setMessages([])
      localStorage.removeItem('jarvis-react-session')
    }
  }

  const exportSession = async (id: string) => {
    if (!id) return false
    const response = await fetch(`/api/sessions/${id}/history`)
    const data = await response.json().catch(() => ({}))
    const history = (data.history || []) as ChatMessage[]
    if (!history.length) {
      setAnswer('Este chat está vazio, não há nada para exportar.')
      return false
    }
    let markdown = `# Chat Export\n\nData: ${new Date().toLocaleString('pt-BR')}\n\n---\n\n`
    history.forEach(msg => {
      const role = msg.role === 'user' ? '👤 Você' : '🤖 Jarvis'
      markdown += `## ${role}\n\n${msg.content}\n\n---\n\n`
    })
    let url: string | null = null
    try {
      const blob = new Blob([markdown], { type: 'text/markdown' })
      url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `chat_${id.slice(0, 8)}.md`
      anchor.click()
      return true
    } finally {
      if (url) URL.revokeObjectURL(url)
    }
  }

  const copySession = async (id: string) => {
    if (!id) return false
    const response = await fetch(`/api/sessions/${id}/history`)
    const data = await response.json().catch(() => ({}))
    const history = (data.history || []) as ChatMessage[]
    if (!history.length) {
      setAnswer('Este chat está vazio, não há nada para copiar.')
      return false
    }
    let markdown = `# Chat Export\n\nData: ${new Date().toLocaleString('pt-BR')}\n\n---\n\n`
    history.forEach(msg => {
      const role = msg.role === 'user' ? '👤 Você' : '🤖 Jarvis'
      markdown += `## ${role}\n\n${msg.content}\n\n---\n\n`
    })
    try {
      await navigator.clipboard.writeText(markdown)
      setAnswer('Chat copiado para o clipboard!')
      return true
    } catch (error) {
      setAnswer('Erro ao copiar para o clipboard.')
      return false
    }
  }

  const postChat = async (message: string, mode: string, activeSessionId: string, racingMode?: boolean, origin?: RequestOrigin): Promise<string> => {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, mode, session_id: activeSessionId, profile_id: getActiveProfileId() || undefined, racing: Boolean(racingMode), origin }),
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok || data.ok === false) {
      throw new Error(data.error || 'Não foi possível obter resposta do Jarvis.')
    }
    const reply = data.reply || data.summary || ''
    if (activeSessionRef.current === activeSessionId) {
      commitRestReply(reply, data.context?.run_id)
      finalMetaRef.current = pickTurnMeta(data.context)
      applyAgentContext(data.context)
    }
    return reply
  }

  // Mensagem do assistente que chega fora de um turno (loop retomado após aprovação).
  const appendAssistantMessage = (reply: string, runId?: string) => {
    const current = messagesRef.current
    if (runId && current.some(item => item.role === 'assistant' && item.run_id === runId && item.content === reply)) return
    const history: ChatMessage[] = [...current, { role: 'assistant', content: reply, run_id: runId }]
    messagesRef.current = history
    pendingHistoryRef.current = history
    setMessages(history)
    setAnswer(reply)
    const sid = activeSessionRef.current
    if (sid) {
      fetch(`/api/sessions/${sid}/history`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ history: withoutMeta(history) }),
      }).catch(() => undefined)
    }
  }

  const commitRestReply = (reply: string, runId?: string) => {
    finalRunIdRef.current = typeof runId === 'string' ? runId : undefined
    stopTyping()
    finalReasoningRef.current = ''
    const marker = '__SCRIPT_CONFIRM__'
    const markerIndex = reply.indexOf(marker)
    finalReplyRef.current = markerIndex >= 0 ? reply.slice(0, markerIndex).trim() : reply
    reasoningBufferRef.current = ''
    typingBufferRef.current = finalReplyRef.current
    const script = getScriptRequest(reply)
    if (script) setPendingScript(script)
    setStreamingReply('Pensando…')
    setLiveReasoning('')
    liveReasoningRef.current = ''
    finalizePendingRef.current = true
    pumpTyping()
  }

  const failReply = (error: unknown) => {
    const message = error instanceof Error ? error.message : String(error || '')
    const generic = 'Não foi possível obter resposta do Jarvis. Verifique a conexão e tente novamente.'
    if (isTechnicalError(message)) {
      setAnswer('Jarvis encontrou um problema técnico. Verifique as configurações da API e tente novamente.')
      setChatError(message)
    } else {
      setAnswer(generic)
      // O texto de "answer" só aparece com a conversa vazia; com histórico a falha precisa ir para o aviso de erro.
      setChatError(generic)
    }
    setStreamingReply('')
    setLiveSearch(null)
    setLiveReasoning('')
    setAgentProgress(null)
    liveReasoningRef.current = ''
    reasoningBufferRef.current = ''
    typingBufferRef.current = ''
    stopTyping()
    setLoading(false)
    if (waitForReplyRef.current) {
      waitForReplyRef.current('')
      waitForReplyRef.current = null
    }
  }

  const sendText = async (message: string, mode = 'general', racingMode = false, origin?: RequestOrigin): Promise<string> => {
    if (!message || loading) return ''
    turnStartRef.current = Date.now()
    turnRunIdRef.current = undefined
    lastActivityRef.current = Date.now()
    setLoading(true)
    setLiveSearch(null)
    setChatError('')
    setAnswer('Pensando…')
    const userMessage: ChatMessage = { role: 'user', content: message }
    // Closures antigas (ligação por voz) não podem ver mensagens/sessão desatualizadas.
    let activeSessionId = activeSessionRef.current || sessionId
    let waitingForSocket = false
    try {
      if (!activeSessionId) activeSessionId = await createSession(message.slice(0, 32))
      const baseHistory = [...messagesRef.current, userMessage]
      messagesRef.current = baseHistory
      setMessages(baseHistory)
      pendingHistoryRef.current = baseHistory
      const socket = chatSocketRef.current
      if (socket?.readyState === WebSocket.OPEN && !racingMode) {
        stopTyping()
        typingBufferRef.current = ''
        reasoningBufferRef.current = ''
        finalizePendingRef.current = false
        setStreamingReply('Pensando…')
        setLiveReasoning('')
        liveReasoningRef.current = ''
        waitingForSocket = true

        socket.send(JSON.stringify({ type: 'message', message, mode, session_id: activeSessionId, profile_id: getActiveProfileId() || undefined, racing: Boolean(racingMode), origin }))
        const reply = await new Promise<string>(resolve => {
          waitForReplyRef.current = resolve
        })
        return reply
      } else {
        return await postChat(message, mode, activeSessionId, racingMode, origin)
      }
    } catch (error) {
      failReply(error)
      return ''
    }
  }

  const sendVisionQuestion = async (prompt: string, image: string, label = 'Imagem') => {
    if (!prompt || loading) return
    turnStartRef.current = Date.now()
    turnRunIdRef.current = undefined
    lastActivityRef.current = Date.now()
    setLoading(true)
    setLiveSearch(null)
    setChatError('')
    setAnswer('👁️ Analisando sua tela com Gemini Vision...')
    setStreamingReply('Analisando captura visual...')
    const userMessage: ChatMessage = { role: 'user', content: prompt }
    let activeSessionId = sessionId
    try {
      if (!activeSessionId) activeSessionId = await createSession(`Análise: ${label}`.slice(0, 32))
      const baseHistory = [...messagesRef.current, userMessage]
      messagesRef.current = baseHistory
      setMessages(baseHistory)
      pendingHistoryRef.current = baseHistory
      const socket = chatSocketRef.current
      if (socket?.readyState === WebSocket.OPEN) {
        stopTyping()
        typingBufferRef.current = ''
        reasoningBufferRef.current = ''
        finalizePendingRef.current = false
        setStreamingReply('Pensando…')
        setLiveReasoning('')
        liveReasoningRef.current = ''
        socket.send(JSON.stringify({ type: 'message', message: prompt, mode: 'vision', session_id: activeSessionId, profile_id: getActiveProfileId() || undefined }))
        await new Promise<string>(resolve => {
          waitForReplyRef.current = resolve
        })
      } else {
        await postChat(prompt, 'vision', activeSessionId)
      }
    } catch (error) {
      failReply(error)
    }
  }


  useEffect(() => {
    if (typeof window !== 'undefined' && (
      window.location.hostname === 'appassets.androidplatform.net' ||
      window.location.protocol === 'file:'
    )) {
      return
    }
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const basePort = Number(window.location.port || (window.location.protocol === 'https:' ? 443 : 80))
    const wsUrl = `${protocol}://${window.location.hostname}:${basePort + 1}/ws/chat`
    let reconnectTimer: number | null = null
    let disposed = false
    let reconnectAttempts = 0
    const MAX_RECONNECT_ATTEMPTS = 10
    const INITIAL_BACKOFF_MS = 3000
    const MAX_BACKOFF_MS = 30000

    const getBackoffDelay = (attempt: number) => {
      const delay = Math.min(INITIAL_BACKOFF_MS * Math.pow(2, attempt), MAX_BACKOFF_MS)
      return delay
    }

    const connect = () => {
      if (disposed) return
      if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
        setChatError('Não foi possível conectar após várias tentativas. Verifique sua conexão.')
        return
      }
      let socket: WebSocket
      try {
        socket = new WebSocket(wsUrl)
      } catch {
        const delay = getBackoffDelay(reconnectAttempts)
        reconnectAttempts++
        reconnectTimer = window.setTimeout(connect, delay)
        return
      }
      chatSocketRef.current = socket
      socket.onopen = () => {
        setChatError('')
        reconnectAttempts = 0
      }
      socket.onmessage = (event) => {
        let data: { type?: string; text?: string; message?: string; summary?: string; payload?: SearchPayload; session_id?: string; phrase?: string; context?: { run_id?: string }; reply?: unknown; run_id?: unknown; popup?: unknown } = {}
        try {
          data = JSON.parse(String(event.data))
        } catch {
          return
        }
        const { type, text = '', message = '', summary = '' } = data
        // Evento do detector local: vale para o aparelho todo, não para uma conversa.
        if (type === 'wake_word') { wakeWordRef.current?.(typeof data.phrase === 'string' ? data.phrase : ''); return }
        // Popup do agente: camada única do app, vale também para a ligação por voz e outras conversas.
        if (type === 'ui_popup') { if (data.popup) popupRef.current?.(data.popup); return }
        if (data.session_id && data.session_id !== activeSessionRef.current) return
        lastActivityRef.current = Date.now()
        if (type === 'agent_progress') {
          const progress = parseProgress(data as Record<string, unknown>)
          if (progress?.run_id && !turnRunIdRef.current && !messagesRef.current.some(item => item.role === 'assistant' && item.run_id === progress.run_id)) turnRunIdRef.current = progress.run_id
          if (progress) setAgentProgress(['done', 'cancelled', 'limit'].includes(progress.phase) ? null : progress)
          return
        }
        if (type === 'agent_reply') {
          // Resposta do loop agêntico retomado depois de uma aprovação.
          const reply = typeof data.reply === 'string' ? data.reply.trim() : ''
          const runId = typeof data.run_id === 'string' ? data.run_id : undefined
          const closesTurn = Boolean(waitForReplyRef.current && runId && runId === turnRunIdRef.current)
          // Resposta de outro pedido não apaga o contador do pedido que ainda está em andamento.
          if (closesTurn || !waitForReplyRef.current) setAgentProgress(null)
          if (!reply) return
          if (closesTurn && waitForReplyRef.current) {
            finalRunIdRef.current = runId
            finalReasoningRef.current = ''
            finalReplyRef.current = reply
            finalizePendingRef.current = true
            pumpTyping()
            waitForReplyRef.current(reply)
            waitForReplyRef.current = null
            return
          }
          appendAssistantMessage(reply, runId)
          return
        }
        if (type === 'reasoning') {
          reasoningBufferRef.current += text || message
          pumpTyping()
        } else if (type === 'chunk') {
          typingBufferRef.current += text || message
          pumpTyping()
        } else if (type === 'search') {
          const payload = data.payload
          if (payload?.query && Array.isArray(payload.results)) setLiveSearch(payload)
        } else if (type === 'complete') {
          finalRunIdRef.current = typeof data.context?.run_id === 'string' ? data.context.run_id : undefined
          finalMetaRef.current = pickTurnMeta(data.context)
          applyAgentContext(data.context)
          finalReasoningRef.current = (liveReasoningRef.current + reasoningBufferRef.current).trim()
          finalReplyRef.current = summary || message || ''
          const script = getScriptRequest(summary)
          if (script) setPendingScript(script)
          finalizePendingRef.current = true
          pumpTyping()
          if (waitForReplyRef.current) {
            waitForReplyRef.current(summary || message || '')
            waitForReplyRef.current = null
          }
        } else if (type === 'error') {
          failReply(message || 'Falha na comunicação com o Jarvis.')
        }
      }
      socket.onclose = () => {
        chatSocketRef.current = null
        if (waitForReplyRef.current) {
          failReply('Conexão com o servidor perdida. Tente novamente.')
        }
        if (!disposed) {
          const delay = getBackoffDelay(reconnectAttempts)
          reconnectAttempts++
          reconnectTimer = window.setTimeout(connect, delay)
        }
      }
      socket.onerror = () => socket.close()
    }

    connect()
    refreshSessions()
      .then((items) => {
        const saved = localStorage.getItem('jarvis-react-session')
        const match = items.find((item) => item.id === saved)
        // Se uma nova conversa foi criada enquanto a consulta inicial estava
        // pendente, ela já é a sessão ativa e não deve ser substituída pela
        // primeira conversa antiga retornada pelo servidor.
        const target = activeSessionRef.current || (match || items[0])?.id
        if (target) selectSession(target).catch(() => undefined)
      })
      .catch(() => undefined)

    return () => {
      disposed = true
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer)
      const socket = chatSocketRef.current
      chatSocketRef.current = null
      if (socket) {
        socket.onclose = null
        socket.onerror = null
        socket.close()
      }
      stopTyping()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Reconciliação: se o turno ficou sem evento final (aprovação feita fora do chat, socket mudo,
  // aba em segundo plano), consulta o Run real da conversa e encerra o "pensando".
  useEffect(() => {
    if (!loading) return
    let disposed = false
    let checking = false
    const HARD_LIMIT_MS = 10 * 60 * 1000
    const IDLE_MS = 15 * 1000
    const check = async () => {
      if (disposed || checking) return
      if (finalizePendingRef.current || typingTimerRef.current !== null) return
      const now = Date.now()
      const sid = activeSessionRef.current
      if (now - turnStartRef.current > HARD_LIMIT_MS) {
        failReply('O Jarvis não respondeu a tempo. Confira o resultado na Central de Execuções.')
        return
      }
      if (!sid || now - lastActivityRef.current < IDLE_MS) return
      checking = true
      try {
        const query = new URLSearchParams({ session_id: sid, limit: '1', include_reads: '1' })
        const response = await fetch(`/api/runs?${query}`)
        const data = await response.json().catch(() => null)
        const run = data?.runs?.[0] as { status?: string; created_at?: number; result_summary?: string | null; reply?: string | null } | undefined
        if (disposed || !run || activeSessionRef.current !== sid) return
        if ((run.created_at || 0) * 1000 < turnStartRef.current - 5000) return
        if (run.status === 'awaiting_confirmation') {
          setStreamingReply(AWAITING_APPROVAL_TEXT)
          lastActivityRef.current = Date.now() - IDLE_MS + 4000
          return
        }
        if (run.status && ['succeeded', 'failed', 'cancelled', 'interrupted'].includes(run.status)) {
          const labels: Record<string, string> = { failed: 'falhou', cancelled: 'foi cancelado', interrupted: 'foi interrompido' }
          // A resposta do agente (loop retomado) vale mais que o resumo do estado.
          const reply = (run.reply || '').trim() || (run.result_summary || '').trim()
            || (run.status === 'succeeded' ? 'Pedido concluído. Confira o resultado na Central de Execuções.' : `O pedido ${labels[run.status]}. Confira os detalhes na Central de Execuções.`)
          finalReasoningRef.current = ''
          finalReplyRef.current = reply
          finalizePendingRef.current = false
          doFinalize()
          if (waitForReplyRef.current) { waitForReplyRef.current(reply); waitForReplyRef.current = null }
        }
      } catch {
        /* tenta de novo no próximo ciclo */
      } finally {
        checking = false
      }
    }
    const timer = window.setInterval(() => { void check() }, 4000)
    const onVisible = () => { if (!document.hidden) void check() }
    document.addEventListener('visibilitychange', onVisible)
    window.addEventListener('focus', onVisible)
    return () => {
      disposed = true
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
      window.removeEventListener('focus', onVisible)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading])

  // Chamadas por voz: acrescenta o turno (fala + resposta) ao histórico sem substituir mensagens anteriores.
  const appendExchange = async (userText: string, assistantText: string) => {
    const user = userText.trim()
    const reply = assistantText.trim()
    if (!user || !reply) return
    let sid = activeSessionRef.current
    if (!sid) sid = await createSession(user.slice(0, 32))
    const history: ChatMessage[] = [...messagesRef.current, { role: 'user', content: user }, { role: 'assistant', content: reply }]
    messagesRef.current = history
    pendingHistoryRef.current = history
    setMessages(history)
    fetch(`/api/sessions/${sid}/history`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ history }),
    }).catch(() => undefined)
    refreshSessions().catch(() => undefined)
  }

  const runPendingScript = async () => {
    if (!pendingScript) return
    const script = pendingScript
    setPendingScript(null)
    setLoading(true)
    setChatError('')
    try {
      const approval = await fetch('/api/script/authorize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ language: script.language, code: script.code, confirmed: true }),
      })
      const approved = await approval.json().catch(() => ({}))
      if (!approval.ok || !approved.ok || !approved.receipt) {
        throw new Error(approved.error || 'Não foi possível autorizar o script.')
      }
      const response = await fetch('/api/script/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ language: script.language, code: script.code, receipt: approved.receipt }),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok || data.ok === false) throw new Error(data.error || 'Não foi possível executar o script.')
      const output = [data.stdout, data.stderr].filter(Boolean).join('\n').trim()
      const preview = script.code.split('\n').slice(0, 8).join('\n')
      const visibleReply = [
        `Script ${script.language} executado${data.returncode === 0 ? '' : ` (código de saída ${data.returncode})`}.`,
        script.description,
        '```',
        preview,
        '```',
      ].join('\n') + (output ? `\n\nSaída:\n\`\`\`\n${output}\n\`\`\`` : '')
      const content = buildAssistantContent('', visibleReply)
      const history = [...pendingHistoryRef.current, { role: 'assistant' as const, content }]
      setMessages(history)
      setAnswer(visibleReply)
      setStreamingReply('')
      setLoading(false)
      if (activeSessionRef.current) {
        fetch(`/api/sessions/${activeSessionRef.current}/history`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ history }),
        }).catch(error => {
          console.warn('Erro ao salvar histórico após script:', error)
        })
      }
      refreshSessions().catch(() => undefined)
    } catch (error) {
      failReply(error)
    }
  }

  return {
    answer,
    appendExchange,
    chatError,
    copySession,
    createSession,
    deleteSession,
    exportSession,
    loading,
    liveReasoning,
    liveSearch,
    messages,
    pendingScript,
    agentProgress,
    query,
    runPendingScript,
    selectSession,
    sendText,
    sendVisionQuestion,
    sessionId,
    sessions,
    setAnswer,
    setChatError,
    setPendingScript,
    setQuery,
    streamingReply,
  }
}
