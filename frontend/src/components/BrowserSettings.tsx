import { useEffect, useState } from 'react'
import { Switch } from './Switch'
import { Globe, Monitor, Shield, Zap } from 'lucide-react'

export type BrowserConfig = {
  headless: boolean
  timeout_seconds: number
}

const DEFAULTS: BrowserConfig = {
  headless: true,
  timeout_seconds: 15,
}

export function BrowserSettings() {
  const [config, setConfig] = useState<BrowserConfig>(DEFAULTS)
  const [status, setStatus] = useState<'loading' | 'idle' | 'saving' | 'saved' | 'error'>('loading')
  const [message, setMessage] = useState('')

  useEffect(() => {
    let cancelled = false
    fetch('/api/settings/browser')
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
        setMessage(error instanceof Error && error.message ? error.message : 'Não foi possível carregar a configuração da navegação web.')
      })
    return () => {
      cancelled = true
    }
  }, [])

  const edit = (patch: Partial<BrowserConfig>) => {
    setConfig(prev => ({ ...prev, ...patch }))
    if (status === 'saved' || status === 'error') {
      setStatus('idle')
      setMessage('')
    }
  }

  const save = async () => {
    setStatus('saving')
    setMessage('')
    try {
      const response = await fetch('/api/settings/browser', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok || !data.ok || !data.settings) throw new Error(data.error || '')
      setConfig({ ...DEFAULTS, ...data.settings })
      setStatus('saved')
      setMessage('Configuração de navegação web salva com sucesso.')
    } catch (error) {
      setStatus('error')
      setMessage(error instanceof Error && error.message ? error.message : 'Erro ao salvar configurações do navegador.')
    }
  }

  return (
    <article
      className="settings-card"
      style={{
        background: 'var(--ws-panel, #202324)',
        border: '1px solid var(--ws-border, #303435)',
        borderRadius: 'var(--ws-radius, 12px)',
        padding: '20px',
        color: 'var(--ws-text, #eceeed)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <Globe size={18} style={{ color: 'var(--ws-accent, #b4d9c6)' }} />
        <p className="eyebrow" style={{ margin: 0, color: 'var(--ws-muted, #a0a8a5)', fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
          AUTOMAÇÃO PLAYWRIGHT
        </p>
      </div>

      <h2 style={{ fontSize: 18, fontWeight: 700, margin: '4px 0 8px 0', color: 'var(--ws-text, #eceeed)' }}>
        Navegação Web Ativa
      </h2>
      <p style={{ color: 'var(--ws-muted, #a0a8a5)', fontSize: 13, lineHeight: 1.5, marginBottom: 20 }}>
        Controle o comportamento do motor de navegação ativa do Jarvis. O Jarvis interage programaticamente com páginas,
        aguarda o DOM, extrai dados limpos, clica em botões e preenche formulários.
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* Switch Modo Visível / Headless */}
        <div
          style={{
            background: 'var(--ws-field, rgba(255,255,255,0.03))',
            border: '1px solid var(--ws-border, #303435)',
            borderRadius: 'var(--ws-radius, 10px)',
            padding: 14,
          }}
        >
          <Switch
            label="Modo em segundo plano (Headless)"
            description={
              config.headless
                ? 'Ativo: o Chromium roda silenciosamente em segundo plano sem abrir janela gráfica.'
                : 'Desativado (Headful): uma janela do navegador é aberta na tela para acompanhar visualmente as ações.'
            }
            checked={config.headless}
            onChange={checked => edit({ headless: checked })}
            glowColor="green"
          />
        </div>

        {/* Informações de Modo */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 12 }}>
          <div
            style={{
              padding: 12,
              borderRadius: 8,
              border: '1px solid var(--ws-border, #303435)',
              background: 'var(--ws-field, rgba(255,255,255,0.02))',
              display: 'flex',
              alignItems: 'flex-start',
              gap: 10,
            }}
          >
            <Monitor size={18} style={{ color: config.headless ? 'var(--ws-muted)' : 'var(--ws-accent)', marginTop: 2 }} />
            <div>
              <strong style={{ fontSize: 12, display: 'block', color: 'var(--ws-text)' }}>
                {config.headless ? 'Modo Silencioso' : 'Modo Visível Interativo'}
              </strong>
              <span style={{ fontSize: 11, color: 'var(--ws-muted)' }}>
                {config.headless
                  ? 'Ideal para extração rápida e sem distrações visuais.'
                  : 'Ideal para depuração e conferência visual de cliques e formulários.'}
              </span>
            </div>
          </div>

          <div
            style={{
              padding: 12,
              borderRadius: 8,
              border: '1px solid var(--ws-border, #303435)',
              background: 'var(--ws-field, rgba(255,255,255,0.02))',
              display: 'flex',
              alignItems: 'flex-start',
              gap: 10,
            }}
          >
            <Shield size={18} style={{ color: 'var(--ws-accent, #b4d9c6)', marginTop: 2 }} />
            <div>
              <strong style={{ fontSize: 12, display: 'block', color: 'var(--ws-text)' }}>
                Proteção do Action Kernel
              </strong>
              <span style={{ fontSize: 11, color: 'var(--ws-muted)' }}>
                Leituras têm risco Observe. Cliques são Low e preenchimentos são High com política de segurança.
              </span>
            </div>
          </div>
        </div>

        {/* Timeout defensivo */}
        <div
          style={{
            background: 'var(--ws-field, rgba(255,255,255,0.03))',
            border: '1px solid var(--ws-border, #303435)',
            borderRadius: 'var(--ws-radius, 10px)',
            padding: 14,
          }}
        >
          <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 13, fontWeight: 600 }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Zap size={14} style={{ color: 'var(--ws-warn, #dfba7e)' }} />
              Tempo limite defensivo por ação (segundos)
            </span>
            <span style={{ fontSize: 11, fontWeight: 400, color: 'var(--ws-muted)' }}>
              Máximo de 15 segundos recomendado para evitar travamento da sessão agêntica.
            </span>
            <input
              type="number"
              min={1}
              max={30}
              value={config.timeout_seconds}
              onChange={e => edit({ timeout_seconds: Math.max(1, Math.min(30, parseInt(e.target.value) || 15)) })}
              style={{
                marginTop: 6,
                padding: '8px 12px',
                borderRadius: 8,
                background: 'var(--ws-bg, #191b1c)',
                border: '1px solid var(--ws-border, #303435)',
                color: 'var(--ws-text, #eceeed)',
                fontSize: 13,
                width: 120,
              }}
            />
          </label>
        </div>

        {/* Ações e Feedback */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 8 }}>
          <button
            type="button"
            className="outline-button"
            onClick={save}
            disabled={status === 'saving'}
            style={{
              padding: '9px 18px',
              borderRadius: 'var(--ws-radius, 8px)',
              background: 'var(--ws-accent-soft, rgba(180, 217, 198, 0.1))',
              borderColor: 'var(--ws-accent-line, #3e4943)',
              color: 'var(--ws-accent, #b4d9c6)',
              fontWeight: 700,
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            {status === 'saving' ? 'Salvando...' : 'Salvar preferências'}
          </button>
          {message && (
            <span
              style={{
                fontSize: 12,
                color: status === 'error' ? 'var(--ws-danger, #d98f83)' : 'var(--ws-ok, #8fc7a5)',
              }}
            >
              {message}
            </span>
          )}
        </div>
      </div>
    </article>
  )
}

