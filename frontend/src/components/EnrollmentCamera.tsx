import { useEffect, useRef, useState } from 'react'
import { cameraLabel, openConfiguredCamera, registerDetectedCameras, type SavedCamera } from '../utils/cameraCatalog'
import { selectActiveCamera } from '../utils/cameraCapture'
import { speakGuidance } from '../utils/guidanceVoice'

export const posePrompts = ['Olhe de frente para a câmera.', 'Vire levemente a cabeça para um lado.', 'Agora vire a cabeça para o lado oposto.']

export function EnrollmentCamera({ onComplete }: { onComplete: (images: string[]) => void }) {
  const video = useRef<HTMLVideoElement>(null)
  const [cameras, setCameras] = useState<SavedCamera[]>([])
  const [selected, setSelected] = useState('')
  const [notice, setNotice] = useState('Procurando movimento nas câmeras…')
  const [count, setCount] = useState(0)
  const callback = useRef(onComplete)
  const guided = useRef(false)
  callback.current = onComplete
  useEffect(() => {
    guided.current = false
    if (!posePrompts[count] || !selected) return
    const controller = new AbortController()
    void speakGuidance(posePrompts[count], controller.signal).catch(() => undefined)
      .finally(() => { if (!controller.signal.aborted) guided.current = true })
    return () => controller.abort()
  }, [count, selected])
  useEffect(() => {
    let closed = false
    let stream: MediaStream | undefined
    let timer = 0
    const abort = new AbortController()
    const images: string[] = [], poses: number[] = []
    setCount(0)
    void (async () => {
      try {
        if (!selected) {
          const active = await selectActiveCamera(abort.signal)
          if (!closed) { setSelected(active); setNotice('Câmera selecionada automaticamente. Enquadre seu rosto.') }
          return
        }
        stream = await openConfiguredCamera(selected)
        if (closed) { stream.getTracks().forEach(t => t.stop()); return }
        const devices = await navigator.mediaDevices.enumerateDevices()
        if (closed) return
        const available = registerDetectedCameras(devices).filter(c => c.enabled && devices.some(d => d.deviceId === c.id))
        setCameras(available)
        if (!available.length) throw new Error('Nenhuma câmera habilitada.')
        if (video.current) { video.current.srcObject = stream; await video.current.play() }
        if (closed) return
        let pending = false
        timer = window.setInterval(async () => {
          const source = video.current
          if (pending || !guided.current || !source || source.readyState < 2 || images.length === 3) return
          pending = true
          try {
            const canvas = document.createElement('canvas')
            canvas.width = source.videoWidth; canvas.height = source.videoHeight
            canvas.getContext('2d')?.drawImage(source, 0, 0)
            const image = canvas.toDataURL('image/jpeg', 0.85)
            const response = await fetch('/api/identity', { method: 'POST', signal: abort.signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'enrollment_pose', image }) })
            const data = await response.json()
            if (closed) return
            if (!response.ok || !data.ok) throw new Error(data.error || 'Falha ao analisar o rosto.')
            if (data.count !== 1 || !Number.isFinite(data.pose)) { setNotice('Enquadre somente a pessoa apresentada.'); return }
            const difference = data.pose - poses[0]
            const ready = images.length === 0 ? Math.abs(data.pose) <= 0.22 : images.length === 1 ? Math.abs(difference) >= 0.10 : difference * Math.sign(poses[1] - poses[0]) <= -0.10
            setNotice(posePrompts[images.length])
            if (!ready) return
            guided.current = false
            images.push(image); poses.push(data.pose); setCount(images.length)
            if (images.length === 3) callback.current(images)
          } catch (error) { if (!closed) setNotice(error instanceof Error ? error.message : 'Câmera indisponível.') }
          finally { pending = false }
        }, 800)
      } catch { stream?.getTracks().forEach(t => t.stop()); if (!closed) setNotice('Não foi possível abrir a câmera. Confira a permissão e a conexão.') }
    })()
    return () => { closed = true; abort.abort(); clearInterval(timer); stream?.getTracks().forEach(t => t.stop()) }
  }, [selected])
  return <div>
    <label>Câmera <select value={selected} onChange={e => setSelected(e.target.value)}>{cameras.map(c => <option key={c.id} value={c.id}>{cameraLabel(c)}</option>)}</select></label>
    <video ref={video} autoPlay muted playsInline style={{ width: '100%', maxHeight: 260 }} />
    <p aria-live="polite">{posePrompts[count] || 'Posições coletadas.'} {count} de 3</p>
    <p role="status">{notice}</p>
  </div>
}
