import { useEffect, useRef, useState } from 'react'
import { Check, ListChecks, Wallet } from 'lucide-react'
import { panelRequest } from '../utils/panelApi'
import { broadcastSyncEvent, onSyncEvent } from '../utils/syncChannel'
import { useWindows } from '../windows/WindowManager'
import { WINDOW_FINANCE, WINDOW_LIFE_OS } from '../windows/registry'
import { RecentNotes } from './RecentNotes'
import { PersonalOrganizer } from './PersonalOrganizer'
import type { PersonalPreferences } from '../utils/personalRecords'

type Habit = { id: string; name: string; completed_today: boolean; completed_at?: number | null; isPriority?: boolean; start_time?: string }
type Entry = { id: string; description: string; category: string; type: 'income' | 'expense'; timestamp: number; amount: number }
type Spending = { totals: { expense: number }; transactions: Entry[] }
const currency = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })
const dateFormat = new Intl.DateTimeFormat('pt-BR', { day: 'numeric', month: 'long' })
const hourFormat = new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' })

function localDay(date: Date) {
  return [date.getFullYear(), String(date.getMonth() + 1).padStart(2, '0'), String(date.getDate()).padStart(2, '0')].join('-')
}

export function TodayPanel() {
  const [preferences, setPreferences] = useState<PersonalPreferences>({ blocks: ['habits', 'tasks', 'workout', 'finance', 'notes'], reduced_motion: false, review: 'off' })
  const { open } = useWindows()
  const [habits, setHabits] = useState<Habit[] | null>(null)
  const [spending, setSpending] = useState<Spending | null>(null)
  const [savedNotes, setSavedNotes] = useState<{ id: string; title: string; timestamp: number }[]>([])
  const [habitError, setHabitError] = useState('')
  const [financeError, setFinanceError] = useState('')
  const [checking, setChecking] = useState(false)
  const [notice, setNotice] = useState('')
  const checkPending = useRef(false)
  const [refresh, setRefresh] = useState(0)
  const [day, setDay] = useState(() => localDay(new Date()))

  useEffect(() => {
    const now = new Date()
    const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1)
    const updateDay = () => setDay(localDay(new Date()))
    const timer = window.setTimeout(updateDay, midnight.getTime() - now.getTime() + 50)
    document.addEventListener('visibilitychange', updateDay)
    return () => { clearTimeout(timer); document.removeEventListener('visibilitychange', updateDay) }
  }, [day])

  useEffect(() => {
    let habitRequest: AbortController
    let financeRequest: AbortController
    function loadHabits() {
      habitRequest?.abort()
      habitRequest = new AbortController()
      const { signal } = habitRequest
      panelRequest<{ habits: Habit[] }>('/api/lifeos/habits?today=1', { signal })
        .then(result => {
          if (!Array.isArray(result.habits)) throw new Error()
          if (!signal.aborted) { setHabits(result.habits); setHabitError('') }
        })
        .catch(() => { if (!signal.aborted) setHabitError('Não foi possível consultar os hábitos.') })
    }
    function loadFinance() {
      financeRequest?.abort()
      financeRequest = new AbortController()
      const { signal } = financeRequest
      panelRequest<Spending>('/api/finance', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal,
        body: JSON.stringify({ action: 'list', date_from: day, date_to: day, limit: 5 }),
      }).then(result => {
        if (typeof result.totals?.expense !== 'number' || !Array.isArray(result.transactions)) throw new Error()
        if (!signal.aborted) { setSpending(result); setFinanceError('') }
      }).catch(() => { if (!signal.aborted) setFinanceError('Não foi possível consultar os gastos.') })
    }
    const loadAll = () => { loadHabits(); loadFinance() }
    const whenVisible = () => { if (!document.hidden) loadAll() }
    loadAll()
    const offHabit = onSyncEvent('HABIT_UPDATED', loadHabits)
    window.addEventListener('jarvis:finance-changed', loadFinance)
    window.addEventListener('jarvis-sync-applied', loadAll)
    document.addEventListener('visibilitychange', whenVisible)
    return () => {
      habitRequest.abort(); financeRequest.abort(); offHabit()
      window.removeEventListener('jarvis:finance-changed', loadFinance)
      window.removeEventListener('jarvis-sync-applied', loadAll)
      document.removeEventListener('visibilitychange', whenVisible)
    }
  }, [day, refresh])

  async function markDone(habit: Habit) {
    if (checkPending.current) return
    checkPending.current = true
    setChecking(true)
    setNotice('')
    try {
      const { habit: saved } = await panelRequest<{ habit: Habit & { changed?: boolean } }>(
        '/api/lifeos/habits/' + encodeURIComponent(habit.id) + '/toggle',
        { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ completed: true }) },
      )
      if (!saved?.completed_today) throw new Error()
      setHabits(previous => previous?.map(item => item.id === habit.id ? { ...item, ...saved } : item) ?? null)
      setNotice(saved.changed === false ? habit.name + ' já estava feito hoje.' : habit.name + ' concluído.')
      broadcastSyncEvent('HABIT_UPDATED')
    } catch {
      setNotice('Não consegui confirmar a marcação. Confira a lista e tente novamente.')
      broadcastSyncEvent('HABIT_UPDATED')
    } finally {
      checkPending.current = false
      setChecking(false)
    }
  }

  const done = habits?.filter(item => item.completed_today) ?? []
  const pending = (habits ?? []).filter(item => !item.completed_today)
  pending.sort((a, b) => Number(!!b.isPriority) - Number(!!a.isPriority) || (a.start_time || '24:00').localeCompare(b.start_time || '24:00'))
  const next = pending[0]
  const recent = [
    ...(habitError ? [] : done).map(item => ({ key: 'h-' + item.id, time: item.completed_at ?? 0, text: item.name, value: 'Feito' })),
    ...savedNotes.filter(item => localDay(new Date(item.timestamp * 1000)) === day).map(item => ({
      key: 'n-' + item.id, time: item.timestamp, text: item.title, value: 'Anotação',
    })),
    ...(financeError ? [] : spending?.transactions ?? []).map(item => ({
      key: 'f-' + item.id, time: item.timestamp, text: item.description || item.category,
      value: (item.type === 'income' ? '+' : '−') + currency.format(item.amount),
    })),
  ].sort((a, b) => b.time - a.time).slice(0, 5)
  const retry = <button type="button" className="ws-text-button" onClick={() => setRefresh(value => value + 1)}>Tentar novamente</button>

  return <section className="today-panel" aria-label="Hoje">
    <header className="today-heading"><h2>Hoje</h2><time dateTime={day}>{dateFormat.format(new Date(day + 'T12:00:00'))}</time></header>
    <div className="today-grid">
      <section hidden={!preferences.blocks.includes('habits')} className="today-cell" aria-label="Próximo hábito">
        <h3><ListChecks size={16} /> Próximo hábito</h3>
        {habitError ? <p role="status">{habitError} {retry}</p> : !habits ? <p>Carregando…</p> : <>
          <strong>{next?.name ?? (habits.length ? 'Tudo feito por hoje' : 'Nenhum hábito para hoje')}</strong>
          {habits.length > 0 && <small>{done.length} de {habits.length} feitos</small>}
          <div className="today-actions">
            {next && <button type="button" disabled={checking} className="ws-button primary" onClick={() => void markDone(next)}><Check size={14} /> {checking ? 'Salvando…' : 'Feito'}</button>}
            <button type="button" className="ws-text-button" onClick={() => open(WINDOW_LIFE_OS, { tab: 'habitos' })}>Ver hábitos</button>
          </div>
        </>}
        {notice && <small role="status">{notice}</small>}
      </section>
      <section hidden={!preferences.blocks.includes('finance')} className="today-cell" aria-label="Saídas de hoje">
        <h3><Wallet size={16} /> Saídas de hoje</h3>
        {financeError ? <p role="status">{financeError} {retry}</p> : spending ? <strong>{currency.format(spending.totals.expense)}</strong> : <p>Carregando…</p>}
        <button type="button" className="ws-text-button" onClick={() => open(WINDOW_FINANCE)}>Ver finanças</button>
      </section>
      <div hidden={!preferences.blocks.includes('notes')} className="today-cell"><RecentNotes onRecentSaved={setSavedNotes} /></div>
    </div>
    <PersonalOrganizer onPreferences={setPreferences} />
    <details className="today-history"><summary>Registros de hoje</summary>
      {recent.length > 0 ? <ul>{recent.map(item => <li key={item.key}>
        <span>{item.text}</span><b>{item.value}</b>{item.time > 0 && <time>{hourFormat.format(item.time * 1000)}</time>}
      </li>)}</ul> : <p>{habitError || financeError ? 'Alguns registros estão indisponíveis.' : habits && spending ? 'Nenhum registro de hoje para mostrar.' : 'Carregando…'}</p>}
    </details>
  </section>
}
