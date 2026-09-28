import { ReactorCommandCard } from './ReactorCommandCard'
import type { Weather } from '../types'

export type DashboardHeroProps = {
  weather: Weather | null
  onOpenCinema: () => void
  onCaptureVision?: () => void
  onToggleVoice?: () => void
  onOpenLiveCall?: () => void
  onDetachOverlay?: () => void
  recording?: boolean
}

export function DashboardHero({
  weather,
  onOpenCinema,
  onCaptureVision,
  onToggleVoice,
  onOpenLiveCall,
  onDetachOverlay,
  recording = false,
}: DashboardHeroProps) {
  return (
    <div className="hero-section-wrapper">
      <ReactorCommandCard
        weather={weather}
        onOpenCinema={onOpenCinema}
        onCaptureVision={onCaptureVision}
        onToggleVoice={onToggleVoice}
        onOpenLiveCall={onOpenLiveCall}
        onDetachOverlay={onDetachOverlay}
        recording={recording}
      />
    </div>
  )
}
