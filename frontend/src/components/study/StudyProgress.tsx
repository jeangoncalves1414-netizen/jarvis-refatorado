import type { StudyDashboardData, StudyStateCounts, StudyStatsData } from '../../types'

type StudyProgressProps = {
  stats: StudyStatsData | null
  dashboard: StudyDashboardData | null
}

const CELL = 11
const GAP = 2
const STEP = CELL + GAP
const MONTH_ROW = 14
const MONTHS = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
const STATES: { id: keyof StudyStateCounts; label: string }[] = [
  { id: 'new', label: 'Novos' },
  { id: 'learning', label: 'Aprendendo' },
  { id: 'review', label: 'Revisão' },
  { id: 'relearning', label: 'Reaprendendo' },
]
const BAR_WIDTH = 14
const BAR_GAP = 4
const BAR_HEIGHT = 80
const BAR_LABEL = 14

// Datas da API são 'AAAA-MM-DD' locais; lidas em UTC para o dia da semana não variar com o fuso.
function parseDay(date: string) {
  return new Date(`${date}T00:00:00Z`)
}

function formatDay(date: string, withYear = true) {
  const [year, month, day] = date.split('-')
  return withYear ? `${day}/${month}/${year}` : `${day}/${month}`
}

function heatLevel(xp: number, reviews: number, goal: number) {
  if (xp <= 0) return reviews > 0 ? 1 : 0
  const ratio = xp / Math.max(1, goal)
  if (ratio < 0.25) return 1
  if (ratio < 0.5) return 2
  if (ratio < 1) return 3
  return 4
}

function Heatmap({ days, goal }: { days: StudyStatsData['heatmap']; goal: number }) {
  // Semanas começam no domingo: a primeira coluna é deslocada pelo dia da semana do primeiro dia.
  const offset = days.length ? parseDay(days[0].date).getUTCDay() : 0
  const columns = Math.max(1, Math.ceil((days.length + offset) / 7))
  const width = columns * STEP
  const height = MONTH_ROW + 7 * STEP
  const months: { col: number; label: string }[] = []
  days.forEach((day, index) => {
    const date = parseDay(day.date)
    const col = Math.floor((index + offset) / 7)
    if (date.getUTCDate() === 1 || index === 0) {
      if (!months.length || col - months[months.length - 1].col >= 3) months.push({ col, label: MONTHS[date.getUTCMonth()] })
    }
  })
  return (
    <svg className="study-heatmap" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Atividade de estudo nos últimos 12 meses">
      {months.map(month => (
        <text key={`${month.col}-${month.label}`} className="study-chart-label" x={month.col * STEP} y={10}>{month.label}</text>
      ))}
      {days.map((day, index) => {
        const col = Math.floor((index + offset) / 7)
        const row = (index + offset) % 7
        return (
          <rect
            key={day.date}
            className={`hm-cell hm-${heatLevel(day.xp, day.reviews, goal)}`}
            x={col * STEP}
            y={MONTH_ROW + row * STEP}
            width={CELL}
            height={CELL}
            rx={2}
          >
            <title>{`${formatDay(day.date)}: ${day.reviews} revisões, ${day.xp} XP`}</title>
          </rect>
        )
      })}
    </svg>
  )
}

function ReviewBars({ days }: { days: StudyStatsData['daily_reviews'] }) {
  const max = Math.max(1, ...days.map(day => day.tutor + day.language))
  const width = Math.max(1, days.length * (BAR_WIDTH + BAR_GAP))
  const scale = (value: number) => (value / max) * BAR_HEIGHT
  return (
    <svg className="study-bars" viewBox={`0 0 ${width} ${BAR_HEIGHT + BAR_LABEL}`} role="img" aria-label="Revisões por dia nos últimos 30 dias">
      {days.map((day, index) => {
        const x = index * (BAR_WIDTH + BAR_GAP)
        const tutorHeight = scale(day.tutor)
        const languageHeight = scale(day.language)
        return (
          <g key={day.date}>
            <title>{`${formatDay(day.date, false)}: ${day.tutor} ENEM, ${day.language} Idiomas`}</title>
            <rect className="study-bar-bg" x={x} y={0} width={BAR_WIDTH} height={BAR_HEIGHT} rx={2} />
            {tutorHeight > 0 && <rect className="study-bar-tutor" x={x} y={BAR_HEIGHT - tutorHeight} width={BAR_WIDTH} height={tutorHeight} rx={2} />}
            {languageHeight > 0 && <rect className="study-bar-language" x={x} y={BAR_HEIGHT - tutorHeight - languageHeight} width={BAR_WIDTH} height={languageHeight} rx={2} />}
            {index % 5 === 0 && <text className="study-chart-label" x={x} y={BAR_HEIGHT + BAR_LABEL - 2}>{formatDay(day.date, false)}</text>}
          </g>
        )
      })}
    </svg>
  )
}

function StateBar({ states }: { states: StudyStatsData['states'] }) {
  const total = STATES.reduce((sum, state) => sum + states.total[state.id], 0)
  return (
    <>
      <div className="study-state-bar" role="img" aria-label="Distribuição dos cartões por estado">
        {total > 0 && STATES.map(state => states.total[state.id] > 0 && (
          <div key={state.id} className={`study-state-${state.id}`} style={{ width: `${(states.total[state.id] / total) * 100}%` }} />
        ))}
      </div>
      <div className="study-legend study-state-legend">
        {STATES.map(state => (
          <span key={state.id}>
            <i className={`study-state-${state.id}`} />
            <b>{state.label}</b> {states.total[state.id]}
            <small>ENEM {states.tutor[state.id]} · Idiomas {states.language[state.id]}</small>
          </span>
        ))}
      </div>
    </>
  )
}

export function StudyProgress({ stats, dashboard }: StudyProgressProps) {
  if (!stats) return <p className="study-today-copy">Carregando estatísticas…</p>
  const goal = dashboard?.xp.daily_goal || 100
  const rate = stats.retention.rate
  return (
    <div className="study-progress">
      <section>
        <h3>Atividade no último ano</h3>
        <Heatmap days={stats.heatmap} goal={goal} />
        <div className="study-legend study-heatmap-legend">
          <span>Menos</span>
          {[0, 1, 2, 3, 4].map(level => <i key={level} className={`hm-${level}`} />)}
          <span>Mais</span>
        </div>
      </section>
      <section>
        <h3>Revisões nos últimos 30 dias</h3>
        <ReviewBars days={stats.daily_reviews} />
        <div className="study-legend">
          <span><i className="study-bar-tutor" />ENEM</span>
          <span><i className="study-bar-language" />Idiomas</span>
        </div>
      </section>
      <div className="study-progress-row">
        <section className="study-retention">
          <h3>Retenção ({stats.retention.window_days} dias)</h3>
          <strong>{rate === null ? '—' : `${Math.round(rate * 100)}%`}</strong>
          <small>{stats.retention.correct} de {stats.retention.total} revisões de cartões maduros</small>
        </section>
        <section className="study-states">
          <h3>Estados dos cartões</h3>
          <StateBar states={stats.states} />
        </section>
      </div>
      {dashboard && (
        <section>
          <h3>Conquistas</h3>
          <div className="study-badges">
            {dashboard.badges.map(badge => (
              <div key={badge.id} className={`study-badge${badge.earned ? ' earned' : ''}`} title={badge.description}>
                <span aria-hidden="true">{badge.earned ? '🏅' : '🔒'}</span>
                <b>{badge.label}</b>
                {badge.earned && <small>{badge.description}</small>}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
