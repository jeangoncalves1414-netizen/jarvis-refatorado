/**
 * Jarvis Tactical SFX Synthesizer
 * Pure procedural Web Audio API sounds - zero external audio assets.
 */

let audioCtx: AudioContext | null = null

function getAudioContext(): AudioContext | null {
  if (typeof window === 'undefined') return null
  if (!audioCtx) {
    const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
    if (AudioContextClass) {
      try {
        audioCtx = new AudioContextClass()
      } catch {
        audioCtx = null
      }
    }
  }
  if (audioCtx && audioCtx.state === 'suspended') {
    audioCtx.resume().catch(() => {})
  }
  return audioCtx
}

export function isSfxEnabled(): boolean {
  if (typeof window === 'undefined') return false
  return localStorage.getItem('jarvis-sfx-enabled') !== 'false'
}

export function setSfxEnabled(enabled: boolean): void {
  if (typeof window === 'undefined') return
  localStorage.setItem('jarvis-sfx-enabled', enabled ? 'true' : 'false')
}

export function toggleSfx(): boolean {
  const current = isSfxEnabled()
  setSfxEnabled(!current)
  return !current
}

/**
 * Micro-click for keyboard navigation (CommandPalette, buttons)
 */
export function playClick(): void {
  if (!isSfxEnabled()) return
  const ctx = getAudioContext()
  if (!ctx) return

  try {
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()

    osc.type = 'triangle'
    const now = ctx.currentTime
    osc.frequency.setValueAtTime(1400, now)
    osc.frequency.exponentialRampToValueAtTime(700, now + 0.015)

    gain.gain.setValueAtTime(0.08, now)
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.015)

    osc.connect(gain)
    gain.connect(ctx.destination)

    osc.start(now)
    osc.stop(now + 0.018)
  } catch {
    /* AudioContext not allowed yet */
  }
}

/**
 * Harmonic cyber chime on action completion / success
 */
export function playSuccess(): void {
  if (!isSfxEnabled()) return
  const ctx = getAudioContext()
  if (!ctx) return

  try {
    const now = ctx.currentTime
    const notes = [587.33, 880] // D5, A5

    notes.forEach((freq, i) => {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()

      osc.type = 'sine'
      osc.frequency.setValueAtTime(freq, now + i * 0.04)

      gain.gain.setValueAtTime(0.09, now + i * 0.04)
      gain.gain.exponentialRampToValueAtTime(0.001, now + i * 0.04 + 0.12)

      osc.connect(gain)
      gain.connect(ctx.destination)

      osc.start(now + i * 0.04)
      osc.stop(now + i * 0.04 + 0.13)
    })
  } catch {}
}

/**
 * Smooth cyber swoop on modal opening
 */
export function playOpen(): void {
  if (!isSfxEnabled()) return
  const ctx = getAudioContext()
  if (!ctx) return

  try {
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()

    osc.type = 'sine'
    const now = ctx.currentTime
    osc.frequency.setValueAtTime(280, now)
    osc.frequency.exponentialRampToValueAtTime(560, now + 0.05)

    gain.gain.setValueAtTime(0.07, now)
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.06)

    osc.connect(gain)
    gain.connect(ctx.destination)

    osc.start(now)
    osc.stop(now + 0.065)
  } catch {}
}

/**
 * Crisp tick on switch / toggle
 */
export function playToggle(): void {
  if (!isSfxEnabled()) return
  const ctx = getAudioContext()
  if (!ctx) return

  try {
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()

    osc.type = 'square'
    const now = ctx.currentTime
    osc.frequency.setValueAtTime(900, now)

    gain.gain.setValueAtTime(0.04, now)
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.02)

    osc.connect(gain)
    gain.connect(ctx.destination)

    osc.start(now)
    osc.stop(now + 0.025)
  } catch {}
}
