import { Check, Circle, Flame } from 'lucide-react'
import { motion } from 'framer-motion'
import { CountUp, InsertHighlight, StaggerList, motionTokens, useCalmMotion } from '../motion'
import type { HabitListPopupData, HabitPopupItem, PopupComponentProps } from '../registry'

// Lista de hábitos: os recém-criados entram um a um (StaggerList), os marcados hoje ganham o selo
// em sequência e a contagem de feitos/streak sobe com CountUp. Dados sempre do backend.

const BLOCKS: Record<string, string> = { morning: 'manhã', afternoon: 'tarde', evening: 'noite', anytime: 'qualquer hora' }

const idList = (value: unknown) => Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []

export function HabitListPopup({ popup }: PopupComponentProps<HabitListPopupData>) {
  const { items, completed, total, filter } = popup.data
  const added = idList(popup.animate.added_ids)
  const checked = idList(popup.animate.checked_ids)
  const updated = idList(popup.animate.updated_ids)
  const newlyDone = items.filter(item => checked.includes(item.id) && item.completed_today).length
  return (
    <div className="ws-popup-habits">
      <p className="ws-popup-summary">
        <CountUp from={Math.max(0, completed - newlyDone)} to={completed} /> de {total} feito(s) {filter === 'today' ? 'hoje' : 'no total'}
      </p>
      {items.length === 0
        ? <p className="ws-popup-empty">{filter === 'today' ? 'Nenhum hábito programado para hoje.' : 'Nenhum hábito cadastrado.'}</p>
        : (
          <StaggerList
            items={items}
            getId={item => item.id}
            newIds={added}
            renderItem={item => <HabitRow item={item} eventId={popup.id} checkOrder={checked.indexOf(item.id)} updated={updated.includes(item.id)} isNew={added.includes(item.id)} />}
          />
        )}
    </div>
  )
}

function HabitRow({ item, eventId, checkOrder, updated, isNew }: { item: HabitPopupItem; eventId: string; checkOrder: number; updated: boolean; isNew: boolean }) {
  const calm = useCalmMotion()
  const done = item.completed_today
  const justChecked = checkOrder >= 0 && done && !calm
  const meta = [item.start_time, BLOCKS[item.routine_block] ?? item.routine_block].filter(Boolean).join(' · ')
  return (
    <InsertHighlight active={updated}>
      <div className="ws-popup-habit" data-new={isNew ? 'true' : undefined} data-done={done ? 'true' : 'false'}>
        <motion.span
          key={justChecked ? eventId : "rest"}
          className={`ws-popup-habit-check${done ? ' done' : ''}`}
          role="img"
          aria-label={done ? 'feito hoje' : 'pendente'}
          initial={justChecked ? { scale: 0.3, opacity: 0.3 } : false}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: justChecked ? 0.12 + checkOrder * motionTokens.staggerMs / 1000 : 0, duration: motionTokens.base, ease: motionTokens.ease }}
        >
          {done ? <Check size={12} strokeWidth={3} /> : <Circle size={12} />}
        </motion.span>
        <span className="ws-popup-habit-name">{item.name}</span>
        {meta && <span className="ws-popup-habit-meta">{meta}</span>}
        {item.streak > 0 && (
          <span className="ws-popup-habit-streak" title="Sequência de dias">
            <Flame size={11} aria-hidden="true" />
            <CountUp from={justChecked ? Math.max(0, item.streak - 1) : item.streak} to={item.streak} />
          </span>
        )}
      </div>
    </InsertHighlight>
  )
}
