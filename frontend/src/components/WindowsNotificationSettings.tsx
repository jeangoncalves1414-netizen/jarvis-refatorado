import { useEffect, useState } from 'react'
import { Bell, Play, CheckCircle2 } from 'lucide-react'
import { Switch } from './Switch'

export type WindowsNotificationConfig = {
  enabled: boolean
  sound: boolean
}

const DEFAULTS: WindowsNotificationConfig = {
  enabled: true,
  sound: true,
}

export function WindowsNotificationSettings() {
  const [config, setConfig] = useState<WindowsNotificationConfig>(DEFAULTS)
  const [status, setStatus] = useState<'loading' | 'idle' | 'saving' | 'saved' | 'error'>('loading')
  const [message, setMessage] = useState('')
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle')

  useEffect(() => {
    let cancelled = false
    fetch('/api/settings/notifications')
      .then(async response => {
        const data = await response.json().catch(() => ({}))
        if (!response.ok || !data.ok || !data.settings) throw new Error(data.error || '')
        if (!cancelled) {
          setConfig({ ...DEFAULTS, ...data.settings })
          setStatus('idle')
        }
      })
      .catch(error => {
        if (cancelled) return
        setStatus('error')
        setMessage(
          error instanceof Error && error.message
            ? error.message
            : 'Não foi possível carregar configurações de notificações do Windows.'
        )
      })
    return () => {
      cancelled = true
    }
  }, [])

  const edit = (patch: Partial<WindowsNotificationConfig>) => {
    setConfig(previous => ({ ...previous, ...patch }))
    if (status === 'saved' || status === 'error') {
      setStatus('idle')
      setMessage('')
    }
  }

  const save = async () => {
    setStatus('saving')
    setMessage('')
    try {
      const response = await fetch('/api/settings/notifications', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok || !data.ok || !data.settings) throw new Error(data.error || '')
      setConfig({ ...DEFAULTS, ...data.settings })
      setStatus('saved')
      setMessage('Configurações de notificações salvas com sucesso.')
    } catch (error) {
      setStatus('error')
      setMessage(
        error instanceof Error && error.message && error.message !== 'Failed to fetch'
          ? error.message
          : 'Não foi possível salvar configurações de notificações.'
      )
    }
  }

  const testNotification = async () => {
    setTestStatus('testing')
    try {
      const response = await fetch('/api/notifications/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok || !data.ok) throw new Error(data.error || 'Erro ao disparar notificação')
      setTestStatus('success')
      setTimeout(() => setTestStatus('idle'), 3500)
    } catch {
      setTestStatus('error')
      setTimeout(() => setTestStatus('idle'), 3500)
    }
  }

  const busy = status === 'loading' || status === 'saving'

  return (
    <article className="settings-card windows-notifications-card" style={{ gridColumn: '1 / -1' }}>
      <p className="eyebrow" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <Bell size={13} /> NOTIFICAÇÕES DO WINDOWS 10/11
      </p>
      <h2>Notificações Acionáveis com Ações Rápidas</h2>
      <p>
        Notificações Toast nativas com botões interativos e deep-links. Permite ouvir o briefing
        matinal, checar hábitos, registrar hidratação (+300ml) e abrir links de reuniões
        diretamente da barra de notificações do Windows, mesmo com a janela minimizada.
      </p>

      <Switch
        label="Notificações nativas do Windows ativas"
        description="Quando ligado, o Jarvis envia avisos importantes do sistema, rotinas e proatividade via Toast do Windows."
        checked={config.enabled}
        disabled={busy}
        onChange={checked => edit({ enabled: checked })}
        glowColor="green"
      />

      <div style={{ marginTop: '10px' }}>
        <Switch
          label="Emitir som de notificação"
          description="Toca o efeito sonoro padrão do Windows ao exibir cada notificação."
          checked={config.sound}
          disabled={busy || !config.enabled}
          onChange={checked => edit({ sound: checked })}
          glowColor="blue"
        />
      </div>

      <div style={{ marginTop: '16px', display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center' }}>
        <button
          className="outline-button"
          type="button"
          disabled={busy}
          onClick={() => void save()}
        >
          {status === 'saving' ? 'Salvando…' : 'Salvar configurações'}
        </button>

        <button
          className="outline-button"
          type="button"
          disabled={busy || !config.enabled || testStatus === 'testing'}
          onClick={() => void testNotification()}
          style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          {testStatus === 'testing' ? (
            'Enviando notificação…'
          ) : testStatus === 'success' ? (
            <>
              <CheckCircle2 size={15} color="#00daf8" /> Notificação enviada!
            </>
          ) : testStatus === 'error' ? (
            'Falha no envio'
          ) : (
            <>
              <Play size={14} /> Testar notificação do Windows
            </>
          )}
        </button>
      </div>

      {message && (
        <p
          className={status === 'error' ? 'settings-error' : 'settings-muted'}
          role={status === 'error' ? 'alert' : 'status'}
          style={{ marginTop: '10px' }}
        >
          {message}
        </p>
      )}
    </article>
  )
}
