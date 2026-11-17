import { createAgentAudio } from './voiceSpeed'
import { playAudioToEnd } from './voicePlayback'

/** The same configured voice as the assistant, never the browser's default voice. */
export async function speakGuidance(text: string, signal: AbortSignal) {
  const response = await fetch('/api/voice/tts', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }), signal,
  })
  if (!response.ok) throw new Error('A voz do Jarvis está indisponível. A instrução continua na tela.')
  const blob = await response.blob()
  if (signal.aborted) return
  const url = URL.createObjectURL(blob)
  const audio = createAgentAudio(url)
  try { await playAudioToEnd(audio, signal) }
  finally { audio.pause(); audio.src = ''; URL.revokeObjectURL(url) }
}
