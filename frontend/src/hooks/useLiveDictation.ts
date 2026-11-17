import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchCaptureEvents, isLoopbackPage, postCapture } from '../utils/backendCapture'
import { liveDictationBus, type DictationSink } from '../utils/dictationBus'
import { isMobileStandalone } from './useDirectChat'
import { createMicrophoneRecognition } from '../utils/micPrefs'

// Ditado das anotações ao vivo (lote 6, decisão 12). Motor, em ordem:
// 1. ligação por voz ativa: as falas da ligação vêm para a nota (ponte liveDictationBus);
// 2. microfone do PC pelo backend (/api/voice/capture/*), frase a frase;
// 3. reconhecimento do navegador (com texto provisório);
// 4. nenhum: a nota continua editável à mão.
// "fim da nota", "terminar anotação" ou "parar anotação" encerram a gravação.

export type DictationEngine = 'call' | 'backend' | 'browser' | 'manual'

const STOP_PHRASES = ['fim da nota', 'fim da anotacao', 'terminar anotacao', 'terminar a anotacao', 'terminar nota', 'parar anotacao', 'parar a anotacao', 'parar nota']

const fold = (text: string) => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()

/** Separa a frase de parada: "comprar café, fim da nota" → { text: "comprar café", stop: true }. */
export function splitStopPhrase(raw: string): { text: string; stop: boolean } {
  const folded = fold(raw)
  for (const phrase of STOP_PHRASES) {
    const index = folded.indexOf(phrase)
    if (index >= 0) {
      // A normalização remove só os acentos combinados; os índices do texto original mudam,
      // então cortamos pela contagem de letras base.
      const prefix = cutByFoldedLength(raw, index)
      return { text: prefix.replace(/[\s,.;:!?-]+$/, '').trim(), stop: true }
    }
  }
  return { text: raw.trim(), stop: false }
}

function cutByFoldedLength(raw: string, foldedLength: number) {
  let count = 0
  let out = ''
  for (const char of raw) {
    if (count >= foldedLength) break
    out += char
    count += fold(char).length
  }
  return out
}

type Options = {
  onPhrase: (text: string) => void
  onInterim: (text: string) => void
  // Gravação encerrada (botão, frase de parada, microfone perdido).
  onStopped?: (reason: 'user' | 'phrase' | 'lost') => void
}

type Session = { stop: () => void }

export function useLiveDictation({ onPhrase, onInterim, onStopped }: Options) {
  const handlersRef = useRef({ onPhrase, onInterim, onStopped })
  handlersRef.current = { onPhrase, onInterim, onStopped }
  const sessionRef = useRef<Session | null>(null)
  const startingRef = useRef(0)
  const [active, setActive] = useState(false)
  const [engine, setEngine] = useState<DictationEngine | null>(null)
  const [notice, setNotice] = useState('')

  const stop = useCallback((reason: 'user' | 'phrase' | 'lost' = 'user') => {
    startingRef.current += 1
    const session = sessionRef.current
    sessionRef.current = null
    session?.stop()
    setActive(false)
    handlersRef.current.onInterim('')
    if (session) handlersRef.current.onStopped?.(reason)
  }, [])

  const deliver = useCallback((raw: string) => {
    const { text, stop: shouldStop } = splitStopPhrase(raw)
    if (text) handlersRef.current.onPhrase(text)
    if (shouldStop) stop('phrase')
  }, [stop])

  const start = useCallback(async () => {
    if (sessionRef.current) return
    const token = ++startingRef.current
    const stale = () => token !== startingRef.current

    // 1. Ligação por voz: a nota recebe as falas da ligação.
    if (liveDictationBus.callActive()) {
      const sink: DictationSink = { onPhrase: deliver, onInterim: text => handlersRef.current.onInterim(text) }
      liveDictationBus.setSink(sink)
      sessionRef.current = { stop: () => { if (liveDictationBus.sink() === sink) liveDictationBus.setSink(null) } }
      setEngine('call')
      setNotice('Anotando pela ligação: diga "fim da nota" para voltar a falar com o agente.')
      setActive(true)
      return
    }

    // 2. Microfone do PC pelo backend.
    let fallbackReason = ''
    if (!isMobileStandalone() && isLoopbackPage()) {
      const result = await startBackendSession(deliver, message => { if (sessionRef.current) { setNotice(message); stop('lost') } }, stale)
      if (stale()) { if (result.ok) result.session.stop(); return }
      if (result.ok) {
        sessionRef.current = result.session
        setEngine('backend')
        setNotice('Ouvindo pelo microfone do PC.')
        setActive(true)
        return
      }
      fallbackReason = result.reason || ''
    }

    // 3. Reconhecimento do navegador.
    const browser = startBrowserSession(deliver, text => handlersRef.current.onInterim(text), message => { if (sessionRef.current) { setNotice(message); stop('lost') } })
    if (browser) {
      sessionRef.current = browser
      setEngine('browser')
      setNotice(fallbackReason ? `${fallbackReason} Usando o microfone do navegador.` : 'Ouvindo pelo microfone do navegador.')
      setActive(true)
      return
    }

    // 4. Sem ditado: escrita à mão.
    setEngine('manual')
    setNotice('Ditado indisponível neste aparelho (precisa de reconhecimento de fala). Escreva a anotação à mão.')
    setActive(false)
  }, [deliver, stop])

  useEffect(() => () => {
    startingRef.current += 1
    sessionRef.current?.stop()
    sessionRef.current = null
  }, [])

  return { active, engine, notice, start, stop }
}

type BackendResult = { ok: true; session: Session } | { ok: false; reason?: string }

async function startBackendSession(onTranscript: (text: string) => void, onLost: (message: string) => void, stale: () => boolean): Promise<BackendResult> {
  try {
    const mic: { engine?: string } = await fetch('/api/settings/mic').then(response => response.ok ? response.json() : {}).catch(() => ({}))
    if (stale()) return { ok: false }
    if (mic?.engine === 'browser') return { ok: false }
    const status = await (await fetch('/api/voice/capture/status')).json()
    // Pedido cancelado antes de abrir o microfone: não abre (evita brigar com outra gravação).
    if (stale()) return { ok: false }
    if (!status.available) return { ok: false, reason: status.reason || 'Captura do PC indisponível.' }
    if (status.active) return { ok: false, reason: 'O microfone do PC está ocupado.' }
    const started = await postCapture('start')
    if (!started.ok) return { ok: false, reason: started.error || 'Não foi possível abrir o microfone do PC.' }
    const abort = new AbortController()
    let stopped = false
    const session: Session = {
      stop: () => {
        if (stopped) return
        stopped = true
        abort.abort()
        void postCapture('stop').catch(() => undefined)
      },
    }
    void (async () => {
      let after = Number(started.seq) || 0
      let failures = 0
      while (!stopped) {
        try {
          const data = await fetchCaptureEvents(after, abort.signal)
          failures = 0
          after = Number(data.seq) || after
          for (const event of data.events || []) {
            if (stopped) return
            if (event.type === 'transcript' && String(event.text || '').trim()) onTranscript(String(event.text).trim())
            else if (event.type === 'error' && event.fatal) { onLost(String(event.message || 'Falha no microfone do PC.')); return }
          }
          if (!data.active && !stopped) { onLost('O microfone do PC foi encerrado.'); return }
        } catch {
          if (stopped) return
          failures += 1
          if (failures >= 5) { onLost('Perdi a conexão com o microfone do PC.'); return }
          await new Promise(resolve => window.setTimeout(resolve, 400))
        }
      }
    })()
    return { ok: true, session }
  } catch {
    return { ok: false, reason: 'O backend não respondeu sobre o microfone do PC.' }
  }
}

function startBrowserSession(onFinal: (text: string) => void, onInterim: (text: string) => void, onLost: (message: string) => void): Session | null {
  const browserWindow = window as Window & { SpeechRecognition?: any; webkitSpeechRecognition?: any }
  const Recognition = browserWindow.SpeechRecognition || browserWindow.webkitSpeechRecognition
  if (!Recognition) return null
  let stopped = false
  let recognition: any
  try {
    recognition = createMicrophoneRecognition(Recognition)
  } catch {
    return null
  }
  recognition.lang = 'pt-BR'
  recognition.continuous = true
  recognition.interimResults = true
  recognition.onresult = (event: any) => {
    let interim = ''
    for (let index = event.resultIndex || 0; index < event.results.length; index += 1) {
      const result = event.results[index]
      const text = String(result[0]?.transcript || '')
      if (result.isFinal) { if (text.trim()) onFinal(text.trim()) } else interim += text
    }
    onInterim(interim.trim())
  }
  recognition.onerror = (event: any) => {
    if (stopped || event?.error === 'no-speech' || event?.error === 'aborted') return
    onLost(event?.message || (event?.error === 'not-allowed' ? 'O navegador não liberou o microfone.' : 'O reconhecimento de fala do navegador parou.'))
  }
  // O navegador encerra sozinho após silêncio; enquanto a gravação está ligada, recomeça.
  recognition.onend = () => { if (!stopped) { try { recognition.start() } catch { /* já iniciado */ } } }
  try {
    recognition.start()
  } catch {
    return null
  }
  return { stop: () => { stopped = true; try { recognition.abort() } catch { /* ignore */ } } }
}
