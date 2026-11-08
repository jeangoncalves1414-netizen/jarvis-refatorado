import { useCallback, useEffect, useRef, useState } from 'react'
import { micAudioConstraints } from '../utils/micPrefs'
import { isMobileStandalone } from './useDirectChat'
import type { RequestOrigin } from './useChat'
import {
  hasNativeVoice,
  installNativeVoiceHandlers,
  nativeSpeak,
  pickRecorderOptions,
  startNativeSpeech,
  stopNativeSpeak,
  stopNativeSpeech,
  transcribeMobileAudio,
} from '../utils/mobileVoice'

const SPEAK_STORAGE_KEY = 'jarvis_speak_responses'
const SPEAKER_IDENTIFICATION_STORAGE_KEY = 'jarvis_speaker_identification'

export type LiveAudioDiagnostics = {
  mode: 'browser-speech' | 'fallback-vad' | 'native-speech'
  rms?: number
  threshold?: number
  noiseFloor?: number
  turnId?: string
  speakerName?: string
  speakerConfidence?: number
  speakerUnknown?: boolean
}

function newVoiceTurnId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  return `voice-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function recordDiagnostic(event: string, level: 'INFO' | 'WARN' | 'ERROR' = 'INFO', context: Record<string, string | number | boolean | undefined> = {}) {
  if (typeof window !== 'undefined' && (window.location.hostname === 'appassets.androidplatform.net' || window.location.protocol === 'file:')) {
    return
  }
  const safeContext = Object.fromEntries(Object.entries(context).filter(([, value]) => value !== undefined))
  void fetch('/api/diagnostics/event', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ component: 'voice.browser', event, level, context: safeContext }),
  }).catch(() => undefined)
}

function readSpeakEnabled() {
  try {
    const stored = localStorage.getItem(SPEAK_STORAGE_KEY)
    if (stored !== null) return stored === '1'
  } catch {
    /* ignore storage errors */
  }
  return true
}

function readSpeakerIdentificationEnabled() {
  try { return localStorage.getItem(SPEAKER_IDENTIFICATION_STORAGE_KEY) === '1' } catch { return false }
}

async function createStreamingAudio(response: Response): Promise<{ audio: HTMLAudioElement; url: string } | null> {
  if (!response.body || typeof MediaSource === 'undefined' || !MediaSource.isTypeSupported('audio/mpeg')) return null
  const mediaSource = new MediaSource()
  const url = URL.createObjectURL(mediaSource)
  const audio = new Audio(url)
  const firstChunk = new Promise<void>((resolve, reject) => {
    mediaSource.addEventListener('sourceopen', async () => {
      try {
        const source = mediaSource.addSourceBuffer('audio/mpeg')
        const reader = response.body!.getReader()
        let started = false
        const append = (chunk: Uint8Array) => new Promise<void>((done, fail) => {
          const attempt = () => {
            if (source.updating) { window.setTimeout(attempt, 10); return }
            try {
              source.addEventListener('updateend', () => done(), { once: true })
              source.appendBuffer(chunk as unknown as ArrayBuffer)
            } catch (error) { fail(error) }
          }
          attempt()
        })
        while (true) {
          const { value, done } = await reader.read()
          if (done) break
          if (value?.length) {
            await append(value)
            if (!started) { started = true; resolve() }
          }
        }
        if (source.updating) await new Promise<void>(done => source.addEventListener('updateend', () => done(), { once: true }))
        if (mediaSource.readyState === 'open') mediaSource.endOfStream()
        if (!started) reject(new Error('Fish did not return audio.'))
      } catch (error) { reject(error) }
    }, { once: true })
  })
  await firstChunk
  return { audio, url }
}

type MediaAssistantOptions = {
  query: string
  sendText: (message: string, mode?: string, racingMode?: boolean, origin?: RequestOrigin) => Promise<string>
  setAnswer: (answer: string) => void
  setQuery: (query: string) => void
  sessionId?: string
  appendExchange?: (userText: string, assistantText: string) => Promise<void>
}

export function useMediaAssistant({ query, sendText: sendChatText, setAnswer, setQuery, sessionId, appendExchange }: MediaAssistantOptions) {
  const appendExchangeRef = useRef(appendExchange)
  appendExchangeRef.current = appendExchange
  const sessionIdRef = useRef(sessionId)
  sessionIdRef.current = sessionId
  const [liveTurns, setLiveTurns] = useState<{ id: string; user: string; jarvis: string }[]>([])
  // Pedidos falados chegam ao servidor com origem "voice": as ações entram na Central como voz (C10).
  const sendText = useCallback((message: string) => sendChatText(message, 'general', false, 'voice'), [sendChatText])
  const [speakEnabled, setSpeakEnabledState] = useState(readSpeakEnabled)
  const [speakerIdentificationEnabled, setSpeakerIdentificationEnabledState] = useState(readSpeakerIdentificationEnabled)
  const [recording, setRecording] = useState(false)
  const [liveCallOpen, setLiveCallOpen] = useState(false)
  const [liveCallRecording, setLiveCallRecording] = useState(false)
  const [liveCallStatus, setLiveCallStatus] = useState('Pronto para ouvir.')
  const [liveAudioDiagnostics, setLiveAudioDiagnostics] = useState<LiveAudioDiagnostics | null>(null)
  const [visionResult, setVisionResult] = useState<{ reply: string; imageUrl?: string } | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const liveCallRecorderRef = useRef<MediaRecorder | null>(null)
  const liveCallStreamRef = useRef<MediaStream | null>(null)
  const liveRecognitionRef = useRef<any>(null)
  const liveCallActiveRef = useRef(false)
  const liveCallProcessingRef = useRef(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const audioUrlRef = useRef<string | null>(null)
  const speechRequestRef = useRef(0)
  const speechAbortRef = useRef<AbortController | null>(null)
  const isSpeakingRef = useRef(false)
  const spokenSentencesRef = useRef<string[]>([])
  const lastInterruptionRef = useRef<{ text: string; time: number } | null>(null)
  // flag: barge-in ocorreu, próxima fala final deve ser processada mesmo se processando
  const bargedInRef = useRef(false)
  // Envio especulativo: guarda o texto da última frase enviada + timestamp para permitir cancelamento retroativo
  const lastDispatchedSpeechRef = useRef<{ text: string; timestamp: number; abort: AbortController; isCancelled?: boolean } | null>(null)
  // Timer de janela de correção — se o usuário continuar falando cancela e reenvia merged
  const correctionWindowTimerRef = useRef<number | null>(null)
  // evita race condition de duplo-set no estado 'listening'
  const listeningRestoredRef = useRef(false)
  // flag: evita reiniciar recognition enquanto já está rodando
  const recognitionAliveRef = useRef(false)
  // Timer para reiniciar recognition após Jarvis parar de falar (dá pausa de calibração)
  const postSpeechRestartTimerRef = useRef<number | null>(null)
  // Fallback MediaRecorder não é contínuo; após uma falha de STT ele precisa
  // ser armado novamente sem deixar a ligação em um estado morto.
  const liveCallRetryTimerRef = useRef<number | null>(null)
  const liveCallSttFailureCountRef = useRef(0)
  const fallbackAudioContextRef = useRef<AudioContext | null>(null)
  const fallbackAnimationFrameRef = useRef<number | null>(null)
  const fallbackListeningRef = useRef(false)
  const fallbackSilenceStartedAtRef = useRef<number | null>(null)
  const fallbackNoiseFloorRef = useRef(0.004)
  const fallbackLastDiagnosticsUpdateRef = useRef(0)
  const voiceTurnIdRef = useRef<string | null>(null)
  const liveSpeakerRef = useRef<{ name?: string; confidence?: number; unknown?: boolean }>({})
  const nativeVoiceModeRef = useRef<'idle' | 'call' | 'composer'>('idle')
  const nativeCallActiveRef = useRef(false)
  const ttsDoneResolverRef = useRef<(() => void) | null>(null)

  const toggleVoiceInput = async () => {
    if (nativeVoiceModeRef.current === 'composer') {
      nativeVoiceModeRef.current = 'idle'
      stopNativeSpeech()
      setRecording(false)
      setAnswer('Gravação encerrada.')
      return
    }
    if (hasNativeVoice() && isMobileStandalone()) {
      nativeVoiceModeRef.current = 'composer'
      setRecording(true)
      setAnswer('Estou ouvindo… fale e pause para transcrever.')
      startNativeSpeech(false)
      return
    }
    if (recorderRef.current?.state === 'recording') {
      recorderRef.current.stop()
      return
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setAnswer('A captura de microfone não é suportada neste navegador.')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: micAudioConstraints() })
      const chunks: BlobPart[] = []
      const options = pickRecorderOptions()
      const recorder = new MediaRecorder(stream, options)
      recorderRef.current = recorder
      recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data) }
      recorder.onstop = async () => {
        recorderRef.current = null
        setRecording(false)
        stream.getTracks().forEach(track => track.stop())
        try {
          setAnswer('Transcrevendo áudio…')
          const audio = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' })
          if (isMobileStandalone()) {
            const text = await transcribeMobileAudio(audio)
            setQuery(text)
            setAnswer('Transcrição pronta. Revise a mensagem e envie quando quiser.')
            return
          }
          const response = await fetch('/api/voice/stt', { method: 'POST', headers: { 'Content-Type': audio.type }, body: audio })
          const data = await response.json()
          if (!response.ok || !data.ok || !data.text) throw new Error(data.error || 'Não foi possível entender o áudio.')
          setQuery(data.text)
          setAnswer('Transcrição pronta. Revise a mensagem e envie quando quiser.')
        } catch (error) {
          setAnswer(error instanceof Error ? error.message : 'Falha ao transcrever o áudio.')
        }
      }
      recorder.start()
      setRecording(true)
      setAnswer('Estou ouvindo… Clique novamente para parar.')
    } catch {
      setAnswer('Não consegui acessar o microfone. Verifique a permissão do navegador.')
    }
  }

  const closeLiveCall = () => {
    liveCallActiveRef.current = false
    liveCallProcessingRef.current = false
    nativeCallActiveRef.current = false
    nativeVoiceModeRef.current = 'idle'
    stopNativeSpeech()
    stopNativeSpeak()
    try { liveRecognitionRef.current?.stop() } catch { /* already stopped */ }
    liveRecognitionRef.current = null
    if (liveCallRecorderRef.current?.state === 'recording') liveCallRecorderRef.current.stop()
    fallbackListeningRef.current = false
    fallbackSilenceStartedAtRef.current = null
    if (fallbackAnimationFrameRef.current !== null) {
      window.cancelAnimationFrame(fallbackAnimationFrameRef.current)
      fallbackAnimationFrameRef.current = null
    }
    if (fallbackAudioContextRef.current) {
      void fallbackAudioContextRef.current.close().catch(() => undefined)
      fallbackAudioContextRef.current = null
    }
    if (liveCallStreamRef.current) {
      liveCallStreamRef.current.getTracks().forEach(track => track.stop())
    }
    liveCallStreamRef.current = null
    liveCallRecorderRef.current = null
    if (liveCallRetryTimerRef.current !== null) {
      window.clearTimeout(liveCallRetryTimerRef.current)
      liveCallRetryTimerRef.current = null
    }
    liveCallSttFailureCountRef.current = 0
    voiceTurnIdRef.current = null
    liveSpeakerRef.current = {}
    setLiveAudioDiagnostics(null)
    speechRequestRef.current += 1
    speechAbortRef.current?.abort()
    speechAbortRef.current = null
    audioRef.current?.pause()
    if (audioRef.current) audioRef.current.src = ''
    if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current)
    audioRef.current = null
    audioUrlRef.current = null
    setLiveCallRecording(false)
    setLiveTurns([])
    setLiveCallOpen(false)
  }

  const stopSpeaking = useCallback(() => {
    speechRequestRef.current += 1
    speechAbortRef.current?.abort()
    speechAbortRef.current = null
    if (audioRef.current) {
      try {
        audioRef.current.pause()
        audioRef.current.currentTime = 0
        audioRef.current.src = ''
      } catch { /* ignore */ }
    }
    if (audioUrlRef.current) {
      try { URL.revokeObjectURL(audioUrlRef.current) } catch { /* ignore */ }
      audioUrlRef.current = null
    }
    audioRef.current = null
  }, [])

  const [liveUserTranscript, setLiveUserTranscript] = useState('')
  const [liveJarvisTranscript, setLiveJarvisTranscript] = useState('')
  const [liveOrbState, setLiveOrbState] = useState<'idle' | 'listening' | 'thinking' | 'speaking'>('idle')

  const fetchAndCreateAudio = async (text: string, signal?: AbortSignal): Promise<HTMLAudioElement | null> => {
    const cleaned = text.replace(/[*_#`~]/g, '').trim()
    if (!cleaned) return null
    try {
      const streamRes = await fetch('/api/voice/tts/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: cleaned }),
        signal,
      })
      if (streamRes.ok) {
        const streamed = await createStreamingAudio(streamRes)
        if (streamed) return streamed.audio
      }
      const res = await fetch('/api/voice/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: cleaned }),
        signal,
      })
      if (!res.ok) return null
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      return new Audio(url)
    } catch {
      return null
    }
  }

  const sendTextStreamAndPlay = async (userText: string, displayText?: string, externalAbort?: AbortController) => {
    if (!userText || !liveCallActiveRef.current) return

    // Mostra apenas o texto limpo (sem o prompt de contexto interno)
    if (displayText !== undefined) setLiveUserTranscript(displayText)
    setLiveJarvisTranscript('')
    setLiveOrbState('thinking')
    setLiveCallStatus('⚡ Processando fala (sub-segundo)…')

    listeningRestoredRef.current = false
    const abortController = new AbortController()
    speechAbortRef.current = abortController

    // Propaga cancelamento externo (dispatch especulativo) para o AbortController interno
    if (externalAbort) {
      if (externalAbort.signal.aborted) { return }
      externalAbort.signal.addEventListener('abort', () => abortController.abort(), { once: true })
    }

    const audioQueue: { text: string; audioPromise?: Promise<HTMLAudioElement | null> }[] = []
    let isPlayingQueue = false
    const turnStartedAt = performance.now()
    let firstAudioReported = false
    let phrasesEnqueued = 0

    // Promessa que resolve imediatamente quando o abort é acionado
    const abortPromise = new Promise<null>((resolve) => {
      if (abortController.signal.aborted) { resolve(null); return }
      abortController.signal.addEventListener('abort', () => resolve(null), { once: true })
    })

    const playNextInQueue = async () => {
      if (isPlayingQueue || audioQueue.length === 0 || !liveCallActiveRef.current || abortController.signal.aborted) {
        // Se a fila está vazia e não estamos tocando nada → Jarvis terminou de falar
        if (!isPlayingQueue && audioQueue.length === 0 && liveCallActiveRef.current && !abortController.signal.aborted) {
          isSpeakingRef.current = false
          if (!listeningRestoredRef.current) {
            listeningRestoredRef.current = true
            setLiveOrbState('listening')
            setLiveCallStatus('Ouvindo continuamente… fale normalmente.')
            setLiveCallRecording(true)
          }
        }
        return
      }
      isPlayingQueue = true
      const item = audioQueue.shift()
      if (!item) {
        isPlayingQueue = false
        isSpeakingRef.current = false
        if (liveCallActiveRef.current && !abortController.signal.aborted && !listeningRestoredRef.current) {
          listeningRestoredRef.current = true
          setLiveOrbState('listening')
          setLiveCallStatus('Ouvindo continuamente… fale normalmente.')
          setLiveCallRecording(true)
        }
        return
      }

      listeningRestoredRef.current = false
      isSpeakingRef.current = true
      spokenSentencesRef.current.push(item.text)
      setLiveOrbState('speaking')
      setLiveCallStatus('⚡ Transmitindo resposta em tempo real…')
      setLiveJarvisTranscript((prev) => (prev ? prev + ' ' + item.text : item.text))

      try {
        // Race contra abort para não ficar preso aguardando TTS
        let audioEl: HTMLAudioElement | null = null
        if (item.audioPromise) {
          audioEl = await Promise.race([item.audioPromise, abortPromise]) as HTMLAudioElement | null
        } else {
          audioEl = await fetchAndCreateAudio(item.text, abortController.signal)
        }

        if (audioEl && liveCallActiveRef.current && !abortController.signal.aborted) {
          audioRef.current = audioEl
          await Promise.race([
            new Promise<void>((resolve) => {
              audioEl!.onplaying = () => {
                if (firstAudioReported) return
                firstAudioReported = true
                const ms = Math.round(performance.now() - turnStartedAt)
                setLiveCallStatus(`⚡ Primeiro áudio em ${ms} ms`)
                recordDiagnostic('voice_first_audio_ms', 'INFO', { ms })
              }
              audioEl!.onended = () => resolve()
              audioEl!.onerror = () => resolve()
              audioEl!.play().catch(() => resolve())
            }),
            abortPromise,
          ])
          // Se abortado enquanto tocava, para o áudio
          if (abortController.signal.aborted && audioEl) {
            try { audioEl.pause(); audioEl.src = '' } catch { /* ignore */ }
          }
        }
      } catch {
        /* skip broken audio chunk */
      } finally {
        audioRef.current = null
        isPlayingQueue = false
        // Quando a fila drena, Jarvis parou de falar
        if (audioQueue.length === 0 || abortController.signal.aborted) {
          isSpeakingRef.current = false
          if (liveCallActiveRef.current && !abortController.signal.aborted && !listeningRestoredRef.current) {
            listeningRestoredRef.current = true
            setLiveOrbState('listening')
            setLiveCallStatus('Ouvindo continuamente… fale normalmente.')
            setLiveCallRecording(true)
            // ⚡ Jarvis terminou de falar: reiniciar recognition com pausa de calibração
            // para que o baseline de ruído seja resetado antes de ouvir o usuário
            if (!recognitionAliveRef.current) {
              safeRestartLiveRecognition(true)
            }
          }
        }
        if (liveCallActiveRef.current && !abortController.signal.aborted) {
          void playNextInQueue()
        }
      }
    }

    const enqueuePhrase = (phrase: string) => {
      const trimmed = phrase.trim()
      if (!trimmed) return
      phrasesEnqueued += 1
      const audioPromise = fetchAndCreateAudio(trimmed, abortController.signal)
      audioQueue.push({ text: trimmed, audioPromise })
      void playNextInQueue()
    }

    let sentenceBuffer = ''
    let fullReply = ''

    try {
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userText, mode: 'general', origin: 'voice', session_id: sessionIdRef.current || undefined }),
        signal: abortController.signal,
      })

      if (!response.ok || !response.body) {
        const reply = await sendText(userText)
        if (reply && liveCallActiveRef.current) {
          setLiveJarvisTranscript(reply)
          await speakText(reply)
        }
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let eventBuffer = ''

      while (true) {
        if (abortController.signal.aborted || !liveCallActiveRef.current) break
        const { value, done } = await reader.read()
        if (done) break
        eventBuffer += decoder.decode(value, { stream: true })

        const lines = eventBuffer.split('\n\n')
        eventBuffer = lines.pop() || ''

        for (const line of lines) {
          const trimmedLine = line.trim()
          if (!trimmedLine.startsWith('data: ')) continue
          const jsonStr = trimmedLine.slice(6)
          try {
            const data = JSON.parse(jsonStr)
            if (data.status === 'streaming' && data.chunk) {
              sentenceBuffer += data.chunk
              fullReply += data.chunk

              let match: RegExpExecArray | null = null
              const sentenceRegex = /([.!?\n]+|[,;:]\s+)/g

              while ((match = sentenceRegex.exec(sentenceBuffer)) !== null) {
                const chunkCandidate = sentenceBuffer.slice(0, match.index + match[0].length)
                if (chunkCandidate.trim().length >= (phrasesEnqueued === 0 ? 8 : 12) || /[.!?\n]/.test(match[0])) {
                  enqueuePhrase(chunkCandidate)
                  sentenceBuffer = sentenceBuffer.slice(match.index + match[0].length)
                  sentenceRegex.lastIndex = 0
                }
              }
            } else if (data.status === 'complete') {
              if (sentenceBuffer.trim()) {
                enqueuePhrase(sentenceBuffer)
                sentenceBuffer = ''
              }
            }
          } catch {
            /* ignore parse error */
          }
        }
      }

      if (sentenceBuffer.trim() && !abortController.signal.aborted) {
        enqueuePhrase(sentenceBuffer)
      }

      while ((audioQueue.length > 0 || isPlayingQueue) && liveCallActiveRef.current && !abortController.signal.aborted) {
        await new Promise((r) => setTimeout(r, 60))
      }
    } catch (err: any) {
      if (err?.name !== 'AbortError') {
        setLiveCallStatus(err?.message || 'Falha durante a ligação.')
      }
    } finally {
      // Cada fala vira um turno novo (fala + resposta), preservando os anteriores no chat e na ligação.
      const turnReply = fullReply.trim()
      if (turnReply) {
        const turnUser = (displayText ?? userText).trim()
        const turnId = `turn_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
        setLiveTurns((previous) => [...previous, { id: turnId, user: turnUser, jarvis: turnReply }].slice(-30))
        void appendExchangeRef.current?.(turnUser, turnReply)
      }
      isSpeakingRef.current = false
      // Só restaura 'listening' aqui se playNextInQueue ainda não o fez
      if (liveCallActiveRef.current && !abortController.signal.aborted && !listeningRestoredRef.current) {
        listeningRestoredRef.current = true
        setLiveCallRecording(true)
        setLiveOrbState('listening')
        setLiveCallStatus('Ouvindo continuamente… fale normalmente.')
      }
    }
  }

  const triggerBargeIn = useCallback(() => {
    if (!liveCallActiveRef.current) return
    const interruptedText = spokenSentencesRef.current.join(' ').trim()
    if (interruptedText) {
      lastInterruptionRef.current = {
        text: interruptedText,
        time: Date.now(),
      }
      setLiveJarvisTranscript(`${interruptedText} ✂️ [interrompido]`)
    } else {
      setLiveJarvisTranscript((prev) => (prev ? `${prev} ✂️ [interrompido]` : '[interrompido]'))
    }

    // Para o áudio imediatamente
    isSpeakingRef.current = false
    speechRequestRef.current += 1
    speechAbortRef.current?.abort()
    speechAbortRef.current = null
    stopNativeSpeak()

    if (audioRef.current) {
      try {
        audioRef.current.pause()
        audioRef.current.currentTime = 0
        audioRef.current.src = ''
      } catch { /* ignore */ }
      audioRef.current = null
    }
    if (audioUrlRef.current) {
      try { URL.revokeObjectURL(audioUrlRef.current) } catch { /* ignore */ }
      audioUrlRef.current = null
    }

    // ⚡ Libera o processamento para a próxima fala do usuário
    liveCallProcessingRef.current = false
    bargedInRef.current = true
    spokenSentencesRef.current = []

    setLiveOrbState('listening')
    setLiveCallRecording(true)
    setLiveCallStatus('Interrompido por você. Ouvindo...')
  }, [])

  const safeRestartLiveRecognition = (forceCalibrationPause = false) => {
    if (!liveCallActiveRef.current) return

    // Se o Jarvis ainda está falando, não reinicia agora.
    // Quando o áudio terminar, o próprio fluxo de TTS chama safeRestartLiveRecognition.
    // Fazemos isso para evitar que o SpeechRecognition recalibre o ruído base enquanto
    // há áudio saindo, o que faria a sensibilidade do mic cair na próxima sessão.
    if (isSpeakingRef.current) {
      // Agenda verificação para quando o Jarvis parar: o fluxo de áudio já cuida disso
      return
    }

    setLiveCallRecording(true)
    if (!isSpeakingRef.current) {
      setLiveOrbState('listening')
      setLiveCallStatus('Ouvindo continuamente… fale normalmente.')
    }

    // Evita reiniciar se já existe uma instância ativa
    if (recognitionAliveRef.current && liveRecognitionRef.current) return

    try {
      if (liveRecognitionRef.current) {
        liveRecognitionRef.current.onend = null
        liveRecognitionRef.current.onerror = null
        liveRecognitionRef.current.onresult = null
        try { liveRecognitionRef.current.abort() } catch { /* ignore */ }
      }
    } catch { /* ignore */ }
    liveRecognitionRef.current = null
    recognitionAliveRef.current = false

    // Pausa de calibração: após Jarvis falar, dar 200ms para o sistema de áudio do
    // browser resetar o baseline de ruído antes de ouvir novamente o microfone.
    const delay = forceCalibrationPause ? 200 : 40
    window.setTimeout(() => {
      if (liveCallActiveRef.current) {
        startBrowserLiveRecognition()
      }
    }, delay)
  }

  const startBrowserLiveRecognition = () => {
    const browserWindow = window as Window & { SpeechRecognition?: any; webkitSpeechRecognition?: any }
    const Recognition = browserWindow.SpeechRecognition || browserWindow.webkitSpeechRecognition
    if (!Recognition) return false
    if (recognitionAliveRef.current && liveRecognitionRef.current) return true // já rodando
    const recognition = new Recognition()
    setLiveAudioDiagnostics({ mode: 'browser-speech' })
    recognition.lang = 'pt-BR'
    recognition.continuous = true
    recognition.interimResults = true
    recognition.maxAlternatives = 1
    liveRecognitionRef.current = recognition
    recognitionAliveRef.current = false // será true no onstart
    recognition.onstart = () => {
      recognitionAliveRef.current = true
      if (liveCallActiveRef.current) {
        setLiveCallRecording(true)
        if (!isSpeakingRef.current) {
          setLiveOrbState('listening')
          setLiveCallStatus('Ouvindo continuamente… fale normalmente.')
        }
      }
    }
    recognition.onresult = (event: any) => {
      let interimText = ''
      let finalText = ''
      for (let index = event.resultIndex || 0; index < event.results.length; index += 1) {
        const result = event.results[index]
        if (result.isFinal) {
          finalText += `${result[0]?.transcript || ''} `
        } else {
          interimText += `${result[0]?.transcript || ''} `
        }
      }

      const heardSpeech = (finalText || interimText).trim()

      const prevDispatch = lastDispatchedSpeechRef.current
      const CORRECTION_WINDOW_MS = 1400

      // ── VERIFICAÇÃO EM PARALELO DE CONTINUAÇÃO (ZERO DELAY) ─────────────
      // Se enviamos uma mensagem especulativa recente e o usuário voltou a falar:
      // No primeiro instante (interim ou final), cancelamos imediatamente o envio anterior
      // antes que gere fala do Jarvis, e atualizamos a tela com a frase se completando.
      if (prevDispatch && !prevDispatch.isCancelled) {
        const elapsed = Date.now() - prevDispatch.timestamp
        if (elapsed <= CORRECTION_WINDOW_MS && heardSpeech.length >= 1) {
          prevDispatch.isCancelled = true
          try { prevDispatch.abort.abort() } catch { /* ignore */ }
          if (correctionWindowTimerRef.current !== null) {
            window.clearTimeout(correctionWindowTimerRef.current)
            correctionWindowTimerRef.current = null
          }
          liveCallProcessingRef.current = false
          isSpeakingRef.current = false
          if (audioRef.current) {
            try { audioRef.current.pause(); audioRef.current.src = '' } catch { /* ignore */ }
          }
          const continuationText = (interimText || finalText).trim()
          setLiveUserTranscript(`${prevDispatch.text} ${continuationText}`.trim())
          setLiveJarvisTranscript('')
          setLiveOrbState('listening')
          setLiveCallStatus('Completando frase…')
        }
      } else if (prevDispatch && prevDispatch.isCancelled && interimText.trim()) {
        setLiveUserTranscript(`${prevDispatch.text} ${interimText.trim()}`.trim())
      }

      // ⚡ BARGE-IN: detecta fala do usuário enquanto Jarvis está falando (quando NÃO é continuação própria)
      if ((isSpeakingRef.current || (audioRef.current && !audioRef.current.paused)) && (!prevDispatch || !prevDispatch.isCancelled)) {
        if (heardSpeech.length >= 2 && !bargedInRef.current) {
          triggerBargeIn()
        }
      }

      if (!finalText.trim() || !liveCallActiveRef.current) return

      // Permite processar após barge-in mesmo que processando
      const wasBargedIn = bargedInRef.current
      if (wasBargedIn) bargedInRef.current = false

      const newText = finalText.trim()

      // Caso 1: Usuário terminou a continuação que já havia começado no interim:
      if (prevDispatch && prevDispatch.isCancelled) {
        const mergedText = `${prevDispatch.text} ${newText}`.replace(/\s+/g, ' ').trim()
        lastDispatchedSpeechRef.current = null
        dispatchFinalSpeech(mergedText)
        return
      }

      // Caso 2: Chegou uma frase final rápida dentro da janela de pausa (ex: pausa curta + frase direta):
      if (prevDispatch && !prevDispatch.isCancelled && (Date.now() - prevDispatch.timestamp <= CORRECTION_WINDOW_MS) && !wasBargedIn) {
        prevDispatch.isCancelled = true
        try { prevDispatch.abort.abort() } catch { /* ignore */ }
        if (correctionWindowTimerRef.current !== null) {
          window.clearTimeout(correctionWindowTimerRef.current)
          correctionWindowTimerRef.current = null
        }
        liveCallProcessingRef.current = false
        isSpeakingRef.current = false
        if (audioRef.current) {
          try { audioRef.current.pause(); audioRef.current.src = '' } catch { /* ignore */ }
        }
        const mergedText = `${prevDispatch.text} ${newText}`.replace(/\s+/g, ' ').trim()
        lastDispatchedSpeechRef.current = null
        dispatchFinalSpeech(mergedText)
        return
      }

      // Caso 3: Envio inicial imediato (zero delay):
      dispatchFinalSpeech(newText)

      function dispatchFinalSpeech(cleanText: string) {
        if (!cleanText || !liveCallActiveRef.current) return

        // Limpa janela de correção anterior se houver
        if (correctionWindowTimerRef.current !== null) {
          window.clearTimeout(correctionWindowTimerRef.current)
          correctionWindowTimerRef.current = null
        }

        if (liveCallProcessingRef.current && !wasBargedIn) {
          // Uma nova frase final não pode desaparecer enquanto a anterior ainda
          // está processando. Cancela a solicitação antiga e privilegia a fala atual.
          lastDispatchedSpeechRef.current?.abort.abort()
          lastDispatchedSpeechRef.current = null
          speechAbortRef.current?.abort()
          liveCallProcessingRef.current = false
          isSpeakingRef.current = false
          recordDiagnostic('speech_replaced_while_processing', 'WARN')
        }
        liveCallProcessingRef.current = true

        const dispatchAbort = new AbortController()
        lastDispatchedSpeechRef.current = {
          text: cleanText,
          timestamp: Date.now(),
          abort: dispatchAbort,
          isCancelled: false,
        }

        setLiveCallRecording(false)
        setLiveUserTranscript(cleanText)

        // Janela de correção: após 1400ms sem nova fala, o envio é confirmado definitivamente
        correctionWindowTimerRef.current = window.setTimeout(() => {
          correctionWindowTimerRef.current = null
          if (lastDispatchedSpeechRef.current && !lastDispatchedSpeechRef.current.isCancelled) {
            lastDispatchedSpeechRef.current = null
          }
        }, CORRECTION_WINDOW_MS)

        void (async () => {
          try {
            let prompt = cleanText
            if (lastInterruptionRef.current?.text) {
              const cutOff = lastInterruptionRef.current.text
              lastInterruptionRef.current = null
              prompt = `[Contexto: você estava falando e foi interrompido exatamente após dizer: "${cutOff}". Responda de forma ágil ao que ele disse agora:] ${cleanText}`
            }
            // Passa o abort do dispatch especulativo para sendTextStreamAndPlay poder ser cancelado
            if (!dispatchAbort.signal.aborted) {
              await sendTextStreamAndPlay(prompt, cleanText, dispatchAbort)
            }
          } catch (error) {
            if (!dispatchAbort.signal.aborted) {
              setLiveCallStatus(error instanceof Error ? error.message : 'Falha durante a ligação.')
            }
          } finally {
            if (!dispatchAbort.signal.aborted || wasBargedIn) {
              liveCallProcessingRef.current = false
              isSpeakingRef.current = false
              bargedInRef.current = false
              if (liveCallActiveRef.current) {
                safeRestartLiveRecognition()
              }
            }
          }
        })()
      }
    }
    recognition.onerror = (event: any) => {
      recognitionAliveRef.current = false
      if (!liveCallActiveRef.current) return
      if (event?.error === 'not-allowed' || event?.error === 'service-not-allowed') {
        recordDiagnostic('browser_recognition_permission_denied', 'ERROR', { error: event?.error || 'unknown' })
        liveCallActiveRef.current = false
        setLiveCallRecording(false)
        setLiveOrbState('idle')
        setLiveCallStatus('Permissão de microfone negada. Verifique as configurações.')
        return
      }
      if (event?.error === 'aborted') return
      recordDiagnostic('browser_recognition_error', 'WARN', { error: event?.error || 'unknown' })
      // Em caso de erro, aguardar um pouco mais se Jarvis estiver falando
      const delay = isSpeakingRef.current ? 300 : 150
      window.setTimeout(() => {
        if (liveCallActiveRef.current && !recognitionAliveRef.current) {
          // Se Jarvis ainda fala, reinicia mesmo assim para manter barge-in
          startBrowserLiveRecognition()
        }
      }, delay)
    }
    recognition.onend = () => {
      recognitionAliveRef.current = false
      if (!liveCallActiveRef.current) return
      // Não rearma o reconhecimento durante a saída de áudio: alguns motores
      // recalibram o microfone contra a própria voz do Jarvis e perdem sensibilidade.
      if (isSpeakingRef.current) {
        return
      } else {
        // Jarvis parou de falar: pausa de calibração (200ms) para resetar o baseline de ruído
        if (postSpeechRestartTimerRef.current !== null) {
          window.clearTimeout(postSpeechRestartTimerRef.current)
        }
        postSpeechRestartTimerRef.current = window.setTimeout(() => {
          postSpeechRestartTimerRef.current = null
          if (liveCallActiveRef.current && !recognitionAliveRef.current) {
            startBrowserLiveRecognition()
          }
        }, 200)
      }
    }
    try {
      recognition.start()
      return true
    } catch {
      liveRecognitionRef.current = null
      return false
    }
  }

  const startFallbackContinuousCapture = async () => {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      liveCallActiveRef.current = false
      setLiveCallStatus('Microfone não suportado neste navegador.')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: micAudioConstraints({ echoCancellation: true, noiseSuppression: true, autoGainControl: true }) })
      if (!liveCallActiveRef.current) { stream.getTracks().forEach(track => track.stop()); return }
      liveCallStreamRef.current = stream
      const audioContext = new AudioContext()
      const analyser = audioContext.createAnalyser()
      analyser.fftSize = 1024
      audioContext.createMediaStreamSource(stream).connect(analyser)
      fallbackAudioContextRef.current = audioContext
      fallbackListeningRef.current = true
      setLiveCallRecording(true)
      setLiveOrbState('listening')
      setLiveCallStatus('Ouvindo continuamente… fale normalmente.')
      recordDiagnostic('fallback_vad_started')
      setLiveAudioDiagnostics({ mode: 'fallback-vad', rms: 0, threshold: 0.012, noiseFloor: fallbackNoiseFloorRef.current })

      // Sensibilidade, silêncio para encerrar a fala e ganho vêm de Configurações (/api/settings/mic).
      let mic = { sensitivity: 75, silence_ms: 700, gain: 1 }
      try {
        const micResponse = await fetch('/api/settings/mic')
        if (micResponse.ok) mic = { ...mic, ...(await micResponse.json()) }
      } catch { /* mantém os padrões */ }
      const thresholdFloor = 0.03 - 0.026 * (mic.sensitivity / 100)
      const noiseMultiplier = 3.5 - 1.5 * (mic.sensitivity / 100)

      const data = new Uint8Array(analyser.fftSize)
      const startUtterance = () => {
        if (!liveCallActiveRef.current || liveCallProcessingRef.current || liveCallRecorderRef.current?.state === 'recording') return
        const chunks: BlobPart[] = []
        const options = pickRecorderOptions()
        const recorder = new MediaRecorder(stream, options)
        const turnId = newVoiceTurnId()
        voiceTurnIdRef.current = turnId
        liveSpeakerRef.current = {}
        const turnStartedAt = performance.now()
        recordDiagnostic('voice_turn_started', 'INFO', { turn_id: turnId, session_id: sessionId || 'unknown', capture_mode: 'fallback-vad' })
        liveCallRecorderRef.current = recorder
        recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data) }
        recorder.onstop = async () => {
          if (liveCallRecorderRef.current === recorder) liveCallRecorderRef.current = null
          const audio = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' })
          if (!liveCallActiveRef.current || audio.size < 500) return
          liveCallProcessingRef.current = true
          setLiveCallRecording(false)
          try {
            setLiveCallStatus('Transcrevendo…')
            if (isMobileStandalone()) {
              const text = await transcribeMobileAudio(audio)
              liveCallSttFailureCountRef.current = 0
              setLiveUserTranscript(text)
              setLiveOrbState('thinking')
              setLiveCallStatus('Jarvis está processando…')
              const reply = await sendText(text)
              if (reply && liveCallActiveRef.current) {
                isSpeakingRef.current = true
                setLiveOrbState('speaking')
                await speakText(reply)
                isSpeakingRef.current = false
              }
              return
            }
            const stt = await fetch('/api/voice/stt', {
              method: 'POST',
              headers: { 'Content-Type': audio.type, 'X-Jarvis-Turn-ID': turnId, 'X-Jarvis-Session-ID': sessionId || '' },
              body: audio,
            })
            const transcription = await stt.json()
            if (!stt.ok || !transcription.ok || !transcription.text) throw new Error(transcription.error || 'Não foi possível entender o áudio.')
            const speaker = transcription.speaker
            if (speaker?.enabled) {
              liveSpeakerRef.current = speaker.matched
                ? { name: speaker.profile?.name, confidence: speaker.confidence }
                : { confidence: speaker.confidence, unknown: true }
              setLiveAudioDiagnostics(previous => previous ? { ...previous, speakerName: liveSpeakerRef.current.name, speakerConfidence: speaker.confidence, speakerUnknown: liveSpeakerRef.current.unknown } : previous)
              recordDiagnostic(speaker.matched ? 'voice_speaker_recognized' : 'voice_speaker_unknown', 'INFO', { turn_id: turnId, confidence: speaker.confidence || 0 })
            }
            liveCallSttFailureCountRef.current = 0
            recordDiagnostic('voice_turn_stt_completed', 'INFO', { turn_id: turnId, elapsed_ms: Math.round(performance.now() - turnStartedAt) })
            setLiveUserTranscript(transcription.text.trim())
            setLiveOrbState('thinking')
            setLiveCallStatus('Jarvis está processando…')
            recordDiagnostic('voice_turn_llm_started', 'INFO', { turn_id: turnId })
            const reply = await sendText(transcription.text.trim())
            recordDiagnostic('voice_turn_llm_completed', 'INFO', { turn_id: turnId, elapsed_ms: Math.round(performance.now() - turnStartedAt), reply_received: Boolean(reply) })
            if (reply && liveCallActiveRef.current) {
              isSpeakingRef.current = true
              setLiveOrbState('speaking')
              recordDiagnostic('voice_turn_tts_started', 'INFO', { turn_id: turnId })
              await speakText(reply)
              isSpeakingRef.current = false
              recordDiagnostic('voice_turn_completed', 'INFO', { turn_id: turnId, elapsed_ms: Math.round(performance.now() - turnStartedAt) })
            }
          } catch (error) {
            liveCallSttFailureCountRef.current += 1
            const message = error instanceof Error ? error.message : 'Falha durante a ligação.'
            recordDiagnostic('fallback_stt_failed', 'ERROR', { turn_id: turnId, attempt: liveCallSttFailureCountRef.current, message, elapsed_ms: Math.round(performance.now() - turnStartedAt) })
            setLiveCallStatus(`${message} Continuo ouvindo quando você tentar novamente.`)
          } finally {
            liveCallProcessingRef.current = false
            if (liveCallActiveRef.current) {
              setLiveCallRecording(true)
              setLiveOrbState('listening')
              setLiveCallStatus('Ouvindo continuamente… fale normalmente.')
            }
          }
        }
        recorder.start()
        fallbackSilenceStartedAtRef.current = null
        setLiveCallStatus('Ouvindo sua fala…')
      }

      const monitor = () => {
        if (!fallbackListeningRef.current || !liveCallActiveRef.current) return
        analyser.getByteTimeDomainData(data)
        let squareSum = 0
        for (const value of data) { const normalized = (value - 128) / 128; squareSum += normalized * normalized }
        const rms = Math.sqrt(squareSum / data.length) * mic.gain
        if (!isSpeakingRef.current && !liveCallProcessingRef.current && liveCallRecorderRef.current?.state !== 'recording') {
          fallbackNoiseFloorRef.current = fallbackNoiseFloorRef.current * 0.97 + rms * 0.03
        }
        const threshold = Math.max(thresholdFloor, fallbackNoiseFloorRef.current * noiseMultiplier)
        if (performance.now() - fallbackLastDiagnosticsUpdateRef.current >= 180) {
          fallbackLastDiagnosticsUpdateRef.current = performance.now()
          setLiveAudioDiagnostics({ mode: 'fallback-vad', rms, threshold, noiseFloor: fallbackNoiseFloorRef.current, turnId: voiceTurnIdRef.current || undefined, speakerName: liveSpeakerRef.current.name, speakerConfidence: liveSpeakerRef.current.confidence, speakerUnknown: liveSpeakerRef.current.unknown })
        }
        const recordingNow = liveCallRecorderRef.current?.state === 'recording'
        if (!isSpeakingRef.current && !liveCallProcessingRef.current && rms >= threshold) {
          if (!recordingNow) startUtterance()
          fallbackSilenceStartedAtRef.current = null
        } else if (recordingNow) {
          if (fallbackSilenceStartedAtRef.current === null) fallbackSilenceStartedAtRef.current = performance.now()
          if (performance.now() - fallbackSilenceStartedAtRef.current >= mic.silence_ms) liveCallRecorderRef.current?.stop()
        }
        fallbackAnimationFrameRef.current = window.requestAnimationFrame(monitor)
      }
      monitor()
    } catch (error) {
      liveCallActiveRef.current = false
      recordDiagnostic('fallback_microphone_unavailable', 'ERROR', { error: error instanceof Error ? error.name : 'unknown' })
      setLiveCallStatus('Não consegui acessar o microfone. Verifique a permissão.')
    }
  }

  const toggleLiveCallCapture = async () => {
    if (nativeCallActiveRef.current || nativeVoiceModeRef.current === 'call') {
      nativeCallActiveRef.current = false
      nativeVoiceModeRef.current = 'idle'
      liveCallActiveRef.current = false
      stopNativeSpeech()
      stopNativeSpeak()
      setLiveCallRecording(false)
      setLiveOrbState('idle')
      setLiveCallStatus('Ligação pausada. Toque para retomar.')
      return
    }
    if (liveRecognitionRef.current) {
      liveCallActiveRef.current = false
      try { liveRecognitionRef.current.abort() } catch { /* ignore */ }
      liveRecognitionRef.current = null
      setLiveCallRecording(false)
      setLiveCallStatus('Ligação pausada. Toque para retomar.')
      return
    }
    if (liveCallActiveRef.current && fallbackListeningRef.current) {
      closeLiveCall()
      setLiveCallOpen(true)
      setLiveCallStatus('Ligação pausada. Toque para retomar.')
      return
    }
    liveCallActiveRef.current = true
    if (isMobileStandalone() && hasNativeVoice()) {
      nativeCallActiveRef.current = true
      nativeVoiceModeRef.current = 'call'
      setLiveAudioDiagnostics({ mode: 'native-speech' })
      setLiveCallRecording(true)
      setLiveOrbState('listening')
      setLiveCallStatus('Ouvindo continuamente… fale normalmente.')
      console.log('[JarvisVoice] Starting native call mode via Android bridge')
      startNativeSpeech(true)
      return
    }
    // No app de PC (pywebview/WebView2) e navegadores locais, o Web Speech API não funciona
    // sem serviço embutido no SO. Usamos sempre o VAD contínuo de alta precisão com Groq Whisper no backend local.
    await startFallbackContinuousCapture()
  }

  // Auto-iniciar captura ao abrir a ligação
  useEffect(() => {
    if (liveCallOpen && !liveCallActiveRef.current) {
      void toggleLiveCallCapture()
    }
  }, [liveCallOpen])

  const setSpeakEnabled = useCallback((enabled: boolean) => {
    setSpeakEnabledState(enabled)
    try {
      localStorage.setItem(SPEAK_STORAGE_KEY, enabled ? '1' : '0')
    } catch {
      /* ignore storage errors */
    }
  }, [])

  const setSpeakerIdentificationEnabled = useCallback((enabled: boolean) => {
    setSpeakerIdentificationEnabledState(enabled)
    try { localStorage.setItem(SPEAKER_IDENTIFICATION_STORAGE_KEY, enabled ? '1' : '0') } catch { /* ignore storage errors */ }
  }, [])

  const speakText = async (text: string) => {
    if (!text || !speakEnabled) return
    const requestId = ++speechRequestRef.current
    speechAbortRef.current?.abort()
    const abortController = new AbortController()
    speechAbortRef.current = abortController
    if (isMobileStandalone() && hasNativeVoice()) {
      setLiveJarvisTranscript(text.replace(/[*_#`~]/g, '').trim())
      await new Promise<void>(resolve => {
        let settled = false
        const finish = () => {
          if (settled) return
          settled = true
          ttsDoneResolverRef.current = null
          resolve()
        }
        ttsDoneResolverRef.current = finish
        nativeSpeak(text)
        const timeout = Math.min(24000, 600 + text.length * 70)
        window.setTimeout(finish, timeout)
      })
      if (requestId !== speechRequestRef.current) return
      return
    }
    audioRef.current?.pause()
    if (audioRef.current) audioRef.current.src = ''
    if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current)
    audioRef.current = null
    audioUrlRef.current = null
    let url: string | null = null
    try {
      const request = { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }), signal: abortController.signal }
      const streamResponse = await fetch('/api/voice/tts/stream', request)
      if (streamResponse.ok) {
        const streamed = await createStreamingAudio(streamResponse)
        if (streamed) {
          if (requestId !== speechRequestRef.current) { URL.revokeObjectURL(streamed.url); return }
          url = streamed.url
          audioUrlRef.current = url
          audioRef.current = streamed.audio
          streamed.audio.onended = () => {
            if (url) URL.revokeObjectURL(url)
            url = null
            audioUrlRef.current = null
            audioRef.current = null
          }
          await streamed.audio.play()
          return
        }
      }
      const response = await fetch('/api/voice/tts', request)
      if (!response.ok) throw new Error('A leitura por voz não está disponível.')
      if (requestId !== speechRequestRef.current) return
      const blob = await response.blob()
      if (requestId !== speechRequestRef.current) return
      url = URL.createObjectURL(blob)
      audioUrlRef.current = url
      const audio = new Audio(url)
      audioRef.current = audio
      audio.onended = () => {
        if (url) URL.revokeObjectURL(url)
        url = null
        audioUrlRef.current = null
        audioRef.current = null
      }
      await audio.play()
    } catch (error) {
      if (!abortController.signal.aborted) setAnswer(error instanceof Error ? error.message : 'Falha ao gerar áudio.')
    } finally {
      if (speechAbortRef.current === abortController) speechAbortRef.current = null
    }
  }

  useEffect(() => {
    if (!isMobileStandalone()) return undefined
    return installNativeVoiceHandlers({
      onSpeechPartial: text => {
        if (nativeVoiceModeRef.current === 'call') setLiveUserTranscript(text)
      },
      onSpeechFinal: text => {
        const spoken = text.trim()
        if (!spoken) return
        if (nativeVoiceModeRef.current === 'composer') {
          nativeVoiceModeRef.current = 'idle'
          stopNativeSpeech()
          setRecording(false)
          setQuery(spoken)
          setAnswer('Transcrição pronta. Revise a mensagem e envie quando quiser.')
          return
        }
        if (nativeVoiceModeRef.current !== 'call' || !liveCallActiveRef.current) return
        if (liveCallProcessingRef.current || isSpeakingRef.current) return
        liveCallProcessingRef.current = true
        // Note: do NOT call stopNativeSpeech() here — Kotlin already stopped the recognizer
        // after delivering onResults. Calling it again causes ERROR_RECOGNIZER_BUSY on restart.
        console.log('[JarvisVoice] onSpeechFinal received:', spoken)
        setLiveUserTranscript(spoken)
        setLiveOrbState('thinking')
        setLiveCallRecording(false)
        setLiveCallStatus('Jarvis está pensando…')
        void (async () => {
          try {
            const reply = await sendText(spoken)
            if (reply && liveCallActiveRef.current) {
              isSpeakingRef.current = true
              setLiveOrbState('speaking')
              setLiveCallStatus('Jarvis está falando…')
              await speakText(reply)
              isSpeakingRef.current = false
            }
          } catch (error) {
            setLiveCallStatus(error instanceof Error ? error.message : 'Falha durante a ligação.')
          } finally {
            liveCallProcessingRef.current = false
            if (liveCallActiveRef.current && nativeCallActiveRef.current) {
              setLiveCallRecording(true)
              setLiveOrbState('listening')
              setLiveCallStatus('Ouvindo continuamente… fale normalmente.')
              startNativeSpeech(true)
            }
          }
        })()
      },
      onSpeechError: code => {
        console.log('[JarvisVoice] onSpeechError received:', code)
        if (code === 'permission') {
          setLiveCallStatus('Permissão de microfone negada. Verifique as configurações do Android.')
          nativeCallActiveRef.current = false
          setRecording(false)
          return
        }
        // Note: Kotlin's NativeVoiceBridge already handles auto-retry on recoverable errors
        // in continuous mode. We do NOT restart here from JS to avoid race conditions.
        if (code === 'unavailable' && liveCallActiveRef.current) {
          // Android's SpeechRecognizer not available — use VAD + Groq Whisper (best quality for PT-BR)
          console.log('[JarvisVoice] Native STT unavailable, switching to Groq Whisper VAD')
          nativeVoiceModeRef.current = 'idle'
          nativeCallActiveRef.current = false
          setLiveCallStatus('Ouvindo continuamente… fale normalmente.')
          void startFallbackContinuousCapture()
        }
      },
      onTtsDone: () => {
        ttsDoneResolverRef.current?.()
        ttsDoneResolverRef.current = null
      },
      onTtsError: () => {
        ttsDoneResolverRef.current?.()
        ttsDoneResolverRef.current = null
      },
    })
  }, [sendText, setQuery, setAnswer])

  const captureVision = async (action: unknown = 'analyze_screen') => {
    const captureAction = action === 'analyze_camera' ? 'analyze_camera' : 'analyze_screen'
    try {
      setAnswer(captureAction === 'analyze_camera' ? 'Analisando a câmera…' : 'Analisando a tela…')
      const response = await fetch('/api/vision/capture', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: captureAction, prompt: query.trim() || (captureAction === 'analyze_camera' ? 'Analise a imagem da câmera e descreva os elementos importantes.' : 'Analise a tela atual e descreva os elementos importantes.') }),
      })
      const data = await response.json()
      if (!response.ok || !data.ok) throw new Error(data.error || 'Não foi possível analisar a tela.')
      setVisionResult({ reply: data.reply || 'Análise concluída.', imageUrl: data.capture_url })
    } catch (error) {
      setAnswer(error instanceof Error ? error.message : 'Falha na análise visual.')
    }
  }

  return {
    captureVision,
    closeLiveCall,
    liveCallOpen,
    liveCallRecording,
    liveCallStatus,
    liveAudioDiagnostics,
    liveUserTranscript,
    liveJarvisTranscript,
    liveTurns,
    liveOrbState,
    recording,
    speakerIdentificationEnabled,
    setSpeakerIdentificationEnabled,
    setLiveCallOpen,
    setSpeakEnabled,
    setVisionResult,
    speakEnabled,
    speakText,
    stopSpeaking,
    toggleLiveCallCapture,
    toggleVoiceInput,
    triggerBargeIn,
    visionResult,
  }
}
