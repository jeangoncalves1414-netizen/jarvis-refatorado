import { Eye, Film, Mic, PhoneCall } from 'lucide-react'
import type { Weather } from '../types'

export type DashboardHeroProps = {
  weather: Weather | null
  onOpenCinema: () => void
  onCaptureVision?: () => void
  onToggleVoice?: () => void
  onOpenLiveCall?: () => void
  recording?: boolean
}

export function DashboardHero({ onOpenCinema, onCaptureVision, onToggleVoice, onOpenLiveCall, recording = false }: DashboardHeroProps) {
  return <section className="ws-panel" aria-label="Ferramentas pessoais">
    <div className="ws-filters">
      <button type="button" className="ws-button" onClick={onToggleVoice} aria-pressed={recording}><Mic size={16} />{recording ? 'Parar ditado' : 'Ditar mensagem'}</button>
      <button type="button" className="ws-button" onClick={onOpenLiveCall}><PhoneCall size={16} />Conversa por voz</button>
      <button type="button" className="ws-button" onClick={onCaptureVision}><Eye size={16} />Analisar tela</button>
      <button type="button" className="ws-button" onClick={onOpenCinema}><Film size={16} />Cinema e mídia</button>
    </div>
  </section>
}
