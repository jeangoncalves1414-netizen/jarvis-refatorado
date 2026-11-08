import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { ArrowUp, AudioLines, Film, LoaderCircle, Mic, Monitor, Paperclip, X } from 'lucide-react'
import type { ChatMode } from './ChatComposer'
import { parseSlashInput, runCommand, searchSlashCommands, type CommandDef, type CommandHandlers } from '../commands/registry'

type Props = {
  supportsRuns: boolean
  commandHandlers: CommandHandlers
  value: string; loading: boolean; mode: ChatMode; recording: boolean
  attachment: { name: string; dataUrl: string } | null
  onChange: (value: string) => void; onModeChange: (mode: ChatMode) => void
  onAttachment: (file: File) => void; onClearAttachment: () => void; onSubmit: () => void
  onVoice: () => void; onScreen: () => void; onCinema: () => void; onOpenLiveCall: () => void
}
export function WorkspaceComposer(props: Props) {
  const textarea = useRef<HTMLTextAreaElement>(null)
  const file = useRef<HTMLInputElement>(null)
  const menu = useRef<HTMLDivElement>(null)
  const [menuIndex, setMenuIndex] = useState(0)
  const [menuDismissed, setMenuDismissed] = useState(false)
  const [hint, setHint] = useState('')
  const canSend = !props.loading && Boolean(props.value.trim() || props.attachment)
  // O menu "/" só existe enquanto o texto é "/" seguido de uma palavra ainda sem espaço.
  const slashQuery = /^\/(\S*)$/.exec(props.value)
  const matches = slashQuery ? searchSlashCommands(slashQuery[1]) : []
  const isSlash = Boolean(slashQuery)
  const menuOpen = isSlash && !menuDismissed && matches.length > 0
  useEffect(() => { if (textarea.current) { textarea.current.style.height = 'auto'; textarea.current.style.height = `${Math.min(textarea.current.scrollHeight, 180)}px` } }, [props.value])
  useEffect(() => { setMenuIndex(0); setHint(''); setMenuDismissed(false) }, [props.value])
  useEffect(() => { menu.current?.querySelector<HTMLElement>('[aria-selected="true"]')?.scrollIntoView({ block: 'nearest' }) }, [menuIndex, menuOpen])
  // Comando reconhecido roda no navegador e nunca vai ao modelo; "/xyz" desconhecido só mostra uma dica.
  const runSlash = (command: CommandDef, args: string) => {
    props.onChange('')
    runCommand(command, props.commandHandlers, args)
    textarea.current?.focus()
  }
  const submit = () => {
    const parsed = parseSlashInput(props.value)
    if (parsed.kind === 'known') return runSlash(parsed.command, parsed.args)
    if (parsed.kind === 'unknown') return setHint(`Comando desconhecido: /${parsed.word}. Digite / para ver os comandos.`)
    if (canSend) props.onSubmit()
  }
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (menuOpen) {
      if (event.key === 'ArrowDown') { event.preventDefault(); setMenuIndex(index => (index + 1) % matches.length); return }
      if (event.key === 'ArrowUp') { event.preventDefault(); setMenuIndex(index => (index - 1 + matches.length) % matches.length); return }
      if (event.key === 'Escape') { event.preventDefault(); setMenuDismissed(true); return }
      if ((event.key === 'Enter' || event.key === 'Tab') && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); runSlash(matches[menuIndex] ?? matches[0], ''); return }
    }
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); submit() }
  }
  return <div className="ws-composer-wrap">
    {menuOpen && <div className="ws-slash-menu" ref={menu} role="listbox" id="ws-slash-menu" aria-label="Comandos" onMouseDown={event => event.preventDefault()}>
      {matches.map((command, index) => <div key={command.id} role="option" id={`ws-slash-${command.id}`} aria-selected={index === menuIndex} className={`ws-slash-item${index === menuIndex ? ' selected' : ''}`} onMouseEnter={() => setMenuIndex(index)} onClick={() => runSlash(command, '')}>
        <command.icon size={15} /><span className="ws-slash-text"><strong>{command.label}</strong><span>{command.description}</span></span><code>/{command.slash}{command.argHint ? ` ${command.argHint}` : ''}</code>
      </div>)}
    </div>}
    <form className="ws-composer" onSubmit={event => { event.preventDefault(); submit() }}>
      {props.attachment && <div className="ws-attachment"><img src={props.attachment.dataUrl} alt="Imagem anexada" /><span>{props.attachment.name}</span><button type="button" aria-label="Remover imagem" onClick={props.onClearAttachment}><X size={15} /></button></div>}
      <textarea ref={textarea} aria-label="Mensagem para o agente" aria-autocomplete="list" aria-expanded={menuOpen} aria-controls={menuOpen ? 'ws-slash-menu' : undefined} aria-activedescendant={menuOpen && matches[menuIndex] ? `ws-slash-${matches[menuIndex].id}` : undefined} placeholder="Pergunte, explore uma ideia ou descreva uma tarefa…" rows={2} value={props.value} onChange={event => props.onChange(event.target.value)} onFocus={() => setMenuDismissed(false)} onKeyDown={onKeyDown} />
      <div className="ws-composer-toolbar"><div className="ws-composer-tools">
        <input ref={file} type="file" accept="image/*" hidden onChange={event => { const selected = event.target.files?.[0]; if (selected) props.onAttachment(selected); event.target.value = '' }} />
        <button type="button" className="ws-icon-button" aria-label="Anexar imagem" title="Anexar imagem (até 8 MB)" onClick={() => file.current?.click()}><Paperclip size={18} /></button>
        <select aria-label="Modo de conversa" value={props.mode} onChange={event => props.onModeChange(event.target.value as ChatMode)}><option value="general">Conversa</option><option value="planning">Planejamento</option><option value="research">Pesquisa</option><option value="coder">Código</option><option value="browser">Navegação</option>{props.supportsRuns && <option value="react">Execução por etapas</option>}</select>
        <details className="ws-composer-more"><summary aria-label="Mais ferramentas">•••</summary><div><button type="button" onClick={props.onScreen}><Monitor size={15} /> Analisar tela</button><button type="button" onClick={props.onCinema}><Film size={15} /> Cinema</button></div></details>
      </div><div className="ws-composer-tools"><button type="button" className={`ws-icon-button ${props.recording ? 'recording' : ''}`} aria-label={props.recording ? 'Parar gravação' : 'Ditar mensagem'} aria-pressed={props.recording} onClick={props.onVoice}><Mic size={18} /></button><button type="button" className="ws-icon-button" aria-label="Abrir conversa por voz" title="Conversa por voz" onClick={props.onOpenLiveCall}><AudioLines size={19} /></button><button className="ws-send" disabled={!canSend} aria-label={props.loading ? 'Aguardando resposta' : 'Enviar mensagem'}>{props.loading ? <LoaderCircle size={19} className="ws-spin" /> : <ArrowUp size={20} />}</button></div></div>
    </form>
    <div className="ws-composer-caption">{hint ? <span className="ws-slash-hint" role="status">{hint}</span> : <span>{props.recording ? 'Microfone em gravação' : props.loading ? 'Resposta em andamento · as ações podem ser acompanhadas em Execuções' : 'Você conduz. O agente ajuda a realizar.'}</span>}<span>Shift + Enter para nova linha · / para comandos</span></div>
  </div>
}
