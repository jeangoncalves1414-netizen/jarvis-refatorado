import { useEffect, useState } from 'react'
import { Switch } from './Switch'

export type ResourceConfig = {
  enabled: boolean
  threshold: number
  for_seconds: number
}

export type EventSettings = {
  enabled: boolean
  interval_seconds: number
  cpu: ResourceConfig
  ram: ResourceConfig
  disk: ResourceConfig
  disk_path: string
  cooldown_minutes: number
}

const DEFAULTS: EventSettings = {
  enabled: true,
  interval_seconds: 15,
  cpu: { enabled: false, threshold: 90, for_seconds: 120 },
  ram: { enabled: false, threshold: 90, for_seconds: 120 },
  disk: { enabled: false, threshold: 95, for_seconds: 120 },
  disk_path: 'C:\\',
  cooldown_minutes: 30,
}

function clampInt(value: string, low: number, high: number) {
  const number = Math.round(Number(value))
  if (!Number.isFinite(number)) return low
  return Math.min(high, Math.max(low, number))
}

export function EventAlertsSettings() {
  const [settings, setSettings] = useState<EventSettings>(DEFAULTS)
  const [status, setStatus] = useState<'loading' | 'idle' | 'saving' | 'saved' | 'error'>('loading')
  const [message, setMessage] = useState('')

  useEffect(() => {
    let cancelled = false
    fetch('/api/settings/events')
      .then(async response => {
        const data = await response.json().catch(() => ({}))
        if (!response.ok || !data.ok || !data.settings) throw new Error(data.error || '')
        if (!cancelled) {
          setSettings({ ...DEFAULTS, ...data.settings })
          setStatus('idle')
        }
      })
      .catch(error => {
        if (cancelled) return
        setStatus('error')
        setMessage(
          error instanceof Error && error.message
            ? error.message
            : 'Não foi possível carregar as configurações de eventos. Verifique se o backend está ligado.'
        )
      })
    return () => {
      cancelled = true
    }
  }, [])

  const edit = (patch: Partial<EventSettings>) => {
    setSettings(previous => ({ ...previous, ...patch }))
    if (status === 'saved' || status === 'error') {
      setStatus('idle')
      setMessage('')
    }
  }

  const editResource = (res: 'cpu' | 'ram' | 'disk', patch: Partial<ResourceConfig>) => {
    setSettings(previous => ({
      ...previous,
      [res]: { ...previous[res], ...patch },
    }))
    if (status === 'saved' || status === 'error') {
      setStatus('idle')
      setMessage('')
    }
  }

  const save = async () => {
    setStatus('saving')
    setMessage('')
    try {
      const response = await fetch('/api/settings/events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok || !data.ok || !data.settings) throw new Error(data.error || '')
      setSettings({ ...DEFAULTS, ...data.settings })
      setStatus('saved')
      setMessage('Configurações de eventos salvas com sucesso.')
    } catch (error) {
      setStatus('error')
      setMessage(
        error instanceof Error && error.message && error.message !== 'Failed to fetch'
          ? error.message
          : 'Não foi possível salvar as configurações de eventos.'
      )
    }
  }

  const busy = status === 'loading' || status === 'saving'

  return (
    <article className="settings-card event-alerts-card" style={{ gridColumn: '1 / -1' }}>
      <p className="eyebrow">MONITOR DE RECURSOS E EVENTOS</p>
      <h2>Alertas do Sistema e Hardware</h2>
      <p>
        Monitoramento local de recursos (CPU, RAM, disco) e gatilhos de eventos.
        <strong> Nada é encerrado automaticamente:</strong> o sistema gera apenas avisos visuais no painel,
        salvo se você tiver configurado uma rotina específica para executar uma ação.
      </p>

      <Switch
        label="Monitor de eventos ativo"
        description="Quando ligado, o backend verifica eventos e recursos periodicamente em segundo plano."
        checked={settings.enabled}
        disabled={busy}
        onChange={checked => edit({ enabled: checked })}
        glowColor="green"
      />

      <div className="agent-loop-limits" style={{ marginTop: '12px' }}>
        <label className="field-label">
          Intervalo de verificação (10 a 120 s)
          <input
            type="number"
            min={10}
            max={120}
            step={1}
            value={settings.interval_seconds}
            disabled={busy || !settings.enabled}
            onChange={e => edit({ interval_seconds: clampInt(e.target.value, 10, 120) })}
          />
        </label>
        <label className="field-label">
          Intervalo entre alertas repetidos (1 a 1440 min)
          <input
            type="number"
            min={1}
            max={1440}
            step={1}
            value={settings.cooldown_minutes}
            disabled={busy || !settings.enabled}
            onChange={e => edit({ cooldown_minutes: clampInt(e.target.value, 1, 1440) })}
          />
        </label>
      </div>

      {/* Alerta de CPU */}
      <fieldset className="ws-fieldset" style={{ marginTop: '12px' }} disabled={busy || !settings.enabled}>
        <legend>Alerta de CPU</legend>
        <Switch
          label="Avisar sobre uso elevado de CPU"
          description="Emite aviso quando a CPU ultrapassar o limiar pelo tempo determinado."
          checked={settings.cpu.enabled}
          disabled={busy || !settings.enabled}
          onChange={checked => editResource('cpu', { enabled: checked })}
          glowColor="blue"
        />
        {settings.cpu.enabled && (
          <div className="agent-loop-limits" style={{ marginTop: '8px' }}>
            <label className="field-label">
              Limiar (50 a 99 %)
              <input
                type="number"
                min={50}
                max={99}
                value={settings.cpu.threshold}
                onChange={e => editResource('cpu', { threshold: clampInt(e.target.value, 50, 99) })}
              />
            </label>
            <label className="field-label">
              Por quantos segundos contínuos (0 a 3600 s)
              <input
                type="number"
                min={0}
                max={3600}
                value={settings.cpu.for_seconds}
                onChange={e => editResource('cpu', { for_seconds: clampInt(e.target.value, 0, 3600) })}
              />
            </label>
          </div>
        )}
      </fieldset>

      {/* Alerta de RAM */}
      <fieldset className="ws-fieldset" style={{ marginTop: '12px' }} disabled={busy || !settings.enabled}>
        <legend>Alerta de Memória RAM</legend>
        <Switch
          label="Avisar sobre uso elevado de Memória"
          description="Emite aviso quando a memória RAM ultrapassar o limiar pelo tempo determinado."
          checked={settings.ram.enabled}
          disabled={busy || !settings.enabled}
          onChange={checked => editResource('ram', { enabled: checked })}
          glowColor="blue"
        />
        {settings.ram.enabled && (
          <div className="agent-loop-limits" style={{ marginTop: '8px' }}>
            <label className="field-label">
              Limiar (50 a 99 %)
              <input
                type="number"
                min={50}
                max={99}
                value={settings.ram.threshold}
                onChange={e => editResource('ram', { threshold: clampInt(e.target.value, 50, 99) })}
              />
            </label>
            <label className="field-label">
              Por quantos segundos contínuos (0 a 3600 s)
              <input
                type="number"
                min={0}
                max={3600}
                value={settings.ram.for_seconds}
                onChange={e => editResource('ram', { for_seconds: clampInt(e.target.value, 0, 3600) })}
              />
            </label>
          </div>
        )}
      </fieldset>

      {/* Alerta de Disco */}
      <fieldset className="ws-fieldset" style={{ marginTop: '12px' }} disabled={busy || !settings.enabled}>
        <legend>Alerta de Espaço em Disco</legend>
        <Switch
          label="Avisar sobre disco quase cheio"
          description="Emite aviso quando o volume de armazenamento especificado estiver no limite."
          checked={settings.disk.enabled}
          disabled={busy || !settings.enabled}
          onChange={checked => editResource('disk', { enabled: checked })}
          glowColor="blue"
        />
        {settings.disk.enabled && (
          <div className="agent-loop-limits" style={{ marginTop: '8px' }}>
            <label className="field-label">
              Caminho da unidade
              <input
                type="text"
                value={settings.disk_path}
                onChange={e => edit({ disk_path: e.target.value })}
                placeholder="Ex.: C:\"
              />
            </label>
            <label className="field-label">
              Limiar (50 a 99 %)
              <input
                type="number"
                min={50}
                max={99}
                value={settings.disk.threshold}
                onChange={e => editResource('disk', { threshold: clampInt(e.target.value, 50, 99) })}
              />
            </label>
          </div>
        )}
      </fieldset>

      <div style={{ marginTop: '14px' }}>
        <button className="outline-button" type="button" disabled={busy} onClick={() => void save()}>
          {status === 'saving' ? 'Salvando…' : 'Salvar configurações de eventos'}
        </button>
      </div>

      {message && (
        <p className={status === 'error' ? 'settings-error' : 'settings-muted'} role={status === 'error' ? 'alert' : 'status'}>
          {message}
        </p>
      )}
    </article>
  )
}
