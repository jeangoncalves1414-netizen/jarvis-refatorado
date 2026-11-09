import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { Pin, PinOff, X, type LucideIcon } from 'lucide-react'

// Primitivas de animação dos popups (lote 6, seção d do plano). Reutilizadas pelos modelos de
// hábitos, agenda, água, anotações, tarefas e lugares. Com movimento reduzido, toda primitiva
// mostra o estado final sem transição (só troca de opacidade curta).

export const motionTokens = {
  fast: 0.16,
  base: 0.28,
  slow: 0.9,
  ease: [0.2, 0.8, 0.2, 1] as [number, number, number, number],
  staggerMs: 280,
  highlightMs: 1200,
  calmFade: 0.12,
}

const REDUCED_QUERY = '(prefers-reduced-motion: reduce)'

/** true quando o sistema pede movimento reduzido (framer ou matchMedia). */
export function useCalmMotion() {
  const framer = useReducedMotion()
  const [media, setMedia] = useState(() => typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia(REDUCED_QUERY).matches)
  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return
    const query = window.matchMedia(REDUCED_QUERY)
    const onChange = () => setMedia(query.matches)
    onChange()
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])
  return Boolean(framer) || media
}

// ── 2. Moldura ────────────────────────────────────────────────────────────────

type PopupFrameProps = {
  id: string
  title: string
  icon: LucideIcon
  pinned: boolean
  tone?: string
  // Barra fina do tempo restante; ausente quando o popup não expira.
  ttl?: { ms: number; running: boolean; revision: number } | null
  onPin: () => void
  onClose: () => void
  onEntered?: () => void
  onPause?: (paused: boolean) => void
  children: ReactNode
}

export function PopupFrame({ id, title, icon: Icon, pinned, tone, ttl, onPin, onClose, onEntered, onPause, children }: PopupFrameProps) {
  const calm = useCalmMotion()
  const enteredRef = useRef(onEntered)
  enteredRef.current = onEntered
  useEffect(() => {
    const timer = window.setTimeout(() => enteredRef.current?.(), calm ? 0 : motionTokens.base * 1000 + 40)
    return () => window.clearTimeout(timer)
  }, [calm])
  const onKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key !== 'Escape' || event.defaultPrevented) return
    event.preventDefault()
    event.stopPropagation()
    onClose()
  }
  const titleId = `ws-popup-title-${id}`
  return (
    <motion.section
      layout={!calm}
      className={`ws-popup${tone ? ` tone-${tone}` : ''}`}
      data-popup-id={id}
      data-motion={calm ? 'calm' : 'full'}
      role="dialog"
      aria-modal="false"
      aria-labelledby={titleId}
      tabIndex={-1}
      initial={calm ? { opacity: 0 } : { opacity: 0, y: 12, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={calm ? { opacity: 0, transition: { duration: motionTokens.calmFade } } : { opacity: 0, y: 8, scale: 0.98, transition: { duration: motionTokens.fast } }}
      transition={calm ? { duration: motionTokens.calmFade } : { duration: motionTokens.base, ease: motionTokens.ease }}
      onKeyDown={onKeyDown}
      onMouseEnter={() => onPause?.(true)}
      onMouseLeave={() => onPause?.(false)}
      onFocus={() => onPause?.(true)}
      onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) onPause?.(false) }}
    >
      <header className="ws-popup-head">
        <Icon size={15} aria-hidden="true" />
        <strong id={titleId}>{title}</strong>
        <span className="ws-popup-spacer" />
        <button type="button" className="ws-popup-button" aria-pressed={pinned} aria-label={pinned ? 'Soltar popup' : 'Fixar popup'} title={pinned ? 'Soltar' : 'Fixar'} onClick={onPin}>
          {pinned ? <PinOff size={14} /> : <Pin size={14} />}
        </button>
        <button type="button" className="ws-popup-button" aria-label="Fechar popup" title="Fechar (Esc)" onClick={onClose}><X size={14} /></button>
      </header>
      <div className="ws-popup-body">{children}</div>
      {ttl && ttl.ms > 0 && (
        <div className="ws-popup-ttl" aria-hidden="true">
          <span key={ttl.revision} style={{ animationDuration: `${ttl.ms}ms`, animationPlayState: ttl.running ? 'running' : 'paused' }} />
        </div>
      )}
    </motion.section>
  )
}

// ── 3. Lista em sequência ────────────────────────────────────────────────────

type StaggerListProps<T> = {
  items: T[]
  getId: (item: T) => string
  // Ids novos, na ordem em que devem entrar. Itens que não estão aqui aparecem parados.
  newIds?: string[]
  renderItem: (item: T, state: { isNew: boolean; highlighted: boolean }) => ReactNode
  className?: string
  intervalMs?: number
}

export function StaggerList<T>({ items, getId, newIds = [], renderItem, className, intervalMs = motionTokens.staggerMs }: StaggerListProps<T>) {
  const calm = useCalmMotion()
  const present = new Set(items.map(getId))
  const order = newIds.filter(id => present.has(id))
  const signature = order.join('|')
  const [revealed, setRevealed] = useState(calm ? order.length : 0)
  const [highlighted, setHighlighted] = useState<string[]>([])

  useEffect(() => {
    if (calm) { setRevealed(order.length); setHighlighted([]); return }
    setRevealed(0)
    let index = 0
    const timers: number[] = []
    const step = () => {
      if (index >= order.length) return
      const id = order[index]
      index += 1
      setRevealed(index)
      setHighlighted(previous => [...previous, id])
      timers.push(window.setTimeout(() => setHighlighted(previous => previous.filter(item => item !== id)), motionTokens.highlightMs))
      if (index < order.length) timers.push(window.setTimeout(step, intervalMs))
    }
    timers.push(window.setTimeout(step, 60))
    return () => timers.forEach(timer => window.clearTimeout(timer))
    // A assinatura dos ids novos decide quando reiniciar a sequência.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature, calm, intervalMs])

  const visibleNew = new Set(order.slice(0, revealed))
  const pending = new Set(order.slice(revealed))
  return (
    <ul className={`ws-popup-list${className ? ` ${className}` : ''}`}>
      {items.filter(item => !pending.has(getId(item))).map(item => {
        const id = getId(item)
        const isNew = visibleNew.has(id)
        const lit = highlighted.includes(id)
        return (
          <motion.li
            key={id}
            layout={!calm}
            data-popup-item={id}
            className={lit ? 'ws-popup-item is-new' : 'ws-popup-item'}
            initial={isNew && !calm ? { opacity: 0, x: 14 } : false}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: motionTokens.base, ease: motionTokens.ease }}
          >
            {renderItem(item, { isNew, highlighted: lit })}
          </motion.li>
        )
      })}
    </ul>
  )
}

// ── 4. Número que conta ──────────────────────────────────────────────────────

type CountUpProps = { from: number; to: number; format?: (value: number) => string; durationMs?: number; className?: string }

const defaultFormat = (value: number) => Math.round(value).toLocaleString('pt-BR')

export function CountUp({ from, to, format = defaultFormat, durationMs = motionTokens.slow * 1000, className }: CountUpProps) {
  const calm = useCalmMotion()
  const [value, setValue] = useState(calm ? to : from)
  useEffect(() => {
    if (calm || from === to) { setValue(to); return }
    let frame = 0
    const start = performance.now()
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs)
      const eased = 1 - Math.pow(1 - t, 3)
      setValue(from + (to - from) * eased)
      if (t < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [from, to, durationMs, calm])
  return <span className={className}>{format(value)}</span>
}

// ── 5. Copo/tanque com ondas ─────────────────────────────────────────────────

type LiquidGaugeProps = { fromPct: number; toPct: number; label: string; targetLabel?: string }

const clampPct = (value: number) => Math.max(0, Math.min(100, Number.isFinite(value) ? value : 0))
const WAVE = 'M0 6 Q 15 0 30 6 T 60 6 T 90 6 T 120 6 T 150 6 T 180 6 T 210 6 T 240 6 V 200 H 0 Z'

export function LiquidGauge({ fromPct, toPct, label, targetLabel = 'meta' }: LiquidGaugeProps) {
  const calm = useCalmMotion()
  const height = 150
  const levelY = (pct: number) => 8 + (height - 8) * (1 - clampPct(pct) / 100)
  const reached = toPct >= 100
  return (
    <div className={`ws-popup-gauge${reached ? ' reached' : ''}`} role="img" aria-label={label}>
      <svg viewBox="0 0 120 160" width="96" height="128" aria-hidden="true">
        <defs>
          <clipPath id="ws-popup-gauge-clip"><rect x="4" y="4" width="112" height="152" rx="18" /></clipPath>
        </defs>
        <rect className="ws-popup-gauge-glass" x="4" y="4" width="112" height="152" rx="18" />
        <g clipPath="url(#ws-popup-gauge-clip)">
          <motion.g
            initial={{ y: levelY(calm ? toPct : fromPct) }}
            animate={{ y: levelY(toPct) }}
            transition={calm ? { duration: 0 } : { duration: motionTokens.slow, ease: motionTokens.ease }}
          >
            <path className="ws-popup-wave back" d={WAVE} />
            <path className="ws-popup-wave front" d={WAVE} />
          </motion.g>
        </g>
        <line className="ws-popup-gauge-target" x1="10" x2="110" y1="8" y2="8" />
      </svg>
      <span className="ws-popup-gauge-target-label">{reached ? 'meta batida' : targetLabel}</span>
    </div>
  )
}

// ── 6. Texto que se escreve ──────────────────────────────────────────────────

// `startAt`: quantos caracteres já aparecem prontos ao montar (texto que já estava na tela).
type TypewriterTextProps = { committed: string; interim?: string; charsPerSecond?: number; className?: string; startAt?: number }

export function TypewriterText({ committed, interim = '', charsPerSecond = 40, className, startAt = 0 }: TypewriterTextProps) {
  const calm = useCalmMotion()
  const [shown, setShown] = useState(calm ? committed.length : Math.min(Math.max(0, startAt), committed.length))
  const target = committed.length
  useEffect(() => {
    if (calm) { setShown(target); return }
    if (shown > target) { setShown(target); return }
    if (shown === target) return
    // Fila grande escreve mais rápido para nunca ficar muito atrás da fala.
    const backlog = target - shown
    const chunk = backlog > 120 ? Math.ceil(backlog / 20) : 1
    const timer = window.setTimeout(() => setShown(value => Math.min(target, value + chunk)), 1000 / charsPerSecond)
    return () => window.clearTimeout(timer)
  }, [shown, target, calm, charsPerSecond])
  return (
    <p className={`ws-popup-typewriter${className ? ` ${className}` : ''}`} aria-live="polite">
      <span>{committed.slice(0, shown)}</span>
      {interim && <span className="ws-popup-interim">{shown < target ? '' : ` ${interim}`}</span>}
      <span className="ws-popup-caret" aria-hidden="true" />
    </p>
  )
}

// ── 7. Pulso no item inserido ────────────────────────────────────────────────

export function InsertHighlight({ active, children, className }: { active: boolean; children: ReactNode; className?: string }) {
  const calm = useCalmMotion()
  return (
    <motion.div
      className={`ws-popup-insert${active ? ' active' : ''}${className ? ` ${className}` : ''}`}
      initial={false}
      animate={active && !calm ? { boxShadow: ['0 0 0 0 var(--ws-accent-line)', '0 0 0 6px #b4d9c600', '0 0 0 0 #b4d9c600'] } : { boxShadow: '0 0 0 0 #b4d9c600' }}
      transition={{ duration: motionTokens.highlightMs / 1000, ease: 'easeOut' }}
    >
      {children}
    </motion.div>
  )
}
