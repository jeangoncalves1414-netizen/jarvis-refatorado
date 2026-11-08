import { useCallback, useEffect, useRef, useState } from 'react'
import { Mic, MicOff, Play, Volume2, AudioLines } from 'lucide-react'
import type { OxyySettings, SttSettings, TtsSettings } from '../types'
import { getPreferredMicDevice, micAudioConstraints, setPreferredMicDevice } from '../utils/micPrefs'

type Props = {
  ttsSettings: TtsSettings | null
  sttSettings: SttSettings | null
  oxyySettings: OxyySettings | null
  onSetTtsProvider: (provider: 'fish' | 'gemini' | 'edge' | 'oxyy') => void
  onSetSttProvider: (provider: 'local' | 'groq' | 'oxyy' | 'google') => void
  onSaveOxyy: (models: OxyySettings['models']) => void
}

type Mic = { sensitivity: number; silence_ms: number; gain: number }
const MIC_DEFAULT: Mic = { sensitivity: 75, silence_ms: 700, gain: 1 }
const METER_FULL_SCALE = 0.12
const TEST_RECORD_MS = 4000
const TEST_PHRASE = 'Olá, este é um teste de voz do assistente.'
const GEMINI_VOICES = ['Charon', 'Fenrir', 'Puck', 'Aoede', 'Kore', 'Zephyr']
const EDGE_VOICES = ['pt-BR-AntonioNeural', 'pt-BR-FranciscaNeural', 'pt-BR-ThalitaMultilingualNeural']
const OXYY_VOICES = ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']
const TTS_LABEL: Record<string, string> = {
  fish: 'Fish Audio S2.1 Pro',
  gemini: 'Gemini Flash TTS',
  edge: 'Edge TTS (local)',
  oxyy: 'Oxyy Audio',
}

type TestState = { busy: boolean; lines: string[]; error?: string }
const idle: TestState = { busy: false, lines: [] }

const withCurrent = (options: string[], current?: string) => (current && !options.includes(current) ? [current, ...options] : options)

export function VoiceSettings({ ttsSettings, sttSettings, oxyySettings, onSetTtsProvider, onSetSttProvider, onSaveOxyy }: Props) {
  const [mic, setMic] = useState<Mic>(MIC_DEFAULT)
  const [micLoaded, setMicLoaded] = useState(false)
  const [micMessage, setMicMessage] = useState('')
  const saveTimer = useRef<number | undefined>(undefined)
  const micRef = useRef<Mic>(MIC_DEFAULT)

  const [devices, setDevices] = useState<MediaDeviceInfo[]>([])
  const [deviceId, setDeviceId] = useState(getPreferredMicDevice)

  const [monitoring, setMonitoring] = useState(false)
  const [level, setLevel] = useState(0)
  const [peak, setPeak] = useState(0)
  const streamRef = useRef<MediaStream | null>(null)
  const ctxRef = useRef<AudioContext | null>(null)
  const frameRef = useRef(0)

  const [micTest, setMicTest] = useState<TestState>(idle)
  const [sttTest, setSttTest] = useState<TestState>(idle)
  const [ttsTest, setTtsTest] = useState<TestState>(idle)

  const [voiceOverride, setVoiceOverride] = useState<Partial<TtsSettings>>({})
  const [fishRef, setFishRef] = useState('')
  const tts = { ...ttsSettings, ...voiceOverride }
  const provider = tts.tts_provider || 'fish'

  useEffect(() => { setFishRef(tts.fish_reference_id || '') }, [tts.fish_reference_id])

  useEffect(() => {
    fetch('/api/settings/mic')
      .then(response => response.json())
      .then(data => {
        if (!data?.ok) return
        const next = { sensitivity: data.sensitivity, silence_ms: data.silence_ms, gain: data.gain }
        micRef.current = next
        setMic(next)
      })
      .catch(() => setMicMessage('Não foi possível ler os ajustes do microfone. Verifique se o backend está ligado.'))
      .finally(() => setMicLoaded(true))
  }, [])

  const refreshDevices = useCallback(async () => {
    try {
      const list = await navigator.mediaDevices.enumerateDevices()
      setDevices(list.filter(device => device.kind === 'audioinput'))
    } catch { /* sem permissão ou sem suporte */ }
  }, [])

  useEffect(() => { void refreshDevices() }, [refreshDevices])

  const saveMic = (patch: Partial<Mic>) => {
    const next = { ...micRef.current, ...patch }
    micRef.current = next
    setMic(next)
    window.clearTimeout(saveTimer.current)
    saveTimer.current = window.setTimeout(async () => {
      try {
        const response = await fetch('/api/settings/mic', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(micRef.current) })
        const data = await response.json()
        if (!response.ok || !data.ok) throw new Error(data.error || '')
        setMicMessage('Ajustes do microfone salvos. Valem na próxima ligação por voz.')
      } catch (error) {
        setMicMessage(error instanceof Error && error.message ? error.message : 'Não foi possível salvar os ajustes do microfone.')
      }
    }, 450)
  }

  const stopMonitor = useCallback(() => {
    cancelAnimationFrame(frameRef.current)
    streamRef.current?.getTracks().forEach(track => track.stop())
    streamRef.current = null
    void ctxRef.current?.close().catch(() => undefined)
    ctxRef.current = null
    setMonitoring(false)
    setLevel(0)
  }, [])

  useEffect(() => () => {
    window.clearTimeout(saveTimer.current)
    stopMonitor()
  }, [stopMonitor])

  const openStream = async () => {
    if (!navigator.mediaDevices?.getUserMedia) throw new Error('Este navegador não permite acessar o microfone.')
    const stream = await navigator.mediaDevices.getUserMedia({ audio: micAudioConstraints({ echoCancellation: true, noiseSuppression: true, autoGainControl: true }) })
    void refreshDevices()
    return stream
  }

  const startMonitor = async () => {
    if (monitoring) return
    try {
      const stream = await openStream()
      const ctx = new AudioContext()
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 1024
      ctx.createMediaStreamSource(stream).connect(analyser)
      streamRef.current = stream
      ctxRef.current = ctx
      setMonitoring(true)
      setPeak(0)
      const data = new Float32Array(analyser.fftSize)
      const tick = () => {
        analyser.getFloatTimeDomainData(data)
        let sum = 0
        for (let i = 0; i < data.length; i++) sum += data[i] * data[i]
        const rms = Math.sqrt(sum / data.length) * micRef.current.gain
        const value = Math.min(1, rms / METER_FULL_SCALE)
        setLevel(value)
        setPeak(previous => Math.max(value, previous * 0.992))
        frameRef.current = requestAnimationFrame(tick)
      }
      tick()
    } catch (error) {
      stopMonitor()
      setMicMessage(error instanceof Error && error.message ? error.message : 'Não foi possível abrir o microfone.')
    }
  }

  const changeDevice = (value: string) => {
    setDeviceId(value)
    setPreferredMicDevice(value)
    if (monitoring) { stopMonitor(); setMicMessage('Dispositivo alterado. Ligue o medidor de novo para testar.') }
  }

  const postStt = async (audio: Blob, contentType: string) => {
    const started = performance.now()
    const response = await fetch('/api/voice/stt', { method: 'POST', headers: { 'Content-Type': contentType }, body: audio })
    const data = await response.json().catch(() => ({}))
    return { data, ms: Math.round(performance.now() - started) }
  }

  const runMicTest = async () => {
    if (micTest.busy) return
    setMicTest({ busy: true, lines: [`Gravando ${TEST_RECORD_MS / 1000} s… fale agora.`] })
    let stream: MediaStream | null = null
    try {
      stream = streamRef.current ?? await openStream()
      if (typeof MediaRecorder === 'undefined') throw new Error('Gravação não suportada neste navegador.')
      const recorder = new MediaRecorder(stream)
      const chunks: BlobPart[] = []
      recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data) }
      const stopped = new Promise<void>(resolve => { recorder.onstop = () => resolve() })
      recorder.start()
      await new Promise(resolve => setTimeout(resolve, TEST_RECORD_MS))
      recorder.stop()
      await stopped
      if (stream !== streamRef.current) stream.getTracks().forEach(track => track.stop())
      setMicTest({ busy: true, lines: ['Transcrevendo…'] })
      const type = recorder.mimeType || 'audio/webm'
      const { data, ms } = await postStt(new Blob(chunks, { type }), type)
      if (!data.ok || !data.text) setMicTest({ busy: false, lines: [`Tempo: ${ms} ms`], error: data.error || 'Nenhuma fala reconhecida. Aumente a sensibilidade ou o ganho.' })
      else setMicTest({ busy: false, lines: [`Transcrição: “${data.text}”`, `Tempo de transcrição: ${ms} ms`] })
    } catch (error) {
      if (stream && stream !== streamRef.current) stream.getTracks().forEach(track => track.stop())
      setMicTest({ busy: false, lines: [], error: error instanceof Error ? error.message : 'Falha no teste do microfone.' })
    }
  }

  const fetchTtsAudio = async () => {
    const started = performance.now()
    const response = await fetch('/api/voice/tts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: TEST_PHRASE }) })
    if (!response.ok) throw new Error('O provedor de voz não retornou áudio. Verifique chave e provedor.')
    const blob = await response.blob()
    return { blob, ms: Math.round(performance.now() - started) }
  }

  const runSttTest = async () => {
    if (sttTest.busy) return
    setSttTest({ busy: true, lines: ['Gerando áudio de teste com o TTS…'] })
    try {
      const { blob } = await fetchTtsAudio()
      setSttTest({ busy: true, lines: ['Transcrevendo…'] })
      const contentType = blob.type.includes('wav') ? 'audio/wav' : blob.type.includes('ogg') ? 'audio/ogg' : 'audio/mp3'
      const { data, ms } = await postStt(blob, contentType)
      if (!data.ok || !data.text) setSttTest({ busy: false, lines: [`Tempo: ${ms} ms`], error: data.error || 'O STT não retornou texto.' })
      else setSttTest({ busy: false, lines: [`Frase enviada: “${TEST_PHRASE}”`, `Transcrito: “${data.text}”`, `Tempo de transcrição: ${ms} ms`] })
    } catch (error) {
      setSttTest({ busy: false, lines: [], error: error instanceof Error ? error.message : 'Falha no teste de STT.' })
    }
  }

  const runTtsTest = async () => {
    if (ttsTest.busy) return
    setTtsTest({ busy: true, lines: ['Sintetizando…'] })
    try {
      const started = performance.now()
      let blob: Blob | null = null
      let firstMs = 0
      const streamResponse = await fetch('/api/voice/tts/stream', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: TEST_PHRASE }) })
      if (streamResponse.ok && streamResponse.body) {
        const reader = streamResponse.body.getReader()
        const parts: BlobPart[] = []
        for (;;) {
          const { done, value } = await reader.read()
          if (done) break
          if (value?.length) {
            if (!firstMs) firstMs = Math.round(performance.now() - started)
            parts.push(value as unknown as BlobPart)
          }
        }
        if (parts.length) blob = new Blob(parts, { type: streamResponse.headers.get('Content-Type') || 'audio/mpeg' })
      }
      if (!blob) {
        const fallback = await fetchTtsAudio()
        blob = fallback.blob
        firstMs = fallback.ms
      }
      const totalMs = Math.round(performance.now() - started)
      const audio = new Audio(URL.createObjectURL(blob))
      audio.onended = () => URL.revokeObjectURL(audio.src)
      await audio.play().catch(() => undefined)
      setTtsTest({ busy: false, lines: [`Provedor: ${TTS_LABEL[provider] || provider}`, `Tempo até o primeiro áudio: ${firstMs} ms`, `Síntese completa: ${totalMs} ms`] })
    } catch (error) {
      setTtsTest({ busy: false, lines: [], error: error instanceof Error ? error.message : 'Falha no teste de TTS.' })
    }
  }

  const saveVoices = async (voices: Record<string, string>) => {
    try {
      const response = await fetch('/api/settings/tts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ voices }) })
      const data = await response.json()
      if (!response.ok || data.ok === false) throw new Error(data.error || '')
      setVoiceOverride({ fish_reference_id: data.fish_reference_id, tts_gemini_voice: data.tts_gemini_voice, tts_voice: data.tts_voice })
      setMicMessage('')
    } catch (error) {
      setTtsTest({ busy: false, lines: [], error: error instanceof Error && error.message ? error.message : 'Não foi possível salvar a voz.' })
    }
  }

  const threshold = 0.03 - 0.026 * (mic.sensitivity / 100)
  const thresholdPct = Math.min(100, (threshold / METER_FULL_SCALE) * 100)
  const localOff = sttSettings?.local_available === false
  const sttProvider = sttSettings?.stt_provider || 'local'

  const result = (state: TestState) => (
    <>
      {state.lines.map(line => <p className="st-result" key={line}>{line}</p>)}
      {state.error && <p className="ws-error st-result" role="alert">{state.error}</p>}
    </>
  )

  return (
    <div className="st-stack">
      <article className="settings-card">
        <p className="eyebrow">MICROFONE</p>
        <h2>Detecção de fala</h2>
        <p>Valem para a ligação por voz e o ditado. Mudanças são salvas sozinhas.</p>

        <label className="field-label st-range">
          <span>Sensibilidade <b>{mic.sensitivity}</b></span>
          <input type="range" min={1} max={100} step={1} value={mic.sensitivity} disabled={!micLoaded} onChange={event => saveMic({ sensitivity: Number(event.target.value) })} />
          <small className="settings-muted">Mais alto detecta falas baixas, mas também mais ruído. Padrão 75.</small>
        </label>
        <label className="field-label st-range">
          <span>Silêncio para encerrar a fala <b>{mic.silence_ms} ms</b></span>
          <input type="range" min={300} max={3000} step={50} value={mic.silence_ms} disabled={!micLoaded} onChange={event => saveMic({ silence_ms: Number(event.target.value) })} />
          <small className="settings-muted">Quanto menor, mais rápido o envio, com risco de cortar pausas. Padrão 700 ms.</small>
        </label>
        <label className="field-label st-range">
          <span>Ganho <b>{mic.gain.toFixed(1)}×</b></span>
          <input type="range" min={0.5} max={4} step={0.1} value={mic.gain} disabled={!micLoaded} onChange={event => saveMic({ gain: Number(event.target.value) })} />
          <small className="settings-muted">Multiplica o nível medido antes de comparar com o limiar. Padrão 1,0×.</small>
        </label>
        <button className="outline-button" type="button" onClick={() => saveMic(MIC_DEFAULT)} disabled={!micLoaded}>Restaurar padrões</button>

        <label className="field-label">Dispositivo de entrada
          <select value={deviceId} onChange={event => changeDevice(event.target.value)}>
            <option value="">Padrão do sistema</option>
            {devices.filter(device => device.deviceId && device.deviceId !== 'default').map((device, index) => (
              <option key={device.deviceId} value={device.deviceId}>{device.label || `Microfone ${index + 1}`}</option>
            ))}
          </select>
          {devices.length > 0 && devices.every(device => !device.label) && <span className="settings-muted">Ligue o medidor uma vez para o navegador mostrar os nomes dos dispositivos.</span>}
        </label>

        <div className="st-meter-head">
          <strong>Nível ao vivo</strong>
          <button className="outline-button" type="button" onClick={monitoring ? stopMonitor : startMonitor}>
            {monitoring ? <><MicOff size={14} /> Parar medidor</> : <><Mic size={14} /> Ligar medidor</>}
          </button>
        </div>
        <div className="st-meter" aria-label="Nível do microfone">
          <div className="st-meter-fill" style={{ width: `${level * 100}%` }} data-active={level * 100 >= thresholdPct} />
          <div className="st-meter-peak" style={{ left: `${peak * 100}%` }} />
          <div className="st-meter-threshold" style={{ left: `${thresholdPct}%` }} title="Limiar mínimo de detecção" />
        </div>
        <small className="settings-muted">A linha marca o limiar mínimo para sua sensibilidade. A barra acende quando passa dela. O limiar real também acompanha o ruído de fundo.</small>
        {micMessage && <p className="settings-notice" aria-live="polite">{micMessage}</p>}
      </article>

      <article className="settings-card">
        <p className="eyebrow">TRANSCRIÇÃO (STT)</p>
        <h2>Provedor e modelo</h2>
        <label className="field-label">Provedor de STT
          <select value={sttProvider} onChange={event => onSetSttProvider(event.target.value as 'local' | 'groq' | 'oxyy' | 'google')}>
            <option value="local">STT local (faster-whisper) · recomendado</option>
            <option value="groq">Groq Whisper</option>
            <option value="oxyy">Oxyy Whisper</option>
            <option value="google">Google Speech</option>
          </select>
        </label>
        <label className="field-label">Modelo do STT local
          <select
            value={sttSettings?.local_model || 'base'}
            onChange={async event => {
              await fetch('/api/settings/stt', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ local_model: event.target.value }) })
              onSetSttProvider(sttProvider)
            }}
          >
            {(sttSettings?.local_models || ['tiny', 'base', 'small', 'medium']).map(model => <option key={model} value={model}>{model}</option>)}
          </select>
        </label>
        {localOff ? (
          <p className="ws-error" role="alert">
            STT local desligado: faster-whisper não instalado. Rode <code>pip install faster-whisper</code> e reinicie o Jarvis.
            {sttSettings?.local_reason ? ` (${sttSettings.local_reason})` : ''}
          </p>
        ) : (
          <span className="settings-muted">{sttSettings?.local_download_hint || 'STT local pronto (modelo já baixado).'}</span>
        )}
        <div className="st-actions">
          <button className="outline-button" type="button" onClick={runMicTest} disabled={micTest.busy}><Mic size={14} /> {micTest.busy ? 'Testando…' : 'Testar microfone'}</button>
          <button className="outline-button" type="button" onClick={runSttTest} disabled={sttTest.busy}><AudioLines size={14} /> {sttTest.busy ? 'Testando…' : 'Testar STT'}</button>
        </div>
        <small className="settings-muted">Testar microfone grava {TEST_RECORD_MS / 1000} s e transcreve. Testar STT gera uma frase com o TTS e transcreve de volta. Nenhum modelo de chat é usado.</small>
        {result(micTest)}
        {result(sttTest)}
      </article>

      <article className="settings-card">
        <p className="eyebrow">SÍNTESE DE VOZ (TTS)</p>
        <h2>Provedor e voz</h2>
        <div className="provider-list">
          {(['fish', 'gemini', 'edge', 'oxyy'] as const).map(id => (
            <button key={id} type="button" className={provider === id ? 'provider-active' : ''} onClick={() => onSetTtsProvider(id)}>
              <span>{TTS_LABEL[id]}</span>
              <small>{id === 'fish' ? (tts.fish_configured ? 'Voz personalizada · configurado' : 'Adicione a chave Fish Audio') : id === 'gemini' ? (tts.gemini_configured ? 'Voz natural · configurado' : 'Adicione a chave Gemini') : id === 'edge' ? 'Neural PT-BR · sem chave' : (tts.oxyy_configured ? `Modelo ${tts.oxyy_model || oxyySettings?.models?.tts || 'TTS'}` : 'Adicione a chave Oxyy')}</small>
            </button>
          ))}
        </div>

        {provider === 'fish' && (
          <label className="field-label">Voz (ID de referência do Fish Audio)
            <div className="st-inline">
              <input value={fishRef} onChange={event => setFishRef(event.target.value)} placeholder="reference_id da voz" />
              <button className="outline-button" type="button" disabled={!fishRef.trim() || fishRef.trim() === tts.fish_reference_id} onClick={() => saveVoices({ fish_reference_id: fishRef.trim() })}>Salvar voz</button>
            </div>
            <span className="settings-muted">Modelo: {tts.fish_model || 's2.1-pro-free'}. O ID vem da página da voz em fish.audio.</span>
          </label>
        )}
        {provider === 'gemini' && (
          <label className="field-label">Voz do Gemini
            <select value={tts.tts_gemini_voice || 'Charon'} onChange={event => saveVoices({ gemini: event.target.value })}>
              {withCurrent(GEMINI_VOICES, tts.tts_gemini_voice).map(voice => <option key={voice} value={voice}>{voice}</option>)}
            </select>
          </label>
        )}
        {provider === 'edge' && (
          <label className="field-label">Voz do Edge
            <select value={tts.tts_voice || EDGE_VOICES[0]} onChange={event => saveVoices({ edge: event.target.value })}>
              {withCurrent(EDGE_VOICES, tts.tts_voice).map(voice => <option key={voice} value={voice}>{voice}</option>)}
            </select>
          </label>
        )}
        {provider === 'oxyy' && (
          <label className="field-label">Voz do Oxyy
            <select value={oxyySettings?.models?.tts_voice || tts.oxyy_voice || 'alloy'} onChange={event => onSaveOxyy({ ...(oxyySettings?.models || {}), tts_voice: event.target.value })}>
              {withCurrent(OXYY_VOICES, oxyySettings?.models?.tts_voice || tts.oxyy_voice).map(voice => <option key={voice} value={voice}>{voice}</option>)}
            </select>
          </label>
        )}

        <div className="st-actions">
          <button className="outline-button" type="button" onClick={runTtsTest} disabled={ttsTest.busy}><Volume2 size={14} /> {ttsTest.busy ? 'Sintetizando…' : 'Testar TTS'}</button>
        </div>
        <small className="settings-muted">Fala “{TEST_PHRASE}” e mostra o tempo até o primeiro áudio. <Play size={10} style={{ verticalAlign: 'middle' }} /></small>
        {result(ttsTest)}
      </article>
    </div>
  )
}
