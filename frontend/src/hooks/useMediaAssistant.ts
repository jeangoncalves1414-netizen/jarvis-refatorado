import { useCallback, useRef, useState } from 'react'

const SPEAK_STORAGE_KEY = 'jarvis_speak_responses'

function readSpeakEnabled() {
  try {
    const stored = localStorage.getItem(SPEAK_STORAGE_KEY)
    if (stored !== null) return stored === '1'
  } catch {
    /* ignore storage errors */
  }
  return true
}

type MediaAssistantOptions = {
  query: string
  sendText: (message: string) => Promise<void>
  setAnswer: (answer: string) => void
  setQuery: (query: string) => void
}

export function useMediaAssistant({ query, sendText, setAnswer, setQuery }: MediaAssistantOptions) {
  const [speakEnabled, setSpeakEnabledState] = useState(readSpeakEnabled)
  const [recording, setRecording] = useState(false)
  const [liveCallOpen, setLiveCallOpen] = useState(false)
  const [liveCallRecording, setLiveCallRecording] = useState(false)
  const [liveCallStatus, setLiveCallStatus] = useState('Pronto para ouvir.')
  const [visionResult, setVisionResult] = useState<{ reply: string; imageUrl?: string } | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const liveCallRecorderRef = useRef<MediaRecorder | null>(null)
  const liveCallStreamRef = useRef<MediaStream | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  const toggleVoiceInput = async () => {
    if (recorderRef.current?.state === 'recording') {
      recorderRef.current.stop()
      return
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setAnswer('A captura de microfone não é suportada neste navegador.')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const chunks: BlobPart[] = []
      const options = MediaRecorder.isTypeSupported('audio/webm') ? { mimeType: 'audio/webm' } : undefined
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
    if (liveCallRecorderRef.current?.state === 'recording') liveCallRecorderRef.current.stop()
    if (liveCallStreamRef.current) {
      liveCallStreamRef.current.getTracks().forEach(track => track.stop())
    }
    liveCallStreamRef.current = null
    liveCallRecorderRef.current = null
    audioRef.current?.pause()
    setLiveCallRecording(false)
    setLiveCallOpen(false)
  }

  const toggleLiveCallCapture = async () => {
    if (liveCallRecorderRef.current?.state === 'recording') {
      liveCallRecorderRef.current.stop()
      return
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setLiveCallStatus('Microfone não suportado neste navegador.')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      liveCallStreamRef.current = stream
      const chunks: BlobPart[] = []
      const options = MediaRecorder.isTypeSupported('audio/webm') ? { mimeType: 'audio/webm' } : undefined
      const recorder = new MediaRecorder(stream, options)
      liveCallRecorderRef.current = recorder
      recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data) }
      recorder.onstop = async () => {
        setLiveCallRecording(false)
        stream.getTracks().forEach(track => track.stop())
        liveCallStreamRef.current = null
        const audio = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' })
        if (audio.size < 1000) {
          setLiveCallStatus('Não captei fala suficiente. Tente novamente.')
          return
        }
        try {
          setLiveCallStatus('Transcrevendo…')
          const stt = await fetch('/api/voice/stt', { method: 'POST', headers: { 'Content-Type': audio.type }, body: audio })
          const transcription = await stt.json()
          if (!stt.ok || !transcription.ok || !transcription.text) throw new Error(transcription.error || 'Não foi possível entender o áudio.')
          setLiveCallStatus('Jarvis está pensando…')
          await sendText(transcription.text.trim())
          setLiveCallStatus('Resposta enviada ao chat. Toque para falar novamente.')
        } catch (error) {
          setLiveCallStatus(error instanceof Error ? error.message : 'Falha durante a ligação.')
        }
      }
      recorder.start()
      setLiveCallRecording(true)
      setLiveCallStatus('Ouvindo… toque novamente ao terminar.')
    } catch {
      setLiveCallStatus('Não consegui acessar o microfone. Verifique a permissão.')
    }
  }

  const setSpeakEnabled = useCallback((enabled: boolean) => {
    setSpeakEnabledState(enabled)
    try {
      localStorage.setItem(SPEAK_STORAGE_KEY, enabled ? '1' : '0')
    } catch {
      /* ignore storage errors */
    }
  }, [])

  const speakText = async (text: string) => {
    if (!text || !speakEnabled) return
    audioRef.current?.pause()
    let url: string | null = null
    try {
      const response = await fetch('/api/voice/tts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }) })
      if (!response.ok) throw new Error('A leitura por voz não está disponível.')
      const blob = await response.blob()
      url = URL.createObjectURL(blob)
      const audio = new Audio(url)
      audioRef.current = audio
      audio.onended = () => {
        if (url) URL.revokeObjectURL(url)
        url = null
      }
      await audio.play()
    } catch (error) {
      setAnswer(error instanceof Error ? error.message : 'Falha ao gerar áudio.')
    } finally {
      if (url) URL.revokeObjectURL(url)
    }
  }

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
    recording,
    setLiveCallOpen,
    setSpeakEnabled,
    setVisionResult,
    speakEnabled,
    speakText,
    toggleLiveCallCapture,
    toggleVoiceInput,
    visionResult,
  }
}
