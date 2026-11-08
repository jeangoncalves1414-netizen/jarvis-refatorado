import { useEffect, useRef, useState } from 'react'
import { ArrowDown, ArrowUpRight, Code2, Copy, Download, Lightbulb, Search, Sparkles, Trash2, Volume2, X } from 'lucide-react'
import type { ChatMode } from '../components/ChatComposer'
import { WorkspaceComposer } from '../components/WorkspaceComposer'
import type { CommandHandlers } from '../commands/registry'
import { MessageRenderer } from '../components/chat/MessageRenderer'
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
  commandHandlers: CommandHandlers
  onOpenRun?: (id: string) => void
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
}


const suggestions = [
  { title: 'Explorar uma ideia', description: 'Transforme uma ideia em possibilidades', icon: Lightbulb, mode: 'general', prompt: 'Quero explorar uma ideia. Me ajude a organizar as possibilidades.' },
  { title: 'Pesquisar um assunto', description: 'Compare informações e encontre fontes', icon: Search, mode: 'research', prompt: 'Quero pesquisar um assunto e comparar fontes. O tema é: ' },
  { title: 'Planejar um projeto', description: 'Do primeiro passo ao plano de ação', icon: Sparkles, mode: 'planning', prompt: 'Me ajude a criar um plano de projeto com etapas e critérios de conclusão. Meu objetivo é: ' },
  { title: 'Construir com código', description: 'Crie, revise ou resolva um problema', icon: Code2, mode: 'coder', prompt: 'Quero ajuda com código. Meu contexto é: ' },
] as const

export function ChatPage(props: ChatPageProps) {
  const [maxVisible, setMaxVisible] = useState(25)
  const [following, setFollowing] = useState(true)
  const [feedback, setFeedback] = useState('')
  const history = useRef<HTMLDivElement>(null)
  const deleteDialog = useRef<HTMLDialogElement>(null)
  const empty = !props.messages.length && !props.loading && !props.streamingReply
  useEffect(() => { setMaxVisible(25); setFollowing(true); setFeedback('') }, [props.sessionId])
  useEffect(() => { if (following && history.current) history.current.scrollTop = history.current.scrollHeight }, [props.messages.length, props.streamingReply, following])
  const renderContent = (content: string, streaming = false) => <MessageRenderer content={content} mode={props.chatMode} isStreaming={streaming} liveText={streaming ? props.liveReasoning : undefined} pendingScript={props.pendingScript} onRunPendingScript={() => props.onRunPendingScript().catch(() => setFeedback('Não foi possível executar a ação.'))} onSendText={text => props.onSendText(text).catch(() => { setFeedback('Não foi possível enviar.'); return '' })} onCinemaRequest={props.onCinemaRequest} liveSearch={streaming ? props.liveSearch : null} />
  const copy = async (text: string) => { try { await navigator.clipboard.writeText(text); setFeedback('Mensagem copiada.') } catch { setFeedback('Não foi possível acessar a área de transferência.') } }
  return <section className={`ws-chat ${empty ? 'is-empty' : ''}`}>
    <header className="ws-chat-header"><div><span className="ws-overline">CONVERSA</span><strong>{props.sessions.find(item => item.id === props.sessionId)?.title || 'Nova conversa'}</strong></div><div className="ws-chat-actions"><PlanningWorkspace sessionId={props.sessionId} messages={props.messages} /><button className="ws-icon-button" title="Copiar conversa" aria-label="Copiar conversa" disabled={!props.messages.length} onClick={props.onCopySession}><Copy size={16} /></button><button className="ws-icon-button" title="Exportar Markdown" aria-label="Exportar conversa" disabled={!props.messages.length} onClick={props.onExportSession}><Download size={16} /></button><button className="ws-icon-button" title="Excluir conversa" aria-label="Excluir conversa" disabled={!props.sessionId || props.loading} onClick={() => deleteDialog.current?.showModal()}><Trash2 size={16} /></button></div></header>
    <div className="ws-chat-history" ref={history} onScroll={() => { const element = history.current; if (element) setFollowing(element.scrollHeight - element.scrollTop - element.clientHeight < 80) }}>
      {empty ? <div className="ws-welcome"><div className="ws-welcome-mark"><Sparkles size={30} strokeWidth={1.3} /></div><span className="ws-overline">UM ESPAÇO PARA SUAS IDEIAS</span><h1>O que vamos fazer hoje?</h1><p>Uma conversa pode ser o começo de algo maior.<br />Pesquise, crie e coloque seus planos em movimento.</p><div className="ws-suggestions">{suggestions.map(item => <button key={item.title} onClick={() => { props.onModeChange(item.mode); props.onQueryChange(item.prompt); document.querySelector<HTMLTextAreaElement>('.ws-composer textarea')?.focus() }}><item.icon size={19} /><ArrowUpRight size={14} className="suggestion-arrow" /><strong>{item.title}</strong><span>{item.description}</span></button>)}</div>{props.answer && !['Olá. Estou pronto para ajudar.', 'Ola. Estou pronto para ajudar.', 'Nova conversa iniciada.', 'Sessão carregada.'].includes(props.answer) && <div className="ws-answer-note">{renderContent(props.answer)}</div>}</div> : <div className="ws-message-list">
        {props.messages.length > maxVisible && <button className="ws-button ws-load-more" onClick={() => { setFollowing(false); setMaxVisible(value => value + 25) }}>Carregar mensagens anteriores</button>}
        {props.messages.slice(-maxVisible).map((message, index) => <article key={props.messages.length - Math.min(props.messages.length, maxVisible) + index} className={`ws-message ${message.role}`}><div className="ws-message-label">{message.role === 'assistant' && <Sparkles size={15} />}<span>{message.role === 'user' ? 'Você' : 'Assistente'}</span></div><div className="ws-message-content">{renderContent(message.content)}</div>{message.role === 'assistant' && <div className="ws-message-actions">{message.run_id && props.onOpenRun && <button className="ws-text-button" onClick={() => props.onOpenRun?.(message.run_id!)}>Ver execução <ArrowUpRight size={14} /></button>}<button className="ws-icon-button" aria-label="Copiar resposta" onClick={() => void copy(message.content)}><Copy size={14} /></button>{props.onSpeakText && <button className="ws-icon-button" aria-label="Ouvir resposta" onClick={() => props.onSpeakText?.(message.content)}><Volume2 size={14} /></button>}</div>}</article>)}
        {(props.loading || props.streamingReply) && <article className="ws-message assistant"><div className="ws-message-label"><Sparkles size={15} /><span>Assistente</span><span className="ws-generating">Respondendo</span></div>{renderContent(props.streamingReply || 'Pensando…', true)}</article>}
      </div>}
    </div>
    {!following && !empty && <button className="ws-jump-latest" aria-label="Ir para a última mensagem" onClick={() => setFollowing(true)}><ArrowDown size={16} /> Últimas mensagens</button>}
    {props.chatError && <div className="ws-error" role="alert"><span>{props.chatError}</span><button className="ws-icon-button" aria-label="Fechar erro" onClick={props.onClearChatError}><X size={16} /></button></div>}
    {feedback && <div className="ws-feedback" role="status">{feedback}<button aria-label="Fechar aviso" onClick={() => setFeedback('')}><X size={13} /></button></div>}
    <WorkspaceComposer supportsRuns={!!props.onOpenRun} commandHandlers={props.commandHandlers} value={props.query} loading={props.loading} mode={props.chatMode} attachment={props.chatAttachment} recording={props.recording} onChange={props.onQueryChange} onModeChange={props.onModeChange} onAttachment={props.onAttachment} onClearAttachment={props.onClearAttachment} onSubmit={props.onSubmit} onVoice={props.onVoice} onScreen={props.onScreen} onCinema={props.onCinema} onOpenLiveCall={props.onOpenLiveCall} />
    <dialog ref={deleteDialog} className="ws-confirm-dialog" aria-labelledby="delete-chat-title"><h2 id="delete-chat-title">Excluir esta conversa?</h2><p>As mensagens desta conversa serão removidas. Exporte uma cópia se quiser guardá-las.</p><div><button className="ws-button" onClick={() => deleteDialog.current?.close()}>Manter conversa</button><button className="ws-button danger" onClick={() => { props.onDeleteSession(props.sessionId); deleteDialog.current?.close() }}>Excluir conversa</button></div></dialog>
  </section>
}
