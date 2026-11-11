import { useEffect, useState } from 'react'
import { BentoCard } from '../components/BentoCard'
import { GlowCard } from '../components/GlowCard'
import { SpotlightCard } from '../components/SpotlightCard'
import { TodayPanel } from '../components/TodayPanel'
import { QuantumStatsWidget } from '../components/QuantumStatsWidget'
import { Flame, Droplets, Play, Volume2, X } from 'lucide-react'
import type { Dashboard, Finance, Proactive, Tray, TtsSettings } from '../types'
import { playClick, playSuccess } from '../utils/sfx'
import { broadcastSyncEvent, onSyncEvent } from '../utils/syncChannel'
import { isMobileStandalone } from '../hooks/useDirectChat'
import { addWaterDraft, flushWaterDrafts, loadWaterDrafts, postWater } from '../utils/waterDrafts'

type DashboardPageProps = {
  dashboard: Dashboard | null
  finance: Finance | null
  ttsSettings: TtsSettings | null
  proactive: Proactive | null
  tray: Tray | null
  onOpenEvolute?: () => void
}

export function DashboardPage({
  dashboard,
  finance,
  ttsSettings,
  proactive,
  tray,
  onOpenEvolute,
}: DashboardPageProps) {
  const reminderCount = proactive?.reminders?.length ?? 0

  // Life OS mini-HUD state
  type LifeVice = { id: string; name: string; streak: number; longestStreak: number }
  const [lifeVices, setLifeVices] = useState<LifeVice[]>([])
  const [waterMl, setWaterMl] = useState<number>(0)
  const [addingWater, setAddingWater] = useState(false)
  const [waterError, setWaterError] = useState('')
  const [waterPending, setWaterPending] = useState(() => loadWaterDrafts().length)
  const [briefingLoading, setBriefingLoading] = useState(false)
  const [briefingText, setBriefingText] = useState<string | null>(null)

  const fetchStatus = () => {
    fetch('/api/evolute/status')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (!data) return
        setWaterMl(data.waterMl ?? 0)
        setLifeVices(data.vices ?? [])
      })
      .catch(() => {})
  }

  useEffect(() => {
    fetchStatus()
    // Subscribe to cross-window sync events
    const unsubWater = onSyncEvent('WATER_UPDATED', fetchStatus)
    const unsubAll = onSyncEvent('DATA_MUTATED', fetchStatus)
    return () => {
      unsubWater()
      unsubAll()
    }
  }, [])

  const handleAddWater = async (amount: number = 250) => {
    if (addingWater) return
    setAddingWater(true)
    try {
      const result = await postWater(amount)
      if (!result.ok) {
        // Sem confirmação do servidor nada é somado: guarda o rascunho para reenviar.
        addWaterDraft(amount)
        setWaterPending(loadWaterDrafts().length)
        setWaterError(`Não consegui registrar +${amount}ml (${result.error}). Guardei neste aparelho para reenviar.`)
        return
      }
      playSuccess()
      setWaterError('')
      if (typeof result.data?.total_ml === 'number') setWaterMl(result.data.total_ml)
      else fetchStatus()
      broadcastSyncEvent('WATER_UPDATED', { total_ml: result.data?.total_ml })
      if (loadWaterDrafts().length) await handleResendWater()
    } finally {
      setAddingWater(false)
    }
  }

  const handleResendWater = async () => {
    const flushed = await flushWaterDrafts()
    setWaterPending(flushed.pending)
    if (flushed.sent) { fetchStatus(); broadcastSyncEvent('WATER_UPDATED', { amount: flushed.sentMl }) }
    if (flushed.pending) setWaterError(`Ainda não consegui reenviar${flushed.error ? ` (${flushed.error})` : ''}. ${flushed.pending} registro(s) de água guardado(s) neste aparelho.`)
    else setWaterError('')
  }

  const handleTriggerBriefing = async () => {
    if (briefingLoading) return
    setBriefingLoading(true)
    playClick()
    try {
      const res = await fetch('/api/proactive', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'trigger_briefing' })
      })
      const data = await res.json()
      if (data.ok && data.briefing_text) {
        setBriefingText(data.briefing_text)
        playSuccess()
      } else {
        setBriefingText('Briefing disparado no motor de voz do Jarvis.')
      }
    } catch {
      setBriefingText('Não foi possível carregar o briefing agora. Verifique a conexão com o Jarvis.')
    } finally {
      setBriefingLoading(false)
    }
  }

  return (
    <section className="dashboard-bento">
      <TodayPanel />
      <div style={{ gridColumn: '1 / -1' }} className="lifeos-hud-card">
        <div className="lifeos-hud-body">
          {/* Hydration quick badge */}
          <div className="lifeos-water-section">
            <span className="lifeos-section-label"><Droplets size={11} /> Hidratação</span>
            <div className="lifeos-water-row">
              <span className="lifeos-water-amount">{waterMl} ml</span>
              <button
                type="button"
                className="lifeos-water-btn"
                onClick={() => handleAddWater(250)}
                disabled={addingWater}
                title="Registrar 250ml de água"
              >
                {addingWater ? '…' : '+250ml'}
              </button>
            </div>
            {(waterError || waterPending > 0) && (
              <small role="alert" style={{ display: 'block', marginTop: 6, color: '#f87171' }}>
                {waterError || `${waterPending} registro(s) de água guardado(s) neste aparelho.`}{' '}
                <button type="button" className="lifeos-water-btn" onClick={() => { void handleResendWater() }} disabled={addingWater}>Reenviar</button>
              </small>
            )}
          </div>

          {/* Anti-Vice / Clean Streak section */}
          {lifeVices.length > 0 && (
            <div className="lifeos-vice-section">
              <span className="lifeos-section-label"><Flame size={11} color="#f97316" /> Foco & Blindagem</span>
              <div className="lifeos-habit-row-group">
                {lifeVices.map(v => (
                  <span key={v.id} className="lifeos-vice-chip" title={`Recorde: ${v.longestStreak} dias`}>
                    🔥 {v.name}: <strong>{v.streak}d limpos</strong>
                  </span>
                ))}
              </div>
            </div>
          )}

        </div>
      </div>
      {!isMobileStandalone() && (
        <div style={{ gridColumn: '1 / -1' }}><QuantumStatsWidget /></div>
      )}
      <GlowCard glowColor="purple" className="hud-widget hud-briefing-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <p className="eyebrow">BRIEFING</p>
            <strong>{proactive?.config?.briefing_time || '08:00'}</strong>
            <span>{proactive?.config?.briefing_enabled ? 'Ativo diariamente' : 'Desativado'}</span>
          </div>
          <button
            type="button"
            className="hud-briefing-trigger-btn"
            onClick={handleTriggerBriefing}
            disabled={briefingLoading}
            title="Disparar resumo matinal do Jarvis agora"
          >
            {briefingLoading ? <Volume2 size={13} className="spin" /> : <Play size={13} fill="currentColor" />}
            {briefingLoading ? 'Gerando…' : 'Ouvir'}
          </button>
        </div>
        {briefingText && (
          <div className="hud-briefing-popup">
            <div className="hud-briefing-popup-header">
              <span>🎙️ Resumo do Jarvis</span>
              <button type="button" onClick={() => setBriefingText(null)} aria-label="Fechar">
                <X size={12} />
              </button>
            </div>
            <p className="hud-briefing-popup-text">{briefingText}</p>
          </div>
        )}
      </GlowCard>
      <GlowCard glowColor="blue" className="hud-widget">
        <p className="eyebrow">LEMBRETES</p>
        <strong>{reminderCount}</strong>
        <span>
          {reminderCount === 1 ? '1 pendente' : `${reminderCount} pendentes`}
        </span>
      </GlowCard>
      <GlowCard glowColor="green" className="hud-widget">
        <p className="eyebrow">INICIALIZAÇÃO</p>
        <strong>{tray?.boot_enabled ? 'Ativo' : 'Off'}</strong>
        <span>Boot com Windows</span>
      </GlowCard>
      <BentoCard eyebrow="SESSÕES" title="Salvas">
        <strong className="stat-big">{dashboard?.sessions?.total ?? '—'}</strong>
      </BentoCard>
      <BentoCard eyebrow="SISTEMA" title="CPU / RAM">
        <strong className="stat-big">
          {dashboard?.system?.cpu !== undefined ? `${Math.round(dashboard.system.cpu)}%` : '—'}
        </strong>
        <span>RAM {dashboard?.system?.ram_percent ?? '—'}%</span>
      </BentoCard>
      <BentoCard eyebrow="PAINEL DEDICADO" title="Life OS · Evolute" span={2}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: '4px 0' }}>
          <p style={{ margin: 0, fontSize: '13px', color: '#9ca3af', lineHeight: 1.5 }}>
            Central unificada de hábitos, treinos, hidratação, leitura e estudos gerenciados em janela independente.
          </p>
          {onOpenEvolute && (
            <div>
              <button
                type="button"
                onClick={onOpenEvolute}
                style={{
                  background: 'rgba(168, 85, 247, 0.15)',
                  border: '1px solid rgba(168, 85, 247, 0.35)',
                  color: '#d8b4fe',
                  padding: '7px 14px',
                  borderRadius: '10px',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  transition: 'all 0.2s ease',
                }}
              >
                <span>⚡</span> Abrir Painel de Evolução Completo ↗
              </button>
            </div>
          )}
        </div>
      </BentoCard>
      <SpotlightCard glowColor="cyan" customSize className="hud-widget">
        <p className="eyebrow">MERCADO</p>
        {finance?.ok && finance?.currencies ? (
          Object.entries(finance.currencies).map(([code, value]) => {
            const valObj = value as { bid?: number | string } | undefined
            const rawBid = valObj?.bid
            const numericBid = typeof rawBid === 'number' ? rawBid : Number(rawBid)
            return (
              <p className="market-row" key={code}>
                <span>{code}</span>
                <b>R$ {!isNaN(numericBid) ? numericBid.toFixed(code === 'BTC' ? 0 : 2) : '—'}</b>
              </p>
            )
          })
        ) : (
          <p className="empty-state">Cotações indisponíveis.</p>
        )}
      </SpotlightCard>
      <BentoCard eyebrow="TIMERS" title="Ativos">
        {dashboard?.timers?.length ? (
          dashboard.timers.map((timer, index) => (
            <p className="timer-row" key={index}>
              <b>{timer?.label || 'Timer'}</b>
              <span>{timer?.fire_at ? new Date(timer.fire_at).toLocaleString('pt-BR') : '—'}</span>
            </p>
          ))
        ) : (
          <p className="empty-state">Nenhum timer ativo.</p>
        )}
      </BentoCard>
      <div className="tts-status-widget">
        <p className="eyebrow">VOZ · TTS</p>
        <strong>{ttsSettings?.tts_provider === 'fish' ? 'Fish Audio S2.1 Pro' : ttsSettings?.tts_provider === 'edge' ? 'Edge TTS (Antonio)' : 'Gemini Flash TTS'}</strong>
        <p>{ttsSettings?.tts_provider === 'fish' ? (ttsSettings?.fish_configured ? 'Voz personalizada ativa' : 'Fallback: Edge TTS') : ttsSettings?.tts_provider === 'gemini' ? 'Fallback: Edge TTS' : 'Provedor alternativo ativo'}</p>
      </div>
      <BentoCard eyebrow="ESTUDOS" title="Centro ENEM" span={2}>
        <p>
          <strong>{dashboard?.tutor?.due_flashcards ?? 0}</strong> flashcards · Etapa:{' '}
          {dashboard?.tutor?.stage || '—'}
        </p>
      </BentoCard>
      <BentoCard eyebrow="ATIVIDADE" title="Recente" span={3}>
        {dashboard?.activity?.length ? (
          dashboard.activity.slice(0, 6).map((entry, index) => (
            <p className="activity-row" key={`${entry.timestamp}-${index}`}>
              <span>{entry.type === 'study' ? 'Estudo' : entry.type === 'task' ? 'Tarefa' : 'Chat'}</span>
              {entry.message}
            </p>
          ))
        ) : (
          <p className="empty-state">Nenhuma atividade recente.</p>
        )}
      </BentoCard>
    </section>
  )
}
