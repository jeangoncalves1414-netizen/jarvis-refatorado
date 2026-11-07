import { useEffect, useRef } from 'react'
import { ArrowUp, AudioLines, Film, LoaderCircle, Mic, Monitor, Paperclip, X } from 'lucide-react'
import type { ChatMode } from './ChatComposer'

type Props = {
  supportsRuns: boolean
  value: string; loading: boolean; mode: ChatMode; recording: boolean
  attachment: { name: string; dataUrl: string } | null
  onChange: (value: string) => void; onModeChange: (mode: ChatMode) => void
  onAttachment: (file: File) => void; onClearAttachment: () => void; onSubmit: () => void
  onVoice: () => void; onScreen: () => void; onCinema: () => void; onOpenLiveCall: () => void
}
export function WorkspaceComposer(props: Props) {
  const textarea = useRef<HTMLTextAreaElement>(null)
  const file = useRef<HTMLInputElement>(null)
  const canSend = !props.loading && Boolean(props.value.trim() || props.attachment)
  useEffect(() => { if (textarea.current) { textarea.current.style.height = 'auto'; textarea.current.style.height = `${Math.min(textarea.current.scrollHeight, 180)}px` } }, [props.value])
  return <div className="ws-composer-wrap">
    <form className="ws-composer" onSubmit={event => { event.preventDefault(); if (canSend) props.onSubmit() }}>
      {props.attachment && <div className="ws-attachment"><img src={props.attachment.dataUrl} alt="Imagem anexada" /><span>{props.attachment.name}</span><button type="button" aria-label="Remover imagem" onClick={props.onClearAttachment}><X size={15} /></button></div>}
      <textarea ref={textarea} aria-label="Mensagem para o agente" placeholder="Pergunte, explore uma ideia ou descreva uma tarefa…" rows={2} value={props.value} onChange={event => props.onChange(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); if (canSend) props.onSubmit() } }} />
      <div className="ws-composer-toolbar"><div className="ws-composer-tools">
        <input ref={file} type="file" accept="image/*" hidden onChange={event => { const selected = event.target.files?.[0]; if (selected) props.onAttachment(selected); event.target.value = '' }} />
        <button type="button" className="ws-icon-button" aria-label="Anexar imagem" title="Anexar imagem (até 8 MB)" onClick={() => file.current?.click()}><Paperclip size={18} /></button>
        <select aria-label="Modo de conversa" value={props.mode} onChange={event => props.onModeChange(event.target.value as ChatMode)}><option value="general">Conversa</option><option value="planning">Planejamento</option><option value="research">Pesquisa</option><option value="coder">Código</option><option value="browser">Navegação</option>{props.supportsRuns && <option value="react">Execução por etapas</option>}</select>
        <details className="ws-composer-more"><summary aria-label="Mais ferramentas">•••</summary><div><button type="button" onClick={props.onScreen}><Monitor size={15} /> Analisar tela</button><button type="button" onClick={props.onCinema}><Film size={15} /> Cinema</button></div></details>
      </div><div className="ws-composer-tools"><button type="button" className={`ws-icon-button ${props.recording ? 'recording' : ''}`} aria-label={props.recording ? 'Parar gravação' : 'Ditar mensagem'} aria-pressed={props.recording} onClick={props.onVoice}><Mic size={18} /></button><button type="button" className="ws-icon-button" aria-label="Abrir conversa por voz" title="Conversa por voz" onClick={props.onOpenLiveCall}><AudioLines size={19} /></button><button className="ws-send" disabled={!canSend} aria-label={props.loading ? 'Aguardando resposta' : 'Enviar mensagem'}>{props.loading ? <LoaderCircle size={19} className="ws-spin" /> : <ArrowUp size={20} />}</button></div></div>
    </form>
    <div className="ws-composer-caption"><span>{props.recording ? 'Microfone em gravação' : props.loading ? 'Resposta em andamento · as ações podem ser acompanhadas em Execuções' : 'Você conduz. O agente ajuda a realizar.'}</span><span>Shift + Enter para nova linha</span></div>
  </div>
}
