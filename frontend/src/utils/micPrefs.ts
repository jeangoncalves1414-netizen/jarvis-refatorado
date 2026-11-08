const MIC_DEVICE_KEY = 'jarvis_mic_device'

export function getPreferredMicDevice(): string {
  try { return localStorage.getItem(MIC_DEVICE_KEY) || '' } catch { return '' }
}

export function setPreferredMicDevice(deviceId: string): void {
  try {
    if (deviceId) localStorage.setItem(MIC_DEVICE_KEY, deviceId)
    else localStorage.removeItem(MIC_DEVICE_KEY)
  } catch { /* ignore */ }
}

/** Restrições de áudio com o dispositivo de entrada escolhido em Configurações (se houver). */
export function micAudioConstraints(base: MediaTrackConstraints = {}): MediaTrackConstraints {
  const deviceId = getPreferredMicDevice()
  return deviceId ? { ...base, deviceId: { ideal: deviceId } } : base
}
