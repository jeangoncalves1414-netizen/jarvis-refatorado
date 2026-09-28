import { useEffect, useState } from 'react'
import { BentoCard } from '../components/BentoCard'
import { GlowCard } from '../components/GlowCard'
import { SpotlightCard } from '../components/SpotlightCard'
import { AnimatedProgressCard } from '../components/AnimatedProgressCard'
import { QuantumStatsWidget } from '../components/QuantumStatsWidget'
import { CheckCircle2, Crown, Flame, Zap, Droplets, Play, Volume2, X } from 'lucide-react'
import type { Dashboard, Finance, Proactive, Tray, TtsSettings } from '../types'
import { playClick, playSuccess } from '../utils/sfx'
import { broadcastSyncEvent, onSyncEvent } from '../utils/syncChannel'
import { isMobileStandalone } from '../hooks/useDirectChat'

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
  type LifeHabit = { id: string; name: string; done: boolean; streak?: number; isPriority?: boolean }
  type LifeVice = { id: string; name: string; streak: number; longestStreak: number }
  const [lifeHabits, setLifeHabits] = useState<LifeHabit[]>([])
  const [lifeVices, setLifeVices] = useState<LifeVice[]>([])
  const [lifeScore, setLifeScore] = useState<number | null>(null)
  const [waterMl, setWaterMl] = useState<number>(0)
  const [addingWater, setAddingWater] = useState(false)
  const [briefingLoading, setBriefingLoading] = useState(false)
  const [briefingText, setBriefingText] = useState<string | null>(null)

  const fetchStatus = () => {
    fetch('/api/evolute/status')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (!data) return
        const habits: LifeHabit[] = (data.habits ?? []).map((h: LifeHabit) => ({
          id: h.id,
          name: h.name,
          done: !!h.done,
          streak: h.streak ?? 0,
          isPriority: !!h.isPriority,
        }))
        setLifeHabits(habits)
        setWaterMl(data.waterMl ?? 0)
        setLifeVices(data.vices ?? [])
        const done = habits.filter(h => h.done).length
        const total = habits.length
        setLifeScore(total > 0 ? Math.round((done / total) * 100) : 0)
      })
      .catch(() => {})
  }

  useEffect(() => {
    fetchStatus()
    // Subscribe to cross-window sync events
    const unsubWater = onSyncEvent('WATER_UPDATED', fetchStatus)
    const unsubHabits = onSyncEvent('HABIT_UPDATED', fetchStatus)
    const unsubAll = onSyncEvent('DATA_MUTATED', fetchStatus)
    return () => {
      unsubWater()
      unsubHabits()
      unsubAll()
    }
  }, [])

  const handleAddWater = async (amount: number = 250) => {
    if (addingWater) return
    setAddingWater(true)
    playSuccess()
    try {
      const res = await fetch('/api/evolute/water/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ amount_ml: amount })
      })
      const data = await res.json()
      if (data.ok) {
        setWaterMl(data.total_ml ?? (waterMl + amount))
        broadcastSyncEvent('WATER_UPDATED', { total_ml: data.total_ml })
      }
    } catch {
      setWaterMl(prev => prev + amount)
      broadcastSyncEvent('WATER_UPDATED', { amount })
    } finally {
      setAddingWater(false)
    }
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

  const priorityHabits = lifeHabits.filter(h => h.isPriority)
  const regularHabits = lifeHabits.filter(h => !h.isPriority).slice(0, 4)
  const doneCount = lifeHabits.filter(h => h.done).length
  const totalHabits = lifeHabits.length

  return (
    <section className="dashboard-bento">
      {!isMobileStandalone() && (
      <div style={{ gridColumn: '1 / -1', marginBottom: 10 }}>
        <QuantumStatsWidget />
      </div>
      )}

      {/* ── Life OS Mini HUD ─────────────────────────────────────────── */}
      <div style={{ gridColumn: '1 / -1' }} className="lifeos-hud-card">
        <div className="lifeos-hud-header">
          <span className="lifeos-hud-title"><Zap size={15} /> Life OS · Hoje</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span className="lifeos-hud-score">
              {lifeScore !== null ? (
                <><Flame size={13} style={{ color: lifeScore >= 70 ? '#f97316' : '#64748b' }} /> {doneCount}/{totalHabits} hábitos · {lifeScore}%</>
              ) : 'Carregando…'}
            </span>
            {onOpenEvolute && (
              <button
                type="button"
                onClick={onOpenEvolute}
                className="lifeos-hud-open-btn"
                title="Abrir Painel de Evolução na janela dedicada"
              >
                Abrir Painel ↗
              </button>
            )}
          </div>
        </div>
        <div className="lifeos-hud-body">
          {priorityHabits.length > 0 && (
            <div className="lifeos-priority-section">
              <span className="lifeos-section-label"><Crown size={11} /> Inegociáveis</span>
              <div className="lifeos-habit-row-group">
                {priorityHabits.map(h => (
                  <span key={h.id} className={`lifeos-habit-chip ${h.done ? 'done' : 'pending'} priority`}>
                    {h.done ? '✓' : '○'} {h.name}
                  </span>
                ))}
              </div>
            </div>
          )}
          {regularHabits.length > 0 && (
            <div className="lifeos-regular-section">
              <span className="lifeos-section-label">Hábitos do dia</span>
              <div className="lifeos-habit-row-group">
                {regularHabits.map(h => (
                  <span key={h.id} className={`lifeos-habit-chip ${h.done ? 'done' : 'pending'}`}>
                    {h.done ? '✓' : '○'} {h.name}
                  </span>
                ))}
                {lifeHabits.filter(h => !h.isPriority).length > 4 && (
                  <span className="lifeos-habit-chip more">+{lifeHabits.filter(h => !h.isPriority).length - 4} mais</span>
                )}
              </div>
            </div>
          )}
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

          {lifeHabits.length === 0 && (
            <p className="lifeos-empty">Nenhum hábito cadastrado. Abra o Evolute para começar.</p>
          )}
        </div>
        {totalHabits > 0 && (
          <div className="lifeos-hud-bar-wrap">
            <div className="lifeos-hud-bar" style={{ width: `${lifeScore ?? 0}%` }} />
          </div>
        )}
      </div>

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
      <AnimatedProgressCard
        icon={<CheckCircle2 aria-hidden="true" />}
        title="Ritmo de execução"
        label="HÁBITOS CONCLUÍDOS"
        subLabel={totalHabits ? `${doneCount} de ${totalHabits} hábitos marcados hoje` : 'abra o painel de evolução para começar'}
        currentValue={doneCount}
        maxValue={totalHabits}
      />
      <BentoCard eyebrow="LIFE OS" title="Inegociáveis" meta={`${priorityHabits.filter(h => !h.done).length} pendentes`}>
        <strong className="stat-big">{priorityHabits.length ? `${priorityHabits.filter(h => h.done).length}/${priorityHabits.length}` : '—'}</strong>
      </BentoCard>
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
