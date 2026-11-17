import { useEffect, useRef, useState } from 'react'
import { openConfiguredCamera } from '../utils/cameraCatalog'

let capture: (() => string | undefined) | undefined
export function captureIdentityFrame() { return capture?.() }

export function CallIdentityCamera() {
  const video = useRef<HTMLVideoElement>(null)
  const stream = useRef<MediaStream | null>(null)
  const alive = useRef(true)
  const enrolling = useRef(false)
  const request = useRef(0)
  const [enabled, setEnabled] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const stop = () => {
    request.current++
    capture = undefined
    stream.current?.getTracks().forEach(track => track.stop())
    stream.current = null
    setEnabled(false)
  }
  useEffect(() => {
    alive.current = true
    const enrollment = (event: Event) => {
      enrolling.current = Boolean((event as CustomEvent<boolean>).detail)
      if (enrolling.current) stop()
    }
    window.addEventListener('jarvis-enrollment-active', enrollment)
    return () => { alive.current = false; capture = undefined; stream.current?.getTracks().forEach(track => track.stop()); window.removeEventListener('jarvis-enrollment-active', enrollment) }
  }, [])
  const start = async () => {
    const id = ++request.current
    setBusy(true); setError('')
    try {
      const media = await openConfiguredCamera()
      if (!alive.current || enrolling.current || request.current !== id) { media.getTracks().forEach(track => track.stop()); return }
      stream.current = media
      if (video.current) { video.current.srcObject = media; await video.current.play() }
      if (!alive.current || enrolling.current || stream.current !== media) { media.getTracks().forEach(track => track.stop()); return }
      setEnabled(true)
      capture = () => {
        const source = video.current
        if (!source || source.readyState < 2) return undefined
        const canvas = document.createElement('canvas')
        canvas.width = source.videoWidth; canvas.height = source.videoHeight
        canvas.getContext('2d')?.drawImage(source, 0, 0)
        return canvas.toDataURL('image/jpeg', 0.85)
      }
    } catch { stop(); setError('Não foi possível abrir a câmera. Confira a permissão.') }
    finally { if (alive.current) setBusy(false) }
  }
  return <div aria-label="Identificação visual local">
    <button disabled={busy} onClick={enabled ? stop : start}>{enabled ? 'Desligar câmera de identificação' : 'Ligar câmera de identificação'}</button>
    <video ref={video} muted playsInline style={{ display: enabled ? 'block' : 'none', width: 160, maxWidth: '100%' }} />
    {enabled && <small>Câmera ativa. Rostos processados localmente após cada fala; presença não comprova quem falou.</small>}
    {error && <p role="status">{error}</p>}
  </div>
}
