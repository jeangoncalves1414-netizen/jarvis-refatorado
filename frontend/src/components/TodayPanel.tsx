import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Check, CircleStop, ListChecks, Play, Wallet } from 'lucide-react'
import { panelRequest } from '../utils/panelApi'
import { broadcastSyncEvent, onSyncEvent } from '../utils/syncChannel'
import { useWindows } from '../windows/WindowManager'
import { WINDOW_FINANCE, WINDOW_LIFE_OS } from '../windows/registry'
import { RecentNotes } from './RecentNotes'
import { PersonalOrganizer } from './PersonalOrganizer'
import type { PersonalPreferences } from '../utils/personalRecords'

type Habit = { id: string; name: string; completed_today: boolean; completed_at?: number | null; isPriority?: boolean; start_time?: string }
type Task = { id: string; title: string; completed: boolean; priority?: number; due_date?: string }
type Entry = { id: string; description: string; category: string; type: 'income' | 'expense'; timestamp: number; amount: number }
type Spending = { totals: { expense: number }; transactions: Entry[] }
const currency = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })
const dateFormat = new Intl.DateTimeFormat('pt-BR', { day: 'numeric', month: 'long' })
const hourFormat = new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' })
const FOCUS_STORAGE_KEY = 'jarvis-today-focus'

function localDay(date: Date) {
  return [date.getFullYear(), String(date.getMonth() + 1).padStart(2, '0'), String(date.getDate()).padStart(2, '0')].join('-')
}

export function TodayPanel() {
  const [preferences, setPreferences] = useState<PersonalPreferences>({ blocks: ['habits', 'tasks', 'workout', 'finance', 'notes'], reduced_motion: false, review: 'off' })
  const { open } = useWindows()
  const [habits, setHabits] = useState<Habit[] | null>(null)
  const [tasks, setTasks] = useState<Task[] | null>(null)
  const [spending, setSpending] = useState<Spending | null>(null)
  const [savedNotes, setSavedNotes] = useState<{ id: string; title: string; timestamp: number }[]>([])
  const [habitError, setHabitError] = useState('')
  const [taskError, setTaskError] = useState('')
  const [financeError, setFinanceError] = useState('')
  const [checking, setChecking] = useState(false)
  const [notice, setNotice] = useState('')
  const checkPending = useRef(false)
  const [refresh, setRefresh] = useState(0)
  const [day, setDay] = useState(() => localDay(new Date()))
  const [capture, setCapture] = useState('')
  const [capturing, setCapturing] = useState(false)
  const [focus, setFocus] = useState<{ taskId: string; endsAt: number } | null>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(FOCUS_STORAGE_KEY) || 'null')
      return saved && typeof saved.taskId === 'string' && Number.isFinite(saved.endsAt) && saved.endsAt > Date.now() ? saved : null
    } catch { return null }
  })
  const [now, setNow] = useState(Date.now())

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
    let taskRequest: AbortController
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
    function loadTasks() {
      taskRequest?.abort()
      taskRequest = new AbortController()
      const { signal } = taskRequest
      panelRequest<{ tasks: Task[] }>('/api/tasks', { signal })
        .then(result => {
          if (!Array.isArray(result.tasks)) throw new Error()
          if (!signal.aborted) { setTasks(result.tasks.filter(task => !task.completed)); setTaskError('') }
        })
        .catch(() => { if (!signal.aborted) setTaskError('Não foi possível consultar a caixa de entrada.') })
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
    const loadAll = () => { loadHabits(); loadTasks(); loadFinance() }
    const whenVisible = () => { if (!document.hidden) loadAll() }
    loadAll()
    const offHabit = onSyncEvent('HABIT_UPDATED', loadHabits)
    window.addEventListener('jarvis:finance-changed', loadFinance)
    window.addEventListener('jarvis-sync-applied', loadAll)
    document.addEventListener('visibilitychange', whenVisible)
    return () => {
      habitRequest.abort(); taskRequest.abort(); financeRequest.abort(); offHabit()
      window.removeEventListener('jarvis:finance-changed', loadFinance)
      window.removeEventListener('jarvis-sync-applied', loadAll)
      document.removeEventListener('visibilitychange', whenVisible)
    }
  }, [day, refresh])

  useEffect(() => {
    if (!focus) return
    const tick = () => {
      const current = Date.now()
      setNow(current)
      if (focus.endsAt <= current) {
        setFocus(null)
        localStorage.removeItem(FOCUS_STORAGE_KEY)
        setNotice('Sessão de foco concluída. Escolha o próximo passo no seu ritmo.')
      }
    }
    tick()
    const timer = window.setInterval(tick, 1_000)
    return () => window.clearInterval(timer)
  }, [focus])

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

  async function captureTask(event: FormEvent) {
    event.preventDefault()
    const title = capture.trim()
    if (!title || capturing) return
    setCapturing(true)
    setTaskError('')
    try {
      const result = await panelRequest<{ ok?: boolean; task?: Task; error?: string }>('/api/tasks', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'create', title }),
      })
      if (result.ok === false || !result.task) throw new Error(result.error || 'Não foi possível salvar a tarefa.')
      setTasks(previous => [result.task!, ...(previous || [])])
      setCapture('')
      setNotice('Guardado na caixa de entrada. Você não precisa organizar isso agora.')
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : 'Não foi possível guardar esta tarefa.')
    } finally { setCapturing(false) }
  }

  async function completeTask(task: Task) {
    if (checking) return
    setChecking(true)
    setTaskError('')
    try {
      const result = await panelRequest<{ ok?: boolean; error?: string }>('/api/tasks', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'toggle', task_id: task.id }),
      })
      if (result.ok === false) throw new Error(result.error || 'Não foi possível concluir a tarefa.')
      setTasks(previous => previous?.filter(item => item.id !== task.id) ?? null)
      setNotice(`${task.title} concluída. Bom trabalho.`)
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : 'Não foi possível concluir a tarefa.')
    } finally { setChecking(false) }
  }

  function startFocus(task: Task) {
    const next = { taskId: task.id, endsAt: Date.now() + 10 * 60_000 }
    setFocus(next)
    localStorage.setItem(FOCUS_STORAGE_KEY, JSON.stringify(next))
    setNotice(`Foco iniciado: ${task.title}. Só dez minutos.`)
  }

  function stopFocus() {
    setFocus(null)
    localStorage.removeItem(FOCUS_STORAGE_KEY)
    setNotice('Foco pausado. Sua tarefa continua guardada para quando der.')
  }

  const done = habits?.filter(item => item.completed_today) ?? []
  const pending = (habits ?? []).filter(item => !item.completed_today)
  pending.sort((a, b) => Number(!!b.isPriority) - Number(!!a.isPriority) || (a.start_time || '24:00').localeCompare(b.start_time || '24:00'))
  const next = pending[0]
  const nextTask = tasks?.[0]
  const focusedTask = focus ? tasks?.find(task => task.id === focus.taskId) : null
  const focusSeconds = focus ? Math.max(0, Math.ceil((focus.endsAt - now) / 1_000)) : 0
  const focusTime = `${String(Math.floor(focusSeconds / 60)).padStart(2, '0')}:${String(focusSeconds % 60).padStart(2, '0')}`
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
    <header className="today-heading"><div><p className="today-overline">SEM PRESSA, SÓ O PRÓXIMO PASSO</p><h2>Hoje</h2></div><time dateTime={day}>{dateFormat.format(new Date(day + 'T12:00:00'))}</time></header>
    <section className="today-now" aria-label="Agora">
      <div className="today-now-copy"><span>AGORA</span><strong>{focusedTask?.title || nextTask?.title || 'Nada definido ainda'}</strong><small>{focusedTask ? `Foco em andamento · ${focusTime}` : nextTask ? `${tasks?.length || 0} tarefa(s) na caixa de entrada` : 'Capture o que está na cabeça e escolha depois.'}</small></div>
      <div className="today-now-actions">
        {focusedTask ? <button type="button" className="ws-button" onClick={stopFocus}><CircleStop size={15} /> Pausar foco</button> : nextTask && <button type="button" className="ws-button primary" onClick={() => startFocus(nextTask)}><Play size={15} /> Focar 10 min</button>}
        {nextTask && !focusedTask && <button type="button" className="ws-text-button" disabled={checking} onClick={() => void completeTask(nextTask)}><Check size={15} /> Concluir</button>}
      </div>
    </section>
    <form className="today-capture" onSubmit={event => void captureTask(event)}>
      <label htmlFor="today-capture-input">Tirar isso da cabeça</label>
      <div><input id="today-capture-input" value={capture} onChange={event => setCapture(event.target.value)} placeholder="Ex.: marcar dentista, responder a mensagem…" maxLength={300} /><button type="submit" className="ws-button primary" disabled={capturing || !capture.trim()}>{capturing ? 'Guardando…' : 'Guardar'}</button></div>
      <small>O texto entra na sua caixa de entrada; organizar pode esperar.</small>
    </form>
    {taskError && <p className="today-error" role="status">{taskError} {retry}</p>}
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
