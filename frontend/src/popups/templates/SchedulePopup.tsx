import { BellRing } from 'lucide-react'
import { InsertHighlight, StaggerList } from '../motion'
import type { PopupComponentProps, ScheduleEvent, SchedulePopupData } from '../registry'

// Linha do tempo do dia: compromissos em ordem de horário; o recém-agendado entra em sequência
// e pulsa (InsertHighlight). Horários em pt-BR a partir do ISO local do backend.

const idList = (value: unknown) => Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []

const hourOf = (iso: string) => iso.slice(11, 16)

function localDay(offset = 0) {
  const now = new Date()
  now.setDate(now.getDate() + offset)
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

export function dayLabel(date: string) {
  const formatted = new Date(`${date}T12:00:00`).toLocaleDateString('pt-BR', { weekday: 'long', day: '2-digit', month: 'long' })
  if (date === localDay(0)) return `Hoje, ${formatted}`
  if (date === localDay(1)) return `Amanhã, ${formatted}`
  return formatted.charAt(0).toUpperCase() + formatted.slice(1)
}

export function SchedulePopup({ popup }: PopupComponentProps<SchedulePopupData>) {
  const { date, events } = popup.data
  const added = idList(popup.animate.added_ids)
  return (
    <div className="ws-popup-schedule">
      <p className="ws-popup-summary">{dayLabel(date)} · {events.length} compromisso(s)</p>
      {events.length === 0
        ? <p className="ws-popup-empty">Nenhum compromisso neste dia.</p>
        : (
          <StaggerList
            className="ws-popup-timeline"
            items={events}
            getId={event => event.id}
            newIds={added}
            renderItem={(event, state) => <EventRow event={event} isNew={added.includes(event.id)} pulsing={state.highlighted} />}
          />
        )}
    </div>
  )
}

function EventRow({ event, isNew, pulsing }: { event: ScheduleEvent; isNew: boolean; pulsing: boolean }) {
  return (
    <InsertHighlight active={pulsing} className="ws-popup-event-wrap">
      <div className="ws-popup-event" data-new={isNew ? 'true' : undefined}>
        <time className="ws-popup-event-time" dateTime={event.start}>{hourOf(event.start)}</time>
        <span className="ws-popup-event-dot" aria-hidden="true" />
        <span className="ws-popup-event-title">{event.title}</span>
        {event.reminder_at && (
          <span className="ws-popup-event-reminder" title="Aviso">
            <BellRing size={11} aria-hidden="true" /> {hourOf(event.reminder_at)}
          </span>
        )}
      </div>
    </InsertHighlight>
  )
}
