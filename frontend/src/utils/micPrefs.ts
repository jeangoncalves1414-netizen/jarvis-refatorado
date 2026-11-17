import { pairedAndroid } from './pairedAndroid'

export type MicrophonePreference = { device_id: string; device_name: string }
const CACHE_KEY = 'jarvis_microphone_preference'
const DEFAULT: MicrophonePreference = { device_id: '', device_name: '' }

export function rememberMicrophone(value: Partial<MicrophonePreference>): MicrophonePreference {
  const preference = { device_id: value.device_id || '', device_name: value.device_name || '' }
  try { localStorage.setItem(CACHE_KEY, JSON.stringify(preference)) } catch { /* storage unavailable */ }
  return preference
}

export async function loadMicrophone(): Promise<MicrophonePreference> {
  try {
    const response = await fetch('/api/settings/mic')
    if (response.ok) {
      const data = await response.json()
      if (data.ok) return rememberMicrophone(data)
    }
  } catch { /* The lock screen uses the last successfully saved preference. */ }
  try { return { ...DEFAULT, ...JSON.parse(localStorage.getItem(CACHE_KEY) || '{}') } } catch { return DEFAULT }
}

export async function openMicrophone(base: MediaTrackConstraints = {}): Promise<MediaStream> {
  // O WebView do Android expõe o microfone físico como a entrada padrão. Uma
  // preferência salva no painel de PC pode apontar para um id inexistente no
  // telefone e o Chromium responde apenas com "Could not start audio source".
  if (pairedAndroid) return navigator.mediaDevices.getUserMedia({ audio: base })

  const preference = await loadMicrophone()
  if (!preference.device_name) return navigator.mediaDevices.getUserMedia({ audio: { ...base, deviceId: { ideal: 'default' } } })
  let deviceId = preference.device_id
  if (navigator.mediaDevices.enumerateDevices) {
    const devices = (await navigator.mediaDevices.enumerateDevices()).filter(d => d.kind === 'audioinput' && !['default', 'communications'].includes(d.deviceId))
    if (!devices.some(d => d.deviceId === deviceId)) {
      const matches = devices.filter(d => d.label === preference.device_name)
      deviceId = matches.length === 1 ? matches[0].deviceId : ''
    }
  }
  if (!deviceId) throw new Error('Microfone selecionado indisponível. Escolha o dispositivo novamente nas configurações.')
  return navigator.mediaDevices.getUserMedia({ audio: { ...base, deviceId: { exact: deviceId } } })
}

// SpeechRecognition.start() without an audio track always uses the default microphone.
export function createMicrophoneRecognition(Recognition: new () => any) {
  const recognition = new Recognition()
  const start = recognition.start.bind(recognition)
  const abort = recognition.abort.bind(recognition)
  const stop = recognition.stop.bind(recognition)
  let generation = 0
  let stream: MediaStream | undefined
  const release = () => { stream?.getTracks().forEach(track => track.stop()); stream = undefined }
  recognition.addEventListener?.('end', release)
  recognition.abort = () => { generation++; release(); return abort() }
  recognition.stop = () => { generation++; release(); return stop() }
  recognition.start = () => {
    const current = ++generation
    void (async () => {
      const preference = await loadMicrophone()
      if (current !== generation) return
      if (!preference.device_name) { start(); return }
      // Older engines silently ignore the track argument; never capture the wrong mic.
      const chromium = Number(navigator.userAgent.match(/(?:Chrome|Chromium)\/(\d+)/)?.[1] || 0)
      const firefox = Number(navigator.userAgent.match(/Firefox\/(\d+)/)?.[1] || 0)
      if (/Android|iPhone|iPad/.test(navigator.userAgent) || (chromium < 135 && firefox < 160)) {
        throw new Error('Para usar este microfone no reconhecimento do navegador, atualize o Chrome ou Edge, ou use a captura do PC.')
      }
      const acquired = await openMicrophone()
      if (current !== generation) { acquired.getTracks().forEach(track => track.stop()); return }
      release(); stream = acquired
      start(acquired.getAudioTracks()[0])
    })().catch(error => {
      if (current === generation) {
        release()
        recognition.onerror?.({ error: 'not-allowed', message: error instanceof Error ? error.message : 'Não foi possível abrir o microfone selecionado.' })
      }
    })
  }
  return recognition
}
