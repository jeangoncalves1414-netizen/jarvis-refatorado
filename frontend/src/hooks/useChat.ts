import { FormEvent, useEffect, useRef, useState } from 'react'
import type { ChatMessage, ChatSession, ScriptRequest } from '../types'
import type { SearchPayload } from '../components/tools/SearchTool'
import { extractWindowRequest, type WindowOpenRequest } from '../windows/registry'

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

type UseChatOptions = { onOpenWindow?: (request: WindowOpenRequest) => void }

export function useChat(options: UseChatOptions = {}) {
  // O efeito da conexão roda uma vez; a referência mantém o callback sempre atual.
  const openWindowRef = useRef(options.onOpenWindow)
  openWindowRef.current = options.onOpenWindow
  const openRequestedWindow = (context: unknown) => {
    const request = extractWindowRequest(context)
    if (request) openWindowRef.current?.(request)
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
  const waitForReplyRef = useRef<((reply: string) => void) | null>(null)
  const sessionMutationRef = useRef(0)

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
    const history = [...pendingHistoryRef.current, { role: 'assistant' as const, content, run_id: finalRunIdRef.current }]
    finalRunIdRef.current = undefined
    setAnswer(visibleReply)
    setMessages(history)
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
        body: JSON.stringify({ history }),
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

  const postChat = async (message: string, mode: string, activeSessionId: string, racingMode?: boolean): Promise<string> => {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, mode, session_id: activeSessionId, profile_id: getActiveProfileId() || undefined, racing: Boolean(racingMode) }),
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok || data.ok === false) {
      throw new Error(data.error || 'Não foi possível obter resposta do Jarvis.')
    }
    const reply = data.reply || data.summary || ''
    if (activeSessionRef.current === activeSessionId) {
      commitRestReply(reply, data.context?.run_id)
      openRequestedWindow(data.context)
    }
    return reply
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
    }
    setStreamingReply('')
    setLiveSearch(null)
    setLiveReasoning('')
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

  const sendText = async (message: string, mode = 'general', racingMode = false): Promise<string> => {
    if (!message || loading) return ''
    setLoading(true)
    setLiveSearch(null)
    setChatError('')
    setAnswer('Pensando…')
    const userMessage: ChatMessage = { role: 'user', content: message }
    let activeSessionId = sessionId
    let waitingForSocket = false
    try {
      if (!activeSessionId) activeSessionId = await createSession(message.slice(0, 32))
      const baseHistory = [...messages, userMessage]
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

        socket.send(JSON.stringify({ type: 'message', message, mode, session_id: activeSessionId, profile_id: getActiveProfileId() || undefined, racing: Boolean(racingMode) }))
        const reply = await new Promise<string>(resolve => {
          waitForReplyRef.current = resolve
        })
        return reply
      } else {
        return await postChat(message, mode, activeSessionId, racingMode)
      }
    } catch (error) {
      failReply(error)
      return ''
    }
  }

  const sendVisionQuestion = async (prompt: string, image: string, label = 'Imagem') => {
    if (!prompt || loading) return
    setLoading(true)
    setLiveSearch(null)
    setChatError('')
    setAnswer('👁️ Analisando sua tela com Gemini Vision...')
    setStreamingReply('Analisando captura visual...')
    const userMessage: ChatMessage = { role: 'user', content: prompt }
    let activeSessionId = sessionId
    try {
      if (!activeSessionId) activeSessionId = await createSession(`Análise: ${label}`.slice(0, 32))
      const baseHistory = [...messages, userMessage]
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
        let data: { type?: string; text?: string; message?: string; summary?: string; payload?: SearchPayload; session_id?: string; context?: { run_id?: string } } = {}
        try {
          data = JSON.parse(String(event.data))
        } catch {
          return
        }
        const { type, text = '', message = '', summary = '' } = data
        if (data.session_id && data.session_id !== activeSessionRef.current) return
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
          openRequestedWindow(data.context)
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
