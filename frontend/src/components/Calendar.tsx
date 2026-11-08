import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { DayPicker } from 'react-day-picker'
import { ptBR } from 'react-day-picker/locale'
import '../styles/calendar.css'

export type CalendarEvent = {
  id: string
  title: string
  start: string
  reminder_minutes?: number
  reminder_policy?: 'once' | 'until_confirmed' | 'next_conversation'
  reminder_at?: string
  reminder_status?: string
}

type CalendarSectionProps = { onNotice?: (notice: string) => void }

const MONTHS_PT = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
const reminderOptions = [{ value: '5', label: '5 min antes' }, { value: '15', label: '15 min antes' }, { value: '30', label: '30 min antes' }, { value: '60', label: '1 hora antes' }, { value: 'custom', label: 'Em um horário específico' }]

const toDateInput = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
const dayKey = (date: Date) => toDateInput(date)
const eventDate = (event: CalendarEvent) => new Date(event.start)

export function CalendarSection({ onNotice }: CalendarSectionProps) {
  const [events, setEvents] = useState<CalendarEvent[]>([])
  const [selectedDay, setSelectedDay] = useState<Date>()
  const [modalOpen, setModalOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [title, setTitle] = useState('')
  const [date, setDate] = useState(() => toDateInput(new Date()))
  const [time, setTime] = useState('09:00')
  const [reminder, setReminder] = useState('15')
  const [reminderTime, setReminderTime] = useState('09:00')
  const [policy, setPolicy] = useState<CalendarEvent['reminder_policy']>('once')

  const loadEvents = useCallback(async () => {
    try {
      const response = await fetch('/api/calendar')
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || 'Não foi possível carregar os eventos.')
      setEvents(Array.isArray(data.events) ? data.events : [])
    } catch (error) {
      onNotice?.(error instanceof Error ? error.message : 'Não foi possível carregar o calendário.')
    }
  }, [onNotice])

  useEffect(() => { loadEvents().catch(() => undefined) }, [loadEvents])

  const selectedEvents = useMemo(() => selectedDay ? events.filter(event => dayKey(eventDate(event)) === dayKey(selectedDay)) : [], [events, selectedDay])
  const eventDays = useMemo(() => Array.from(new Set(events.map(event => dayKey(eventDate(event))))).map(key => new Date(`${key}T12:00:00`)), [events])

  const openNewEvent = () => {
    const day = selectedDay || new Date()
    setDate(toDateInput(day))
    setReminderTime(time)
    setModalOpen(true)
  }

  const saveEvent = async (event: FormEvent) => {
    event.preventDefault()
    if (!title.trim()) return onNotice?.('Dê um nome ao lembrete.')
    setSaving(true)
    try {
      const reminderAt = reminder === 'custom' ? `${date}T${reminderTime}:00` : undefined
      const response = await fetch('/api/calendar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
        title: title.trim(), start: `${date}T${time}:00`, reminder_minutes: reminder === 'custom' ? 0 : Number(reminder), reminder_at: reminderAt, reminder_policy: policy,
      }) })
      const data = await response.json()
      if (!response.ok || !data.ok) throw new Error(data.error || 'Não foi possível criar o lembrete.')
      setTitle('')
      setModalOpen(false)
      await loadEvents()
    } catch (error) {
      onNotice?.(error instanceof Error ? error.message : 'Não foi possível criar o lembrete.')
    } finally { setSaving(false) }
  }

  const cancelReminder = async (id: string) => {
    const response = await fetch('/api/calendar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'cancel_reminder', id }) })
    const data = await response.json().catch(() => ({}))
    if (!response.ok || !data.ok) return onNotice?.(data.error || 'Não foi possível parar este lembrete.')
    await loadEvents()
  }

  return <section className="cal-page">
    <div className="cal-card"><p className="cal-eyebrow">Calendário</p>
      <DayPicker
        mode="single"
        selected={selectedDay}
        onSelect={day => setSelectedDay(day)}
        locale={ptBR}
        modifiers={{ hasEvent: eventDays }}
        modifiersClassNames={{ hasEvent: 'rdp-day--has-event' }}
        formatters={{ formatCaption: value => `${MONTHS_PT[value.getMonth()]} ${value.getFullYear()}` }}
      />
    </div>
    <div className="cal-card cal-side"><p className="cal-eyebrow">{selectedDay ? selectedDay.toLocaleDateString('pt-BR') : 'Dia'}</p>{!selectedDay && <p className="cal-empty">Selecione um dia para ver ou agendar lembretes.</p>}{selectedDay && <>
      <button type="button" className="cal-btn primary" onClick={openNewEvent}>＋ Agendar lembrete para {selectedDay.toLocaleDateString('pt-BR')}</button>
      {selectedEvents.map(event => <div className="cal-event" key={event.id}><span>{eventDate(event).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })} · {event.title}</span>{event.reminder_status !== 'cancelled' && <button type="button" onClick={() => cancelReminder(event.id)} title="Parar lembrete">×</button>}</div>)}
    </>}</div>
    {modalOpen && <div className="cal-modal" role="dialog" aria-modal="true" aria-label="Agendar lembrete"><form onSubmit={saveEvent}>
      <button type="button" className="cal-close" onClick={() => setModalOpen(false)} aria-label="Fechar">×</button>
      <input autoFocus value={title} onChange={event => setTitle(event.target.value)} placeholder="Ex.: Festa da Ana" />
      <div><input type="date" value={date} onChange={event => setDate(event.target.value)} /><input type="time" value={time} onChange={event => setTime(event.target.value)} /></div>
      <select value={reminder} onChange={event => setReminder(event.target.value)}>{reminderOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select>
      {reminder === 'custom' && <input type="time" value={reminderTime} onChange={event => setReminderTime(event.target.value)} />}
      <select value={policy} onChange={event => setPolicy(event.target.value as CalendarEvent['reminder_policy'])}><option value="once">Avisar uma única vez</option><option value="until_confirmed">Repetir até eu confirmar</option><option value="next_conversation">Avisar na próxima conversa</option></select>
      <button type="submit" className="cal-btn primary" disabled={saving}>{saving ? 'Salvando…' : 'Salvar lembrete'}</button>
    </form></div>}
  </section>
}
