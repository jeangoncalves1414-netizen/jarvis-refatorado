import { useMemo, useState } from 'react'
import { Download, Plus, Search } from 'lucide-react'
import { ChatComposer, type ChatMode } from '../components/ChatComposer'
import { JarvisOrb } from '../components/JarvisOrb'
import { MessageRenderer } from '../components/chat/MessageRenderer'
import { ChatSidebar } from '../components/ChatSidebar'
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
  onExportSession: () => void
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
  onSendText: (text: string, mode?: ChatMode) => Promise<void>
  onCinemaRequest: (payload: CinemaRequestPayload) => void
  onRunPendingScript: () => Promise<void>
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
  query,
  chatMode,
  chatAttachment,
  recording,
  pendingScript,
  onSelectSession,
  onCreateSession,
  onExportSession,
  onOpenLiveCall,
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
}: ChatPageProps) {
  const [sessionQuery, setSessionQuery] = useState('')
  const handleCreateSession = () => {
    void Promise.resolve(onCreateSession()).catch(() => undefined)
  }
  const filteredSessions = useMemo(() => {
    const normalized = sessionQuery.trim().toLocaleLowerCase('pt-BR')
    if (!normalized) return sessions
    return sessions.filter(item => (item.title || 'Conversa').toLocaleLowerCase('pt-BR').includes(normalized))
  }, [sessionQuery, sessions])

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

  return (
    <section className="chat-card chat-card-modern">
      {(loading || streamingReply) && <JarvisOrb size={56} className="chat-orb-indicator" listening />}
      <div className="chat-workspace">
        <ChatSidebar>
          <div className="chat-sessions-panel">
            <div className="chat-sessions-heading">
              <div><span className="eyebrow">HISTÓRICO</span><strong>Conversas</strong></div>
              <button type="button" className="chat-new-icon" onClick={handleCreateSession} title="Nova conversa" aria-label="Nova conversa"><Plus size={16} /></button>
            </div>
            <label className="chat-session-search">
              <Search size={14} />
              <input aria-label="Buscar conversas" value={sessionQuery} onChange={event => setSessionQuery(event.target.value)} placeholder="Buscar conversas…" />
            </label>
            <div className="chat-session-list">
              {filteredSessions.length ? filteredSessions.map(item => (
                <button key={item.id} type="button" className={item.id === sessionId ? 'session-active' : ''} onClick={() => onSelectSession(item.id)}>
                  <span className="chat-session-dot" /><span>{item.title || 'Conversa'}</span>
                </button>
              )) : <span className="session-empty">Nenhuma conversa encontrada.</span>}
            </div>
          </div>
        </ChatSidebar>

        <main className="chat-main-column">
          <header className="chat-main-header">
            <div><span className="eyebrow">JARVIS</span><strong>{sessions.find(item => item.id === sessionId)?.title || 'Nova conversa'}</strong></div>
            <button className="chat-export-icon" type="button" disabled={!sessionId} onClick={onExportSession} title="Exportar conversa" aria-label="Exportar conversa"><Download size={15} /></button>
          </header>
          <div className="chat-history">
            {messages.length ? messages.map(renderMessage) : !loading && !streamingReply ? (
              <div className="chat-answer"><p className="eyebrow">JARVIS</p><MessageRenderer content={answer} mode={chatMode} pendingScript={pendingScript} onRunPendingScript={() => onRunPendingScript().catch(() => undefined)} onSendText={text => onSendText(text).catch(() => undefined)} onCinemaRequest={onCinemaRequest} liveSearch={liveSearch} /></div>
            ) : null}
            {(loading || streamingReply) && (
              <article className="message assistant message-streaming">
                <small>JARVIS</small>
                <MessageRenderer content={streamingReply || 'Pensando…'} isStreaming liveText={liveReasoning} mode={chatMode} pendingScript={pendingScript} onRunPendingScript={() => onRunPendingScript().catch(() => undefined)} onSendText={text => onSendText(text).catch(() => undefined)} onCinemaRequest={onCinemaRequest} liveSearch={liveSearch} />
              </article>
            )}
          </div>
        </main>
      </div>
      <ChatComposer value={query} loading={loading} mode={chatMode} attachment={chatAttachment} recording={recording} onChange={onQueryChange} onModeChange={onModeChange} onAttachment={onAttachment} onClearAttachment={onClearAttachment} onSubmit={onSubmit} onVoice={onVoice} onScreen={onScreen} onCinema={onCinema} onOpenLiveCall={onOpenLiveCall} />
    </section>
  )
}
