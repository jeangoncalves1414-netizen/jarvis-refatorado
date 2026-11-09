import { Check, Circle } from 'lucide-react'
import { motion } from 'framer-motion'
import { CountUp, InsertHighlight, StaggerList, motionTokens, useCalmMotion } from '../motion'
import type { PopupComponentProps, TaskListPopupData, TaskPopupItem } from '../registry'

// Lista de tarefas: as criadas entram uma a uma (StaggerList), a concluída agora ganha o selo e o
// risco em sequência, e o total de pendentes desce com CountUp. Dados sempre do backend.

const idList = (value: unknown) => Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []

function formatDue(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return ''
  const [year, month, day] = value.split('-').map(Number)
  const due = new Date(year, month - 1, day)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const diff = Math.round((due.getTime() - today.getTime()) / 86_400_000)
  if (diff === 0) return 'hoje'
  if (diff === 1) return 'amanhã'
  if (diff === -1) return 'ontem'
  return due.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
}

export function TaskListPopup({ popup }: PopupComponentProps<TaskListPopupData>) {
  const { items, pending, filter } = popup.data
  const added = idList(popup.animate.added_ids)
  const toggled = idList(popup.animate.toggled_ids)
  const updated = idList(popup.animate.updated_ids)
  const newlyDone = items.filter(item => toggled.includes(item.id) && item.completed).length
  const newlyOpen = items.filter(item => added.includes(item.id) && !item.completed).length
  return (
    <div className="ws-popup-tasks">
      <p className="ws-popup-summary">
        <CountUp from={Math.max(0, pending + newlyDone - newlyOpen)} to={pending} /> pendente(s){filter === 'all' ? ` de ${items.length}` : ''}
      </p>
      {items.length === 0
        ? <p className="ws-popup-empty">{filter === 'pending' ? 'Nenhuma tarefa pendente.' : 'Nenhuma tarefa cadastrada.'}</p>
        : (
          <StaggerList
            items={items}
            getId={item => item.id}
            newIds={added}
            renderItem={item => <TaskRow item={item} toggleOrder={toggled.indexOf(item.id)} updated={updated.includes(item.id)} isNew={added.includes(item.id)} />}
          />
        )}
    </div>
  )
}

function TaskRow({ item, toggleOrder, updated, isNew }: { item: TaskPopupItem; toggleOrder: number; updated: boolean; isNew: boolean }) {
  const calm = useCalmMotion()
  const done = item.completed
  const justToggled = toggleOrder >= 0 && !calm
  const delay = justToggled ? 0.12 + toggleOrder * motionTokens.staggerMs / 1000 : 0
  const due = formatDue(item.due_date)
  return (
    <InsertHighlight active={updated}>
      <div className="ws-popup-task" data-new={isNew ? 'true' : undefined} data-done={done ? 'true' : 'false'}>
        <motion.span
          className={`ws-popup-habit-check${done ? ' done' : ''}`}
          role="img"
          aria-label={done ? 'concluída' : 'pendente'}
          initial={justToggled ? { scale: 0.3, opacity: 0.3 } : false}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay, duration: motionTokens.base, ease: motionTokens.ease }}
        >
          {done ? <Check size={12} strokeWidth={3} /> : <Circle size={12} />}
        </motion.span>
        <span className="ws-popup-task-title">
          {item.title}
          {done && (
            <motion.span
              className="ws-popup-task-strike"
              aria-hidden="true"
              initial={justToggled ? { scaleX: 0 } : false}
              animate={{ scaleX: 1 }}
              transition={{ delay: delay + 0.1, duration: motionTokens.base, ease: motionTokens.ease }}
            />
          )}
        </span>
        {due && <span className="ws-popup-task-due">{due}</span>}
        <span className={`ws-popup-task-priority p${item.priority}`} title={`Prioridade ${item.priority}`}>P{item.priority}</span>
      </div>
    </InsertHighlight>
  )
}
