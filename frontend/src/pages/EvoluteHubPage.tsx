import { useEffect, useRef, useState } from 'react'
import { isMobileStandalone } from '../hooks/useDirectChat'

// Janela LifeOS no tema do workspace (tokens --ws-*, classes lo-* em styles/lifeos.css).
// O app completo (/evolute) recebe o mesmo tema via ?shell=jarvis; aqui ficam a moldura e o hub de resumo.

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

function getConnectedEmoji(connected?: string) {
  const map: Record<string, string> = { treino: '🏋️', agua: '💧', estudo: '📚', leitura: '📖' }
  return map[connected || ''] || '⚡'
}

function WaterMeter({ current, target, onAdd }: { current: number; target: number; onAdd: (ml: number) => void }) {
  const pct = Math.min(100, Math.round((current / target) * 100))
  const circumference = 2 * Math.PI * 50
  const colorAt = pct >= 100 ? 'var(--ws-warn)' : pct >= 60 ? 'var(--ws-accent)' : pct >= 30 ? 'var(--ws-info)' : 'var(--ws-danger)'
  return (
    <div className="lo-water">
      <div className="lo-ring">
        <svg width={120} height={120}>
          <circle cx={60} cy={60} r={50} fill="none" stroke="#ffffff10" strokeWidth={10} />
          <circle
            cx={60} cy={60} r={50} fill="none" stroke={colorAt} strokeWidth={10}
            strokeDasharray={`${circumference}`} strokeDashoffset={`${circumference * (1 - pct / 100)}`}
            strokeLinecap="round" style={{ transition: 'stroke-dashoffset 0.8s ease, stroke 0.4s ease' }}
          />
        </svg>
        <div className="lo-ring-center">
          <b style={{ color: colorAt }}>{pct}%</b>
          <small>{current}ml</small>
        </div>
      </div>
      <small className="lifeos-empty">{current} / {target} ml</small>
      <div className="lo-water-actions">
        {[250, 500, 750].map(ml => (
          <button key={ml} type="button" className="lo-btn" onClick={() => onAdd(ml)}>+{ml}ml</button>
        ))}
      </div>
    </div>
  )
}

function HabitRow({ habit, onToggle, onTogglePriority }: { habit: HabitItem; onToggle: () => void; onTogglePriority?: () => void }) {
  const done = habit.completed_today
  const isPriority = !!habit.isPriority
  return (
    <div className={`lo-habit${done ? ' is-done' : ''}${isPriority ? ' is-priority' : ''}`} onClick={onToggle}>
      <div className="lo-habit-check">{done ? '✓' : ''}</div>
      <div className="lo-habit-title">
        {isPriority && <span title="Hábito Inegociável">👑</span>}
        <span>{getConnectedEmoji(habit.connectedTo)}</span>
        <span>{habit.title}</span>
      </div>
      {onTogglePriority && (
        <button
          type="button"
          className={`lo-crown${isPriority ? ' on' : ''}`}
          onClick={e => { e.stopPropagation(); onTogglePriority() }}
          title={isPriority ? 'Hábito Inegociável (clique para remover)' : 'Promover a Hábito Inegociável'}
        >
          👑
        </button>
      )}
      <span className={`lo-pill${isPriority ? ' warn' : habit.streak >= 7 ? ' accent' : ''}`}>🔥 {habit.streak}d</span>
    </div>
  )
}

function MotivationalCard({ speech, author, action }: { speech: string; quote: string; author: string; action: string }) {
  return (
    <div className="lo-card">
      <p className="lo-eyebrow">Fala do dia · Jarvis</p>
      <p className="lo-quote">"{speech}"</p>
      <div className="lo-quote-author">— {author}</div>
      {action && <div className="lo-focus">Foco: {action}</div>}
    </div>
  )
}

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
        priority_completed: priorityItems.filter(i => i.isPriority && i.completed_today).length,
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
      <div className="lo-frame">
        <div className="lo-frame-bar">
          <strong>Life OS</strong>
          {iframeLoading && <small>Iniciando motor local…</small>}
          <button
            type="button"
            className="lo-btn ghost"
            onClick={() => { setIframeLoading(true); setIframeKey(k => k + 1) }}
            title="Recarregar tela do Evolute"
          >
            Recarregar
          </button>
          <button type="button" className="lo-btn ghost" onClick={handleOpenWindow} title="Abrir em janela separada">
            ↗ Janela
          </button>
          <button type="button" className="lo-btn ghost" onClick={() => setShowEmbedded(false)} title="Alternar para visão de resumo (HUD)">
            Resumo
          </button>
        </div>

        {iframeLoading && (
          <div className="lo-frame-loader">
            <div className="lo-spinner" />
            <p>Carregando Life OS…</p>
          </div>
        )}
        <iframe
          key={iframeKey}
          src={evoluteFrameSrc}
          title="Evolute Life OS"
          onLoad={() => setIframeLoading(false)}
          className="lo-frame-iframe"
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
    <div className="lo-hub">
      <div className="lo-hub-head">
        <div>
          <p className="lo-eyebrow" style={{ margin: 0 }}>Life OS · Evolute</p>
          <h1>Hub de Evolução</h1>
          {summary?.date && (
            <p>{new Date(summary.date + 'T12:00:00').toLocaleDateString('pt-BR', { weekday: 'long', day: '2-digit', month: 'long' })}</p>
          )}
        </div>
        <div className="lo-hub-actions">
          <button type="button" className="lo-btn primary" onClick={() => setShowEmbedded(true)}>Painel Integrado</button>
          <button type="button" className="lo-btn" onClick={handleOpenWindow}>Janela Separada</button>
        </div>
      </div>

      {notice && <div className="lo-notice">{notice}</div>}

      {loading ? (
        <div className="lo-loading">Carregando dados do Life OS…</div>
      ) : (
        <div className="lo-grid">
          <div className="lo-card">
            <p className="lo-eyebrow">💧 Hidratação</p>
            <WaterMeter current={w?.current_ml ?? 0} target={w?.target_ml ?? 3000} onAdd={handleAddWater} />
          </div>

          <div className="lo-card">
            <div className="lo-card-head">
              <div className="lo-row-group">
                <span className="lo-eyebrow">🔥 Hábitos</span>
                {(h?.priority_total ?? 0) > 0 && (
                  <span className="lo-pill warn">👑 {h?.priority_completed ?? 0}/{h?.priority_total ?? 0} inegociáveis</span>
                )}
              </div>
              <span className="lo-pill accent">{h?.completed ?? 0}/{h?.total ?? 0}</span>
            </div>
            <div className="lo-bar"><span style={{ width: `${h?.rate_percentage ?? 0}%` }} /></div>
            <div className="lo-habits">
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

          <div className="lo-col">
            <div className={`lo-card${workout?.completed ? ' is-done' : ''}`}>
              <p className="lo-eyebrow">🏋️ Treino de hoje</p>
              <p className="lo-title-lg">
                {workout?.is_rest_day ? 'Descanso Ativo / Recuperação' : (workout?.split_name ?? 'Treino Geral')}
              </p>
              <span className={`lo-pill${workout?.completed ? ' accent' : ''}`}>{workout?.completed ? '✓ Concluído' : '○ Pendente'}</span>
            </div>
            <div className="lo-card">
              <p className="lo-eyebrow">📚 Estudos de hoje</p>
              <div className="lo-stats">
                <div><b>{study?.minutes_today ?? 0}</b><small>minutos</small></div>
                <div><b>{study?.sessions_count ?? 0}</b><small>sessões</small></div>
              </div>
            </div>
          </div>

          {motiv && (
            <div className="lo-span">
              <MotivationalCard speech={motiv.speech} quote={motiv.quote} author={motiv.author} action={motiv.action} />
            </div>
          )}

          <div className="lo-span lo-tiles">
            {[
              { icon: '📚', label: 'Estudos & Flashcards', desc: 'Matérias, simulados e repetição espaçada.' },
              { icon: '🏋️', label: 'Treino & Físico', desc: 'Volume, carga e split semanal.' },
              { icon: '🎯', label: 'Hábitos & Streaks', desc: 'Metas quantitativas e disciplina diária.' },
              { icon: '🛡️', label: 'Mente & Anti-Vício', desc: 'Diário estóico e botão SOS.' },
              { icon: '📖', label: 'Leitura Ativa', desc: 'Livros, citações e resumos.' },
              { icon: '📸', label: 'Álbum de Evolução', desc: 'Fotos corporais e progresso físico.' },
            ].map(tile => (
              <button key={tile.label} type="button" className="lo-tile" onClick={handleOpenWindow}>
                <span>{tile.icon}</span>
                <b>{tile.label}</b>
                <small>{tile.desc}</small>
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="lo-hint">
        No Desktop: pressione <kbd>Alt + E</kbd> para abrir a janela dedicada instantaneamente.
      </div>
    </div>
  )
}
