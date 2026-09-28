import { useEffect, useRef, useState } from 'react'
import { isMobileStandalone } from '../hooks/useDirectChat'

// ─── Types ─────────────────────────────────────────────────────────────────
interface HabitItem {
  id: string
  title: string
  streak: number
  bestStreak: number
  connectedTo?: string
  completed_today: boolean
  isPriority?: boolean
}

interface LifeOSSummary {
  ok: boolean
  date: string
  water: { current_ml: number; target_ml: number; percentage: number }
  habits: { 
    total: number
    completed: number
    rate_percentage: number
    items: HabitItem[]
    priority_total?: number
    priority_completed?: number
  }
  workout: { split_name: string; is_rest_day: boolean; completed: boolean }
  study: { minutes_today: number; sessions_count: number }
  motivational: { quote: string; author: string; action: string; speech: string }
}

// ─── Utilities ─────────────────────────────────────────────────────────────
function getConnectedEmoji(connected?: string) {
  const map: Record<string, string> = {
    treino: '🏋️',
    agua: '💧',
    estudo: '📚',
    leitura: '📖',
  }
  return map[connected || ''] || '⚡'
}

// ─── Sub-components ────────────────────────────────────────────────────────
function WaterMeter({ current, target, onAdd }: { current: number; target: number; onAdd: (ml: number) => void }) {
  const pct = Math.min(100, Math.round((current / target) * 100))
  const angle = (pct / 100) * 360

  const colorAt = pct >= 100 ? '#fbbf24' : pct >= 60 ? '#10b981' : pct >= 30 ? '#f59e0b' : '#ef4444'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16 }}>
      {/* Circular ring */}
      <div style={{ position: 'relative', width: 120, height: 120 }}>
        <svg width={120} height={120} style={{ transform: 'rotate(-90deg)' }}>
          <circle cx={60} cy={60} r={50} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={10} />
          <circle
            cx={60} cy={60} r={50}
            fill="none"
            stroke={colorAt}
            strokeWidth={10}
            strokeDasharray={`${2 * Math.PI * 50}`}
            strokeDashoffset={`${2 * Math.PI * 50 * (1 - pct / 100)}`}
            strokeLinecap="round"
            style={{ transition: 'stroke-dashoffset 0.8s ease, stroke 0.4s ease' }}
          />
        </svg>
        <div style={{
          position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center'
        }}>
          <span style={{ fontSize: 24, lineHeight: 1 }}>💧</span>
          <span style={{ fontSize: 18, fontWeight: 800, color: colorAt, lineHeight: 1.1 }}>{pct}%</span>
          <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.45)' }}>{current}ml</span>
        </div>
      </div>

      <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.5)', textAlign: 'center' }}>
        {current} / {target} ml
      </div>

      {/* Quick-add buttons */}
      <div style={{ display: 'flex', gap: 8 }}>
        {[250, 500, 750].map(ml => (
          <button
            key={ml}
            type="button"
            onClick={() => onAdd(ml)}
            style={{
              padding: '6px 12px', borderRadius: 8,
              background: 'rgba(251,191,36,0.1)',
              border: '1px solid rgba(251,191,36,0.25)',
              color: '#fbbf24', fontWeight: 700, fontSize: 12,
              cursor: 'pointer', transition: 'all 0.2s',
            }}
            onMouseEnter={e => { (e.target as HTMLElement).style.background = 'rgba(251,191,36,0.22)' }}
            onMouseLeave={e => { (e.target as HTMLElement).style.background = 'rgba(251,191,36,0.1)' }}
          >
            +{ml}ml
          </button>
        ))}
      </div>
    </div>
  )
}

function HabitRow({ 
  habit, 
  onToggle, 
  onTogglePriority 
}: { 
  habit: HabitItem
  onToggle: () => void
  onTogglePriority?: () => void
}) {
  const [ripple, setRipple] = useState(false)
  const done = habit.completed_today
  const isPriority = !!habit.isPriority

  return (
    <div
      onClick={() => { setRipple(true); setTimeout(() => setRipple(false), 400); onToggle() }}
      style={{
        display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px',
        borderRadius: 10, cursor: 'pointer',
        background: done 
          ? (isPriority ? 'rgba(255, 180, 0, 0.08)' : 'rgba(0,218,248,0.08)') 
          : (isPriority ? 'rgba(255, 180, 0, 0.04)' : 'rgba(255,255,255,0.02)'),
        border: `1px solid ${done 
          ? (isPriority ? 'rgba(255, 180, 0, 0.35)' : 'rgba(0,218,248,0.2)') 
          : (isPriority ? 'rgba(255, 180, 0, 0.25)' : 'rgba(255,255,255,0.06)')}`,
        boxShadow: isPriority && !done ? '0 0 14px rgba(255, 180, 0, 0.06)' : 'none',
        transition: 'all 0.2s ease',
        transform: ripple ? 'scale(0.97)' : 'scale(1)',
      }}
    >
      {/* Check circle */}
      <div style={{
        width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: done ? (isPriority ? '#ffb400' : '#fbbf24') : 'transparent',
        border: `2px solid ${done ? (isPriority ? '#ffb400' : '#fbbf24') : (isPriority ? 'rgba(255,180,0,0.45)' : 'rgba(255,255,255,0.2)')}`,
        transition: 'all 0.25s ease',
        fontSize: 13, color: '#000', fontWeight: 800
      }}>
        {done ? '✓' : ''}
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          fontSize: 13, fontWeight: 600,
          color: done ? '#e0f9ff' : 'rgba(255,255,255,0.9)',
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'
        }}>
          {isPriority && (
            <span title="Hábito Inegociável" style={{ fontSize: 13, filter: 'drop-shadow(0 0 4px rgba(255,180,0,0.6))' }}>
              👑
            </span>
          )}
          <span>{getConnectedEmoji(habit.connectedTo)}</span>
          <span style={{ textDecoration: done ? 'line-through' : 'none', opacity: done ? 0.7 : 1 }}>
            {habit.title}
          </span>
          {isPriority && (
            <span style={{
              fontSize: 9, fontWeight: 800, textTransform: 'uppercase', letterSpacing: 0.5,
              padding: '1px 5px', borderRadius: 4, background: 'rgba(255,180,0,0.15)',
              color: '#ffb400', border: '1px solid rgba(255,180,0,0.3)'
            }}>
              Inegociável
            </span>
          )}
        </div>
      </div>

      {/* Crown toggle button */}
      {onTogglePriority && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            onTogglePriority()
          }}
          title={isPriority ? "Hábito Inegociável (clique para remover)" : "Promover a Hábito Inegociável"}
          style={{
            background: isPriority ? 'rgba(255,180,0,0.15)' : 'transparent',
            border: isPriority ? '1px solid rgba(255,180,0,0.4)' : '1px solid transparent',
            borderRadius: 6, padding: '3px 6px', cursor: 'pointer',
            fontSize: 12, display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: isPriority ? '#ffb400' : 'rgba(255,255,255,0.25)',
            transition: 'all 0.2s ease',
          }}
        >
          👑
        </button>
      )}

      {/* Streak badge */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 4,
        padding: '3px 8px', borderRadius: 20,
        background: isPriority ? 'rgba(255,180,0,0.15)' : habit.streak >= 7 ? 'rgba(255,170,0,0.15)' : 'rgba(255,255,255,0.05)',
        border: `1px solid ${isPriority ? 'rgba(255,180,0,0.3)' : habit.streak >= 7 ? 'rgba(255,170,0,0.3)' : 'rgba(255,255,255,0.08)'}`,
      }}>
        <span style={{ fontSize: 11 }}>🔥</span>
        <span style={{
          fontSize: 12, fontWeight: 800,
          color: isPriority ? '#ffb400' : habit.streak >= 7 ? '#ffaa00' : 'rgba(255,255,255,0.6)'
        }}>
          {habit.streak}d
        </span>
      </div>
    </div>
  )
}

function MotivationalCard({ speech, author, action }: { speech: string; quote: string; author: string; action: string }) {
  return (
    <div style={{
      position: 'relative', overflow: 'hidden',
      background: 'linear-gradient(135deg, rgba(0,218,248,0.06) 0%, rgba(0,100,255,0.04) 100%)',
      border: '1px solid rgba(0,218,248,0.18)',
      borderRadius: 14, padding: '18px 20px',
    }}>
      {/* Glow accent */}
      <div style={{
        position: 'absolute', top: -20, right: -20, width: 80, height: 80,
        background: 'radial-gradient(circle, rgba(251,191,36,0.18) 0%, transparent 70%)',
        pointerEvents: 'none',
      }} />

      <div style={{ fontSize: 11, color: '#fbbf24', fontWeight: 700, letterSpacing: 1.5, marginBottom: 8 }}>
        💡 FALA DO DIA · JARVIS
      </div>
      <div style={{
        fontSize: 13, color: 'rgba(255,255,255,0.88)', lineHeight: 1.6,
        fontStyle: 'italic', marginBottom: 10
      }}>
        "{speech}"
      </div>
      <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)' }}>
        — {author}
      </div>
      {action && (
        <div style={{
          marginTop: 12, padding: '8px 12px', borderRadius: 8,
          background: 'rgba(251,191,36,0.06)', border: '1px solid rgba(251,191,36,0.15)',
          fontSize: 12, color: '#fbbf24', fontWeight: 600,
        }}>
          🎯 Foco: {action}
        </div>
      )}
    </div>
  )
}

// ─── Main Component ─────────────────────────────────────────────────────────
function getLocalSummaryFallback(): LifeOSSummary | null {
  try {
    // Use local timezone date to avoid UTC off-by-one issues in UTC-3
    const now = new Date()
    const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
    const habitsRaw = localStorage.getItem('lifeos_habits') || localStorage.getItem('jarvis-habits') || '[]'
    const habits = JSON.parse(habitsRaw)
    if (!Array.isArray(habits) || habits.length === 0) return null

    const logsRaw = localStorage.getItem(`lifeos_hlog_${today}`) || '{}'
    const logs = JSON.parse(logsRaw)

    const waterVal = Number(localStorage.getItem(`lifeos_water_${today}`) || 0)
    const items: HabitItem[] = habits.map((h: any) => ({
      id: h.id || String(Math.random()),
      title: h.title || 'Hábito',
      streak: Number(h.streak || 0),
      bestStreak: Number(h.bestStreak || h.streak || 0),
      connectedTo: h.connectedTo,
      completed_today: !!logs[h.id]?.completed,
      isPriority: !!h.isPriority,
    }))

    const completed = items.filter(i => i.completed_today).length
    const total = items.length
    const priorityItems = items.filter(i => i.isPriority)

    const studyLogsRaw = localStorage.getItem('lifeos_study_logs') || '[]'
    const studyLogs = JSON.parse(studyLogsRaw)
    const todayStudyLogs = Array.isArray(studyLogs) ? studyLogs.filter((s: any) => s && s.date === today) : []
    const studyMins = todayStudyLogs.reduce((acc: number, s: any) => acc + (Number(s.minutes) || 0), 0)

    return {
      ok: true,
      date: today,
      water: {
        current_ml: waterVal,
        target_ml: 3000,
        percentage: Math.min(100, Math.round((waterVal / 3000) * 100)),
      },
      habits: {
        total,
        completed,
        rate_percentage: total > 0 ? Math.round((completed / total) * 100) : 0,
        items,
        priority_total: priorityItems.length,
        priority_completed: priorityItems.filter(i => i.completed_today).length,
      },
      workout: { split_name: 'Treino Diário', is_rest_day: false, completed: false },
      study: { minutes_today: studyMins, sessions_count: todayStudyLogs.length },
      motivational: {
        quote: 'A consistência diária vence o talento esporádico.',
        author: 'Evolute Life OS',
        action: 'Mantenha o foco em seus hábitos.',
        speech: 'Você está no comando do seu dia.',
      }
    }
  } catch {
    return null
  }
}

export function EvoluteHubPage() {
  // Evolute is now the integrated Life OS panel inside Jarvis across PC and mobile
  const [showEmbedded, setShowEmbedded] = useState(true)
  const [summary, setSummary] = useState<LifeOSSummary | null>(() => getLocalSummaryFallback())
  const [loading, setLoading] = useState(true)
  const [notice, setNotice] = useState('')
  const [addingWater, setAddingWater] = useState(false)
  const refreshInterval = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchSummary = async () => {
    try {
      const res = await fetch('/api/evolute/summary')
      if (res.ok) {
        const data = await res.json()
        if (data.ok) {
          setSummary(data)
          setLoading(false)
          return
        }
      }
    } catch {
      // offline-resilient: fall back to localStorage
    } finally {
      setLoading(false)
    }

    const fallback = getLocalSummaryFallback()
    if (fallback) {
      setSummary(fallback)
    }
  }

  useEffect(() => {
    fetchSummary()
    refreshInterval.current = setInterval(fetchSummary, 30_000)
    // Refresh when JarvisCloud sync completes
    const syncHandler = () => fetchSummary()
    window.addEventListener('jarvis-sync-applied', syncHandler)
    return () => {
      if (refreshInterval.current) clearInterval(refreshInterval.current)
      window.removeEventListener('jarvis-sync-applied', syncHandler)
    }
  }, [])

  const handleAddWater = async (ml: number) => {
    if (addingWater) return
    setAddingWater(true)
    const d = new Date()
    const today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    try {
      const res = await fetch('/api/evolute/water/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ amount_ml: ml }),
      })
      if (res.ok) {
        const data = await res.json()
        if (data.ok) {
          setSummary(prev => prev ? {
            ...prev,
            water: { ...prev.water, current_ml: data.total_ml, percentage: data.percentage }
          } : prev)
          if (data.habit_completed) setNotice('🎯 Meta de hidratação atingida!')
          else setNotice(`+${ml}ml registrado!`)
          setTimeout(() => setNotice(''), 2500)
          return
        }
      }
    } catch {
      // offline
    } finally {
      setAddingWater(false)
    }

    // LocalStorage fallback for water
    try {
      const current = Number(localStorage.getItem(`lifeos_water_${today}`) || 0)
      const next = current + ml
      localStorage.setItem(`lifeos_water_${today}`, String(next))
      setNotice(`+${ml}ml registrado localmente!`)
      setTimeout(() => setNotice(''), 2500)
      await fetchSummary()
    } catch { /* ignore */ }
  }

  const handleToggleHabit = async (habitNameOrId: string) => {
    const d = new Date()
    const today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    try {
      const res = await fetch('/api/evolute/habit/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ habit_name_or_id: habitNameOrId }),
      })
      if (res.ok) {
        const data = await res.json()
        if (data.ok) {
          setNotice(data.completed ? `✅ ${data.title} marcado!` : `○ ${data.title} desmarcado.`)
          setTimeout(() => setNotice(''), 2500)
          await fetchSummary()
          return
        }
      }
    } catch { /* offline */ }

    // LocalStorage fallback
    try {
      const logsKey = `lifeos_hlog_${today}`
      const logs = JSON.parse(localStorage.getItem(logsKey) || '{}')
      const current = !!logs[habitNameOrId]?.completed
      logs[habitNameOrId] = { completed: !current, value: !current ? 1 : 0 }
      localStorage.setItem(logsKey, JSON.stringify(logs))
      setNotice(!current ? `✅ Hábito marcado!` : `○ Hábito desmarcado.`)
      setTimeout(() => setNotice(''), 2500)
      await fetchSummary()
    } catch { /* ignore */ }
  }

  const handleTogglePriority = async (habitId: string) => {
    try {
      const res = await fetch('/api/evolute/habit/priority', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ habit_name_or_id: habitId }),
      })
      if (res.ok) {
        const data = await res.json()
        if (data.ok) {
          setNotice(data.isPriority ? `👑 ${data.title} marcado como Inegociável!` : `Prioridade inegociável de ${data.title} removida.`)
          setTimeout(() => setNotice(''), 2500)
          await fetchSummary()
          return
        }
      }
    } catch { /* offline */ }

    // LocalStorage fallback
    try {
      const habitsKey = localStorage.getItem('lifeos_habits') ? 'lifeos_habits' : 'jarvis-habits'
      const habits = JSON.parse(localStorage.getItem(habitsKey) || '[]')
      let changedTitle = ''
      let isNowPriority = false
      const updated = habits.map((h: any) => {
        if (h.id === habitId || h.title === habitId) {
          isNowPriority = !h.isPriority
          changedTitle = h.title
          return { ...h, isPriority: isNowPriority }
        }
        return h
      })
      localStorage.setItem('lifeos_habits', JSON.stringify(updated))
      localStorage.setItem('jarvis-habits', JSON.stringify(updated))
      setNotice(isNowPriority ? `👑 ${changedTitle} marcado como Inegociável!` : `Prioridade inegociável de ${changedTitle} removida.`)
      setTimeout(() => setNotice(''), 2500)
      await fetchSummary()
    } catch { /* ignore */ }
  }

  const handleOpenWindow = () => {
    if (isMobileStandalone()) {
      setShowEmbedded(true)
      return
    }
    const pywebview = (window as any).pywebview
    if (pywebview?.api?.openEvolute) {
      pywebview.api.openEvolute()
    } else {
      window.open('/evolute', '_blank', 'width=1380,height=850')
    }
  }

  // ─── Embedded mode ────────────────────────────────────────────────────────
  const [iframeLoading, setIframeLoading] = useState(true)
  const [iframeKey, setIframeKey] = useState(0)

  const evoluteFrameSrc = isMobileStandalone()
    ? '/evolute/index.html?shell=jarvis'
    : '/evolute/?shell=jarvis'

  if (showEmbedded) {
    return (
      <div className="evolute-integrated-view">
        {/* Discreto toolbar no canto superior para ações rápidas */}
        <div className="evolute-integrated-view__toolbar">
          {iframeLoading && (
            <span style={{ fontSize: 11, color: '#fbbf24', fontStyle: 'italic', marginRight: 6 }}>
              Iniciando motor local…
            </span>
          )}
          <button
            type="button"
            className="evolute-integrated-view__btn"
            onClick={() => { setIframeLoading(true); setIframeKey(k => k + 1) }}
            title="Recarregar tela do Evolute"
          >
            🔄 Recarregar
          </button>
          <button
            type="button"
            className="evolute-integrated-view__btn"
            onClick={handleOpenWindow}
            title="Abrir em janela separada"
          >
            ↗ Janela
          </button>
          <button
            type="button"
            className="evolute-integrated-view__btn"
            onClick={() => setShowEmbedded(false)}
            title="Alternar para visão de resumo (HUD)"
          >
            📊 Resumo
          </button>
        </div>

        {iframeLoading && (
          <div className="evolute-mobile-embed__loader">
            <div className="evolute-mobile-embed__spinner" />
            <p>Carregando Life OS…</p>
          </div>
        )}
        <iframe
          key={iframeKey}
          src={evoluteFrameSrc}
          title="Evolute Life OS"
          onLoad={() => setIframeLoading(false)}
          className="evolute-integrated-view__frame"
          allow="camera; microphone; clipboard-read; clipboard-write"
        />
      </div>
    )
  }

  // ─── Hub mode (Live HUD) ──────────────────────────────────────────────────
  const w = summary?.water
  const h = summary?.habits
  const workout = summary?.workout
  const study = summary?.study
  const motiv = summary?.motivational

  return (
    <div className="workspace" style={{ padding: '20px 24px', maxWidth: 1200, margin: '0 auto' }}>

      {/* ── Header ───────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <div style={{ fontSize: 11, color: '#fbbf24', fontWeight: 700, letterSpacing: 2, marginBottom: 4 }}>
            LIFE OS · EVOLUTE
          </div>
          <h1 style={{ margin: 0, fontSize: 26, fontWeight: 800, color: '#fff', letterSpacing: '-0.5px' }}>
            ⚡ Hub de Evolução
          </h1>
          {summary?.date && (
            <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)', marginTop: 4 }}>
              {new Date(summary.date + 'T12:00:00').toLocaleDateString('pt-BR', { weekday: 'long', day: '2-digit', month: 'long' })}
            </div>
          )}
        </div>

        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <button type="button" onClick={() => setShowEmbedded(true)} style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '10px 20px', borderRadius: 10,
            background: 'linear-gradient(135deg, #fbbf24, #d97706)',
            color: '#07090d', fontWeight: 700, fontSize: 13, border: 'none', cursor: 'pointer',
            boxShadow: '0 6px 20px rgba(251,191,36,0.3)', transition: 'all 0.2s',
          }}>
            ⚡ Painel Integrado
          </button>
          <button type="button" onClick={handleOpenWindow} style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '10px 18px', borderRadius: 10,
            background: 'rgba(255,255,255,0.06)',
            color: '#e0e0e0', fontWeight: 600, fontSize: 13,
            border: '1px solid rgba(255,255,255,0.12)', cursor: 'pointer', transition: 'all 0.2s',
          }}>
            🗗 Janela Separada
          </button>
        </div>
      </div>

      {/* ── Toast notice ─────────────────────────────────────────────── */}
      {notice && (
        <div style={{
          marginBottom: 16, padding: '10px 16px', borderRadius: 10,
          background: 'rgba(251,191,36,0.12)', border: '1px solid rgba(251,191,36,0.3)',
          color: '#fbbf24', fontWeight: 600, fontSize: 13,
          transition: 'all 0.3s',
        }}>
          {notice}
        </div>
      )}

      {/* ── Live HUD Grid ─────────────────────────────────────────────── */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: 60, color: 'rgba(255,255,255,0.3)' }}>
          <div style={{ fontSize: 32, marginBottom: 12, animation: 'spin 1s linear infinite' }}>⟳</div>
          <div>Carregando dados do Life OS…</div>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>

          {/* Water Widget */}
          <div style={{
            background: 'rgba(10,15,26,0.7)', backdropFilter: 'blur(12px)',
            border: '1px solid rgba(251,191,36,0.15)', borderRadius: 16, padding: 24,
          }}>
            <div style={{ fontSize: 11, color: '#fbbf24', fontWeight: 700, letterSpacing: 1.5, marginBottom: 16 }}>
              💧 HIDRATAÇÃO
            </div>
            <WaterMeter
              current={w?.current_ml ?? 0}
              target={w?.target_ml ?? 3000}
              onAdd={handleAddWater}
            />
          </div>

          {/* Habits Widget */}
          <div style={{
            background: 'rgba(10,15,26,0.7)', backdropFilter: 'blur(12px)',
            border: '1px solid rgba(255,255,255,0.08)', borderRadius: 16, padding: 24,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 11, color: '#fbbf24', fontWeight: 700, letterSpacing: 1.5 }}>
                  🔥 HÁBITOS
                </span>
                {(h?.priority_total ?? 0) > 0 && (
                  <span style={{
                    fontSize: 10, fontWeight: 700, color: '#ffb400',
                    background: 'rgba(255,180,0,0.12)', border: '1px solid rgba(255,180,0,0.3)',
                    padding: '2px 8px', borderRadius: 12, display: 'flex', alignItems: 'center', gap: 4
                  }}>
                    👑 {h?.priority_completed ?? 0}/{h?.priority_total ?? 0} inegociáveis
                  </span>
                )}
              </div>
              <div style={{
                fontSize: 12, fontWeight: 800, color: '#fbbf24',
                background: 'rgba(251,191,36,0.1)', border: '1px solid rgba(251,191,36,0.25)',
                padding: '3px 10px', borderRadius: 20,
              }}>
                {h?.completed ?? 0}/{h?.total ?? 0}
              </div>
            </div>

            {/* Progress bar */}
            <div style={{
              height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 4, marginBottom: 16, overflow: 'hidden'
            }}>
              <div style={{
                height: '100%', background: 'linear-gradient(90deg, #fbbf24, #f59e0b)',
                borderRadius: 4, width: `${h?.rate_percentage ?? 0}%`,
                transition: 'width 0.8s ease',
              }} />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {[...(h?.items ?? [])]
                .sort((a, b) => (b.isPriority ? 1 : 0) - (a.isPriority ? 1 : 0))
                .map(habit => (
                  <HabitRow
                    key={habit.id}
                    habit={habit}
                    onToggle={() => handleToggleHabit(habit.id)}
                    onTogglePriority={() => handleTogglePriority(habit.id)}
                  />
                ))}
            </div>
          </div>

          {/* Workout + Study Row */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* Workout card */}
            <div style={{
              background: 'rgba(10,15,26,0.7)', backdropFilter: 'blur(12px)',
              border: `1px solid ${workout?.completed ? 'rgba(120,230,140,0.2)' : 'rgba(255,255,255,0.08)'}`,
              borderRadius: 16, padding: '18px 20px', flex: 1,
            }}>
              <div style={{ fontSize: 11, color: workout?.completed ? '#78e68c' : '#fbbf24', fontWeight: 700, letterSpacing: 1.5, marginBottom: 10 }}>
                🏋️ TREINO DE HOJE
              </div>
              <div style={{ fontSize: 15, fontWeight: 700, color: '#fff', marginBottom: 6 }}>
                {workout?.is_rest_day ? 'Descanso Ativo / Recuperação' : (workout?.split_name ?? 'Treino Geral')}
              </div>
              <div style={{
                display: 'inline-flex', alignItems: 'center', gap: 6,
                padding: '4px 12px', borderRadius: 20,
                background: workout?.completed ? 'rgba(120,230,140,0.1)' : 'rgba(255,255,255,0.04)',
                border: `1px solid ${workout?.completed ? 'rgba(120,230,140,0.3)' : 'rgba(255,255,255,0.08)'}`,
                fontSize: 12, fontWeight: 700,
                color: workout?.completed ? '#78e68c' : 'rgba(255,255,255,0.4)',
              }}>
                {workout?.completed ? '✓ Concluído' : '○ Pendente'}
              </div>
            </div>

            {/* Study card */}
            <div style={{
              background: 'rgba(10,15,26,0.7)', backdropFilter: 'blur(12px)',
              border: '1px solid rgba(255,255,255,0.08)', borderRadius: 16, padding: '18px 20px', flex: 1,
            }}>
              <div style={{ fontSize: 11, color: '#fbbf24', fontWeight: 700, letterSpacing: 1.5, marginBottom: 10 }}>
                📚 ESTUDOS DE HOJE
              </div>
              <div style={{ display: 'flex', gap: 20 }}>
                <div>
                  <div style={{ fontSize: 28, fontWeight: 800, color: '#fbbf24', lineHeight: 1 }}>
                    {study?.minutes_today ?? 0}
                  </div>
                  <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', marginTop: 2 }}>minutos</div>
                </div>
                <div>
                  <div style={{ fontSize: 28, fontWeight: 800, color: '#b8f4ff', lineHeight: 1 }}>
                    {study?.sessions_count ?? 0}
                  </div>
                  <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', marginTop: 2 }}>sessões</div>
                </div>
              </div>
            </div>
          </div>

          {/* Motivational full-width */}
          {motiv && (
            <div style={{ gridColumn: '1 / -1' }}>
              <MotivationalCard
                speech={motiv.speech}
                quote={motiv.quote}
                author={motiv.author}
                action={motiv.action}
              />
            </div>
          )}

          {/* Feature tiles */}
          <div style={{ gridColumn: '1 / -1', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 12 }}>
            {[
              { icon: '📚', label: 'Estudos & Flashcards', desc: 'Matérias, simulados e repetição espaçada.' },
              { icon: '🏋️', label: 'Treino & Físico', desc: 'Volume, carga e split semanal.' },
              { icon: '🎯', label: 'Hábitos & Streaks', desc: 'Metas quantitativas e disciplina diária.' },
              { icon: '🛡️', label: 'Mente & Anti-Vício', desc: 'Diário estóico e botão SOS.' },
              { icon: '📖', label: 'Leitura Ativa', desc: 'Livros, citações e resumos.' },
              { icon: '📸', label: 'Álbum de Evolução', desc: 'Fotos corporais e progresso físico.' },
            ].map(tile => (
              <div
                key={tile.label}
                onClick={handleOpenWindow}
                style={{
                  background: 'rgba(255,255,255,0.02)',
                  border: '1px solid rgba(255,255,255,0.06)',
                  borderRadius: 12, padding: '16px 14px',
                  cursor: 'pointer', transition: 'all 0.2s',
                }}
                onMouseEnter={e => {
                  const el = e.currentTarget as HTMLElement
                  el.style.background = 'rgba(0,218,248,0.05)'
                  el.style.borderColor = 'rgba(0,218,248,0.2)'
                }}
                onMouseLeave={e => {
                  const el = e.currentTarget as HTMLElement
                  el.style.background = 'rgba(255,255,255,0.02)'
                  el.style.borderColor = 'rgba(255,255,255,0.06)'
                }}
              >
                <div style={{ fontSize: 20, marginBottom: 6 }}>{tile.icon}</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#e0e0e0', marginBottom: 4 }}>{tile.label}</div>
                <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)', lineHeight: 1.5 }}>{tile.desc}</div>
              </div>
            ))}
          </div>

        </div>
      )}

      {/* ── Keyboard shortcut hint ────────────────────────────────────── */}
      <div style={{ marginTop: 24, textAlign: 'center', fontSize: 12, color: 'rgba(255,255,255,0.3)' }}>
        No Desktop: pressione{' '}
        <kbd style={{
          background: 'rgba(255,255,255,0.06)', padding: '2px 7px',
          borderRadius: 4, border: '1px solid rgba(255,255,255,0.12)',
          color: '#fbbf24', fontWeight: 700,
        }}>
          Alt + E
        </kbd>
        {' '}para abrir a janela dedicada instantaneamente.
      </div>
    </div>
  )
}
