// Captura de fala pelo backend (SpeechRecognition + PyAudio no PC), compartilhada pela ligação por
// voz (useMediaAssistant) e pelo ditado das anotações ao vivo (useLiveDictation).

export const LOOPBACK_HOSTS = ['127.0.0.1', 'localhost', '[::1]', '::1']

export function isLoopbackPage() {
  return typeof window !== 'undefined' && LOOPBACK_HOSTS.includes(window.location.hostname)
}

export async function postCapture(action: string, body: Record<string, unknown> = {}) {
  const response = await fetch(`/api/voice/capture/${action}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), keepalive: action === 'stop' })
  return response.json().catch(() => ({})) as Promise<Record<string, any>>
}

export async function fetchCaptureEvents(after: number, signal: AbortSignal) {
  const response = await fetch(`/api/voice/capture/events?after=${after}&wait=1`, { signal })
  if (!response.ok) throw new Error(String(response.status))
  return response.json() as Promise<{ events?: Record<string, any>[]; seq?: number; active?: boolean }>
}
