import { useEffect, useState } from 'react'
import { Switch } from './Switch'
import { usePopups } from '../popups/PopupProvider'
import { POPUP_SETTINGS_DEFAULTS, type PopupSettings as PopupConfig } from '../popups/types'

/** Configuração dos popups do agente (lote 6): mostrar, automáticos, tempo na tela e quantos ao mesmo tempo. */

function clampInt(value: string, low: number, high: number) {
  const number = Math.round(Number(value))
  if (!Number.isFinite(number)) return low
  return Math.min(high, Math.max(low, number))
}

export function PopupSettings() {
  const popups = usePopups()
  const [config, setConfig] = useState<PopupConfig>(POPUP_SETTINGS_DEFAULTS)
  const [status, setStatus] = useState<'loading' | 'idle' | 'saving' | 'saved' | 'error'>('loading')
  const [message, setMessage] = useState('')

  useEffect(() => {
    let cancelled = false
    fetch('/api/settings/popups')
      .then(async response => {
        const data = await response.json().catch(() => ({}))
        if (!response.ok || !data.ok || !data.settings) throw new Error(data.error || '')
        if (!cancelled) { setConfig({ ...POPUP_SETTINGS_DEFAULTS, ...data.settings }); setStatus('idle') }
      })
      .catch(error => {
        if (cancelled) return
        setStatus('error')
        setMessage(error instanceof Error && error.message ? error.message : 'Não foi possível carregar a configuração dos popups. Verifique se o backend está ligado.')
      })
    return () => { cancelled = true }
  }, [])

  const edit = (patch: Partial<PopupConfig>) => {
    setConfig(previous => ({ ...previous, ...patch }))
    if (status === 'saved' || status === 'error') { setStatus('idle'); setMessage('') }
  }

  const save = async () => {
    setStatus('saving')
    setMessage('')
    try {
      const response = await fetch('/api/settings/popups', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok || !data.ok || !data.settings) throw new Error(data.error || '')
      const saved = { ...POPUP_SETTINGS_DEFAULTS, ...data.settings }
      setConfig(saved)
      popups.configure(saved)
      setStatus('saved')
      setMessage('Configuração dos popups salva.')
    } catch (error) {
      setStatus('error')
      setMessage(error instanceof Error && error.message && error.message !== 'Failed to fetch' ? error.message : 'Não foi possível salvar a configuração dos popups. Verifique se o backend está ligado.')
    }
  }

  const busy = status === 'loading' || status === 'saving'

  return (
    <article className="settings-card popup-settings-card" style={{ gridColumn: '1 / -1' }}>
      <p className="eyebrow">POPUPS</p>
      <h2>Popups animados</h2>
      <p>Cartões no canto da tela mostram o que o agente fez (hábitos, agenda, água, anotações). Os números vêm sempre dos seus dados, não do texto do modelo.</p>
      <Switch label="Mostrar popups" description="Desligado, o agente não mostra popups na conversa nem na ligação. Os comandos com / continuam abrindo." checked={config.enabled} disabled={busy} onChange={checked => edit({ enabled: checked })} glowColor="green" />
      <Switch label="Popups automáticos" description="Mostra a confirmação de hábitos, gastos, receitas, anotações e outros registros feitos pelo agente." checked={config.auto} disabled={busy || !config.enabled} onChange={checked => edit({ auto: checked })} glowColor="green" />
      <div className="agent-loop-limits">
        <label className="field-label">Fechar sozinho após (s, 0 = fica até fechar)
          <input type="number" min={0} max={120} step={1} value={config.ttl_seconds} disabled={busy} onChange={event => edit({ ttl_seconds: clampInt(event.target.value, 0, 120) })} />
        </label>
        <label className="field-label">Máximo na tela (1 a 5)
          <input type="number" min={1} max={5} step={1} value={config.max_visible} disabled={busy} onChange={event => edit({ max_visible: clampInt(event.target.value, 1, 5) })} />
        </label>
      </div>
      <button className="outline-button" type="button" disabled={busy} onClick={() => void save()}>{status === 'saving' ? 'Salvando…' : 'Salvar configuração dos popups'}</button>
      {message && <p className={status === 'error' ? 'settings-error' : 'settings-muted'} role={status === 'error' ? 'alert' : 'status'}>{message}</p>}
    </article>
  )
}
