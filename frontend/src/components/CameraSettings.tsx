import { useState } from 'react'
import { cameraLabel, detectCameraDevices, readCameraCatalog, registerDetectedCameras, saveCameraCatalog, type SavedCamera } from '../utils/cameraCatalog'

export function CameraSettings() {
  const [cameras, setCameras] = useState(readCameraCatalog)
  const [connected, setConnected] = useState<string[]>([])
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const detect = async () => {
    setBusy(true); setNotice('')
    try {
      const devices = await detectCameraDevices()
      setConnected(devices.filter(d => d.kind === 'videoinput').map(d => d.deviceId))
      setCameras(registerDetectedCameras(devices))
      setNotice('Lista atualizada. Os números permanecem iguais quando você reconecta uma câmera.')
    } catch { setNotice('Não consegui listar as câmeras. Confira a conexão USB e a permissão do navegador.') }
    finally { setBusy(false) }
  }
  const update = (id: string, change: Partial<SavedCamera>) => {
    const next = cameras.map(c => c.id === id ? { ...c, ...change } : c)
    saveCameraCatalog(next); setCameras(next)
  }
  return <article className="settings-card">
    <h3>Câmeras</h3>
    <p>Detecte as webcams deste computador e dê um nome, como Sala ou Quarto. Depois peça “olha na câmera 2”, “olha na câmera da sala” ou “olha todas as câmeras”.</p>
    <button disabled={busy} onClick={detect}>{busy ? 'Detectando…' : 'Detectar câmeras USB'}</button>
    {cameras.map(camera => <div key={camera.id} className="settings-field">
      <label>Câmera {camera.number} <input aria-label={`Nome da câmera ${camera.number}`} value={camera.name} maxLength={80} onChange={e => update(camera.id, { name: e.target.value })} /></label>
      <label><input type="checkbox" checked={camera.enabled} onChange={e => update(camera.id, { enabled: e.target.checked })} /> Usar {cameraLabel(camera)}</label>
      {connected.length > 0 && <small>{connected.includes(camera.id) ? 'Conectada' : 'Não detectada nesta consulta'}</small>}
    </div>)}
    <p role="status">{notice}</p>
    <small>O navegador lista webcams locais. Câmeras IP ainda não são suportadas.</small>
  </article>
}
