import { forwardRef, useEffect, useImperativeHandle, useRef, useState, type CSSProperties } from 'react'
import { BackgroundPattern } from './BackgroundPattern'
import { CameraDock } from './CameraDock'

type Camera = {
  id: string
  label: string
  stream: MediaStream
  scale: number
  x: number
  y: number
}

type CameraLayout = Pick<Camera, 'x' | 'y' | 'scale'>

export type CameraWorkspaceHandle = {
  captureSelectedFrame: () => Promise<{ image: string; cameraName: string } | null>
}

type CameraWorkspaceProps = {
  open: boolean
  initialQuestion?: string
  onClose: () => void
  onQuestion: (image: string, cameraName: string, prompt?: string) => Promise<void>
}

const nameStorageKey = 'jarvis-camera-names'
const layoutStorageKey = 'jarvis-camera-layouts'

function getCameraNames(): Record<string, string> {
  try { return JSON.parse(localStorage.getItem(nameStorageKey) || '{}') } catch { return {} }
}

function getCameraLayouts(): Record<string, CameraLayout> {
  try {
    const saved = JSON.parse(localStorage.getItem(layoutStorageKey) || '{}') as Record<string, CameraLayout>
    return Object.fromEntries(Object.entries(saved).filter(([, layout]) => (
      Number.isFinite(layout?.x) && Number.isFinite(layout?.y) && Number.isFinite(layout?.scale)
    )))
  } catch { return {} }
}

export const CameraWorkspace = forwardRef<CameraWorkspaceHandle, CameraWorkspaceProps>(function CameraWorkspace({ open, initialQuestion = '', onClose, onQuestion }, ref) {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [status, setStatus] = useState('')
  const [question, setQuestion] = useState('')
  const [renameModeId, setRenameModeId] = useState('')
  const [renameValue, setRenameValue] = useState('')
  const [resizeModeId, setResizeModeId] = useState('')
  const [pattern, setPattern] = useState<'grid' | 'dots'>('grid')
  const [viewport, setViewport] = useState({ x: 0, y: 0, zoom: 1 })
  const videoRefs = useRef<Record<string, HTMLVideoElement | null>>({})
  const panStart = useRef<{ x: number; y: number; viewportX: number; viewportY: number } | null>(null)
  const frameDragRef = useRef<{ id: string; x: number; y: number; startX: number; startY: number } | null>(null)
  const resizeDragRef = useRef<{ id: string; scale: number; startX: number; startY: number } | null>(null)
  const streamRequestRef = useRef(0)
  const deviceChangeTimerRef = useRef<number | null>(null)

  const stopStreams = () => {
    streamRequestRef.current += 1
    setCameras(previous => {
      previous.forEach(camera => camera.stream.getTracks().forEach(track => track.stop()))
      return []
    })
    videoRefs.current = {}
    setSelectedId('')
    setResizeModeId('')
  }

  const startCameras = async () => {
    if (!navigator.mediaDevices?.getUserMedia || !navigator.mediaDevices?.enumerateDevices) {
      setStatus('Este navegador não oferece acesso a câmeras.')
      return
    }
    stopStreams()
    const requestId = streamRequestRef.current
    setStatus('Solicitando permissão para listar suas câmeras…')
    try {
      // This temporary stream makes device labels available. It is stopped immediately.
      const permissionStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
      permissionStream.getTracks().forEach(track => track.stop())
      if (requestId !== streamRequestRef.current) return
      const devices = (await navigator.mediaDevices.enumerateDevices()).filter(device => device.kind === 'videoinput')
      if (requestId !== streamRequestRef.current) return
      const names = getCameraNames()
      const layouts = getCameraLayouts()
      const started = await Promise.all(devices.map(async (device, index) => {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ video: { deviceId: { exact: device.deviceId } }, audio: false })
          return {
            id: device.deviceId,
            label: names[device.deviceId] || device.label || `Câmera ${index + 1}`,
            stream,
            scale: Math.min(2, Math.max(0.5, layouts[device.deviceId]?.scale ?? 1)),
            x: layouts[device.deviceId]?.x ?? 90 + (index % 3) * 350,
            y: layouts[device.deviceId]?.y ?? 80 + Math.floor(index / 3) * 270,
          } satisfies Camera
        } catch { return null }
      }))
      const available = started.filter((item): item is Camera => item !== null)
      if (requestId !== streamRequestRef.current) {
        available.forEach(camera => camera.stream.getTracks().forEach(track => track.stop()))
        return
      }
      setCameras(available)
      setSelectedId(available[0]?.id || '')
      setStatus(available.length ? `${available.length} câmera(s) ao vivo. A análise só acontece quando você pedir.` : 'Nenhuma câmera disponível pôde ser aberta.')
    } catch {
      setStatus('Permissão de câmera negada ou indisponível. Libere o acesso e tente novamente.')
    }
  }

  useEffect(() => {
    if (open) startCameras()
    else stopStreams()
    return () => stopStreams()
  // Starting is intentionally tied only to opening this private workspace.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  useEffect(() => {
    if (!open || !navigator.mediaDevices?.addEventListener) return
    const refreshOnDeviceChange = () => {
      if (deviceChangeTimerRef.current) window.clearTimeout(deviceChangeTimerRef.current)
      deviceChangeTimerRef.current = window.setTimeout(() => {
        setStatus('Alteração de câmera detectada. Atualizando transmissões…')
        startCameras()
      }, 500)
    }
    navigator.mediaDevices.addEventListener('devicechange', refreshOnDeviceChange)
    return () => {
      navigator.mediaDevices.removeEventListener('devicechange', refreshOnDeviceChange)
      if (deviceChangeTimerRef.current) window.clearTimeout(deviceChangeTimerRef.current)
    }
  // The listener is registered only while this local workspace is open.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  useEffect(() => {
    if (open && initialQuestion) setQuestion(initialQuestion)
  }, [open, initialQuestion])

  useEffect(() => {
    cameras.forEach(camera => {
      const video = videoRefs.current[camera.id]
      if (video && video.srcObject !== camera.stream) {
        video.srcObject = camera.stream
        video.play().catch(() => undefined)
      }
    })
  }, [cameras])

  const selected = cameras.find(camera => camera.id === selectedId)
  const saveLayouts = (items: Camera[]) => {
    const saved = getCameraLayouts()
    items.forEach(({ id, x, y, scale }) => { saved[id] = { x, y, scale } })
    localStorage.setItem(layoutStorageKey, JSON.stringify(saved))
  }

  const updateCamera = (id: string, change: (camera: Camera) => Camera) => {
    setCameras(previous => {
      const next = previous.map(camera => camera.id === id ? change(camera) : camera)
      saveLayouts(next)
      return next
    })
  }

  const updateSelected = (change: (camera: Camera) => Camera) => {
    if (!selectedId) return
    updateCamera(selectedId, change)
  }

  const renameSelected = () => {
    if (!selected) return
    setRenameModeId(selected.id)
    setRenameValue(selected.label)
  }

  const saveRename = () => {
    if (!selectedId || !renameValue.trim()) {
      setRenameModeId('')
      setRenameValue('')
      return
    }
    const names = getCameraNames()
    names[selectedId] = renameValue.trim()
    localStorage.setItem(nameStorageKey, JSON.stringify(names))
    updateSelected(camera => ({ ...camera, label: renameValue.trim() }))
    setRenameModeId('')
    setRenameValue('')
  }

  const cancelRename = () => {
    setRenameModeId('')
    setRenameValue('')
  }

  const captureSelectedFrame = async () => {
    if (!selected) return null
    const video = videoRefs.current[selected.id]
    if (!video || video.videoWidth === 0 || video.videoHeight === 0) {
      setStatus('A prévia da câmera ainda não está pronta.')
      return null
    }
    const canvas = document.createElement('canvas')
    const maxWidth = 1280
    const ratio = Math.min(1, maxWidth / video.videoWidth)
    canvas.width = Math.round(video.videoWidth * ratio)
    canvas.height = Math.round(video.videoHeight * ratio)
    canvas.getContext('2d')?.drawImage(video, 0, 0, canvas.width, canvas.height)
    return { image: canvas.toDataURL('image/jpeg', 0.85), cameraName: selected.label }
  }

  useImperativeHandle(ref, () => ({ captureSelectedFrame }), [selected, cameras])

  const analyzeSelected = async (prompt?: string) => {
    const capture = await captureSelectedFrame()
    if (!capture) return
    setStatus(`Enviando um único frame da ${capture.cameraName} para análise…`)
    await onQuestion(capture.image, capture.cameraName, prompt)
  }

  const closeWorkspace = () => {
    stopStreams()
    onClose()
  }

  if (!open) return null
  return <div className="camera-workspace-modal" role="dialog" aria-modal="true" aria-label="Espaço de câmeras">
    <section className="camera-workspace">
      <BackgroundPattern variant={pattern} mask="fade-edges" />
      <header className="camera-workspace-header">
        <div><p className="eyebrow">VISÃO · ESPAÇO LOCAL</p><h2>Plano de câmeras</h2><small>{status}</small></div>
        <div className="camera-workspace-actions"><button type="button" onClick={() => setPattern(value => value === 'grid' ? 'dots' : 'grid')}>{pattern === 'grid' ? 'Dots' : 'Grid'}</button><button type="button" onClick={startCameras}>Atualizar</button><button type="button" className="camera-close" onClick={closeWorkspace}>×</button></div>
      </header>
      <div
        className="camera-canvas"
        onWheel={event => {
          event.preventDefault()
          setViewport(previous => ({ ...previous, zoom: Math.min(1.8, Math.max(0.55, previous.zoom - event.deltaY * 0.001)) }))
        }}
        onPointerDown={event => {
          if ((event.target as HTMLElement).closest('.camera-frame')) return
          event.currentTarget.setPointerCapture(event.pointerId)
          panStart.current = { x: event.clientX, y: event.clientY, viewportX: viewport.x, viewportY: viewport.y }
        }}
        onPointerMove={event => {
          if (!panStart.current) return
          setViewport(previous => ({ ...previous, x: panStart.current!.viewportX + event.clientX - panStart.current!.x, y: panStart.current!.viewportY + event.clientY - panStart.current!.y }))
        }}
        onPointerUp={() => { panStart.current = null }}
      >
        <div className="camera-world" style={{ transform: `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.zoom})` }}>
          {cameras.map((camera, index) => <article
            key={camera.id}
            className={camera.id === selectedId ? 'camera-frame selected' : 'camera-frame'}
            style={{ left: camera.x, top: camera.y, transform: `scale(${camera.scale})`, '--camera-delay': `${index * 70}ms` } as CSSProperties}
            onPointerDown={event => {
              if (event.button !== 0 || resizeDragRef.current) return
              event.stopPropagation()
              setSelectedId(camera.id)
              event.currentTarget.setPointerCapture(event.pointerId)
              frameDragRef.current = { id: camera.id, x: camera.x, y: camera.y, startX: event.clientX, startY: event.clientY }
            }}
            onPointerMove={event => {
              const drag = frameDragRef.current
              if (!drag || drag.id !== camera.id) return
              const zoom = viewport.zoom
              updateCamera(camera.id, item => ({ ...item, x: drag.x + (event.clientX - drag.startX) / zoom, y: drag.y + (event.clientY - drag.startY) / zoom }))
            }}
            onPointerUp={event => {
              if (frameDragRef.current?.id === camera.id) frameDragRef.current = null
              if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
            }}
            onPointerCancel={() => { frameDragRef.current = null }}
          >
            <video ref={element => { videoRefs.current[camera.id] = element }} autoPlay muted playsInline />
            {camera.id === renameModeId ? (
              <div className="camera-name-edit">
                <input
                  type="text"
                  value={renameValue}
                  onChange={e => setRenameValue(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter') saveRename()
                    if (e.key === 'Escape') cancelRename()
                  }}
                  autoFocus
                />
                <button type="button" onClick={saveRename}>✓</button>
                <button type="button" onClick={cancelRename}>✕</button>
              </div>
            ) : (
              <span className="camera-name"><i />{camera.label}</span>
            )}
            <span className="camera-live">AO VIVO</span>
            {camera.id === selectedId && <CameraDock
              resizing={resizeModeId === camera.id}
              onResize={() => setResizeModeId(current => current === camera.id ? '' : camera.id)}
              onRename={renameSelected}
              onFocus={() => updateSelected(item => ({ ...item, scale: 1.5, x: 360, y: 140 }))}
              onAnalyze={analyzeSelected}
            />}
            {camera.id === selectedId && resizeModeId === camera.id && <button
              className="camera-resize-handle"
              type="button"
              aria-label="Arraste para redimensionar proporcionalmente"
              title="Arraste para redimensionar proporcionalmente"
              onPointerDown={event => {
                event.preventDefault()
                event.stopPropagation()
                frameDragRef.current = null
                event.currentTarget.setPointerCapture(event.pointerId)
                resizeDragRef.current = { id: camera.id, scale: camera.scale, startX: event.clientX, startY: event.clientY }
              }}
              onPointerMove={event => {
                const resize = resizeDragRef.current
                if (!resize || resize.id !== camera.id) return
                const delta = ((event.clientX - resize.startX) + (event.clientY - resize.startY)) / (2 * viewport.zoom)
                updateCamera(camera.id, item => ({ ...item, scale: Math.min(2, Math.max(0.5, resize.scale + delta / 300)) }))
              }}
              onPointerUp={event => {
                if (resizeDragRef.current?.id === camera.id) resizeDragRef.current = null
                if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
              }}
              onPointerCancel={() => { resizeDragRef.current = null }}
            ><span>↘</span></button>}
          </article>)}
          {!cameras.length && <div className="camera-empty"><b>Nenhuma transmissão aberta</b><span>Conecte uma câmera e escolha “Atualizar”.</span></div>}
        </div>
      </div>
      <footer className="camera-workspace-footer"><span>Arraste um frame para reposicioná-lo. No modo redimensionar, arraste a alça diagonal; posição e tamanho ficam salvos.</span><form className="camera-question" onSubmit={event => { event.preventDefault(); const prompt = question.trim(); setQuestion(''); analyzeSelected(prompt || undefined).catch(() => undefined) }}><input value={question} onChange={event => setQuestion(event.target.value)} placeholder={selected ? `Pergunte sobre ${selected.label}…` : 'Selecione uma câmera primeiro'} disabled={!selected} /><button disabled={!selected}>Perguntar</button></form></footer>
    </section>
  </div>
})
