export type VoiceSpeed = { normal: number; held: number; key: string }
const storageKey = 'jarvis-voice-speed'
const defaults: VoiceSpeed = { normal: 1, held: 2, key: 'ControlRight' }
const active = new Set<HTMLAudioElement>()
let holding = false
let installed = false
const rate = (value: unknown, fallback: number) => typeof value === 'number' && Number.isFinite(value) ? Math.min(3, Math.max(0.5, value)) : fallback

export function getVoiceSpeed(): VoiceSpeed {
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey) || '{}')
    return { normal: rate(saved.normal, 1), held: rate(saved.held, 2), key: typeof saved.key === 'string' ? saved.key : defaults.key }
  } catch { return { ...defaults } }
}
export function currentVoiceRate() {
  const settings = getVoiceSpeed()
  return holding ? settings.held : settings.normal
}
function update() { active.forEach(audio => { audio.playbackRate = currentVoiceRate() }) }
function release() { holding = false; update() }
export function saveVoiceSpeed(settings: VoiceSpeed) {
  localStorage.setItem(storageKey, JSON.stringify({ ...settings, normal: rate(settings.normal, 1), held: rate(settings.held, 2) }))
  release()
  window.dispatchEvent(new Event('jarvis:voice-speed'))
}
function install() {
  if (installed) return
  installed = true
  window.addEventListener('keydown', event => {
    if (event.code !== getVoiceSpeed().key || event.repeat || event.isComposing) return
    const target = event.target as HTMLElement | null
    const controlKey = /^(Control|Shift|Alt)(Left|Right)$/.test(event.code)
    if (!controlKey && target?.closest('input, textarea, select, button, [contenteditable="true"]')) return
    holding = true
    if (active.size) event.preventDefault()
    update()
  })
  window.addEventListener('keyup', event => { if (event.code === getVoiceSpeed().key) release() })
  window.addEventListener('blur', release)
  document.addEventListener('visibilitychange', () => { if (document.hidden) release() })
  window.addEventListener('storage', event => { if (event.key === storageKey) release() })
}
/** Apply only to agent speech, never to music/video or microphone recordings. */
export function createAgentAudio(src: string): HTMLAudioElement {
  install()
  const audio = new Audio(src)
  audio.preservesPitch = true
  audio.playbackRate = currentVoiceRate()
  audio.addEventListener('play', () => { active.add(audio); audio.playbackRate = currentVoiceRate() })
  const remove = () => active.delete(audio)
  audio.addEventListener('pause', remove)
  audio.addEventListener('ended', remove)
  audio.addEventListener('error', remove)
  return audio
}
