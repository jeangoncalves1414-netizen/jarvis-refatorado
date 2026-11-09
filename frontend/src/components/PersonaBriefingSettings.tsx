import { useState, useEffect } from 'react'
import { Switch } from './Switch'
import { Save, Volume2, Sparkles, RefreshCw, Bot, Dumbbell } from 'lucide-react'
import { playSuccess } from '../utils/sfx'

interface PersonaConfig {
  name: string
  tone: string
  morning_challenge: {
    enabled: boolean
    text: string
  }
  custom_rules: string
}

const TONE_OPTIONS = [
  { value: 'amigável', label: 'Amigável & Empático', desc: 'Caloroso, acolhedor e encorajador.' },
  { value: 'formal', label: 'Formal & Preciso', desc: 'Profissional, polido e sem gírias.' },
  { value: 'bem-humorado', label: 'Bem-humorado & Espirituoso', desc: 'Descontraído, leve e divertido.' },
  { value: 'militar', label: 'Militar & Disciplinado', desc: 'Direto ao ponto, tático e focado em metas.' },
  { value: 'sarcástico leve', label: 'Sarcástico Leve & Perspicaz', desc: 'Ironia refinada estilo Jarvis clássico.' },
]

export function PersonaBriefingSettings() {
  const [name, setName] = useState('Jarvis')
  const [tone, setTone] = useState('amigável')
  const [challengeEnabled, setChallengeEnabled] = useState(true)
  const [challengeText, setChallengeText] = useState('10 polichinelos e 10 flexões')
  const [customRules, setCustomRules] = useState('')

  const [status, setStatus] = useState<'loading' | 'idle' | 'saving' | 'saved' | 'error'>('loading')
  const [message, setMessage] = useState('')

  const [previewText, setPreviewText] = useState('')
  const [loadingPreview, setLoadingPreview] = useState(false)
  const [playingAudio, setPlayingAudio] = useState(false)

  // Carrega configuração ativa
  useEffect(() => {
    let cancelled = false
    fetch('/api/persona')
      .then(res => res.json())
      .then(data => {
        if (cancelled) return
        if (data && data.ok && data.persona) {
          const p: PersonaConfig = data.persona
          setName(p.name || 'Jarvis')
          setTone(p.tone || 'amigável')
          setChallengeEnabled(Boolean(p.morning_challenge?.enabled))
          setChallengeText(p.morning_challenge?.text || '10 polichinelos e 10 flexões')
          setCustomRules(p.custom_rules || '')
        }
        setStatus('idle')
      })
      .catch(() => {
        if (!cancelled) {
          setStatus('idle')
        }
      })
    return () => { cancelled = true }
  }, [])

  const handleSave = async () => {
    setStatus('saving')
    setMessage('')
    try {
      const payload: PersonaConfig = {
        name: name.trim() || 'Jarvis',
        tone,
        morning_challenge: {
          enabled: challengeEnabled,
          text: challengeText.trim() || '10 polichinelos e 10 flexões',
        },
        custom_rules: customRules.trim(),
      }

      const res = await fetch('/api/persona', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()
      if (res.ok && data.ok) {
        setStatus('saved')
        setMessage('Personalidade e Briefing salvos com sucesso!')
        playSuccess()
      } else {
        setStatus('error')
        setMessage(data.error || 'Erro ao salvar configurações.')
      }
    } catch (err: any) {
      setStatus('error')
      setMessage(err?.message || 'Falha na comunicação com o servidor.')
    }
  }

  const handlePreviewBriefing = async () => {
    setLoadingPreview(true)
    setMessage('')
    try {
      const res = await fetch('/api/persona/preview-morning')
      const data = await res.json()
      if (res.ok && data.ok && data.text) {
        setPreviewText(data.text)
        // Dispara áudio se disponível
        playSpeech(data.text)
      } else {
        setMessage('Não foi possível gerar a prévia do briefing matinal.')
      }
    } catch (err: any) {
      setMessage('Erro ao obter prévia: ' + (err?.message || ''))
    } finally {
      setLoadingPreview(false)
    }
  }

  const playSpeech = async (text: string) => {
    setPlayingAudio(true)
    try {
      // Tenta via endpoint do backend /api/voice
      const res = await fetch('/api/voice', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      })
      if (res.ok) {
        const blob = await res.blob()
        const url = URL.createObjectURL(blob)
        const audio = new Audio(url)
        audio.onended = () => {
          setPlayingAudio(false)
          URL.revokeObjectURL(url)
        }
        audio.onerror = () => {
          fallbackBrowserSpeech(text)
        }
        await audio.play()
        return
      }
    } catch {
      // Fallback para fala do navegador se backend de voz falhar
    }
    fallbackBrowserSpeech(text)
  }

  const fallbackBrowserSpeech = (text: string) => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel()
      const utterance = new SpeechSynthesisUtterance(text)
      utterance.lang = 'pt-BR'
      utterance.rate = 1.05
      utterance.onend = () => setPlayingAudio(false)
      utterance.onerror = () => setPlayingAudio(false)
      window.speechSynthesis.speak(utterance)
    } else {
      setPlayingAudio(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Card 1: Identidade e Tom */}
      <article
        style={{
          background: 'var(--ws-panel)',
          border: '1px solid var(--ws-border)',
          borderRadius: 'var(--ws-radius)',
          padding: 20,
          color: 'var(--ws-text)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
          <Bot size={20} style={{ color: 'var(--ws-accent)' }} />
          <div>
            <p style={{ margin: 0, fontSize: 11, fontWeight: 700, color: 'var(--ws-muted)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
              IDENTIDADE MODULAR
            </p>
            <h2 style={{ margin: 0, fontSize: 18, color: 'var(--ws-text)' }}>Personalidade e Assistente</h2>
          </div>
        </div>

        <p style={{ fontSize: 13, color: 'var(--ws-muted)', margin: '4px 0 16px 0' }}>
          Personalize o nome, o tom de conversa e as diretrizes comportamentais do Jarvis.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16 }}>
          {/* Nome do Assistente */}
          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--ws-text)', marginBottom: 6 }}>
              Nome do assistente
            </label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="Ex: Jarvis, Sexta-Feira..."
              style={{
                width: '100%',
                padding: '10px 12px',
                background: 'var(--ws-field)',
                border: '1px solid var(--ws-border)',
                borderRadius: 8,
                color: 'var(--ws-text)',
                fontSize: 14,
                boxSizing: 'border-box',
              }}
            />
          </div>

          {/* Tom de resposta */}
          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--ws-text)', marginBottom: 6 }}>
              Estilo / Tom de resposta
            </label>
            <select
              value={tone}
              onChange={e => setTone(e.target.value)}
              style={{
                width: '100%',
                padding: '10px 12px',
                background: 'var(--ws-field)',
                border: '1px solid var(--ws-border)',
                borderRadius: 8,
                color: 'var(--ws-text)',
                fontSize: 14,
                boxSizing: 'border-box',
              }}
            >
              {TONE_OPTIONS.map(opt => (
                <option key={opt.value} value={opt.value}>
                  {opt.label} — {opt.desc}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Regras e instruções específicas */}
        <div style={{ marginTop: 16 }}>
          <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--ws-text)', marginBottom: 6 }}>
            Regras e instruções específicas da persona (Prompt do sistema)
          </label>
          <textarea
            value={customRules}
            onChange={e => setCustomRules(e.target.value)}
            placeholder="Instruções personalizadas adicionais para guiar as respostas do assistente..."
            rows={3}
            style={{
              width: '100%',
              padding: '10px 12px',
              background: 'var(--ws-field)',
              border: '1px solid var(--ws-border)',
              borderRadius: 8,
              color: 'var(--ws-text)',
              fontSize: 13,
              fontFamily: 'inherit',
              lineHeight: 1.5,
              resize: 'vertical',
              boxSizing: 'border-box',
            }}
          />
        </div>
      </article>

      {/* Card 2: Desafio Matinal & Rotina */}
      <article
        style={{
          background: 'var(--ws-panel)',
          border: '1px solid var(--ws-border)',
          borderRadius: 'var(--ws-radius)',
          padding: 20,
          color: 'var(--ws-text)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
          <Dumbbell size={20} style={{ color: 'var(--ws-accent)' }} />
          <div>
            <p style={{ margin: 0, fontSize: 11, fontWeight: 700, color: 'var(--ws-muted)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
              CONDICIONAMENTO & VITALIDADE
            </p>
            <h2 style={{ margin: 0, fontSize: 18, color: 'var(--ws-text)' }}>Desafio Matinal</h2>
          </div>
        </div>

        <p style={{ fontSize: 13, color: 'var(--ws-muted)', margin: '4px 0 16px 0' }}>
          Configuração de exercício diário incluído no briefing matinal para despertar com energia.
        </p>

        <div style={{ marginBottom: 16 }}>
          <Switch
            label="Ativar Desafio Matinal"
            description="Quando ativo, o assistente incentiva a realização do exercício logo na saudação da manhã."
            checked={challengeEnabled}
            onChange={setChallengeEnabled}
            glowColor="blue"
          />
        </div>

        {challengeEnabled && (
          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--ws-text)', marginBottom: 6 }}>
              Descrição do Desafio Físico
            </label>
            <input
              type="text"
              value={challengeText}
              onChange={e => setChallengeText(e.target.value)}
              placeholder="Ex: 10 polichinelos e 10 flexões"
              style={{
                width: '100%',
                padding: '10px 12px',
                background: 'var(--ws-field)',
                border: '1px solid var(--ws-border)',
                borderRadius: 8,
                color: 'var(--ws-text)',
                fontSize: 14,
                boxSizing: 'border-box',
              }}
            />
            <small style={{ color: 'var(--ws-muted)', fontSize: 11, marginTop: 4, display: 'block' }}>
              Dica: defina metas graduais como polichinelos, flexões ou agachamentos.
            </small>
          </div>
        )}
      </article>

      {/* Ações e Salvar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <button
          type="button"
          onClick={handleSave}
          disabled={status === 'saving'}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            padding: '10px 18px',
            background: 'var(--ws-accent)',
            color: 'var(--ws-accent-ink)',
            border: 'none',
            borderRadius: 8,
            fontWeight: 700,
            fontSize: 13,
            cursor: status === 'saving' ? 'not-allowed' : 'pointer',
            transition: 'opacity 0.2s',
          }}
        >
          <Save size={15} />
          {status === 'saving' ? 'Salvando…' : 'Salvar Personalidade'}
        </button>

        <button
          type="button"
          onClick={handlePreviewBriefing}
          disabled={loadingPreview}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            padding: '10px 18px',
            background: 'var(--ws-accent-soft)',
            color: 'var(--ws-accent)',
            border: '1px solid var(--ws-accent-line)',
            borderRadius: 8,
            fontWeight: 600,
            fontSize: 13,
            cursor: loadingPreview ? 'not-allowed' : 'pointer',
          }}
        >
          {loadingPreview ? (
            <RefreshCw size={15} className="spin" />
          ) : (
            <Volume2 size={15} />
          )}
          {playingAudio ? 'Reproduzindo áudio…' : 'Ouvir prévia do Briefing Matinal'}
        </button>

        {status === 'saved' && (
          <span style={{ color: 'var(--ws-ok)', fontSize: 13, fontWeight: 600 }}>
            ✓ {message}
          </span>
        )}
        {status === 'error' && (
          <span style={{ color: 'var(--ws-danger)', fontSize: 13, fontWeight: 600 }}>
            ✕ {message}
          </span>
        )}
      </div>

      {/* Caixa de Prévia do Briefing Matinal */}
      {previewText && (
        <article
          style={{
            background: 'var(--ws-panel)',
            border: '1px solid var(--ws-border)',
            borderRadius: 'var(--ws-radius)',
            padding: 20,
            color: 'var(--ws-text)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Sparkles size={16} style={{ color: 'var(--ws-accent)' }} />
              <h3 style={{ margin: 0, fontSize: 15, color: 'var(--ws-text)' }}>Prévia do Roteiro de Briefing Matinal</h3>
            </div>
            {playingAudio && (
              <span style={{ fontSize: 12, color: 'var(--ws-accent)', fontWeight: 600 }}>
                🔊 Tocando síntese de voz...
              </span>
            )}
          </div>
          <div
            style={{
              padding: 14,
              background: 'var(--ws-field)',
              border: '1px solid var(--ws-border)',
              borderRadius: 8,
              fontSize: 13,
              lineHeight: 1.6,
              color: 'var(--ws-text)',
              whiteSpace: 'pre-wrap',
            }}
          >
            {previewText}
          </div>
        </article>
      )}
    </div>
  )
}
