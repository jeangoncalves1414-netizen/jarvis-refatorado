export type SavedCamera = { id: string; number: number; name: string; enabled: boolean }
const key = 'jarvis-camera-catalog'
export const normalizeCameraText = (text: string) => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()

export function readCameraCatalog(): SavedCamera[] {
  try {
    const value = JSON.parse(localStorage.getItem(key) || '[]')
    return Array.isArray(value) ? value.filter(c => c && typeof c.id === 'string' && c.id && Number.isInteger(c.number) && c.number > 0 && typeof c.name === 'string' && typeof c.enabled === 'boolean') : []
  } catch { return [] }
}

export function saveCameraCatalog(cameras: SavedCamera[]) {
  localStorage.setItem(key, JSON.stringify(cameras))
}

export function registerDetectedCameras(devices: MediaDeviceInfo[]): SavedCamera[] {
  const cameras = readCameraCatalog()
  let oldNames: Record<string, string> = {}
  try { const saved = JSON.parse(localStorage.getItem('jarvis-camera-names') || '{}'); if (saved && typeof saved === 'object' && !Array.isArray(saved)) oldNames = saved } catch { /* optional migration */ }
  for (const device of devices) {
    if (device.kind !== 'videoinput' || !device.deviceId || cameras.some(c => c.id === device.deviceId)) continue
    cameras.push({ id: device.deviceId, number: Math.max(0, ...cameras.map(c => c.number)) + 1,
      name: typeof oldNames[device.deviceId] === 'string' ? oldNames[device.deviceId] : device.label || '', enabled: true })
  }
  saveCameraCatalog(cameras)
  return cameras
}

export const cameraLabel = (camera: SavedCamera) => `Câmera ${camera.number}${camera.name ? ` (${camera.name})` : ''}`

export async function detectCameraDevices(): Promise<MediaDeviceInfo[]> {
  let devices = await navigator.mediaDevices.enumerateDevices()
  if (!devices.some(d => d.kind === 'videoinput' && d.deviceId && d.label)) {
    const permission = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
    permission.getTracks().forEach(track => track.stop())
    devices = await navigator.mediaDevices.enumerateDevices()
  }
  return devices
}

export async function openConfiguredCamera(deviceId?: string): Promise<MediaStream> {
  const devices = await detectCameraDevices()
  const available = registerDetectedCameras(devices).filter(c => c.enabled && devices.some(d => d.kind === 'videoinput' && d.deviceId === c.id))
  const candidates = deviceId ? available.filter(c => c.id === deviceId) : available
  for (const camera of candidates) {
    try { return await navigator.mediaDevices.getUserMedia({ video: { deviceId: { exact: camera.id } }, audio: false }) }
    catch { /* Try the next enabled camera only when none was explicitly selected. */ }
  }
  throw new Error('Nenhuma câmera habilitada está disponível. Confira Configurações → Câmeras.')
}

export function requestedCameras(message: string, cameras: SavedCamera[]): SavedCamera[] | null {
  const text = normalizeCameraText(message)
  const number = text.match(/\b(?:camera|webcam)\s*(?:numero\s*)?(\d+)\b/)
  if (number) return cameras.filter(c => c.number === Number(number[1]))
  if (/\b(?:todas|todos)\s+(?:as\s+|os\s+)?(?:cameras|webcams)\b/.test(text)) return cameras
  const named = cameras.filter(c => {
    const name = normalizeCameraText(c.name).trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    return name && new RegExp(`(?:^|[^\\p{L}\\p{N}])${name}(?=$|[^\\p{L}\\p{N}])`, 'u').test(text)
  })
  if (named.length) return named.length === 1 ? named : null
  // An explicit unknown location must never fall back to a different camera.
  if (/\b(?:camera|webcam)\s+(?:da|do|de)\s+\w+/.test(text)) return []
  return cameras
}
