/** Aguarda a reprodução terminar; play() sozinho resolve assim que ela começa. */
export function playAudioToEnd(audio: HTMLAudioElement, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    let settled = false
    const finish = (error?: Error) => {
      if (settled) return
      settled = true
      clearTimeout(timeout)
      audio.removeEventListener('ended', ended)
      audio.removeEventListener('error', failed)
      signal.removeEventListener('abort', aborted)
      if (error) reject(error)
      else resolve()
    }
    const ended = () => finish()
    const failed = () => finish(new Error('A reprodução do áudio falhou.'))
    const aborted = () => { audio.pause(); finish() }
    const timeout = window.setTimeout(() => { audio.pause(); finish(new Error('A reprodução do áudio excedeu o prazo.')) }, 180000)
    audio.addEventListener('ended', ended)
    audio.addEventListener('error', failed)
    signal.addEventListener('abort', aborted, { once: true })
    if (signal.aborted) { aborted(); return }
    void audio.play().catch(error => finish(error))
  })
}
