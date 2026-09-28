import { useEffect, useMemo, useRef, useState } from 'react'
import { Download, Plus, Search, Trash2, MessageSquare } from 'lucide-react'
import { ChatComposer, type ChatMode, type PersonaMode } from '../components/ChatComposer'
import { JarvisOrb } from '../components/JarvisOrb'
import { MessageRenderer } from '../components/chat/MessageRenderer'
import { ChatSidebar } from '../components/ChatSidebar'
import { PlanningWorkspace } from '../components/PlanningWorkspace'
import type { ChatMessage, ChatSession, ScriptRequest } from '../types'
import type { SearchPayload } from '../components/tools/SearchTool'

type CinemaRequestPayload = {
  title?: string
  detect_url?: string
  discovery_results?: Array<{ title?: string; url?: string; source?: string; snippet?: string }>
  catalog_results?: Array<{ id?: string; title?: string; year?: string | number; description?: string }>
}

type ChatPageProps = {
  sessions: ChatSession[]
  sessionId: string
  messages: ChatMessage[]
  answer: string
  loading: boolean
  streamingReply: string
  liveSearch: SearchPayload | null
  liveReasoning: string
  chatError: string
  query: string
  chatMode: ChatMode
  chatAttachment: { name: string; dataUrl: string } | null
  recording: boolean
  pendingScript: ScriptRequest | null
  onSelectSession: (id: string) => void
  onCreateSession: () => void | Promise<unknown>
  onDeleteSession: (id: string) => void
  onExportSession: () => void
  onCopySession: () => void
  onOpenLiveCall: () => void
  onSpeakText?: (text: string) => void
  onClearChatError?: () => void
  onQueryChange: (value: string) => void
  onModeChange: (mode: ChatMode) => void
  onAttachment: (file: File) => void
  onClearAttachment: () => void
  onSubmit: () => void
  onVoice: () => void
  onScreen: () => void
  onCinema: () => void
  onSendText: (text: string, mode?: ChatMode) => Promise<string>
  onCinemaRequest: (payload: CinemaRequestPayload) => void
  onRunPendingScript: () => Promise<void>
  onOpenEvolute?: () => void
}

export function ChatPage({
  sessions,
  sessionId,
  messages,
  answer,
  loading,
  streamingReply,
  liveSearch,
  liveReasoning,
  chatError,
  query,
  chatMode,
  chatAttachment,
  recording,
  pendingScript,
  onSelectSession,
  onCreateSession,
  onDeleteSession,
  onExportSession,
  onCopySession,
  onOpenLiveCall,
  onClearChatError,
  onQueryChange,
  onModeChange,
  onAttachment,
  onClearAttachment,
  onSubmit,
  onVoice,
  onScreen,
  onCinema,
  onSendText,
  onCinemaRequest,
  onRunPendingScript,
  onOpenEvolute,
}: ChatPageProps) {
  const [persona, setPersona] = useState<PersonaMode>('general')
  const [racingMode, setRacingMode] = useState(false)
  const [sessionQuery, setSessionQuery] = useState('')
  const [showMobileSessions, setShowMobileSessions] = useState(false)
  const [maxVisibleMessages, setMaxVisibleMessages] = useState(25)
  const [hoveredSessionId, setHoveredSessionId] = useState<string | null>(null)
  const [showExportMenu, setShowExportMenu] = useState(false)
  const autoTitledRef = useRef<Set<string>>(new Set())

  const handleCreateSession = () => {
    setShowMobileSessions(false)
    void Promise.resolve(onCreateSession()).catch(() => undefined)
  }

  // Auto-title session from first user message (ChatGPT-style)
  useEffect(() => {
    if (!sessionId || autoTitledRef.current.has(sessionId)) return
    const firstUser = messages.find(m => m.role === 'user')
    if (!firstUser) return
    const currentSession = sessions.find(s => s.id === sessionId)
    if (currentSession && currentSession.title && currentSession.title !== 'Nova conversa') return
    const title = firstUser.content.slice(0, 48).trim()
    if (!title) return
    autoTitledRef.current.add(sessionId)
    fetch(`/api/sessions/${sessionId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title }),
    }).catch(() => undefined)
  }, [sessionId, messages, sessions])

  const filteredSessions = useMemo(() => {
    const normalized = sessionQuery.trim().toLocaleLowerCase('pt-BR')
    if (!normalized) return sessions
    return sessions.filter(item => (item.title || 'Conversa').toLocaleLowerCase('pt-BR').includes(normalized))
  }, [sessionQuery, sessions])

  // Click outside to close export menu
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (showExportMenu && !(e.target as Element).closest('.chat-export-icon') && !(e.target as Element).closest('[style*="position: absolute"]')) {
        setShowExportMenu(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [showExportMenu])

  // Windowing: Render only the last N messages to prevent memory lag on Moto E20
  const visibleMessages = useMemo(() => {
    if (messages.length <= maxVisibleMessages) return messages
    return messages.slice(messages.length - maxVisibleMessages)
  }, [messages, maxVisibleMessages])

  const renderMessage = (message: ChatMessage, index: number) => (
    <article key={`${message.role}-${index}`} className={`message ${message.role}`}>
      <small>{message.role === 'user' ? 'VOCÊ' : 'JARVIS'}</small>
      <MessageRenderer
        content={message.content}
        mode={chatMode}
        defaultOpenReasoning={index === messages.length - 1 && message.role === 'assistant'}
        pendingScript={pendingScript}
        onRunPendingScript={() => onRunPendingScript().catch(() => undefined)}
        onSendText={text => onSendText(text).catch(() => undefined)}
        onCinemaRequest={onCinemaRequest}
        liveSearch={index === messages.length - 1 && message.role === 'assistant' ? liveSearch : null}
      />
    </article>
  )

  const chatHistoryRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to latest message strictly inside the chat history container (no outer window scrolling)
  useEffect(() => {
    if (chatHistoryRef.current) {
      chatHistoryRef.current.scrollTo({
        top: chatHistoryRef.current.scrollHeight,
        behavior: 'smooth',
      })
    }
  }, [visibleMessages.length, streamingReply])

  return (
    <section className="chat-card chat-card-modern">
      {(loading || streamingReply) && <JarvisOrb size={56} className="chat-orb-indicator" listening />}
      <div className="chat-workspace">
        {/* Session Drawer — overlay backdrop on mobile */}
        {showMobileSessions && (
          <div
            className="mobile-sessions-backdrop"
            onClick={() => setShowMobileSessions(false)}
            aria-hidden="true"
          />
        )}
        <div className={`chat-sidebar-wrapper ${showMobileSessions ? 'mobile-sessions-open' : ''}`}>
          {showMobileSessions && (
            <button
              type="button"
              onClick={() => setShowMobileSessions(false)}
              className="mobile-sessions-close"
              aria-label="Fechar menu de conversas"
            >
              ✕ Fechar
            </button>
          )}
          <ChatSidebar>
            <div className="chat-sessions-panel">
              <div className="chat-sessions-heading">
                <div><span className="eyebrow">HISTÓRICO</span><strong>Conversas ({sessions.length})</strong></div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <button type="button" className="chat-new-icon" onClick={handleCreateSession} title="Nova conversa" aria-label="Nova conversa"><Plus size={16} /></button>
                </div>
              </div>

              <label className="chat-session-search">
                <Search size={14} />
                <input aria-label="Buscar conversas" value={sessionQuery} onChange={event => setSessionQuery(event.target.value)} placeholder="Buscar conversas…" />
              </label>
              <div className="chat-session-list">
                {filteredSessions.length ? filteredSessions.map(item => (
                  <div
                    key={item.id}
                    className="chat-session-item"
                    onMouseEnter={() => setHoveredSessionId(item.id)}
                    onMouseLeave={() => setHoveredSessionId(null)}
                  >
                    <button
                      type="button"
                      className={`chat-session-btn ${item.id === sessionId ? 'session-active' : ''}`}
                      onClick={() => { onSelectSession(item.id); setShowMobileSessions(false) }}
                    >
                      <span className="chat-session-dot" />
                      <span>{item.title || 'Conversa'}</span>
                    </button>
                    {hoveredSessionId === item.id && (
                      <button
                        type="button"
                        className="chat-session-delete"
                        title="Excluir conversa"
                        aria-label="Excluir conversa"
                        onClick={e => { e.stopPropagation(); onDeleteSession(item.id) }}
                      >
                        <Trash2 size={13} />
                      </button>
                    )}
                  </div>
                )) : <span className="session-empty">Nenhuma conversa encontrada.</span>}
              </div>
            </div>
          </ChatSidebar>
        </div>

        <main className="chat-main-column">
          <header className="chat-main-header">
            <div className="chat-main-header-title">
              <div className="chat-header-orb-dot" />
              <div>
                <span className="eyebrow" style={{ fontSize: '9px' }}>JARVIS — CHAT</span>
                <strong className="chat-session-title">{sessions.find(item => item.id === sessionId)?.title || 'Nova conversa'}</strong>
              </div>
            </div>
            <div className="chat-main-header-actions">
              <button
                type="button"
                className="chat-export-icon chat-sessions-toggle"
                onClick={() => setShowMobileSessions(true)}
                title="Conversas"
                aria-label="Abrir conversas"
              >
                <MessageSquare size={15} />
              </button>
              <PlanningWorkspace sessionId={sessionId} messages={messages} />
              <div style={{ position: 'relative' }}>
                <button
                  className="chat-export-icon"
                  type="button"
                  disabled={!sessionId}
                  onClick={() => setShowExportMenu(!showExportMenu)}
                  title="Exportar conversa"
                  aria-label="Exportar conversa"
                >
                  <Download size={15} />
                </button>
                {showExportMenu && (
                  <div
                    style={{
                      position: 'absolute',
                      top: '100%',
                      right: 0,
                      marginTop: '8px',
                      background: 'rgba(10,12,24,0.97)',
                      border: '1px solid rgba(255,255,255,0.1)',
                      borderRadius: '8px',
                      padding: '4px',
                      minWidth: '180px',
                      zIndex: 100,
                      backdropFilter: 'blur(16px)',
                      boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
                    }}
                  >
                    <button
                      type="button"
                      onClick={() => { onCopySession(); setShowExportMenu(false) }}
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        background: 'transparent',
                        border: 'none',
                        color: '#fff',
                        cursor: 'pointer',
                        textAlign: 'left',
                        fontSize: '13px',
                        borderRadius: '4px',
                        transition: 'background 0.15s',
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.1)'}
                      onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                    >
                      📋 Copiar como Markdown
                    </button>
                    <button
                      type="button"
                      onClick={() => { onExportSession(); setShowExportMenu(false) }}
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        background: 'transparent',
                        border: 'none',
                        color: '#fff',
                        cursor: 'pointer',
                        textAlign: 'left',
                        fontSize: '13px',
                        borderRadius: '4px',
                        transition: 'background 0.15s',
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.1)'}
                      onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                    >
                      💾 Baixar como Markdown
                    </button>
                  </div>
                )}
              </div>
            </div>
          </header>

          <div className="chat-history" ref={chatHistoryRef}>
            {messages.length > maxVisibleMessages && (
              <button
                type="button"
                onClick={() => setMaxVisibleMessages(prev => prev + 25)}
                className="chat-load-more-btn"
                style={{
                  width: '100%',
                  textAlign: 'center',
                  padding: '8px',
                  fontSize: '12px',
                  color: 'var(--jarvis-cyan, #fbbf24)',
                  background: 'rgba(255, 255, 255, 0.04)',
                  border: '1px solid rgba(251, 191, 36, 0.2)',
                  borderRadius: '12px',
                  margin: '8px 0',
                  fontFamily: 'DM Mono, monospace',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                }}
              >
                ▲ Carregar mensagens anteriores ({messages.length - maxVisibleMessages} ocultas)
              </button>
            )}

            {visibleMessages.length ? visibleMessages.map(renderMessage) : !loading && !streamingReply ? (
              <div className="chat-answer"><p className="eyebrow">JARVIS</p><MessageRenderer content={answer} mode={chatMode} pendingScript={pendingScript} onRunPendingScript={() => onRunPendingScript().catch(() => undefined)} onSendText={text => onSendText(text).catch(() => undefined)} onCinemaRequest={onCinemaRequest} liveSearch={liveSearch} /></div>
            ) : null}
            {(loading || streamingReply) && (
              <article className="message assistant message-streaming">
                <small>JARVIS</small>
                <MessageRenderer content={streamingReply || 'Pensando…'} isStreaming liveText={liveReasoning} mode={chatMode} pendingScript={pendingScript} onRunPendingScript={() => onRunPendingScript().catch(() => undefined)} onSendText={text => onSendText(text).catch(() => undefined)} onCinemaRequest={onCinemaRequest} liveSearch={liveSearch} />
              </article>
            )}
          </div>

          {chatError && (
            <div style={{
              margin: '8px 16px',
              padding: '8px 12px',
              background: 'rgba(239, 68, 68, 0.12)',
              border: '1px solid rgba(239, 68, 68, 0.35)',
              borderRadius: '8px',
              color: '#f87171',
              fontSize: '12px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '8px',
            }}>
              <span>⚠️ {chatError}</span>
              {onClearChatError && (
                <button
                  type="button"
                  onClick={onClearChatError}
                  style={{ background: 'none', border: 'none', color: '#f87171', cursor: 'pointer', fontSize: '14px', padding: '0 4px' }}
                  title="Fechar"
                >
                  ✕
                </button>
              )}
            </div>
          )}

          <ChatComposer
            value={query}
            loading={loading}
            mode={chatMode}
            persona={persona}
            racingMode={racingMode}
            onRacingModeChange={setRacingMode}
            attachment={chatAttachment}
            recording={recording}
            onChange={onQueryChange}
            onModeChange={onModeChange}
            onPersonaChange={setPersona}
            onAttachment={onAttachment}
            onClearAttachment={onClearAttachment}
            onSubmit={onSubmit}
            onVoice={onVoice}
            onScreen={onScreen}
            onCinema={onCinema}
            onOpenLiveCall={onOpenLiveCall}
          />
        </main>
      </div>
    </section>
  )
}
