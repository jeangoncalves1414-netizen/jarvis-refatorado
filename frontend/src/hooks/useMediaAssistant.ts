import { pairedAndroid } from '../utils/pairedAndroid'
import { isCameraObservationRequest, requestVoiceCamera } from '../utils/cameraRequest'
import { captureIdentityFrame } from '../components/CallIdentityCamera'
import { handleLiveIntroduction } from '../components/LiveEnrollment'
import { useCallback, useEffect, useRef, useState } from 'react'
import { playAudioToEnd } from '../utils/voicePlayback'
import { createAgentAudio } from '../utils/voiceSpeed'
import { openMicrophone, loadMicrophone, createMicrophoneRecognition } from '../utils/micPrefs'
import { LOOPBACK_HOSTS, postCapture } from '../utils/backendCapture'
import { liveDictationBus } from '../utils/dictationBus'
import { isMobileStandalone } from './useDirectChat'
import type { RequestOrigin, VoiceExchangePreview } from './useChat'
import type { ToolActivityEntry, TurnMeta } from '../types'
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
  mode: 'browser-speech' | 'fallback-vad' | 'native-speech' | 'backend-sr'
  note?: string
  sttMs?: number
  rms?: number
  threshold?: number
  noiseFloor?: number
  turnId?: string
  speakerName?: string
  speakerConfidence?: number
  speakerUnknown?: boolean
}

type BackendCapture = { cancelled: boolean; abort: AbortController; playbackTimer: number; lastPlayback: boolean; lastLevelAt: number; speaking: boolean; awaitingEnd: boolean; turns: { id: string; result?: Record<string, any> }[] }


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
  if (pairedAndroid) return false
  try { return localStorage.getItem(SPEAKER_IDENTIFICATION_STORAGE_KEY) === '1' } catch { return false }
}

export const SEARCH_FILLERS = [
  'Procurando na web...',
  'Deixa eu conferir as fontes...',
  'Dando uma olhada nos sites...',
]

export const THINKING_FILLERS = [
  'Só um momento...',
  'Hm, analisando aqui...',
  'Deixa eu pensar bem nisso...',
]

export const PROGRESSION_FILLERS = [
  'Ainda estou consultando as informações...',
  'Só mais um instante...',
  'Cruzando os dados que encontrei...',
  'Ainda processando os resultados...',
]

let searchFillerIndex = 0
let thinkingFillerIndex = 0
let progressionFillerIndex = 0

export function pickSearchFiller(): string {
  const filler = SEARCH_FILLERS[searchFillerIndex % SEARCH_FILLERS.length]
  searchFillerIndex++
  return filler
}

export function pickThinkingFiller(): string {
  const filler = THINKING_FILLERS[thinkingFillerIndex % THINKING_FILLERS.length]
  thinkingFillerIndex++
  return filler
}

export function pickProgressionFiller(): string {
  const filler = PROGRESSION_FILLERS[progressionFillerIndex % PROGRESSION_FILLERS.length]
  progressionFillerIndex++
  return filler
}

export function isSearchIntent(text: string): boolean {
  if (!text) return false
  return /\b(pesquis(e|ar?|ando)|procur(e|ar?|ando)|busqu?(e|ar?|ando)|google|not[ií]cias?|sites?|fontes?|internet|quem [eé]|onde fica|quanto custa|pre[cç]o|clima|tempo hoje)\b/i.test(text)
}

export function isToolOrHeavyIntent(text: string): boolean {
  if (!text) return false
  if (isSearchIntent(text)) return true
  return /\b(calcule|calcula|analis(e|ar?|ando)|planej(e|ar?|ando)|execut(e|ar?|ando)|abr(a|ir)|fech(e|ar)|crie?|gerar?|rod(e|ar)|automa[cç]|desenvolv(a|er)|resolv(a|er)|script|c[oó]digo|terminal|navegador|browser|pasta|arquivo|sistema)\b/i.test(text)
}

export const CANCEL_COMMAND_REGEX = /^(?:jarvis[,.]?\s*)?(?:cancela(?:r)?(?:\s+(?:a\s+pesquisa|isso|agora|tudo))?|para(?:r)?(?:\s+(?:de\s+(?:falar|pesquisar|buscar)|tudo|agora|a\s+pesquisa))?|pare(?:\s+(?:de\s+(?:falar|pesquisar|buscar)|tudo|agora|a\s+pesquisa))?|deixa\s+pra\s+l[aá]|aborta(?:r)?|chega|sil[eê]ncio)[.!]?$/i

export function isCancelCommand(text: string): boolean {
  if (!text) return false
  const clean = text.trim()
  return CANCEL_COMMAND_REGEX.test(clean)
}

export function sanitizeSpeechText(text: string): string {
  if (!text) return ''
  let t = text

  // Technical failures belong on screen, including when a provider puts them in a normal reply.
  if (/Traceback \(most recent call last\)|\b\w*(?:Error|Exception):|object has no attribute|\bHTTP\s+[45]\d\d\b/i.test(t)) {
    return 'Não consegui concluir o pedido. Os detalhes estão na tela.'
  }
  t = t.replace(/^.*(?:\[(?:DEBUG|INFO|WARN|ERROR)\]|^\s*at\s+\S+\s*\().*$/gm, '')
  t = t.replace(/\([^)]*(?:\.exe\b|\b(?:pid|hwnd)\s*[:=])[^)]*\)/gi, '')
  t = t.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')

  // Remove marcadores de ferramenta [tool:...]
  t = t.replace(/\[tool:[^\]]+\]/g, '')

  // Remove blocos de código ```...```
  t = t.replace(/```[\s\S]*?```/g, '')

  // Remove código inline mantendo o texto interno
  t = t.replace(/`([^`]+)`/g, '$1').replace(/`/g, '')

  // Remove preâmbulos técnicos de ferramentas
  const toolPreambles = [
    /\bresultados?\s+das?\s+ferramentas?\s*:\s*/gi,
    /\bresultados?\s+de\s+[a-zA-Z0-9_\-]+\s*:\s*/gi,
    /\bresultado\s+da\s+pesquisa\s*:\s*/gi,
    /\bsa[ií]da\s+d[ao]\s+ferramenta\s*:\s*/gi,
    /\bferramenta\s+executada\s*:\s*/gi,
    /\bexecutando\s+ferramenta\s*:\s*/gi,
    /\bcomando\s+executado\s*:\s*/gi,
    /\bsa[ií]da\s+do\s+terminal\s*:\s*/gi,
    /\bnavegador\s+aberto\s+na\s+url\s*:\s*(?:https?:\/\/\S+)?/gi,
    /\bp[aá]gina\s+aberta\s+em\s*:\s*(?:https?:\/\/\S+)?/gi,
    /\bacessando(?:\s+a)?\s+url\s*:\s*(?:https?:\/\/\S+)?/gi,
    /\b(?:no\s+link|do\s+link|pelo\s+link|no\s+site|da\s+fonte|a\s+fonte|o\s+link|a\s+url)\s*:\s*(?:https?:\/\/\S+|www\.\S+)?/gi,
    /\b(?:link|url|fonte|href)\s*:\s*(?:https?:\/\/\S+|www\.\S+)?/gi,
  ]
  for (const pattern of toolPreambles) {
    t = t.replace(pattern, ' ')
  }

  // Remove URLs restantes para nunca serem soletradas pelo TTS
  t = t.replace(/https?:\/\/\S+|www\.\S+/gi, '')
  t = t.replace(/\b(?:[a-z0-9-]+\.)+(?:com|org|net|io|dev|app|gg|br|pt|edu|gov|ai|me|tv|co)(?:\.[a-z]{2})?(?:[/?#][^\s<>"')]*)?\b/gi, '')
  t = t.replace(/\b[a-z0-9_-]+\.exe\b/gi, '')

  // Converte links markdown [texto](url) -> texto
  t = t.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')

  // Remove citações numéricas tipo [1], [2]
  t = t.replace(/\[\d+\]/g, '')

  // Remove títulos markdown (# Título)
  t = t.replace(/^#+\s*/gm, '')

  // Remove formatação básica de markdown (**bold**, *italic*, __underline__, ~~strike~~)
  t = t.replace(/\*\*/g, '').replace(/__/g, '').replace(/~~/g, '').replace(/\*/g, '')

  // Converte marcadores de lista no início de linhas (-, *, +, •)
  t = t.replace(/^\s*[-•>+]\s+/gm, '')

  // Trata numerações repetitivas ou inline: ' 1. Item ... 2. Item' -> ' Item. Item'
  t = t.replace(/(?<=[.:;\n])\s*\d+[\.\)]\s*/g, ' ')
  t = t.replace(/^\s*\d+[\.\)]\s*/gm, '')
  t = t.replace(/\s+\d+[\.\)]\s+/g, '. ')

  // Remove emojis e caracteres gráficos
  t = t.replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/gu, '')

  // Normaliza quebras de linha e espaços
  t = t.replace(/\n{2,}/g, '\n')
  t = t.replace(/[ \t]+/g, ' ')

  // Limpeza de pontuação duplicada ou órfã
  t = t.replace(/\s*([:;])\s*([:;])+/g, '$1')
  t = t.replace(/\s*([.,;!?])\s*([.,;!?])+/g, '$1')
  t = t.replace(/\s+([.,;:!?])/g, '$1')

  // Remove pontuação solta ou espaços nas pontas
  t = t.replace(/^[\s:;,-]+|[\s:;,-]+$/g, '')

  return t.trim()
}

export function detectSilenceCommand(text: string): { isCommand: boolean; enableSilence: boolean } {
  if (!text) return { isCommand: false, enableSilence: false }
  if (/\b(pode\s+(narrar|falar)|desativ(e|ar)\s+(o\s+)?modo\s+silencioso|sa(i|ia)\s+do\s+modo\s+silencioso|desativ(e|ar)\s+sil[eê]ncio)\b/i.test(text)) {
    return { isCommand: true, enableSilence: false }
  }
  if (/\b(n[aã]o\s+precisa\s+(narrar|falar(\s+nada)?(\s+enquanto\s+pesquisa)?)|pesquis(e|a)\s+em\s+sil[eê]ncio|pesquis(e|a)\s+sem\s+falar(\s+nada)?|modo\s+silencioso|ativ(e|ar)\s+(o\s+)?modo\s+silencioso|fiqu?e\s+em\s+sil[eê]ncio|sem\s+narrar)\b/i.test(text)) {
    return { isCommand: true, enableSilence: true }
  }
  return { isCommand: false, enableSilence: false }
}

export function buildContextStitchingPrompt(interruptedText: string, userSpeech: string): string {
  const cutOff = (interruptedText || '').trim()
  const user = (userSpeech || '').trim()
  return `[Contexto da interrupção, não uma nova ordem para repetir ações: ${cutOff}]\nFala atual do usuário: ${user}\nResponda incorporando a correção ou continuação. Considere somente resultados confirmados das ferramentas.`
}

async function createStreamingAudio(response: Response): Promise<{ audio: HTMLAudioElement; url: string } | null> {
  if (!response.body || typeof MediaSource === 'undefined' || !MediaSource.isTypeSupported('audio/mpeg')) {
    if (!pairedAndroid) return null
    const blob = await response.blob()
    if (!blob.size) return null
    const url = URL.createObjectURL(blob)
    return { audio: createAgentAudio(url), url }
  }
  const mediaSource = new MediaSource()
  const url = URL.createObjectURL(mediaSource)
  const audio = createAgentAudio(url)
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
  appendExchange?: (userText: string, assistantText: string, receipt?: { run_id?: string; activity?: ToolActivityEntry[]; meta?: TurnMeta }, previewId?: string) => Promise<void>
  previewExchange?: (id: string, preview: VoiceExchangePreview | null) => void
  // Interface pedida pelo agente durante a ligação (popups, janela, tela): SSE "popup" e plan.context do "complete".
  onAgentContext?: (context: unknown) => void
}

export function useMediaAssistant({ query, sendText: sendChatText, setAnswer, setQuery, sessionId, appendExchange, previewExchange, onAgentContext }: MediaAssistantOptions) {
  const appendExchangeRef = useRef(appendExchange)
  appendExchangeRef.current = appendExchange
  const previewExchangeRef = useRef(previewExchange)
  previewExchangeRef.current = previewExchange
  const agentContextRef = useRef(onAgentContext)
  agentContextRef.current = onAgentContext
  const sessionIdRef = useRef(sessionId)
  sessionIdRef.current = sessionId
  const [liveTurns, setLiveTurns] = useState<{ id: string; user: string; jarvis: string; pending?: boolean; activity?: ToolActivityEntry[] }[]>([])
  // Cada fala vira um turno próprio na tela da ligação (balão da usuária + balão do assistente), em todos os modos.
  const beginLiveTurn = (user: string) => {
    const id = `turn_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
    setLiveTurns(previous => [...previous, { id, user, jarvis: '', pending: true }].slice(-30))
    return id
  }
  const updateLiveTurn = (id: string, patch: { user?: string; jarvis?: string; append?: string; pending?: boolean; activity?: ToolActivityEntry[] }) => {
    setLiveTurns(previous => previous.map(turn => turn.id !== id ? turn : {
      ...turn,
      user: patch.user ?? turn.user,
      jarvis: patch.append !== undefined ? (turn.jarvis ? `${turn.jarvis} ${patch.append}` : patch.append) : (patch.jarvis ?? turn.jarvis),
      pending: patch.pending ?? turn.pending,
      activity: patch.activity ?? turn.activity,
    }))
  }
  const removeLiveTurn = (id: string) => setLiveTurns(previous => previous.filter(turn => turn.id !== id))
  const streamTurnRef = useRef<{ id: string; user: string; session?: string; continuing: boolean } | null>(null)
  const previewContinuation = (text = '', alreadyCombined = false) => {
    const turn = streamTurnRef.current
    if (!turn?.continuing) return
    const user = alreadyCombined ? text : [turn.user, text].filter(Boolean).join(' ')
    setLiveUserTranscript(user)
    updateLiveTurn(turn.id, { user, jarvis: '', activity: [], pending: true })
    previewExchangeRef.current?.(turn.id, { user, reply: '' })
  }
  const preserveStreamTurn = () => {
    const turn = streamTurnRef.current
    if (!turn || turn.session !== sessionIdRef.current) return
    turn.continuing = true
    previewContinuation()
  }
  const discardStreamTurn = () => {
    const turn = streamTurnRef.current
    streamTurnRef.current = null
    if (turn) {
      previewExchangeRef.current?.(turn.id, null)
      removeLiveTurn(turn.id)
    }
  }
  // Fala enviada pelo chat normal (modos VAD do navegador e nativo): o balão da usuária aparece já, o do assistente quando a resposta chega.
  const sendTextAsTurn = async (text: string) => {
    if (handleLiveIntroduction(text)) return ''
    const observation = await requestVoiceCamera(text)
    if (observation !== null) {
      if (observation && liveCallActiveRef.current) {
        const turn = beginLiveTurn(text)
        updateLiveTurn(turn, { jarvis: observation, pending: false })
      }
      return observation
    }
    const liveTurnId = beginLiveTurn(text)
    let reply = ''
    try {
      reply = await sendText(text)
      return reply
    } finally {
      if (reply) updateLiveTurn(liveTurnId, { jarvis: reply, pending: false })
      else removeLiveTurn(liveTurnId)
    }
  }
  // Pedidos falados chegam ao servidor com origem "voice": as ações entram na Central como voz (C10).
  const sendText = useCallback((message: string) => sendChatText(message, 'general', false, 'voice'), [sendChatText])
  const [speakEnabled, setSpeakEnabledState] = useState(readSpeakEnabled)
  const [speakerIdentificationEnabled, setSpeakerIdentificationEnabledState] = useState(readSpeakerIdentificationEnabled)
  const speakerIdentificationEnabledRef = useRef(speakerIdentificationEnabled)
  const [silentMode, setSilentModeState] = useState(false)
  const silentModeRef = useRef(false)
  const [recording, setRecording] = useState(false)
  const [liveCallOpen, setLiveCallOpen] = useState(false)
  const enrollmentActiveRef = useRef(false)
  const resumeAfterEnrollment = useRef(false)
  const callOpenRef = useRef(liveCallOpen)
  callOpenRef.current = liveCallOpen
  const [liveCallRecording, setLiveCallRecording] = useState(false)
  const [liveCallStatus, setLiveCallStatus] = useState('Pronto para ouvir.')
  const [liveAudioDiagnostics, setLiveAudioDiagnostics] = useState<LiveAudioDiagnostics | null>(null)
  const [visionResult, setVisionResult] = useState<{ reply: string; imageUrl?: string } | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const liveCallRecorderRef = useRef<MediaRecorder | null>(null)
  const liveCallStreamRef = useRef<MediaStream | null>(null)
  const liveRecognitionRef = useRef<any>(null)
  const liveCallActiveRef = useRef(false)
  const captureEpochRef = useRef(0)
  const captureSessionRef = useRef(0)
  const transcriptionAbortRef = useRef<AbortController | null>(null)
  const startPttRecordingRef = useRef<(() => void) | null>(null)
  const liveCallProcessingRef = useRef(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const audioUrlRef = useRef<string | null>(null)
  const speechRequestRef = useRef(0)
  const speechAbortRef = useRef<AbortController | null>(null)
  const voiceCancellationRef = useRef<Promise<string> | null>(null)
  const isSpeakingRef = useRef(false)
  const spokenSentencesRef = useRef<string[]>([])
  const lastInterruptionRef = useRef<{ text: string; time: number } | null>(null)
  const lastVoiceRequestRef = useRef<{ text: string; time: number } | null>(null)
  const playingPhraseRef = useRef<{ text: string; audio: HTMLAudioElement } | null>(null)
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
  const identityEvidenceRef = useRef<string | undefined>(undefined)
  const identityPartsRef = useRef<string[]>([])
  const liveSpeakerRef = useRef<{ name?: string; confidence?: number; unknown?: boolean }>({})
  const nativeVoiceModeRef = useRef<'idle' | 'call' | 'composer'>('idle')
  const nativeCallActiveRef = useRef(false)
  const ttsDoneResolverRef = useRef<(() => void) | null>(null)
  // Captura de fala pelo backend (SpeechRecognition no PC): handle da sessão ativa e motivo de cair no navegador.
  const backendCaptureRef = useRef<BackendCapture | null>(null)
  const captureNoteRef = useRef('')
  const backendDispatchAbortRef = useRef<AbortController | null>(null)

  const SILENCE_BUFFER_MS = 800
  const silenceBufferTimerRef = useRef<number | null>(null)
  const silenceAccumulatedTextRef = useRef('')
  const pendingSpeechRef = useRef<{ text: string; send: (text: string) => void; timer: number | null } | null>(null)

  function clearPendingSpeech() {
    if (pendingSpeechRef.current?.timer != null) window.clearTimeout(pendingSpeechRef.current.timer)
    pendingSpeechRef.current = null
  }

  function acceptSpeakerEvidence(token?: string) {
    if (!pendingSpeechRef.current) identityPartsRef.current = []
    identityPartsRef.current.push(speakerIdentificationEnabledRef.current ? token || '' : '')
    identityEvidenceRef.current = identityPartsRef.current.length === 1 ? identityPartsRef.current[0] || undefined : undefined
  }

  function pausePendingSpeech() {
    if (pendingSpeechRef.current?.timer != null) {
      window.clearTimeout(pendingSpeechRef.current.timer)
      pendingSpeechRef.current.timer = null
    }
  }

  function bufferSpeech(text: string, send: (text: string) => void, always = false, delay?: number): boolean {
    if (pushToTalkModeRef.current) return false
    const combined = [pendingSpeechRef.current?.text, text].filter(Boolean).join(' ').trim()
    // A short pause after a transitive verb or connective is not a complete request.
    const incomplete = /\b(abra|abre|abrir|coloque|adicione|pesquise|quero|pode|e|ou|que|para|com|de|depois|em seguida)\s*[,.!?]*$/i.test(combined)
    if (!always && !incomplete && !pendingSpeechRef.current) return false
    clearPendingSpeech()
    const pending = { text: combined, send, timer: null as number | null }
    pendingSpeechRef.current = pending
    setLiveUserTranscript(combined)
    if (backendCaptureRef.current) previewContinuation(combined)
    setLiveCallStatus('Ouvindo… aguardando você concluir.')
    pending.timer = window.setTimeout(() => {
      if (pendingSpeechRef.current !== pending) return
      if (backendCaptureRef.current?.speaking || backendCaptureRef.current?.turns.length || backendCaptureRef.current?.awaitingEnd) {
        pending.timer = null
        return
      }
      pendingSpeechRef.current = null
      if (liveCallActiveRef.current) pending.send(pending.text)
    }, delay ?? (incomplete ? 1800 : 150))
    return true
  }

  // Push-to-Talk (PTT - segurar para falar)
  const [pushToTalkMode, setPushToTalkModeState] = useState(false)
  const pushToTalkModeRef = useRef(false)
  const [isPttActive, setIsPttActiveState] = useState(false)
  const isPttActiveRef = useRef(false)
  const pttAccumulatedTextRef = useRef('')

  // Anotação ao vivo (lote 6): enquanto um popup de nota grava durante a ligação, as falas vão para
  // a nota e não para o agente, até "fim da nota" ou o botão Parar.
  useEffect(() => {
    liveDictationBus.setCallProbe(() => liveCallActiveRef.current)
    return () => liveDictationBus.setCallProbe(null)
  }, [])
  const divertToDictation = (text: string) => {
    const sink = liveDictationBus.sink()
    if (!sink || !text) return false
    setLiveUserTranscript(text)
    sink.onPhrase(text)
    setLiveCallStatus(liveDictationBus.sink() ? 'Anotando… diga "fim da nota" para voltar a falar com o agente.' : 'Anotação encerrada. Ouvindo continuamente…')
    return true
  }

  const toggleVoiceInput = async () => {
    if (nativeVoiceModeRef.current === 'composer') {
      nativeVoiceModeRef.current = 'idle'
      stopNativeSpeech()
      setRecording(false)
      setAnswer('Gravação encerrada.')
      return
    }
    if (hasNativeVoice() && (isMobileStandalone() || pairedAndroid) && !(await loadMicrophone()).device_name) {
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
      const stream = await openMicrophone()
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

  const stopLiveCall = (preserveView = false) => {
    clearPendingSpeech()
    discardStreamTurn()
    lastVoiceRequestRef.current = null
    lastInterruptionRef.current = null
    playingPhraseRef.current = null
    captureSessionRef.current += 1
    captureEpochRef.current += 1
    transcriptionAbortRef.current?.abort()
    transcriptionAbortRef.current = null
    startPttRecordingRef.current = null
    isPttActiveRef.current = false
    setIsPttActiveState(false)
    pttAccumulatedTextRef.current = ''
    silenceAccumulatedTextRef.current = ''
    for (const ref of [silenceBufferTimerRef, correctionWindowTimerRef, postSpeechRestartTimerRef]) {
      if (ref.current !== null) window.clearTimeout(ref.current)
      ref.current = null
    }
    lastDispatchedSpeechRef.current?.abort.abort()
    lastDispatchedSpeechRef.current = null
    stopBackendCapture()
    captureNoteRef.current = ''
    liveCallActiveRef.current = false
    liveCallProcessingRef.current = false
    nativeCallActiveRef.current = false
    nativeVoiceModeRef.current = 'idle'
    stopNativeSpeech()
    stopNativeSpeak()
    try { liveRecognitionRef.current?.stop() } catch { /* already stopped */ }
    liveRecognitionRef.current = null
    recognitionAliveRef.current = false
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
    identityEvidenceRef.current = undefined
    identityPartsRef.current = []
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
    isSpeakingRef.current = false
    if (!preserveView) {
      setLiveTurns([])
      setLiveCallOpen(false)
    }
  }
  const closeLiveCall = () => stopLiveCall()

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
    const cleaned = sanitizeSpeechText(text)
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
        if (streamed) {
          if (signal?.aborted) { URL.revokeObjectURL(streamed.url); return null }
          const release = () => URL.revokeObjectURL(streamed.url)
          streamed.audio.addEventListener('ended', release, { once: true })
          signal?.addEventListener('abort', release, { once: true })
          return streamed.audio
        }
      }
      const res = await fetch('/api/voice/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: cleaned }),
        signal,
      })
      if (!res.ok) return null
      const blob = await res.blob()
      if (signal?.aborted) return null
      const url = URL.createObjectURL(blob)
      const audio = createAgentAudio(url)
      const release = () => URL.revokeObjectURL(url)
      audio.addEventListener('ended', release, { once: true })
      signal?.addEventListener('abort', release, { once: true })
      return audio
    } catch {
      return null
    }
  }

  const sendTextStreamAndPlay = async (userText: string, displayText?: string, externalAbort?: AbortController, alreadyCombined = false) => {
    let identityToken = identityEvidenceRef.current
    const identityParts = identityPartsRef.current
    identityPartsRef.current = []
    identityEvidenceRef.current = undefined
    if (!userText || !liveCallActiveRef.current) return
    if (handleLiveIntroduction(displayText ?? userText, identityToken)) { discardStreamTurn(); return }
    if (isCameraObservationRequest(displayText ?? userText)) {
      setLiveOrbState('thinking'); setLiveCallStatus('Observando as câmeras…')
      setLiveUserTranscript(displayText ?? userText)
    }
    const observation = await requestVoiceCamera(displayText ?? userText)
    if (!liveCallActiveRef.current || externalAbort?.signal.aborted) return
    if (observation !== null) {
      discardStreamTurn()
      setLiveUserTranscript(displayText ?? userText)
      setLiveJarvisTranscript(observation)
      if (observation) {
        const turn = beginLiveTurn(displayText ?? userText)
        updateLiveTurn(turn, { jarvis: observation, pending: false })
        isSpeakingRef.current = true; setLiveOrbState('speaking')
        setLiveCallStatus('Respondendo sobre as câmeras…')
        try { await speakText(observation) } finally {
          isSpeakingRef.current = false
          if (liveCallActiveRef.current && !externalAbort?.signal.aborted) {
            setLiveOrbState('listening'); setLiveCallRecording(true)
            setLiveCallStatus('Ouvindo continuamente… fale normalmente.')
          }
        }
      }
      return
    }

    spokenSentencesRef.current = []

    // A continuação troca a requisição, mas preserva a identidade do balão.
    const previousTurn = streamTurnRef.current
    const continuation = previousTurn?.continuing && previousTurn.session === sessionIdRef.current ? previousTurn : null
    const spokenText = (displayText ?? userText).trim()
    const turnUser = continuation && !alreadyCombined ? `${continuation.user} ${spokenText}` : spokenText
    if (previousTurn && !continuation) discardStreamTurn()
    const liveTurnId = continuation?.id || beginLiveTurn(turnUser)
    const streamTurn = { id: liveTurnId, user: turnUser, session: sessionIdRef.current, continuing: false }
    streamTurnRef.current = streamTurn
    lastVoiceRequestRef.current = { text: turnUser, time: Date.now() }
    setLiveUserTranscript(turnUser)
    setLiveJarvisTranscript('')
    updateLiveTurn(liveTurnId, { user: turnUser, jarvis: '', activity: [], pending: true })
    let handledByChat = false
    setLiveOrbState('thinking')
    setLiveCallStatus('Processando seu pedido…')

    listeningRestoredRef.current = false
    const abortController = new AbortController()
    speechAbortRef.current = abortController
    let voiceRunId: string | null = null
    voiceCancellationRef.current = null
    let turnActivity: ToolActivityEntry[] = []
    let turnMeta: TurnMeta | undefined
    const announcedActions = new Set<string>()
    const cancelVoiceRun = () => {
      if (!voiceRunId) return
      const runId = voiceRunId
      voiceCancellationRef.current = fetch(`/api/runs/${encodeURIComponent(runId)}/cancel`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
        signal: AbortSignal.timeout(5000),
      }).then(async response => {
        const data = await response.json()
        if (!response.ok || !data.ok || data.run?.id !== runId) throw new Error('Cancelamento não confirmado')
        if (data.run.status === 'cancelled') return 'Pedido cancelado. As etapas já concluídas foram preservadas.'
        if (data.run.status === 'cancel_requested') return 'Cancelamento solicitado. Uma etapa já iniciada ainda pode terminar.'
        throw new Error('Cancelamento não confirmado')
      }).catch(() => 'Não consegui confirmar o cancelamento do pedido. Confira em Execuções.')
    }
    abortController.signal.addEventListener('abort', cancelVoiceRun, { once: true })

    // Propaga cancelamento externo (dispatch especulativo) para o AbortController interno
    if (externalAbort) {
      if (externalAbort.signal.aborted) { removeLiveTurn(liveTurnId); return }
      externalAbort.signal.addEventListener('abort', () => abortController.abort(), { once: true })
    }

    const audioQueue: { text: string; audioPromise?: Promise<HTMLAudioElement | null>; actionId?: string }[] = []
    let isPlayingQueue = false
    let isGeneratingResponse = true
    const turnStartedAt = performance.now()
    let firstAudioReported = false

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
          // Não rearmar o microfone se a resposta real ainda estiver sendo gerada
          if (isGeneratingResponse) {
            setLiveOrbState('thinking')
            setLiveCallStatus(isSearch ? '⚡ Buscando na web…' : '⚡ Processando resposta…')
          } else if (!listeningRestoredRef.current) {
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
        if (liveCallActiveRef.current && !abortController.signal.aborted) {
          if (isGeneratingResponse) {
            setLiveOrbState('thinking')
            setLiveCallStatus(isSearch ? '⚡ Buscando na web…' : '⚡ Processando resposta…')
          } else if (!listeningRestoredRef.current) {
            listeningRestoredRef.current = true
            setLiveOrbState('listening')
            setLiveCallStatus('Ouvindo continuamente… fale normalmente.')
            setLiveCallRecording(true)
          }
        }
        return
      }
      if (item.actionId && turnActivity.find(entry => entry.id === item.actionId)?.status !== 'running') {
        isPlayingQueue = false
        void playNextInQueue()
        return
      }

      listeningRestoredRef.current = false
      isSpeakingRef.current = true
      setLiveOrbState('speaking')
      if (item.actionId) {
        setLiveCallStatus(item.text)
      } else {
        setLiveCallStatus('⚡ Transmitindo resposta em tempo real…')
      }

      let audioEl: HTMLAudioElement | null = null
      try {
        // Race contra abort para não ficar preso aguardando TTS
        if (item.audioPromise) {
          audioEl = await Promise.race([item.audioPromise, abortPromise]) as HTMLAudioElement | null
        } else {
          audioEl = await fetchAndCreateAudio(item.text, abortController.signal)
        }

        const staleAnnouncement = item.actionId && turnActivity.find(entry => entry.id === item.actionId)?.status !== 'running'
        if (pairedAndroid && !audioEl && !abortController.signal.aborted) {
          captureNoteRef.current = 'Áudio Fish indisponível. A resposta está na transcrição.'
          recordDiagnostic('fish_audio_unavailable', 'WARN')
        }
        if (audioEl && !staleAnnouncement && liveCallActiveRef.current && !abortController.signal.aborted) {
          audioRef.current = audioEl
          playingPhraseRef.current = { text: item.text, audio: audioEl }
          audioEl.onplaying = () => {
                if (firstAudioReported) return
                firstAudioReported = true
                const ms = Math.round(performance.now() - turnStartedAt)
                setLiveCallStatus(`⚡ Primeiro áudio em ${ms} ms`)
                recordDiagnostic('voice_first_audio_ms', 'INFO', { ms })
          }
          await playAudioToEnd(audioEl, abortController.signal)
          // Se abortado enquanto tocava, para o áudio
          if (abortController.signal.aborted && audioEl) {
            try { audioEl.pause(); audioEl.src = '' } catch { /* ignore */ }
          }
        }
      } catch {
        /* skip broken audio chunk */
      } finally {
        if (audioRef.current === audioEl) audioRef.current = null
        if (audioEl?.src.startsWith('blob:')) URL.revokeObjectURL(audioEl.src)
        isPlayingQueue = false
        if (abortController.signal.aborted) return
        // Quando a fila drena:
        if (audioQueue.length === 0 || abortController.signal.aborted) {
          isSpeakingRef.current = false
          // Não rearmar o microfone enquanto a resposta real ainda estiver sendo gerada!
          if (isGeneratingResponse && !abortController.signal.aborted && liveCallActiveRef.current) {
            setLiveOrbState('thinking')
            setLiveCallStatus(isSearch ? '⚡ Buscando na web…' : '⚡ Processando resposta…')
          } else if (liveCallActiveRef.current && !abortController.signal.aborted && !listeningRestoredRef.current) {
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

    const isSearch = isSearchIntent(displayText || userText)

    const enqueuePhrase = (phrase: string) => {
      const sanitized = sanitizeSpeechText(phrase)
      if (!sanitized) return
      const audioPromise = fetchAndCreateAudio(sanitized, abortController.signal)
      audioQueue.push({ text: sanitized, audioPromise })
      void playNextInQueue()
    }

    let sentenceBuffer = ''
    let fullReply = ''
    const publishPreview = () => {
      if (abortController.signal.aborted || handledByChat || streamTurnRef.current !== streamTurn) return
      setLiveJarvisTranscript(fullReply)
      updateLiveTurn(liveTurnId, { jarvis: fullReply, activity: turnActivity })
      previewExchangeRef.current?.(liveTurnId, { user: turnUser, reply: fullReply, activity: turnActivity })
    }
    const clearPreview = () => {
      if (streamTurnRef.current === streamTurn && !streamTurn.continuing) previewExchangeRef.current?.(liveTurnId, null)
    }
    abortController.signal.addEventListener('abort', clearPreview, { once: true })
    publishPreview()

    try {
      if (identityParts.length > 1 && speakerIdentificationEnabledRef.current) {
        try {
          const response = await fetch('/api/identity', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'merge_turns', tokens: identityParts }), signal: abortController.signal,
          })
          const merged = await response.json()
          identityToken = response.ok && merged.ok ? merged.evidence_token : undefined
        } catch { identityToken = undefined }
      }
      const identityFrame = captureIdentityFrame()
      if (identityFrame) {
        try {
          const cameraResponse = await fetch('/api/identity', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'attach_camera', identity_token: identityToken, image: identityFrame }),
            signal: AbortSignal.any([abortController.signal, AbortSignal.timeout(250)]),
          })
          const cameraData = await cameraResponse.json()
          if (cameraResponse.ok && cameraData.ok) identityToken = cameraData.evidence_token
          else recordDiagnostic('identity_camera_failed', 'WARN', { reason: cameraData.error || 'Modelo facial indisponível' })
        } catch { recordDiagnostic('identity_camera_failed', 'WARN', { reason: 'Câmera não identificada neste turno' }) }
      }
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userText, mode: 'general', origin: 'voice', session_id: sessionIdRef.current || undefined, identity_token: identityToken }),
        signal: abortController.signal,
      })

      if (!response.ok && response.status !== 404 && response.status !== 501) {
        throw new Error('O pedido por voz falhou. Consulte a execução antes de tentar novamente.')
      }
      if (!response.ok || !response.body) {
        clearPreview()
        handledByChat = true
        const reply = await sendText(userText)
        if (reply) {
          // O chat já gravou a troca no histórico; aqui só falta mostrá-la na ligação.
          handledByChat = true
          fullReply = reply
        }
        if (reply && liveCallActiveRef.current && !abortController.signal.aborted) {
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
        if (abortController.signal.aborted) break

        const lines = eventBuffer.split('\n\n')
        eventBuffer = lines.pop() || ''

        for (const line of lines) {
          const trimmedLine = line.trim()
          if (!trimmedLine.startsWith('data: ')) continue
          const jsonStr = trimmedLine.slice(6)
          try {
            const data = JSON.parse(jsonStr)
            if (typeof data.run_id === 'string') voiceRunId = data.run_id
            if (data.status === 'progress' && data.phase === 'tool_activity' && data.activity) {
              const entry = data.activity as ToolActivityEntry
              if (typeof entry.id !== 'string' || typeof entry.tool !== 'string') continue
              turnActivity = [...turnActivity.filter(previous => previous.id !== entry.id), entry]
              updateLiveTurn(liveTurnId, { activity: turnActivity })
              if (entry.status === 'running' && entry.speech && !announcedActions.has(entry.id)) {
                announcedActions.add(entry.id)
                const text = sanitizeSpeechText(entry.speech)
                if (text && !silentModeRef.current) {
                  audioQueue.push({ text, actionId: entry.id })
                  void playNextInQueue()
                }
              }
            } else if (data.status === 'streaming' && data.chunk) {
              sentenceBuffer += data.chunk
              fullReply += data.chunk
              // Sanitize the complete reply: splitting on periods exposes URL/log fragments to TTS.
            } else if (data.status === 'progress' && typeof data.step === 'number' && typeof data.max_steps === 'number') {
              // Loop agêntico: o contador aparece na linha de status da ligação.
              const phases: Record<string, string> = { planning: 'planejando', acting: 'executando', verifying: 'verificando', waiting_approval: 'aguardando aprovação na Central', resumed: 'retomando' }
              if (!isSpeakingRef.current) setLiveCallStatus(`Etapa ${data.step} de ${data.max_steps} · ${phases[data.phase] || 'processando'}…`)
            } else if (data.status === 'popup' && data.popup) {
              agentContextRef.current?.({ ui_popups: [data.popup] })
            } else if (data.status === 'complete') {
              voiceRunId = data.plan?.context?.run_id || voiceRunId
              turnMeta = data.plan?.context?.access_mode === 'public' ? { access_mode: 'public' } : data.plan?.context?.memory_lookup ? { memory_lookup: data.plan.context.memory_lookup } : undefined
              turnActivity = data.plan?.context?.tool_activity || turnActivity
              updateLiveTurn(liveTurnId, { activity: turnActivity })
              if (data.plan?.context) agentContextRef.current?.(data.plan.context)
              // Respostas que não chegam em pedaços (loop agêntico, atalhos como "crie uma tarefa X", erros do modelo): a resposta inteira vem no plano.
              const summary = typeof data.plan?.summary === 'string' ? data.plan.summary.trim() : ''
              if (summary) fullReply = summary
              const failed = data.plan?.intent === 'error' || data.plan?.context?.success === false
              sentenceBuffer = data.plan?.intent === 'cancelled' ? '' : (data.plan?.context?.speech_summary || (failed ? 'Não consegui concluir o pedido. Os detalhes estão na tela.' : fullReply))
              if (sentenceBuffer.trim()) {
                enqueuePhrase(sentenceBuffer)
                sentenceBuffer = ''
              }
            } else if (data.status === 'error') {
              voiceRunId = data.plan?.context?.run_id || voiceRunId
              turnMeta = data.plan?.context?.access_mode === 'public' ? { access_mode: 'public' } : data.plan?.context?.memory_lookup ? { memory_lookup: data.plan.context.memory_lookup } : undefined
              turnActivity = data.plan?.context?.tool_activity || turnActivity
              // Keep diagnostics visible; only a conversational failure notice goes to speech.
              const rawError = typeof data.error === 'string' && data.error.trim() ? data.error : (typeof data.plan?.summary === 'string' ? data.plan.summary : '')
              const errorMessage = rawError.trim() || 'Não consegui responder agora. Tente de novo.'
              setLiveCallStatus(errorMessage)
              fullReply = fullReply.trim() ? `${fullReply} ${errorMessage}` : errorMessage
              sentenceBuffer = 'Não consegui concluir o pedido. Os detalhes estão na tela.'
              if (sentenceBuffer.trim()) {
                enqueuePhrase(sentenceBuffer)
                sentenceBuffer = ''
              }
            }
            publishPreview()
          } catch {
            /* ignore parse error */
          }
        }
      }

      if (sentenceBuffer.trim() && !abortController.signal.aborted) {
        enqueuePhrase(sentenceBuffer)
      }

      isGeneratingResponse = false

      while ((audioQueue.length > 0 || isPlayingQueue) && liveCallActiveRef.current && !abortController.signal.aborted) {
        await new Promise((r) => setTimeout(r, 60))
      }
    } catch (err: any) {
      if (err?.name !== 'AbortError') {
        setLiveCallStatus(err?.message || 'Falha durante a ligação.')
      }
    } finally {
      isGeneratingResponse = false
      abortController.signal.removeEventListener('abort', cancelVoiceRun)
      abortController.signal.removeEventListener('abort', clearPreview)
      // Só a requisição atual conclui o turno; requisições substituídas não removem o balão compartilhado.
      const turnReply = fullReply.trim()
      const ownsTurn = streamTurnRef.current === streamTurn && !streamTurn.continuing
      if (ownsTurn && turnReply && !abortController.signal.aborted) {
        updateLiveTurn(liveTurnId, { jarvis: turnReply, pending: false })
        if (!handledByChat) {
          try {
            await appendExchangeRef.current?.(turnUser, turnReply, { run_id: voiceRunId || undefined, activity: turnActivity, meta: turnMeta }, previewExchangeRef.current ? liveTurnId : undefined)
          } catch {
            setLiveCallStatus('Não consegui salvar esta resposta no chat.')
          }
        }
      } else if (ownsTurn) {
        removeLiveTurn(liveTurnId)
      }
      clearPreview()
      if (ownsTurn && streamTurnRef.current === streamTurn && !streamTurn.continuing) streamTurnRef.current = null
      if (!abortController.signal.aborted) isSpeakingRef.current = false
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
    preserveStreamTurn()
    captureEpochRef.current += 1
    transcriptionAbortRef.current?.abort()
    lastDispatchedSpeechRef.current?.abort.abort()
    backendDispatchAbortRef.current?.abort()
    const playing = playingPhraseRef.current
    // Approximation only: do not claim the unplayed remainder was heard.
    const fraction = playing && Number.isFinite(playing.audio.duration) && playing.audio.duration > 0
      ? Math.min(1, playing.audio.currentTime / playing.audio.duration) : 0
    const words = playing?.text.split(/\s+/) || []
    const interruptedText = words.slice(0, Math.floor(words.length * fraction)).join(' ')
    playingPhraseRef.current = null
    const previous = lastVoiceRequestRef.current
    lastInterruptionRef.current = { time: Date.now(), text: [
      previous && Date.now() - previous.time < 60000 ? `Pedido anterior: ${previous.text}` : '',
      interruptedText ? `Trecho aproximadamente ouvido: ${interruptedText}` : 'A resposta foi interrompida antes de confirmar o que foi ouvido.',
      'Incorpore o complemento ao pedido. Consulte os resultados anteriores; não repita ações já confirmadas. Não presuma que cancelar desfez ações executadas.',
    ].filter(Boolean).join('\n') }
    if (interruptedText) {
      setLiveJarvisTranscript(`${interruptedText} ✂️ [interrompido]`)
    } else {
      setLiveJarvisTranscript((prev) => (prev ? `${prev} ✂️ [interrompido]` : '[interrompido]'))
    }

    // Notifica backend da interrupção (com o trecho preservado)
    if (sessionIdRef.current) {
      void fetch('/api/call/interrupt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionIdRef.current,
          interrupted_text: interruptedText,
        }),
      }).catch(() => undefined)
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

  const setSilentMode = useCallback((silent: boolean) => {
    silentModeRef.current = silent
    setSilentModeState(silent)
    if (sessionIdRef.current) {
      void fetch('/api/call/silent_mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionIdRef.current, silent }),
      }).catch(() => undefined)
    }
  }, [])

  const toggleSilentMode = useCallback(() => {
    setSilentMode(!silentModeRef.current)
  }, [setSilentMode])

  async function handleVoiceCancellation() {
    clearPendingSpeech()
    discardStreamTurn()
    lastInterruptionRef.current = null
    captureEpochRef.current += 1
    const cancellationEpoch = captureEpochRef.current
    const cancelledRequest = lastVoiceRequestRef.current
    speechRequestRef.current += 1
    transcriptionAbortRef.current?.abort()
    if (liveCallRecorderRef.current?.state === 'recording') liveCallRecorderRef.current.stop()
    // 1. Abort ativo imediato de processamento, streaming e playbacks
    speechAbortRef.current?.abort()
    speechAbortRef.current = null
    lastDispatchedSpeechRef.current?.abort.abort()
    lastDispatchedSpeechRef.current = null
    backendDispatchAbortRef.current?.abort()
    backendDispatchAbortRef.current = null

    // Cancela timers de buffer de silêncio e limpa acumuladores
    if (silenceBufferTimerRef.current !== null) {
      window.clearTimeout(silenceBufferTimerRef.current)
      silenceBufferTimerRef.current = null
    }
    silenceAccumulatedTextRef.current = ''
    pttAccumulatedTextRef.current = ''

    // 2. Interrompe áudio instantaneamente em todos os canais (HTMLAudio, Web Speech, Web Audio)
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      try { window.speechSynthesis.cancel() } catch { /* ignore */ }
    }
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
    if (typeof document !== 'undefined') {
      try {
        document.querySelectorAll('audio').forEach((el) => {
          try {
            el.pause()
            el.currentTime = 0
          } catch { /* ignore */ }
        })
      } catch { /* ignore */ }
    }
    // O AudioContext do VAD é entrada do microfone: suspendê-lo deixa a ligação surda.
    stopNativeSpeak()

    // 3. Reseta estados de processamento
    liveCallProcessingRef.current = false
    isSpeakingRef.current = false
    bargedInRef.current = false
    spokenSentencesRef.current = []

    // 4. Notifica backend /api/call/cancel
    if (sessionIdRef.current) {
      void fetch('/api/call/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionIdRef.current }),
      }).catch(() => undefined)
    }

    // 5. Atualiza UI e emite áudio curto de confirmação
    setLiveOrbState('speaking')
    setLiveCallStatus('Fala interrompida. Verificando o pedido…')
    const cancellation = voiceCancellationRef.current
    voiceCancellationRef.current = null
    const confirmationText = 'Interrompi a fala. ' + (cancellation ? await cancellation : 'Se houver uma tarefa em andamento, confira em Execuções.')
    if (!liveCallActiveRef.current || captureEpochRef.current !== cancellationEpoch || lastVoiceRequestRef.current !== cancelledRequest) return
    setLiveJarvisTranscript(confirmationText)

    try {
      isSpeakingRef.current = true
      await speakText(confirmationText)
    } finally {
      isSpeakingRef.current = false
      if (liveCallActiveRef.current) {
        setLiveOrbState('listening')
        setLiveCallRecording(true)
        setLiveCallStatus('Ouvindo continuamente… fale normalmente.')
        safeRestartLiveRecognition(true)
      }
    }
  }

  function safeRestartLiveRecognition(forceCalibrationPause = false) {
    if (!liveCallActiveRef.current) return
    // A captura do PC e o VAD já estão ouvindo. Iniciar SpeechRecognition aqui
    // duplicaria transcrições depois de um cancelamento ou de uma resposta.
    if (backendCaptureRef.current || fallbackListeningRef.current || nativeCallActiveRef.current) return

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
      if (liveCallActiveRef.current && !backendCaptureRef.current && !fallbackListeningRef.current && !nativeCallActiveRef.current && !pushToTalkModeRef.current) {
        startBrowserLiveRecognition()
      }
    }, delay)
  }

  const dispatchFinalSpeech = (cleanText: string, wasBargedIn = false, settled = false, alreadyCombined = false) => {
    if (!cleanText || !liveCallActiveRef.current) return
    if (divertToDictation(cleanText)) return

    if (isCancelCommand(cleanText)) {
      void handleVoiceCancellation()
      return
    }
    previewContinuation(cleanText, alreadyCombined)
    if (!settled && bufferSpeech(cleanText, text => { void dispatchFinalSpeech(text, wasBargedIn, true, alreadyCombined) })) return

    const silenceCheck = detectSilenceCommand(cleanText)
    if (silenceCheck.isCommand) {
      setSilentMode(silenceCheck.enableSilence)
      const isPureSilence = /^(?:n[aã]o\s+precisa\s+(?:narrar|falar(?:\s+nada)?(?:\s+enquanto\s+pesquisa)?)|pesquis(?:e|a)\s+em\s+sil[eê]ncio|pesquis(?:e|a)\s+sem\s+falar(?:\s+nada)?|modo\s+silencioso|ativ(?:e|ar)\s+(?:o\s+)?modo\s+silencioso|fiqu?e\s+em\s+sil[eê]ncio|sem\s+narrar|pode\s+(?:narrar|falar)|desativ(?:e|ar)\s+(?:o\s+)?modo\s+silencioso|sa(?:i|ia)\s+do\s+modo\s+silencioso|desativ(?:e|ar)\s+sil[eê]ncio)[.!]?$/i.test(cleanText.replace(/[^\w\s]/g, '').trim())
      if (isPureSilence) {
        const confirmMsg = silenceCheck.enableSilence ? 'Modo silencioso ativado. Vou pesquisar em silêncio.' : 'Narração ativada.'
        setLiveOrbState('speaking')
        setLiveCallStatus(confirmMsg)
        setLiveJarvisTranscript(confirmMsg)
        void (async () => {
          try {
            isSpeakingRef.current = true
            await speakText(confirmMsg)
          } finally {
            isSpeakingRef.current = false
            liveCallProcessingRef.current = false
            if (liveCallActiveRef.current) {
              setLiveOrbState('listening')
              setLiveCallRecording(true)
              setLiveCallStatus('Ouvindo continuamente… fale normalmente.')
              safeRestartLiveRecognition(true)
            }
          }
        })()
        return
      }
    }

    // Limpa janela de correção anterior se houver
    if (correctionWindowTimerRef.current !== null) {
      window.clearTimeout(correctionWindowTimerRef.current)
      correctionWindowTimerRef.current = null
    }

    if (liveCallProcessingRef.current && !wasBargedIn) {
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

    // Janela de correção após o envio.
    correctionWindowTimerRef.current = window.setTimeout(() => {
      correctionWindowTimerRef.current = null
      if (lastDispatchedSpeechRef.current && !lastDispatchedSpeechRef.current.isCancelled) {
        lastDispatchedSpeechRef.current = null
      }
    }, SILENCE_BUFFER_MS)

    return (async () => {
      try {
        let prompt = cleanText
        if (lastInterruptionRef.current?.text) {
          const cutOff = lastInterruptionRef.current.text
          lastInterruptionRef.current = null
          prompt = buildContextStitchingPrompt(cutOff, cleanText)
        }
        if (!dispatchAbort.signal.aborted) {
          lastVoiceRequestRef.current = { text: cleanText, time: Date.now() }
          await sendTextStreamAndPlay(prompt, cleanText, dispatchAbort, alreadyCombined)
        }
      } catch (error) {
        if (!dispatchAbort.signal.aborted) {
          setLiveCallStatus(error instanceof Error ? error.message : 'Falha durante a ligação.')
        }
      } finally {
        if (!dispatchAbort.signal.aborted) {
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

  const startBrowserLiveRecognition = () => {
    const browserWindow = window as Window & { SpeechRecognition?: any; webkitSpeechRecognition?: any }
    const Recognition = browserWindow.SpeechRecognition || browserWindow.webkitSpeechRecognition
    if (!Recognition) return false
    if (recognitionAliveRef.current && liveRecognitionRef.current) return true // já rodando
    const recognition = createMicrophoneRecognition(Recognition)
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
      identityEvidenceRef.current = undefined
      identityPartsRef.current = []
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
      if (heardSpeech) pausePendingSpeech()

      const dictationSink = liveDictationBus.sink()
      if (dictationSink && liveCallActiveRef.current) {
        dictationSink.onInterim(finalText.trim() ? '' : interimText.trim())
        if (finalText.trim()) divertToDictation(finalText.trim())
        return
      }

      // ⚡ CANCELAMENTO ATIVO POR VOZ (Interim ou Final)
      if (heardSpeech && isCancelCommand(heardSpeech)) {
        if (liveCallProcessingRef.current || isSpeakingRef.current || (audioRef.current && !audioRef.current.paused) || lastDispatchedSpeechRef.current) {
          void handleVoiceCancellation()
          return
        }
      }

      // Modo Push-to-Talk ativo: grava enquanto segurado e envia apenas ao soltar
      if (pushToTalkModeRef.current) {
        if (!isPttActiveRef.current) return
        if (finalText.trim()) {
          pttAccumulatedTextRef.current = (pttAccumulatedTextRef.current + ' ' + finalText.trim()).trim()
        }
        const fullTranscript = (pttAccumulatedTextRef.current + (interimText ? ' ' + interimText : '')).trim()
        if (fullTranscript) { setLiveUserTranscript(fullTranscript); previewContinuation(fullTranscript) }
        setLiveOrbState('listening')
        setLiveCallStatus('🎙️ Ouvindo sua fala… solte o botão para enviar.')
        return
      }

      const prevDispatch = lastDispatchedSpeechRef.current

      // ── VERIFICAÇÃO EM PARALELO DE CONTINUAÇÃO (ZERO DELAY) ─────────────
      if (prevDispatch && !prevDispatch.isCancelled) {
        const elapsed = Date.now() - prevDispatch.timestamp
        if (elapsed <= SILENCE_BUFFER_MS && heardSpeech.length >= 1) {
          prevDispatch.isCancelled = true
          preserveStreamTurn()
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
          previewContinuation(`${prevDispatch.text} ${continuationText}`.trim(), true)
          setLiveJarvisTranscript('')
          setLiveOrbState('listening')
          setLiveCallStatus('Completando frase…')
        }
      } else if (prevDispatch && prevDispatch.isCancelled && interimText.trim()) {
        setLiveUserTranscript(`${prevDispatch.text} ${interimText.trim()}`.trim())
        previewContinuation(`${prevDispatch.text} ${interimText.trim()}`.trim(), true)
      }

      // ⚡ BARGE-IN: detecta fala do usuário enquanto Jarvis está falando
      if ((isSpeakingRef.current || (audioRef.current && !audioRef.current.paused)) && (!prevDispatch || !prevDispatch.isCancelled)) {
        if (heardSpeech.length >= 2 && !bargedInRef.current) {
          triggerBargeIn()
        }
      }

      // Reset do buffer de silêncio se o usuário continuar formulando/falando
      if (silenceBufferTimerRef.current !== null && heardSpeech) {
        window.clearTimeout(silenceBufferTimerRef.current)
        silenceBufferTimerRef.current = null
      }

      const currentFormulation = (silenceAccumulatedTextRef.current + ' ' + heardSpeech).trim()
      if (currentFormulation && !prevDispatch?.isCancelled) {
        setLiveUserTranscript(currentFormulation)
        previewContinuation(currentFormulation)
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
        dispatchFinalSpeech(mergedText, false, false, true)
        return
      }

      // Caso 2: Chegou uma frase final rápida dentro da janela de pausa:
      if (prevDispatch && !prevDispatch.isCancelled && (Date.now() - prevDispatch.timestamp <= SILENCE_BUFFER_MS) && !wasBargedIn) {
        prevDispatch.isCancelled = true
        preserveStreamTurn()
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
        dispatchFinalSpeech(mergedText, false, false, true)
        return
      }

      // Acumula também frases aparentemente completas durante pausas de formulação.
      silenceAccumulatedTextRef.current = (silenceAccumulatedTextRef.current + ' ' + newText).trim()
      setLiveOrbState('listening')
      setLiveCallStatus('Ouvindo… formule sua frase com calma.')

      if (silenceBufferTimerRef.current !== null) {
        window.clearTimeout(silenceBufferTimerRef.current)
      }
      silenceBufferTimerRef.current = window.setTimeout(() => {
        silenceBufferTimerRef.current = null
        const completeSpeech = silenceAccumulatedTextRef.current.trim()
        silenceAccumulatedTextRef.current = ''
        if (completeSpeech && liveCallActiveRef.current) {
          dispatchFinalSpeech(completeSpeech, wasBargedIn)
        }
      }, SILENCE_BUFFER_MS)
    }
    recognition.onerror = (event: any) => {
      recognitionAliveRef.current = false
      if (!liveCallActiveRef.current) return
      if (event?.error === 'not-allowed' || event?.error === 'service-not-allowed') {
        recordDiagnostic('browser_recognition_permission_denied', 'ERROR', { error: event?.error || 'unknown' })
        liveCallActiveRef.current = false
        setLiveCallRecording(false)
        setLiveOrbState('idle')
        setLiveCallStatus(event?.message || 'Permissão de microfone negada. Verifique as configurações.')
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
      // Não bloqueia reinício mesmo se Jarvis estiver falando,
      // para que o microfone permaneça ouvindo e capture comandos como 'cancela' ou 'para'
      if (postSpeechRestartTimerRef.current !== null) {
        window.clearTimeout(postSpeechRestartTimerRef.current)
      }
      const restartDelay = isSpeakingRef.current ? 120 : 200
      postSpeechRestartTimerRef.current = window.setTimeout(() => {
        postSpeechRestartTimerRef.current = null
        if (liveCallActiveRef.current && !recognitionAliveRef.current) {
          startBrowserLiveRecognition()
        }
      }, restartDelay)
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
    const captureEpoch = captureSessionRef.current
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      liveCallActiveRef.current = false
      setLiveCallStatus('Microfone não suportado neste navegador.')
      return
    }
    try {
      const stream = await openMicrophone({ echoCancellation: true, noiseSuppression: true, autoGainControl: true })
      if (!liveCallActiveRef.current || captureEpoch !== captureSessionRef.current) { stream.getTracks().forEach(track => track.stop()); return }
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
      setLiveAudioDiagnostics({ mode: 'fallback-vad', rms: 0, threshold: 0.012, noiseFloor: fallbackNoiseFloorRef.current, note: captureNoteRef.current || undefined })

      // Sensibilidade, silêncio para encerrar a fala e ganho vêm de Configurações (/api/settings/mic).
      let mic = { sensitivity: 75, silence_ms: 800, gain: 1 }
      try {
        const micResponse = await fetch('/api/settings/mic')
        if (micResponse.ok) mic = { ...mic, ...(await micResponse.json()) }
      } catch { /* mantém os padrões */ }
      if (!liveCallActiveRef.current || captureEpoch !== captureSessionRef.current) return
      const thresholdFloor = 0.03 - 0.026 * (mic.sensitivity / 100)
      const noiseMultiplier = 3.5 - 1.5 * (mic.sensitivity / 100)

      const data = new Uint8Array(analyser.fftSize)
      const startUtterance = () => {
        if (!liveCallActiveRef.current || liveCallProcessingRef.current || liveCallRecorderRef.current?.state === 'recording') return
        pausePendingSpeech()
        const turnEpoch = captureEpochRef.current
        const chunks: BlobPart[] = []
        const options = pickRecorderOptions()
        const recorder = new MediaRecorder(stream, options)
        const turnId = newVoiceTurnId()
        voiceTurnIdRef.current = turnId
        liveSpeakerRef.current = {}
        identityEvidenceRef.current = undefined
        const turnStartedAt = performance.now()
        recordDiagnostic('voice_turn_started', 'INFO', { turn_id: turnId, session_id: sessionId || 'unknown', capture_mode: 'fallback-vad' })
        liveCallRecorderRef.current = recorder
        recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data) }
        recorder.onstop = async () => {
          if (liveCallRecorderRef.current === recorder) liveCallRecorderRef.current = null
          const audio = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' })
          if (!liveCallActiveRef.current || turnEpoch !== captureEpochRef.current || audio.size < 500) return
          const abort = new AbortController()
          transcriptionAbortRef.current = abort
          liveCallProcessingRef.current = true
          setLiveCallRecording(false)
          try {
            setLiveCallStatus('Transcrevendo…')
            if (isMobileStandalone()) {
              const text = (await transcribeMobileAudio(audio)).trim()
              if (abort.signal.aborted || turnEpoch !== captureEpochRef.current) return
              if (isCancelCommand(text)) {
                void handleVoiceCancellation()
                return
              }
              const silenceCheck = detectSilenceCommand(text)
              if (silenceCheck.isCommand) {
                setSilentMode(silenceCheck.enableSilence)
              }
              liveCallSttFailureCountRef.current = 0
              liveCallProcessingRef.current = false
              await dispatchFinalSpeech(text)
              return
            }
            const stt = await fetch('/api/voice/stt', {
              method: 'POST',
              headers: { 'Content-Type': audio.type, 'X-Jarvis-Identify-Speaker': speakerIdentificationEnabledRef.current ? '1' : '0', 'X-Jarvis-Turn-ID': turnId, 'X-Jarvis-Session-ID': sessionId || '' },
              body: audio,
              signal: abort.signal,
            })
            const transcription = await stt.json()
            if (abort.signal.aborted || turnEpoch !== captureEpochRef.current) return
            if (!stt.ok || !transcription.ok || !transcription.text) throw new Error(transcription.error || 'Não foi possível entender o áudio.')
            const speaker = transcription.speaker
            acceptSpeakerEvidence(speaker?.evidence_token)
            if (speakerIdentificationEnabledRef.current && speaker?.enabled) {
              liveSpeakerRef.current = speaker.matched && !speaker.requires_confirmation
                ? { name: speaker.profile?.name, confidence: speaker.confidence }
                : speaker.segments?.length ? { name: speaker.segments.map((part: { speaker_name?: string }) => part.speaker_name || 'Voz desconhecida').join(' → ') }
                : { confidence: speaker.confidence, unknown: true }
              setLiveAudioDiagnostics(previous => previous ? { ...previous, speakerName: liveSpeakerRef.current.name, speakerConfidence: speaker.confidence, speakerUnknown: liveSpeakerRef.current.unknown } : previous)
              recordDiagnostic(speaker.matched ? 'voice_speaker_recognized' : 'voice_speaker_unknown', 'INFO', { turn_id: turnId, confidence: speaker.confidence || 0 })
            }
            liveCallSttFailureCountRef.current = 0
            recordDiagnostic('voice_turn_stt_completed', 'INFO', { turn_id: turnId, elapsed_ms: Math.round(performance.now() - turnStartedAt) })
            const heardText = transcription.text.trim()
            if (isCancelCommand(heardText)) {
              void handleVoiceCancellation()
              return
            }
            const silenceCheck = detectSilenceCommand(heardText)
            if (silenceCheck.isCommand) {
              setSilentMode(silenceCheck.enableSilence)
            }
            liveCallProcessingRef.current = false
            await dispatchFinalSpeech(heardText)
          } catch (error) {
            if (abort.signal.aborted || turnEpoch !== captureEpochRef.current) return
            if (pendingSpeechRef.current) bufferSpeech('', pendingSpeechRef.current.send, true)
            liveCallSttFailureCountRef.current += 1
            const message = error instanceof Error ? error.message : 'Falha durante a ligação.'
            recordDiagnostic('fallback_stt_failed', 'ERROR', { turn_id: turnId, attempt: liveCallSttFailureCountRef.current, message, elapsed_ms: Math.round(performance.now() - turnStartedAt) })
            setLiveCallStatus(`${message} Continuo ouvindo quando você tentar novamente.`)
          } finally {
            if (transcriptionAbortRef.current === abort) transcriptionAbortRef.current = null
            if (turnEpoch !== captureEpochRef.current) return
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
      startPttRecordingRef.current = startUtterance
      if (pushToTalkModeRef.current && isPttActiveRef.current) startUtterance()

      let bargeStarted: number | null = null
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
          setLiveAudioDiagnostics({ mode: 'fallback-vad', rms, threshold, noiseFloor: fallbackNoiseFloorRef.current, note: captureNoteRef.current || undefined, turnId: voiceTurnIdRef.current || undefined, speakerName: liveSpeakerRef.current.name, speakerConfidence: liveSpeakerRef.current.confidence, speakerUnknown: liveSpeakerRef.current.unknown })
        }
        const recordingNow = liveCallRecorderRef.current?.state === 'recording'
        if (!pushToTalkModeRef.current && isSpeakingRef.current && rms > threshold * 2.5) {
          bargeStarted ??= performance.now()
          if (performance.now() - bargeStarted >= 250) {
            triggerBargeIn()
            startUtterance()
            bargeStarted = null
          }
        } else { bargeStarted = null }
        if (pushToTalkModeRef.current && !isPttActiveRef.current && !recordingNow) {
          fallbackAnimationFrameRef.current = window.requestAnimationFrame(monitor)
          return
        }
        if (pushToTalkModeRef.current) {
          // PTT termina somente na soltura, mesmo com pausas longas durante a fala.
          if (isPttActiveRef.current && !recordingNow) startUtterance()
        } else if (!isSpeakingRef.current && !liveCallProcessingRef.current && rms >= threshold) {
          if (!recordingNow) startUtterance()
          fallbackSilenceStartedAtRef.current = null
        } else if (recordingNow) {
          if (fallbackSilenceStartedAtRef.current === null) fallbackSilenceStartedAtRef.current = performance.now()
          if (performance.now() - fallbackSilenceStartedAtRef.current >= Math.max(mic.silence_ms, SILENCE_BUFFER_MS)) liveCallRecorderRef.current?.stop()
        }
        fallbackAnimationFrameRef.current = window.requestAnimationFrame(monitor)
      }
      monitor()
    } catch (error) {
      if (captureEpoch !== captureSessionRef.current) return
      liveCallActiveRef.current = false
      recordDiagnostic('fallback_microphone_unavailable', 'ERROR', { error: error instanceof Error ? error.name : 'unknown' })
      setLiveCallStatus(error instanceof Error ? error.message : 'Não consegui acessar o microfone. Verifique a permissão.')
    }
  }

  // ── Captura de fala pelo backend (SpeechRecognition + PyAudio no PC) ─────────────────────────
  const stopBackendCapture = () => {
    const handle = backendCaptureRef.current
    if (!handle) return
    handle.cancelled = true
    handle.abort.abort()
    window.clearInterval(handle.playbackTimer)
    backendCaptureRef.current = null
    backendDispatchAbortRef.current?.abort()
    backendDispatchAbortRef.current = null
    void postCapture('stop').catch(() => undefined)
  }

  const handleBackendLost = (reason: string) => {
    if (!backendCaptureRef.current) return
    stopBackendCapture()
    recordDiagnostic('backend_capture_lost', 'WARN', { reason })
    if (!liveCallActiveRef.current) return
    captureNoteRef.current = reason
    setLiveCallStatus(`${reason} Usando o microfone do navegador.`)
    void startFallbackContinuousCapture()
  }

  const dispatchBackendSpeech = (text: string, settled = false) => {
    if (!text || !liveCallActiveRef.current) return
    if (divertToDictation(text)) return
    if (isCancelCommand(text)) {
      void handleVoiceCancellation()
      return
    }
    if (!settled && bufferSpeech(text, complete => dispatchBackendSpeech(complete, true), true)) return
    const silenceCheck = detectSilenceCommand(text)
    if (silenceCheck.isCommand) {
      setSilentMode(silenceCheck.enableSilence)
      const isPureSilence = /^(?:n[aã]o\s+precisa\s+(?:narrar|falar(?:\s+nada)?(?:\s+enquanto\s+pesquisa)?)|pesquis(?:e|a)\s+em\s+sil[eê]ncio|pesquis(?:e|a)\s+sem\s+falar(?:\s+nada)?|modo\s+silencioso|ativ(?:e|ar)\s+(?:o\s+)?modo\s+silencioso|fiqu?e\s+em\s+sil[eê]ncio|sem\s+narrar|pode\s+(?:narrar|falar)|desativ(?:e|ar)\s+(?:o\s+)?modo\s+silencioso|sa(?:i|ia)\s+do\s+modo\s+silencioso|desativ(?:e|ar)\s+sil[eê]ncio)[.!]?$/i.test(text.replace(/[^\w\s]/g, '').trim())
      if (isPureSilence) {
        const msg = silenceCheck.enableSilence ? 'Modo silencioso ativado. Vou pesquisar em silêncio.' : 'Narração ativada.'
        setLiveCallStatus(msg)
        void speakText(msg)
        return
      }
    }
    const wasBargedIn = bargedInRef.current
    bargedInRef.current = false
    // Uma fala nova substitui qualquer resposta ainda em andamento.
    if (backendDispatchAbortRef.current) backendDispatchAbortRef.current.abort()
    if (liveCallProcessingRef.current && !wasBargedIn) {
      speechAbortRef.current?.abort()
      isSpeakingRef.current = false
      recordDiagnostic('speech_replaced_while_processing', 'WARN')
    }
    liveCallProcessingRef.current = true
    const dispatchAbort = new AbortController()
    backendDispatchAbortRef.current = dispatchAbort
    setLiveCallRecording(false)
    setLiveUserTranscript(text)
    void (async () => {
      try {
        let prompt = text
        if (lastInterruptionRef.current?.text) {
          const cutOff = lastInterruptionRef.current.text
          lastInterruptionRef.current = null
          prompt = buildContextStitchingPrompt(cutOff, text)
        }
        lastVoiceRequestRef.current = { text, time: Date.now() }
        await sendTextStreamAndPlay(prompt, text, dispatchAbort)
      } catch (error) {
        if (!dispatchAbort.signal.aborted) setLiveCallStatus(error instanceof Error ? error.message : 'Falha durante a ligação.')
      } finally {
        if (!dispatchAbort.signal.aborted) {
          liveCallProcessingRef.current = false
          isSpeakingRef.current = false
          bargedInRef.current = false
          if (backendDispatchAbortRef.current === dispatchAbort) backendDispatchAbortRef.current = null
        }
      }
    })()
  }

  const handleBackendEvent = (handle: BackendCapture, event: Record<string, any>) => {
    if (handle.cancelled || !liveCallActiveRef.current) return
    switch (event.type) {
      case 'level': {
        const now = performance.now()
        if (now - handle.lastLevelAt < 150) return
        handle.lastLevelAt = now
        setLiveAudioDiagnostics(previous => ({ ...(previous?.mode === 'backend-sr' ? previous : {}), mode: 'backend-sr', rms: event.level, threshold: event.threshold, note: captureNoteRef.current || undefined }))
        return
      }
      case 'calibrated':
        setLiveCallStatus(`Microfone do PC calibrado (limiar ${event.threshold}).`)
        return
      case 'state':
        handle.speaking = event.state === 'speaking'
        if (event.state === 'speaking') pausePendingSpeech()
        if (event.state === 'speaking' && liveCallProcessingRef.current && !isSpeakingRef.current) triggerBargeIn()
        else if (!handle.speaking && !handle.awaitingEnd && !handle.turns.length && pendingSpeechRef.current?.timer == null && pendingSpeechRef.current) bufferSpeech('', pendingSpeechRef.current.send, true)
        if (event.state === 'speaking' && !isSpeakingRef.current) {
          setLiveCallStatus('Ouvindo sua fala…')
        } else if (event.state === 'listening' && !isSpeakingRef.current && !liveCallProcessingRef.current) {
          setLiveOrbState('listening')
          setLiveCallRecording(true)
          setLiveCallStatus('Ouvindo continuamente… fale normalmente.')
        }
        return
      case 'processing':
        if (event.turn_id) handle.turns.push({ id: String(event.turn_id) })
        pausePendingSpeech()
        if (!isSpeakingRef.current) setLiveCallStatus('Transcrevendo…')
        return
      case 'barge_in':
        if (isSpeakingRef.current || liveCallProcessingRef.current || audioRef.current) triggerBargeIn()
        return
      case 'detector_warning':
        captureNoteRef.current = String(event.message || 'Detector neural indisponível; usando escuta simples.')
        setLiveCallStatus(captureNoteRef.current)
        return
      case 'turn_prediction':
        if (event.probability < 0.8 && !isSpeakingRef.current) setLiveCallStatus('Ouvindo… pode continuar seu pensamento.')
        return
      case 'turn_end':
      case 'transcript':
      case 'empty': {
        const turn = handle.turns.find(item => item.id === String(event.turn_id))
        if (turn) turn.result = event
        else handle.turns.push({ id: String(event.turn_id), result: event })
        // STT requests can finish out of order; retain the user's capture order.
        while (handle.turns[0]?.result) {
          const result = handle.turns.shift()!.result!
          if (result.type === 'turn_end') {
            handle.awaitingEnd = false
            if (pendingSpeechRef.current) bufferSpeech('', pendingSpeechRef.current.send, true, 0)
          } else if (result.type === 'transcript') acceptBackendTranscript(result, handle)
          else {
            if (pendingSpeechRef.current) bufferSpeech('', pendingSpeechRef.current.send, true)
            if (result.error && !/descartad/i.test(String(result.error))) setLiveCallStatus(String(result.error))
          }
        }
        if (handle.speaking || handle.turns.length || handle.awaitingEnd) pausePendingSpeech()
        return
      }
      case 'error':
        if (event.fatal) handleBackendLost(String(event.message || 'Falha no microfone do PC.'))
        return
    }
  }

  const acceptBackendTranscript = (event: Record<string, any>, handle: BackendCapture) => {
    const speaker = event.speaker
    acceptSpeakerEvidence(speaker?.evidence_token)
    liveSpeakerRef.current = speakerIdentificationEnabledRef.current && speaker?.matched && !speaker.requires_confirmation
      ? { name: speaker.profile?.name, confidence: speaker.confidence }
      : speakerIdentificationEnabledRef.current && speaker?.segments?.length ? { name: speaker.segments.map((part: { speaker_name?: string }) => part.speaker_name || 'Voz desconhecida').join(' → ') }
      : { unknown: true }
    setLiveAudioDiagnostics(previous => previous ? { ...previous, speakerName: liveSpeakerRef.current.name, speakerConfidence: liveSpeakerRef.current.confidence, speakerUnknown: liveSpeakerRef.current.unknown } : previous)
    setLiveAudioDiagnostics(previous => previous ? { ...previous, sttMs: event.stt_ms, turnId: event.turn_id } : previous)
    recordDiagnostic('backend_turn_transcribed', 'INFO', { turn_id: event.turn_id, stt_ms: event.stt_ms })
    if (pushToTalkModeRef.current) return // PTT descarta segmentos tardios do PC.
    const text = String(event.text || '').trim()
    if (isCancelCommand(text)) { void handleVoiceCancellation(); return }
    if (divertToDictation(text)) return
    if (event.semantic || event.turn_complete === false) {
      handle.awaitingEnd = event.turn_complete === false
      // The backend already waited for a confident end; only coalesce queued events.
      bufferSpeech(text, complete => dispatchBackendSpeech(complete, true), true, 0)
      if (handle.awaitingEnd) pausePendingSpeech()
    } else dispatchBackendSpeech(text)
  }

  const runBackendEvents = async (handle: BackendCapture, startSeq: number) => {
    let after = startSeq
    let failures = 0
    while (!handle.cancelled) {
      try {
        const response = await fetch(`/api/voice/capture/events?after=${after}&wait=1`, { signal: handle.abort.signal })
        if (!response.ok) throw new Error(String(response.status))
        const data = await response.json()
        failures = 0
        after = Number(data.seq) || after
        for (const event of data.events || []) handleBackendEvent(handle, event)
        if (!data.active && !handle.cancelled) { handleBackendLost('O microfone do PC foi encerrado.'); return }
      } catch {
        if (handle.cancelled) return
        failures += 1
        if (failures >= 5) { handleBackendLost('Perdi a conexão com a captura do PC.'); return }
        await new Promise(resolve => window.setTimeout(resolve, 400))
      }
    }
  }

  // Tenta o motor do PC. ok=false com reason => cai no navegador e mostra o motivo.
  const startBackendCapture = async (): Promise<{ ok: boolean; reason?: string }> => {
    const epoch = captureSessionRef.current
    if (isMobileStandalone() || !LOOPBACK_HOSTS.includes(window.location.hostname)) return { ok: false }
    let engine = 'auto'
    try {
      const micResponse = await fetch('/api/settings/mic')
      if (micResponse.ok) engine = (await micResponse.json()).engine || 'auto'
    } catch { /* usa automático */ }
    if (engine === 'browser') return { ok: false }
    try {
      const status = await (await fetch('/api/voice/capture/status')).json()
      if (!status.available) return { ok: false, reason: status.reason || 'Captura do PC indisponível.' }
    } catch {
      return { ok: false, reason: 'O backend não respondeu sobre o microfone do PC.' }
    }
    setLiveCallStatus('Abrindo e calibrando o microfone do PC…')
    let started: Record<string, any> = {}
    try { started = await postCapture('start', { silence_ms: SILENCE_BUFFER_MS, semantic_turns: true, identify_speakers: speakerIdentificationEnabledRef.current }) } catch { return { ok: false, reason: 'Não foi possível iniciar a captura do PC.' } }
    if (!started.ok) return { ok: false, reason: started.error || 'Não foi possível abrir o microfone do PC.' }
    if (!liveCallActiveRef.current || epoch !== captureSessionRef.current || pushToTalkModeRef.current) { void postCapture('stop').catch(() => undefined); return { ok: true } }
    if (started.turn_detector_warning) captureNoteRef.current = 'Detector neural indisponível; usando escuta simples.'
    else captureNoteRef.current = started.turn_detector === 'smart-turn-v3.2' ? 'Silero VAD + Smart Turn local' : ''
    const handle: BackendCapture = { cancelled: false, abort: new AbortController(), playbackTimer: 0, lastPlayback: false, lastLevelAt: 0, speaking: false, awaitingEnd: false, turns: [] }
    // O microfone do Python não cancela eco: o backend sobe o limiar enquanto o Jarvis fala (barge-in só com voz alta e contínua).
    handle.playbackTimer = window.setInterval(() => {
      const speaking = Boolean(isSpeakingRef.current || (audioRef.current && !audioRef.current.paused))
      if (speaking !== handle.lastPlayback) {
        handle.lastPlayback = speaking
        void postCapture('playback', { active: speaking }).catch(() => undefined)
      }
    }, 80)
    backendCaptureRef.current = handle
    captureNoteRef.current = ''
    setLiveAudioDiagnostics({ mode: 'backend-sr', rms: 0, threshold: started.threshold })
    setLiveCallRecording(true)
    setLiveOrbState('listening')
    setLiveCallStatus('Ouvindo continuamente… fale normalmente.')
    recordDiagnostic('backend_capture_started', 'INFO', { threshold: started.threshold })
    void runBackendEvents(handle, Number(started.seq) || 0)
    return { ok: true }
  }

  useEffect(() => {
    const onPageHide = () => {
      if (backendCaptureRef.current) navigator.sendBeacon?.('/api/voice/capture/stop', new Blob(['{}'], { type: 'application/json' }))
    }
    window.addEventListener('pagehide', onPageHide)
    return () => { window.removeEventListener('pagehide', onPageHide); stopLiveCall() }
  }, [])

  const toggleLiveCallCapture = async () => {
    if (enrollmentActiveRef.current) return
    if (liveCallActiveRef.current) {
      stopLiveCall(true)
      setLiveOrbState('idle')
      setLiveCallStatus('Ligação pausada. Toque para retomar.')
      return
    }
    liveCallActiveRef.current = true
    if (pushToTalkModeRef.current) {
      captureNoteRef.current = 'Push-to-Talk: áudio do navegador enviado somente ao soltar.'
      await startFallbackContinuousCapture()
      return
    }
    if ((isMobileStandalone() || pairedAndroid) && hasNativeVoice() && !(await loadMicrophone()).device_name) {
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
    // No PC (mesma máquina do backend) a fala é detectada pelo Python (SpeechRecognition + PyAudio), como no projeto antigo.
    // Sem PyAudio/SpeechRecognition, ou em outro aparelho, usa o VAD do navegador e mostra o motivo.
    const backend = await startBackendCapture()
    if (backend.ok) return
    captureNoteRef.current = backend.reason || ''
    await startFallbackContinuousCapture()
  }

  useEffect(() => {
    const enrollment = (event: Event) => {
      const active = Boolean((event as CustomEvent<boolean>).detail)
      if (active === enrollmentActiveRef.current) return
      enrollmentActiveRef.current = active
      if (active) {
        resumeAfterEnrollment.current = liveCallActiveRef.current
        if (liveCallActiveRef.current) stopLiveCall(true)
        setLiveOrbState('idle')
        setLiveCallStatus('O cadastro está usando o microfone. Responda às instruções na tela.')
      } else {
        const resume = resumeAfterEnrollment.current
        resumeAfterEnrollment.current = false
        if (resume && callOpenRef.current) void toggleLiveCallCapture()
      }
    }
    window.addEventListener('jarvis-enrollment-active', enrollment)
    return () => window.removeEventListener('jarvis-enrollment-active', enrollment)
  }, [])

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
    if (pairedAndroid) return
    setSpeakerIdentificationEnabledState(enabled)
    speakerIdentificationEnabledRef.current = enabled
    identityEvidenceRef.current = undefined
    identityPartsRef.current = []
    liveSpeakerRef.current = { unknown: true }
    setLiveAudioDiagnostics(previous => previous ? { ...previous, speakerName: undefined, speakerConfidence: undefined, speakerUnknown: true } : previous)
    void postCapture('identity', { enabled }).catch(() => recordDiagnostic('speaker_preference_failed', 'WARN'))
    try { localStorage.setItem(SPEAKER_IDENTIFICATION_STORAGE_KEY, enabled ? '1' : '0') } catch { /* ignore storage errors */ }
  }, [])

  useEffect(() => {
    const changed = (event: Event) => setSpeakerIdentificationEnabled((event as CustomEvent<boolean>).detail)
    window.addEventListener('jarvis-speaker-preference', changed)
    return () => window.removeEventListener('jarvis-speaker-preference', changed)
  }, [setSpeakerIdentificationEnabled])

  useEffect(() => {
    const abort = new AbortController()
    if (pairedAndroid) return
    // Existing enrollment is consent to recognition; preserve an explicit off preference.
    void fetch('/api/identity', { signal: abort.signal }).then(async response => {
      if (!response.ok) return
      const data = await response.json()
      if (!abort.signal.aborted && localStorage.getItem(SPEAKER_IDENTIFICATION_STORAGE_KEY) === null
        && data.profiles?.some((profile: { voice_samples?: number }) => (profile.voice_samples || 0) > 0)) setSpeakerIdentificationEnabled(true)
    }).catch(() => undefined)
    return () => abort.abort()
  }, [setSpeakerIdentificationEnabled])

  async function speakText(text: string) {
    if (!text || !speakEnabled) return
    const sanitized = sanitizeSpeechText(text)
    if (!sanitized) return
    const requestId = ++speechRequestRef.current
    speechAbortRef.current?.abort()
    const abortController = new AbortController()
    speechAbortRef.current = abortController
    if (isMobileStandalone() && hasNativeVoice()) {
      setLiveJarvisTranscript(sanitized)
      await new Promise<void>(resolve => {
        let settled = false
        let timer: number | undefined
        const finish = () => {
          if (settled) return
          settled = true
          window.clearTimeout(timer)
          abortController.signal.removeEventListener('abort', finish)
          ttsDoneResolverRef.current = null
          resolve()
        }
        ttsDoneResolverRef.current = finish
        abortController.signal.addEventListener('abort', finish, { once: true })
        nativeSpeak(sanitized)
        const timeout = Math.min(24000, 600 + sanitized.length * 70)
        timer = window.setTimeout(finish, timeout)
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
      const request = { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: sanitized }), signal: abortController.signal }
      const streamResponse = await fetch('/api/voice/tts/stream', request)
      if (streamResponse.ok) {
        const streamed = await createStreamingAudio(streamResponse)
        if (streamed) {
          if (requestId !== speechRequestRef.current) { URL.revokeObjectURL(streamed.url); return }
          url = streamed.url
          audioUrlRef.current = url
          audioRef.current = streamed.audio
          await playAudioToEnd(streamed.audio, abortController.signal)
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
      const audio = createAgentAudio(url)
      audioRef.current = audio
      await playAudioToEnd(audio, abortController.signal)
    } catch (error) {
      if (!abortController.signal.aborted) setAnswer(error instanceof Error ? error.message : 'Falha ao gerar áudio.')
    } finally {
      if (url) URL.revokeObjectURL(url)
      if (requestId === speechRequestRef.current) {
        audioUrlRef.current = null
        audioRef.current = null
      }
      if (speechAbortRef.current === abortController) speechAbortRef.current = null
    }
  }

  useEffect(() => {
    if (!isMobileStandalone() && !pairedAndroid) return undefined
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
        if (isCancelCommand(spoken)) {
          void handleVoiceCancellation()
          return
        }
        const silenceCheck = detectSilenceCommand(spoken)
        if (silenceCheck.isCommand) {
          setSilentMode(silenceCheck.enableSilence)
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
        const epoch = captureEpochRef.current
        void (async () => {
          try {
            let promptText = spoken
            if (lastInterruptionRef.current?.text) {
              const cutOff = lastInterruptionRef.current.text
              lastInterruptionRef.current = null
              promptText = buildContextStitchingPrompt(cutOff, spoken)
            }
            const reply = await sendTextAsTurn(promptText)
            if (epoch !== captureEpochRef.current) return
            if (reply && liveCallActiveRef.current) {
              isSpeakingRef.current = true
              setLiveOrbState('speaking')
              setLiveCallStatus('Jarvis está falando…')
              await speakText(reply)
              isSpeakingRef.current = false
            }
          } catch (error) {
            if (epoch !== captureEpochRef.current) return
            setLiveCallStatus(error instanceof Error ? error.message : 'Falha durante a ligação.')
          } finally {
            if (epoch !== captureEpochRef.current) return
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

  const setPushToTalkMode = useCallback((enabled: boolean) => {
    if (enabled === pushToTalkModeRef.current) return
    const wasActive = liveCallActiveRef.current
    if (wasActive) stopLiveCall(true)
    pushToTalkModeRef.current = enabled
    setPushToTalkModeState(enabled)
    if (wasActive) void toggleLiveCallCapture()
  }, [])

  const togglePushToTalk = useCallback(() => {
    const next = !pushToTalkModeRef.current
    setPushToTalkMode(next)
    if (next) {
      setLiveCallStatus('Modo Push-to-Talk ativado. Segure o botão ou Barra de Espaço para falar.')
    } else {
      setLiveCallStatus('Modo contínuo (Hands-Free) ativado. Buffer de 1.8s ativo.')
    }
  }, [])

  const startPtt = useCallback(() => {
    if (!liveCallActiveRef.current || !pushToTalkModeRef.current || isPttActiveRef.current) return
    isPttActiveRef.current = true
    setIsPttActiveState(true)
    pttAccumulatedTextRef.current = ''
    if (silenceBufferTimerRef.current !== null) {
      window.clearTimeout(silenceBufferTimerRef.current)
      silenceBufferTimerRef.current = null
    }
    silenceAccumulatedTextRef.current = ''
    if (liveCallProcessingRef.current || isSpeakingRef.current || (audioRef.current && !audioRef.current.paused)) {
      captureEpochRef.current += 1
      transcriptionAbortRef.current?.abort()
      triggerBargeIn()
    }
    setLiveOrbState('listening')
    setLiveCallRecording(true)
    setLiveCallStatus('🎙️ Ouvindo você… solte para enviar.')
    setLiveUserTranscript(streamTurnRef.current?.user || '')
    startPttRecordingRef.current?.()
  }, [triggerBargeIn])

  const stopPtt = useCallback(() => {
    if (!liveCallActiveRef.current || !pushToTalkModeRef.current || !isPttActiveRef.current) return
    isPttActiveRef.current = false
    setIsPttActiveState(false)
    if (silenceBufferTimerRef.current !== null) {
      window.clearTimeout(silenceBufferTimerRef.current)
      silenceBufferTimerRef.current = null
    }
    const captured = pttAccumulatedTextRef.current.trim()
    pttAccumulatedTextRef.current = ''
    silenceAccumulatedTextRef.current = ''
    if (liveCallRecorderRef.current?.state === 'recording') {
      setLiveCallStatus('Transcrevendo sua fala…')
      liveCallRecorderRef.current.stop()
      return
    }
    if (captured) {
      void dispatchFinalSpeech(captured)
    } else {
      setLiveOrbState('listening')
      setLiveCallStatus('Pronto para ouvir.')
    }
  }, [])

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
    silentMode,
    setSilentMode,
    toggleSilentMode,
    cancelCurrentAction: handleVoiceCancellation,
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
    pushToTalkMode,
    setPushToTalkMode,
    togglePushToTalk,
    startPtt,
    stopPtt,
    isPttActive,
  }
}
