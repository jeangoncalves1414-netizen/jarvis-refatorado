import { useEffect, useState } from 'react'
import { Check, KeyRound, RefreshCw, Trash2, Wifi } from 'lucide-react'

type HASettings = {
  url: string
  configured: boolean
  token_masked: string
}

export function HomeAssistantSettings() {
  const [url, setUrl] = useState('')
  const [token, setToken] = useState('')
  const [configured, setConfigured] = useState(false)
  const [tokenMasked, setTokenMasked] = useState('')
  const [status, setStatus] = useState<'loading' | 'idle' | 'saving' | 'testing' | 'error' | 'success'>('loading')
  const [message, setMessage] = useState('')

  const load = () => {
    setStatus('loading')
    fetch('/api/settings/home-assistant')
      .then(async res => {
        const data = await res.json().catch(() => ({}))
        if (!res.ok || !data.ok || !data.settings) throw new Error(data.error || 'Erro ao carregar configurações.')
        const s = data.settings as HASettings
        setUrl(s.url || '')
        setConfigured(Boolean(s.configured))
        setTokenMasked(s.token_masked || '')
        setToken('')
        setStatus('idle')
      })
      .catch(err => {
        setStatus('error')
        setMessage(err instanceof Error && err.message ? err.message : 'Não foi possível carregar a configuração do Home Assistant.')
      })
  }

  useEffect(() => {
    load()
  }, [])

  const handleSave = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    setStatus('saving')
    setMessage('')
    try {
      const payload: { url: string; token?: string } = { url }
      if (token.trim()) payload.token = token.trim()
      const res = await fetch('/api/settings/home-assistant', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok || !data.ok) throw new Error(data.error || 'Falha ao salvar.')
      const s = data.settings as HASettings
      setUrl(s.url || '')
      setConfigured(Boolean(s.configured))
      setTokenMasked(s.token_masked || '')
      setToken('')
      setStatus('success')
      setMessage('Configurações do Home Assistant salvas com sucesso!')
    } catch (err) {
      setStatus('error')
      setMessage(err instanceof Error && err.message ? err.message : 'Erro ao salvar configurações.')
    }
  }

  const handleTest = async () => {
    setStatus('testing')
    setMessage('')
    try {
      const res = await fetch('/api/settings/home-assistant/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok || !data.ok) throw new Error(data.error || 'Falha no teste de conexão.')
      setStatus('success')
      setMessage(data.message || 'Conexão com o Home Assistant bem-sucedida!')
    } catch (err) {
      setStatus('error')
      setMessage(err instanceof Error && err.message ? err.message : 'Não foi possível conectar ao Home Assistant.')
    }
  }

  const handleClear = async () => {
    if (!window.confirm('Deseja realmente remover a integração com o Home Assistant?')) return
    setStatus('saving')
    setMessage('')
    try {
      const res = await fetch('/api/settings/home-assistant', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ clear: true }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok || !data.ok) throw new Error(data.error || 'Falha ao remover.')
      setUrl('')
      setToken('')
      setConfigured(false)
      setTokenMasked('')
      setStatus('success')
      setMessage('Integração com o Home Assistant removida.')
    } catch (err) {
      setStatus('error')
      setMessage(err instanceof Error && err.message ? err.message : 'Erro ao remover configurações.')
    }
  }

  return (
    <article className="settings-card">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <p className="eyebrow" style={{ margin: 0 }}>CASA INTELIGENTE</p>
        <span
          style={{
            fontSize: '11px',
            padding: '2px 8px',
            borderRadius: '999px',
            border: `1px solid ${configured ? '#476a56' : '#525a55'}`,
            color: configured ? '#a8d4b8' : '#8fa196',
            background: configured ? '#476a5622' : 'transparent',
          }}
        >
          {configured ? 'Conectado' : 'Não configurado'}
        </span>
      </div>

      <h2 style={{ margin: '0 0 6px' }}>Home Assistant</h2>
      <p style={{ margin: '0 0 16px', color: '#8fa196', fontSize: '13px' }}>
        Conecte sua instância local do Home Assistant para controlar luzes, tomadas, fechaduras e cenas direto pelo Jarvis ou pela janela Casa.
      </p>

      <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div>
          <label style={{ display: 'block', fontSize: '12px', color: '#cfd9d3', marginBottom: 4 }}>
            Endereço (URL)
          </label>
          <input
            type="text"
            value={url}
            onChange={e => setUrl(e.target.value)}
            placeholder="http://homeassistant.local:8123 ou http://192.168.1.100:8123"
            disabled={status === 'loading' || status === 'saving'}
            style={{
              width: '100%',
              padding: '8px 12px',
              borderRadius: 6,
              border: '1px solid #3a423e',
              background: '#1c1f1e',
              color: '#cfd9d3',
              fontSize: '13px',
              boxSizing: 'border-box',
            }}
          />
        </div>

        <div>
          <label style={{ display: 'block', fontSize: '12px', color: '#cfd9d3', marginBottom: 4 }}>
            Token de longa duração {tokenMasked && <span style={{ color: '#8fa196' }}>({tokenMasked})</span>}
          </label>
          <input
            type="password"
            value={token}
            onChange={e => setToken(e.target.value)}
            placeholder={tokenMasked ? 'Deixe em branco para manter o token atual' : 'Cole aqui o token de longa duração gerado no Home Assistant'}
            disabled={status === 'loading' || status === 'saving'}
            style={{
              width: '100%',
              padding: '8px 12px',
              borderRadius: 6,
              border: '1px solid #3a423e',
              background: '#1c1f1e',
              color: '#cfd9d3',
              fontSize: '13px',
              boxSizing: 'border-box',
            }}
          />
        </div>

        {message && (
          <p
            style={{
              margin: '4px 0',
              padding: '8px 12px',
              borderRadius: 6,
              fontSize: '12px',
              border: `1px solid ${status === 'error' ? '#915e54' : '#476a56'}`,
              background: status === 'error' ? '#59342e44' : '#476a5622',
              color: status === 'error' ? '#f3c5bb' : '#a8d4b8',
            }}
          >
            {message}
          </p>
        )}

        <div style={{ display: 'flex', gap: 8, marginTop: 4, flexWrap: 'wrap' }}>
          <button
            type="submit"
            className="btn-primary"
            disabled={status === 'loading' || status === 'saving'}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 14px', fontSize: '12px', cursor: 'pointer' }}
          >
            <Check size={14} />
            {status === 'saving' ? 'Salvando…' : 'Salvar'}
          </button>

          <button
            type="button"
            className="btn-secondary"
            onClick={handleTest}
            disabled={!configured || status === 'loading' || status === 'saving' || status === 'testing'}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 14px', fontSize: '12px', cursor: 'pointer' }}
          >
            <Wifi size={14} />
            {status === 'testing' ? 'Testando…' : 'Testar conexão'}
          </button>

          {configured && (
            <button
              type="button"
              className="btn-secondary"
              onClick={handleClear}
              disabled={status === 'loading' || status === 'saving'}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 14px', fontSize: '12px', cursor: 'pointer', color: '#f3c5bb' }}
            >
              <Trash2 size={14} />
              Remover
            </button>
          )}
        </div>
      </form>
    </article>
  )
}

