import { useEffect, useState } from 'react'
import { Switch } from './Switch'

/** Contexto da situação (fase contexto 1): o que o agente sabe do momento, sem chamada extra ao modelo. */

type SourceKey = 'datetime' | 'window' | 'media' | 'calendar' | 'lifeos' | 'tasks' | 'routines' | 'pc'
type ContextConfig = {
  enabled: boolean
  show_in_chat: boolean
  send_window_titles: boolean
  sources: Record<SourceKey, boolean>
}

const SOURCES: { key: SourceKey; label: string; description: string }[] = [
  { key: 'datetime', label: 'Data e hora', description: 'Dia da semana, data, hora e período do dia (horário de Brasília).' },
  { key: 'window', label: 'Janela em primeiro plano', description: 'O app que você está usando agora.' },
  { key: 'media', label: 'Música tocando', description: 'Artista e música do Spotify, quando estiver tocando.' },
  { key: 'calendar', label: 'Próximo compromisso', description: 'O próximo evento de hoje na agenda.' },
  { key: 'lifeos', label: 'Água e hábitos', description: 'Água bebida contra a meta e hábitos feitos hoje.' },
  { key: 'tasks', label: 'Tarefas pendentes', description: 'Quantas tarefas ainda estão abertas.' },
  { key: 'routines', label: 'Rotinas em andamento', description: 'Rotinas rodando agora, quando houver.' },
  { key: 'pc', label: 'Estado do PC', description: 'Só aparece com bateria abaixo de 30% sem carregar ou CPU acima de 85%.' },
]

const DEFAULTS: ContextConfig = {
  enabled: true,
  show_in_chat: true,
  send_window_titles: false,
  sources: { datetime: true, window: true, media: true, calendar: true, lifeos: true, tasks: true, routines: true, pc: true },
}

function merge(settings: Partial<ContextConfig> | undefined): ContextConfig {
  return { ...DEFAULTS, ...(settings || {}), sources: { ...DEFAULTS.sources, ...(settings?.sources || {}) } }
}

export function ContextSettings() {
  const [config, setConfig] = useState<ContextConfig>(DEFAULTS)
  const [status, setStatus] = useState<'loading' | 'idle' | 'saving' | 'saved' | 'error'>('loading')
  const [message, setMessage] = useState('')

  useEffect(() => {
    let cancelled = false
    fetch('/api/settings/context')
      .then(async response => {
        const data = await response.json().catch(() => ({}))
        if (!response.ok || !data.ok || !data.settings) throw new Error(data.error || '')
        if (!cancelled) { setConfig(merge(data.settings)); setStatus('idle') }
      })
      .catch(error => {
        if (cancelled) return
        setStatus('error')
        setMessage(error instanceof Error && error.message ? error.message : 'Não foi possível carregar a configuração do contexto. Verifique se o backend está ligado.')
      })
    return () => { cancelled = true }
  }, [])

  const edit = (patch: Partial<ContextConfig>) => {
    setConfig(previous => ({ ...previous, ...patch }))
    if (status === 'saved' || status === 'error') { setStatus('idle'); setMessage('') }
  }

  const save = async () => {
    setStatus('saving')
    setMessage('')
    try {
      const response = await fetch('/api/settings/context', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok || !data.ok || !data.settings) throw new Error(data.error || '')
      setConfig(merge(data.settings))
      setStatus('saved')
      setMessage('Configuração do contexto salva.')
    } catch (error) {
      setStatus('error')
      setMessage(error instanceof Error && error.message && error.message !== 'Failed to fetch' ? error.message : 'Não foi possível salvar a configuração do contexto. Verifique se o backend está ligado.')
    }
  }

  const busy = status === 'loading' || status === 'saving'
  const off = busy || !config.enabled

  return (
    <article className="settings-card context-settings-card" style={{ gridColumn: '1 / -1' }}>
      <p className="eyebrow">CONTEXTO</p>
      <h2>Contexto da situação</h2>
      <p>Antes de cada pedido, o agente recebe um resumo curto do momento (até 600 caracteres), montado no seu PC sem chamada extra ao modelo. Vale para o chat, a ligação de voz e o loop agêntico.</p>
      <Switch label="Usar contexto da situação" description="Desligado, nenhum resumo do momento é enviado ao modelo." checked={config.enabled} disabled={busy} onChange={checked => edit({ enabled: checked })} glowColor="green" />
      <Switch label="Mostrar 'Contexto usado' no chat" description="Mostra abaixo da resposta um detalhe com o que foi enviado. Some ao recarregar a conversa." checked={config.show_in_chat} disabled={off} onChange={checked => edit({ show_in_chat: checked })} glowColor="green" />
      {SOURCES.map(source => (
        <Switch key={source.key} label={source.label} description={source.description} checked={config.sources[source.key]} disabled={off} onChange={checked => edit({ sources: { ...config.sources, [source.key]: checked } })} glowColor="blue" />
      ))}
      <Switch label="Enviar títulos de janelas" description="Desligado, só o nome do app em primeiro plano é enviado (ex.: Chrome). Ligado, o título da janela também vai, cortado em 60 caracteres, e pode conter nomes de arquivos ou páginas." checked={config.send_window_titles} disabled={off || !config.sources.window} onChange={checked => edit({ send_window_titles: checked })} glowColor="purple" />
      <button className="outline-button" type="button" disabled={busy} onClick={() => void save()}>{status === 'saving' ? 'Salvando…' : 'Salvar configuração do contexto'}</button>
      {message && <p className={status === 'error' ? 'settings-error' : 'settings-muted'} role={status === 'error' ? 'alert' : 'status'}>{message}</p>}
    </article>
  )
}
