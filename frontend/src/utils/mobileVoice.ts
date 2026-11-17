import { getMobileApiKeys, getMobileOxyyModels, getMobileProvider, resolveActiveKey } from '../hooks/useDirectChat'

export type NativeVoiceHandlers = {
  onSpeechPartial?: (text: string) => void
  onSpeechAudio?: (base64: string) => void
  onSpeechFinal?: (text: string) => void
  onSpeechError?: (code: string) => void
  onSpeechEnd?: (code: string) => void
  onTtsStart?: (id: string) => void
  onTtsDone?: (id: string) => void
  onTtsError?: (id: string) => void
}

type AndroidBridge = {
  vibrate?: (ms: number) => void
  startSpeech?: (continuous: boolean) => void
  stopSpeech?: () => void
  speak?: (text: string) => void
  stopSpeak?: () => void
}

function android(): AndroidBridge | undefined {
  return (window as Window & { Android?: AndroidBridge }).Android
}

export function hasNativeVoice(): boolean {
  return typeof android()?.startSpeech === 'function'
}

export function startNativeSpeech(continuous = false) {
  android()?.startSpeech?.(continuous)
}

export function stopNativeSpeech() {
  android()?.stopSpeech?.()
}

export function nativeSpeak(text: string) {
  const cleaned = text.replace(/[*_#`~]/g, ' ').replace(/\s+/g, ' ').trim()
  if (!cleaned) return
  android()?.speak?.(cleaned.slice(0, 3500))
}

export function stopNativeSpeak() {
  android()?.stopSpeak?.()
}

export function installNativeVoiceHandlers(handlers: NativeVoiceHandlers) {
  ;(window as Window & { __jarvisNativeVoice?: NativeVoiceHandlers }).__jarvisNativeVoice = handlers
  return () => {
    const current = (window as Window & { __jarvisNativeVoice?: NativeVoiceHandlers }).__jarvisNativeVoice
    if (current === handlers) {
      delete (window as Window & { __jarvisNativeVoice?: NativeVoiceHandlers }).__jarvisNativeVoice
    }
  }
}

function pickRecorderOptions(): MediaRecorderOptions | undefined {
  const types = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/mp4',
    'audio/aac',
    'audio/3gpp',
  ]
  const mimeType = types.find(type => typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(type))
  return mimeType ? { mimeType } : undefined
}

export async function transcribeMobileAudio(blob: Blob): Promise<string> {
  const keys = getMobileApiKeys()
  const provider = getMobileProvider()
  const attempts: Array<{ url: string; key: string; model: string }> = []
  const groqRaw = keys.groq || (provider === 'groq' ? resolveActiveKey('groq') : '')
  const groqKeys = groqRaw ? groqRaw.split(',').map(k => k.trim()).filter(Boolean) : []
  for (const gk of groqKeys) {
    attempts.push({ url: 'https://api.groq.com/openai/v1/audio/transcriptions', key: gk, model: 'whisper-large-v3-turbo' })
  }
  const oxyyKey = keys.oxyy || (provider === 'oxyy' ? resolveActiveKey('oxyy') : '')
  if (oxyyKey) {
    attempts.push({ url: 'https://api.oxyy.ai/v1/audio/transcriptions', key: oxyyKey.split(',')[0].trim(), model: getMobileOxyyModels().stt || 'whisper-1' })
  }
  if (!attempts.length) {
    throw new Error('Sem chave Groq/Oxyy para transcrever. Configure em Jarvis → Configurações, ou use a ligação nativa do Android.')
  }

  let lastError = 'Falha ao transcrever o áudio.'
  for (const attempt of attempts) {
    const form = new FormData()
    const ext = blob.type.includes('mp4') || blob.type.includes('aac') || blob.type.includes('3gpp') ? 'm4a' : 'webm'
    form.append('file', blob, `speech.${ext}`)
    form.append('model', attempt.model)
    form.append('language', 'pt')
    try {
      const response = await fetch(attempt.url, {
        method: 'POST',
        headers: { Authorization: `Bearer ${attempt.key}` },
        body: form,
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) {
        lastError = data?.error?.message || `STT ${response.status}`
        continue
      }
      const text = String(data.text || '').trim()
      if (text) return text
      lastError = 'Transcrição vazia.'
    } catch (error) {
      lastError = error instanceof Error ? error.message : lastError
    }
  }
  throw new Error(lastError)
}

export { pickRecorderOptions }
