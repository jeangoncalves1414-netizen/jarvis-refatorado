import { useState, useEffect, useRef } from 'react'

type PomodoroState = 'idle' | 'work' | 'shortBreak' | 'longBreak'

type PomodoroTimerProps = {
  onComplete?: (type: PomodoroState, minutes: number) => void
}

const DEFAULT_WORK = 25
const DEFAULT_SHORT = 5
const DEFAULT_LONG = 15

export function PomodoroTimer({ onComplete }: PomodoroTimerProps) {
  const [state, setState] = useState<PomodoroState>('idle')
  const [secondsLeft, setSecondsLeft] = useState(DEFAULT_WORK * 60)
  const [workMinutes, setWorkMinutes] = useState(DEFAULT_WORK)
  const [shortMinutes, setShortMinutes] = useState(DEFAULT_SHORT)
  const [pomodoroCount, setPomodoroCount] = useState(0)
  const [editing, setEditing] = useState(false)
  const intervalRef = useRef<number | null>(null)

  const totalSeconds = state === 'work' ? workMinutes * 60
    : state === 'shortBreak' ? shortMinutes * 60
    : state === 'longBreak' ? DEFAULT_LONG * 60
    : workMinutes * 60

  useEffect(() => {
    if (state === 'idle') return
    intervalRef.current = window.setInterval(() => {
      setSecondsLeft(prev => {
        if (prev <= 1) {
          clearInterval(intervalRef.current!)
          const finishedState = state
          const minutes = state === 'work' ? workMinutes : state === 'shortBreak' ? shortMinutes : DEFAULT_LONG

          if (state === 'work') {
            const newCount = pomodoroCount + 1
            setPomodoroCount(newCount)
            if (newCount % 4 === 0) {
              setState('longBreak')
              setSecondsLeft(DEFAULT_LONG * 60)
            } else {
              setState('shortBreak')
              setSecondsLeft(shortMinutes * 60)
            }
          } else {
            setState('work')
            setSecondsLeft(workMinutes * 60)
          }

          onComplete?.(finishedState, minutes)
          return 0
        }
        return prev - 1
      })
    }, 1000)
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [state, workMinutes, shortMinutes, pomodoroCount])

  const mm = String(Math.floor(secondsLeft / 60)).padStart(2, '0')
  const ss = String(secondsLeft % 60).padStart(2, '0')
  const progress = totalSeconds > 0 ? ((totalSeconds - secondsLeft) / totalSeconds) * 100 : 0

  const stateLabel = state === 'work' ? '🎯 FOCO'
    : state === 'shortBreak' ? '☕ PAUSA'
    : state === 'longBreak' ? '🌿 DESCANSO'
    : '⏸ PRONTO'

  const start = () => { setState('work'); setSecondsLeft(workMinutes * 60) }
  const pause = () => { setState('idle'); if (intervalRef.current) clearInterval(intervalRef.current) }
  const extend = () => setSecondsLeft(prev => prev + 300)

  return (
    <div className="pomodoro-timer">
      <div className="pomodoro-ring" style={{ background: `conic-gradient(var(--accent, #00daf8) ${progress}%, transparent ${progress}%)` }}>
        <div className="pomodoro-inner">
          <span className="pomodoro-time">{mm}:{ss}</span>
          <small className="pomodoro-label">{stateLabel}</small>
        </div>
      </div>
      <div className="pomodoro-controls">
        {state === 'idle' ? (
          <button type="button" className="primary" onClick={start}>Iniciar</button>
        ) : (
          <>
            <button type="button" onClick={pause}>Pausar</button>
            <button type="button" onClick={extend}>+5 min</button>
          </>
        )}
        <button type="button" onClick={() => setEditing(!editing)} className="pomodoro-settings-btn">⚙</button>
      </div>
      <div className="pomodoro-count">{pomodoroCount} 🍅</div>
      {editing && (
        <div className="pomodoro-settings">
          <label>Foco: <input type="number" min={5} max={90} value={workMinutes} onChange={e => { setWorkMinutes(+e.target.value); if (state === 'idle') setSecondsLeft(+e.target.value * 60) }} /> min</label>
          <label>Pausa: <input type="number" min={1} max={30} value={shortMinutes} onChange={e => setShortMinutes(+e.target.value)} /> min</label>
        </div>
      )}
    </div>
  )
}

