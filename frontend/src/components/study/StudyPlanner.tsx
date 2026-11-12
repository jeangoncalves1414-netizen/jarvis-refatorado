import { studyGet } from '../../utils/studyGet'
import { useEffect, useState } from 'react'

type Card = { id: string; front: string; topic?: string; tags?: string[]; due?: string; state?: string }
type Scheduled = { due?: string }
type Plan = { goals: Record<string, string>; columns: Record<string, string> }
const columns = ['Novos', 'Aprendendo', 'Revisão', 'Dominados']
const emptyPlan = (): Plan => ({ goals: {}, columns: {} })
function loadPlan(): Plan {
  try {
    const plan = JSON.parse(localStorage.getItem('jarvis.study.plan') || '{}')
    return { goals: plan.goals || {}, columns: plan.columns || {} }
  } catch { return emptyPlan() }
}
function dayKey(date: Date) {
  return [date.getFullYear(), String(date.getMonth() + 1).padStart(2, '0'), String(date.getDate()).padStart(2, '0')].join('-')
}
function dueKey(card: Scheduled, today: string) {
  if (!card.due) return today
  const key = card.due.length === 10 ? card.due : dayKey(new Date(card.due))
  return key < today ? today : key
}
export function StudyPlanner() {
  const [cards, setCards] = useState<Card[]>([])
  const [vocab, setVocab] = useState<Scheduled[]>([])
  const [status, setStatus] = useState<'loading'|'error'|'ready'>('loading')
  const [attempt, setAttempt] = useState(0)
  const [week, setWeek] = useState(0)
  const [filter, setFilter] = useState('')
  const [limit, setLimit] = useState(20)
  const [plan, setPlan] = useState(loadPlan)
  const [saveError, setSaveError] = useState(false)
  useEffect(() => {
    try { localStorage.setItem('jarvis.study.plan', JSON.stringify(plan)); setSaveError(false) }
    catch { setSaveError(true) }
  }, [plan])
  useEffect(() => {
    const controller = new AbortController()
    setStatus('loading')
    async function read(path: string) {
      const response = await studyGet(path, controller.signal)
      if (!response.ok) throw new Error()
      const {cards} = await response.json()
      if (!Array.isArray(cards)) throw new Error()
      return cards
    }
    Promise.all([read('/api/tutor/flashcards'), read('/api/language/vocabulary')]).then(([deck, words]) => {
      if (!controller.signal.aborted) { setCards(deck); setVocab(words); setStatus('ready') }
    }).catch(() => { if (!controller.signal.aborted) setStatus('error') })
    return () => controller.abort()
  }, [attempt])
  const today = dayKey(new Date())
  const dates = Array.from({length: 7}, (_, i) => {
    const date = new Date()
    date.setDate(date.getDate() - (date.getDay() + 6) % 7 + week * 7 + i)
    return date
  })
  const counts = new Map<string, number>()
  for (const card of [...cards, ...vocab]) {
    const day = dueKey(card, today)
    counts.set(day, (counts.get(day) || 0) + 1)
  }
  const visible = cards.filter(card => [card.topic, ...(card.tags || [])].some(t => t?.toLowerCase().includes(filter.trim().toLowerCase())) || !filter.trim())
  function move(id: string, column: string) {
    if (cards.some(card => card.id === id)) setPlan(p => ({...p, columns: {...p.columns, [id]: column}}))
  }
  return <details><summary>Calendário, plano semanal e quadro de cartões</summary>
    {saveError && <p role="alert">O navegador não conseguiu salvar seu plano neste dispositivo.</p>}
    {status === 'loading' && <progress aria-label="Carregando cartões" />}
    {status === 'error' && <p role="alert">Falha ao carregar a previsão. <button onClick={() => setAttempt(n => n + 1)}>Tentar novamente</button></p>}
    <button onClick={() => setWeek(n => n - 1)}>Semana anterior</button> <button onClick={() => setWeek(0)}>Hoje</button> <button onClick={() => setWeek(n => n + 1)}>Próxima semana</button>
    {dates.map(date => {
      const day = dayKey(date)
      return <label key={day} className="lang-vocab-row"><b>{date.toLocaleDateString('pt-BR', {weekday:'short', day:'numeric', month:'numeric'})}</b>
        <span>{status === 'ready' ? (counts.get(day) || 0) + ' revisões' : '…'}</span>
        <input aria-label={'Meta para ' + day} placeholder="Meta de estudo" maxLength={160} value={plan.goals[day] || ''}
          onChange={e => setPlan(p => ({ ...p, goals: {...p.goals, [day]: e.target.value} }))} /></label>
    })}
    <label>Meta da semana <input maxLength={200} placeholder="50 palavras, 3 práticas de pronúncia e 1 conversa" value={plan.goals['week-'+dayKey(dates[0])] || ''}
      onChange={e => setPlan(p => ({...p,goals:{...p.goals,['week-'+dayKey(dates[0])]:e.target.value}}))} /></label>
    {status === 'ready' && <p>{dates.reduce((sum, date) => sum+(counts.get(dayKey(date)) || 0),0)} revisões agendadas nesta semana.</p>}
    <h3>Quadro de cartões</h3>
    <input aria-label="Filtrar por baralho ou tag" placeholder="Baralho ou tag" value={filter} onChange={e => {setFilter(e.target.value); setLimit(20)}} />
    {status === 'ready' && !visible.length && <p>Nenhum cartão encontrado. Crie um na aba Revisão ou ajuste o filtro.</p>}
    <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(140px,1fr))',gap:8}}>
      {columns.map(column => <section key={column} onDragOver={e => e.preventDefault()} onDrop={e => {e.preventDefault(); move(e.dataTransfer.getData('text/plain'), column)}}>
        <h4>{column}</h4>
        {visible.slice(0, limit).filter(c => (plan.columns[c.id] || ({new:columns[0],review:columns[2]}[c.state || 'new'] || columns[1])) === column).map(card =>
          <article draggable key={card.id} onDragStart={e => e.dataTransfer.setData('text/plain',card.id)}>
            <small>{card.topic} {card.tags?.join(' · ')}</small><p>{card.front}</p>
            <select aria-label={'Mover ' + card.front} value={column} onChange={e => move(card.id,e.target.value)}>{columns.map(c => <option key={c}>{c}</option>)}</select>
          </article>)}
      </section>)}
    </div>
    {visible.length > limit && <button onClick={() => setLimit(n => n + 20)}>Mostrar mais cartões</button>}
  </details>
}
