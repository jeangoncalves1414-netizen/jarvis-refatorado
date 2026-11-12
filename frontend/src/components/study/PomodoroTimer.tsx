import { useEffect, useRef, useState } from 'react'

export type PomodoroPhase = 'work' | 'shortBreak' | 'longBreak'

type PomodoroTimerProps = {
  onComplete?: (phase: PomodoroPhase, minutes: number) => void
}

const DEFAULT_WORK = 25
const DEFAULT_SHORT = 5
const DEFAULT_LONG = 15
const RING_RADIUS = 45
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS

// Valor inválido ou vazio enquanto o usuário digita: mantém o anterior.
function parseMinutes(value: number, max: number) {
  const minutes = Math.round(value)
  if (!Number.isFinite(minutes) || minutes < 1) return null
  return Math.min(max, minutes)
}

export function PomodoroTimer({ onComplete }: PomodoroTimerProps) {
  const [phase, setPhase] = useState<PomodoroPhase>('work')
  const [running, setRunning] = useState(false)
  const [secondsLeft, setSecondsLeft] = useState(DEFAULT_WORK * 60)
  const [phaseTotal, setPhaseTotal] = useState(DEFAULT_WORK * 60)
  const [workMinutes, setWorkMinutes] = useState(DEFAULT_WORK)
  const [shortMinutes, setShortMinutes] = useState(DEFAULT_SHORT)
  const [pomodoroCount, setPomodoroCount] = useState(0)
  const [editing, setEditing] = useState(false)
  const audioRef = useRef<AudioContext | null>(null)
  useEffect(() => () => { audioRef.current?.close().catch(() => {}) }, [])
  const deadlineRef = useRef(0)
  // Cada fase recebe um número; o onComplete só dispara uma vez por número (seguro no StrictMode).
  const cycleRef = useRef(0)
  const firedCycleRef = useRef(-1)
  const onCompleteRef = useRef(onComplete)
  onCompleteRef.current = onComplete

  useEffect(() => {
    if (!running) return
    const tick = () => setSecondsLeft(Math.max(0, Math.ceil((deadlineRef.current - Date.now()) / 1000)))
    tick()
    const interval = window.setInterval(tick, 500)
    return () => window.clearInterval(interval)
  }, [running])

  useEffect(() => {
    if (!running || secondsLeft > 0) return
    if (firedCycleRef.current === cycleRef.current) return
    firedCycleRef.current = cycleRef.current
    const audio = audioRef.current
    if (audio?.state === 'running') {
      const tone = audio.createOscillator()
      const volume = audio.createGain()
      tone.frequency.value = 660
      volume.gain.setValueAtTime(0.12, audio.currentTime)
      volume.gain.exponentialRampToValueAtTime(0.001, audio.currentTime + 0.35)
      tone.connect(volume).connect(audio.destination)
      tone.onended = () => { tone.disconnect(); volume.disconnect() }
      tone.start()
      tone.stop(audio.currentTime + 0.35)
    }
    onCompleteRef.current?.(phase, Math.round(phaseTotal / 60))
    let next: PomodoroPhase = 'work'
    if (phase === 'work') {
      const count = pomodoroCount + 1
      setPomodoroCount(count)
      next = count % 4 === 0 ? 'longBreak' : 'shortBreak'
    }
    const total = (next === 'work' ? workMinutes : next === 'shortBreak' ? shortMinutes : DEFAULT_LONG) * 60
    cycleRef.current += 1
    deadlineRef.current = Date.now() + total * 1000
    setPhase(next)
    setPhaseTotal(total)
    setSecondsLeft(total)
  }, [running, secondsLeft, phase, phaseTotal, pomodoroCount, workMinutes, shortMinutes])

  const resume = () => {
    if (typeof AudioContext !== 'undefined') {
      try {
        audioRef.current ??= new AudioContext()
        audioRef.current.resume().catch(() => {})
      } catch { /* O temporizador também funciona sem dispositivo de áudio. */ }
    }
    deadlineRef.current = Date.now() + secondsLeft * 1000
    setRunning(true)
  }
  const pause = () => {
    setSecondsLeft(Math.max(0, Math.ceil((deadlineRef.current - Date.now()) / 1000)))
    setRunning(false)
  }
  const extend = () => {
    deadlineRef.current += 300 * 1000
    setSecondsLeft(previous => previous + 300)
    setPhaseTotal(previous => previous + 300)
  }
  const reset = () => {
    cycleRef.current += 1
    setRunning(false)
    setPhase('work')
    setPhaseTotal(workMinutes * 60)
    setSecondsLeft(workMinutes * 60)
  }

  const changeWorkMinutes = (value: number) => {
    const minutes = parseMinutes(value, 90)
    if (minutes === null) return
    setWorkMinutes(minutes)
    if (!running) {
      cycleRef.current += 1
      setPhase('work')
      setPhaseTotal(minutes * 60)
      setSecondsLeft(minutes * 60)
    }
  }
  const changeShortMinutes = (value: number) => {
    const minutes = parseMinutes(value, 30)
    if (minutes !== null) setShortMinutes(minutes)
  }

  const paused = !running && secondsLeft < phaseTotal
  const mm = String(Math.floor(secondsLeft / 60)).padStart(2, '0')
  const ss = String(secondsLeft % 60).padStart(2, '0')
  const progress = phaseTotal > 0 ? Math.min(1, Math.max(0, (phaseTotal - secondsLeft) / phaseTotal)) : 0

  const phaseLabel = !running && !paused ? '⏸ PRONTO'
    : phase === 'work' ? '🎯 FOCO'
    : phase === 'shortBreak' ? '☕ PAUSA'
    : '🌿 DESCANSO'

  return (
    <div className="pomodoro-timer">
      <div className="pomodoro-ring" role="timer" aria-label={`Tempo restante ${mm}:${ss}`}>
        <svg viewBox="0 0 100 100" width={100} height={100} aria-hidden="true">
          <circle className="pomodoro-track" cx={50} cy={50} r={RING_RADIUS} />
          <circle
            className="pomodoro-progress"
            cx={50}
            cy={50}
            r={RING_RADIUS}
            strokeDasharray={RING_CIRCUMFERENCE}
            strokeDashoffset={RING_CIRCUMFERENCE * (1 - progress)}
          />
        </svg>
        <div className="pomodoro-inner">
          <span className="pomodoro-time">{mm}:{ss}</span>
          <small className="pomodoro-label">{phaseLabel}</small>
        </div>
      </div>
      <div className="pomodoro-controls">
        {running ? (
          <>
            <button type="button" onClick={pause}>Pausar</button>
            <button type="button" onClick={extend}>+5 min</button>
          </>
        ) : paused ? (
          <>
            <button type="button" className="primary" onClick={resume}>Continuar</button>
            <button type="button" onClick={reset}>Reiniciar</button>
          </>
        ) : (
          <button type="button" className="primary" onClick={resume}>Iniciar</button>
        )}
        <button type="button" onClick={() => setEditing(!editing)} className="pomodoro-settings-btn" aria-label="Configurar Pomodoro" title="Configurar Pomodoro">⚙</button>
      </div>
      <div className="pomodoro-count">{pomodoroCount} 🍅</div>
      {editing && (
        <div className="pomodoro-settings">
          <label>Foco: <input type="number" min={5} max={90} value={workMinutes} onChange={e => changeWorkMinutes(+e.target.value)} /> min</label>
          <label>Pausa: <input type="number" min={1} max={30} value={shortMinutes} onChange={e => changeShortMinutes(+e.target.value)} /> min</label>
        </div>
      )}
    </div>
  )
}
