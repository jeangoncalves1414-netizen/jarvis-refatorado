import { cameraLabel, detectCameraDevices, registerDetectedCameras, requestedCameras, type SavedCamera } from './cameraCatalog'

export type CapturedCamera = { image: string; cameraName: string; error?: string }

async function sampleCamera(camera: SavedCamera, motion = false, signal?: AbortSignal) {
  let stream: MediaStream | undefined
  const video = document.createElement('video')
  video.muted = true; video.playsInline = true
  let expired = false
  let deadline = 0
  let onAbort = () => {}
  if (signal?.aborted) throw new DOMException('Cancelado', 'AbortError')
  const work = async () => {
    const acquired = await navigator.mediaDevices.getUserMedia({ video: { deviceId: { exact: camera.id } }, audio: false })
    if (expired) { acquired.getTracks().forEach(t => t.stop()); throw new Error('Câmera indisponível.') }
    stream = acquired; video.srcObject = stream
    await video.play()
    while (video.readyState < 2 || !video.videoWidth) {
      if (expired) throw new Error('A câmera não respondeu.')
      await new Promise(resolve => setTimeout(resolve, 40))
    }
    const canvas = document.createElement('canvas')
    const scale = Math.min(1, 1280 / video.videoWidth)
    canvas.width = Math.round(video.videoWidth * scale); canvas.height = Math.round(video.videoHeight * scale)
    const context = canvas.getContext('2d')!
    context.drawImage(video, 0, 0, canvas.width, canvas.height)
    let activity = 0
    if (motion) {
      const small = document.createElement('canvas'); small.width = 64; small.height = 48
      const pixels = small.getContext('2d', { willReadFrequently: true })!
      pixels.drawImage(video, 0, 0, 64, 48)
      const before = pixels.getImageData(0, 0, 64, 48).data
      await new Promise(resolve => setTimeout(resolve, 400))
      if (expired) throw new Error('A câmera não respondeu.')
      pixels.drawImage(video, 0, 0, 64, 48)
      const after = pixels.getImageData(0, 0, 64, 48).data
      // Ignore uniform exposure changes; motion must change the spatial pattern.
      const changes = Array.from({ length: 64 * 48 }, (_, i) =>
        (after[i * 4] + after[i * 4 + 1] + after[i * 4 + 2] - before[i * 4] - before[i * 4 + 1] - before[i * 4 + 2]) / 3)
      const mean = changes.reduce((sum, value) => sum + value, 0) / changes.length
      activity = changes.reduce((sum, value) => sum + Math.max(0, Math.abs(value - mean) - 8), 0) / changes.length
      context.drawImage(video, 0, 0, canvas.width, canvas.height)
    }
    return { image: canvas.toDataURL('image/jpeg', .85), cameraName: cameraLabel(camera), activity, id: camera.id }
  }
  try {
    return await Promise.race([work(), new Promise<never>((_, reject) => {
      deadline = window.setTimeout(() => { expired = true; reject(new Error('A câmera não respondeu.')) }, 8000)
      onAbort = () => { expired = true; reject(new DOMException('Cancelado', 'AbortError')) }
      signal?.addEventListener('abort', onAbort, { once: true })
    })])
  } finally {
    expired = true; clearTimeout(deadline)
    signal?.removeEventListener('abort', onAbort)
    stream?.getTracks().forEach(t => t.stop()); video.pause(); video.srcObject = null
  }
}

async function availableCameras() {
  const devices = await detectCameraDevices()
  return registerDetectedCameras(devices).filter(c => c.enabled && devices.some(d => d.kind === 'videoinput' && d.deviceId === c.id))
}

export async function captureRequestedCameras(message: string): Promise<CapturedCamera[]> {
  const targets = requestedCameras(message, await availableCameras())
  if (!targets?.length) throw new Error('A câmera solicitada não está disponível. Confira a conexão e as câmeras habilitadas.')
  const frames = await Promise.all(targets.map(async camera => {
    try { return await sampleCamera(camera) }
    catch { return { image: '', cameraName: cameraLabel(camera), error: 'Não consegui acessar esta câmera; não foi possível observar a cena.' } }
  }))
  if (frames.every(frame => !frame.image)) throw new Error('Não consegui acessar as câmeras.')
  return frames
}

export async function selectActiveCamera(signal?: AbortSignal): Promise<string> {
  const cameras = await availableCameras()
  const samples = await Promise.all(cameras.map(async camera => {
    try {
      const sample = await sampleCamera(camera, true, signal)
      let face = false
      try {
        const response = await fetch('/api/identity', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'enrollment_pose', purpose: 'camera_selection', image: sample.image }),
          signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(3000)]) : AbortSignal.timeout(3000),
        })
        const result = await response.json()
        face = response.ok && result.ok && result.count === 1
      } catch { /* Motion still selects a camera if face inference is temporarily unavailable. */ }
      return { ...sample, face }
    } catch { return null }
  }))
  const active = samples.filter(s => s !== null).sort((a, b) => Number(b.face) - Number(a.face) || b.activity - a.activity)
  if (!active.length) throw new Error('Nenhuma câmera habilitada está disponível.')
  return active[0].id
}
