import { useEffect, useState } from 'react'
import { Switch } from './Switch'

/** Configuração do loop agêntico (lote 6): quando o agente planeja, age, confere e continua sozinho. */
export type AgentLoopMode = 'auto' | 'always' | 'off'
export type AgentLoopConfig = { mode: AgentLoopMode; max_steps: number; max_model_calls: number; auto_verify: boolean }

const DEFAULTS: AgentLoopConfig = { mode: 'auto', max_steps: 8, max_model_calls: 10, auto_verify: true }
const MODE_HELP: Record<AgentLoopMode, string> = {
  auto: 'Usa o loop quando o pedido tem várias partes ("adiciona… e depois agenda…"). Pedidos simples seguem direto.',
  always: 'Todo pedido da conversa passa pelo loop. Gasta mais chamadas ao modelo.',
  off: 'Nunca usa o loop na conversa. O modo "Execução por etapas" continua funcionando.',
}

function clampInt(value: string, low: number, high: number) {
  const number = Math.round(Number(value))
  if (!Number.isFinite(number)) return low
  return Math.min(high, Math.max(low, number))
}

export function AgentLoopSettings() {
  const [config, setConfig] = useState<AgentLoopConfig>(DEFAULTS)
  const [status, setStatus] = useState<'loading' | 'idle' | 'saving' | 'saved' | 'error'>('loading')
  const [message, setMessage] = useState('')

  useEffect(() => {
    let cancelled = false
    fetch('/api/settings/agent-loop')
      .then(async response => {
        const data = await response.json().catch(() => ({}))
        if (!response.ok || !data.ok || !data.settings) throw new Error(data.error || '')
        if (!cancelled) { setConfig({ ...DEFAULTS, ...data.settings }); setStatus('idle') }
      })
      .catch(error => {
        if (cancelled) return
        setStatus('error')
        setMessage(error instanceof Error && error.message ? error.message : 'Não foi possível carregar a configuração do agente. Verifique se o backend está ligado.')
      })
    return () => { cancelled = true }
  }, [])

  const edit = (patch: Partial<AgentLoopConfig>) => {
    setConfig(previous => ({ ...previous, ...patch }))
    if (status === 'saved' || status === 'error') { setStatus('idle'); setMessage('') }
  }

  const save = async () => {
    setStatus('saving')
    setMessage('')
    try {
      const response = await fetch('/api/settings/agent-loop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok || !data.ok || !data.settings) throw new Error(data.error || '')
      setConfig({ ...DEFAULTS, ...data.settings })
      setStatus('saved')
      setMessage('Configuração do agente salva.')
    } catch (error) {
      setStatus('error')
      setMessage(error instanceof Error && error.message && error.message !== 'Failed to fetch' ? error.message : 'Não foi possível salvar a configuração do agente. Verifique se o backend está ligado.')
    }
  }

  const busy = status === 'loading' || status === 'saving'

  return (
    <article className="settings-card agent-loop-card" style={{ gridColumn: '1 / -1' }}>
      <p className="eyebrow">LOOP AGÊNTICO</p>
      <h2>Execução em várias etapas</h2>
      <p>O agente planeja, executa pela Central, confere o resultado e continua sozinho até terminar. Etapas que pedem aprovação esperam por você e depois ele segue.</p>
      <fieldset className="agent-loop-modes" disabled={busy}>
        <legend className="field-label">Quando usar</legend>
        {(['auto', 'always', 'off'] as const).map(mode => (
          <label key={mode} className="agent-loop-mode">
            <input type="radio" name="agent-loop-mode" value={mode} checked={config.mode === mode} onChange={() => edit({ mode })} />
            <span><strong>{mode === 'auto' ? 'Automático' : mode === 'always' ? 'Sempre' : 'Desligado'}</strong><small>{MODE_HELP[mode]}</small></span>
          </label>
        ))}
      </fieldset>
      <div className="agent-loop-limits">
        <label className="field-label">Limite de etapas (1 a 20)
          <input type="number" min={1} max={20} step={1} value={config.max_steps} disabled={busy} onChange={event => edit({ max_steps: clampInt(event.target.value, 1, 20) })} />
        </label>
        <label className="field-label">Limite de chamadas ao modelo (1 a 30)
          <input type="number" min={1} max={30} step={1} value={config.max_model_calls} disabled={busy} onChange={event => edit({ max_model_calls: clampInt(event.target.value, 1, 30) })} />
        </label>
      </div>
      <Switch label="Verificação automática" description="Depois de cada escrita, relê o dado (sem chamar o modelo) para confirmar que ficou salvo." checked={config.auto_verify} disabled={busy} onChange={checked => edit({ auto_verify: checked })} glowColor="green" />
      <button className="outline-button" type="button" disabled={busy} onClick={() => void save()}>{status === 'saving' ? 'Salvando…' : 'Salvar configuração do agente'}</button>
      {message && <p className={status === 'error' ? 'settings-error' : 'settings-muted'} role={status === 'error' ? 'alert' : 'status'}>{message}</p>}
    </article>
  )
}
