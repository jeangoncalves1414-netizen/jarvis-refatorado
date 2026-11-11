import { useState } from 'react'
import { getVoiceSpeed, saveVoiceSpeed, type VoiceSpeed } from '../utils/voiceSpeed'

export function VoiceSpeedSettings() {
  const [settings, setSettings] = useState(getVoiceSpeed)
  const [capture, setCapture] = useState(false)
  const change = (patch: Partial<VoiceSpeed>) => {
    const next = { ...settings, ...patch }
    saveVoiceSpeed(next)
    setSettings(next)
  }
  return <article className="settings-card">
    <p className="eyebrow">VELOCIDADE DA FALA</p>
    <h2>Ritmo da voz do agente</h2>
    <label className="field-label">Velocidade padrão: {settings.normal.toFixed(2)}×
      <input aria-label="Velocidade padrão de fala" type="range" min="0.5" max="3" step="0.05" value={settings.normal} onChange={e => change({ normal: Number(e.target.value) })} />
    </label>
    <label className="field-label">Enquanto segura a tecla: {settings.held.toFixed(2)}×
      <input aria-label="Velocidade ao segurar a tecla" type="range" min="0.5" max="3" step="0.05" value={settings.held} onChange={e => change({ held: Number(e.target.value) })} />
    </label>
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 16 }}><button type="button" className="outline-button" onClick={() => setCapture(true)} onBlur={() => setCapture(false)} onKeyDown={e => {
      if (!capture) return
      e.preventDefault(); e.stopPropagation()
      if (e.code !== 'Escape') change({ key: e.code })
      setCapture(false)
    }}>{capture ? 'Pressione uma tecla (Esc cancela)' : `Tecla de velocidade: ${settings.key || 'Desativada'}`}</button>
    <button type="button" className="outline-button" onClick={() => change({ key: '' })}>Desativar atalho</button></div>
    <p className="settings-muted">Salvo automaticamente neste dispositivo. Com o app em foco, segure a tecla para mudar a velocidade e solte para voltar ao padrão. Teclas de letras e números não ativam o atalho enquanto você digita. Padrão: Ctrl direito.</p>
  </article>
}
