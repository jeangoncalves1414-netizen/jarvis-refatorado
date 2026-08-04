import { JarvisOrb } from './JarvisOrb'
import { ShiningText } from './ShiningText'
import { StatusBadge } from './StatusBadge'
import type { Weather } from '../types'

export function DashboardHero({
  weather,
  onOpenCinema,
}: {
  weather: Weather | null
  onOpenCinema: () => void
}) {
  return (
    <div className="content-grid">
      <section className="hero-card">
        <JarvisOrb size={180} className="hero-orb" />
        <div className="hero-copy">
          <p>Bom dia, Maria.</p>
          <h2>
            O que vamos fazer
            <br />
            <ShiningText text="agora?" />
          </h2>
          <span>Seu hub pessoal está conectado e pronto.</span>
          <div className="hero-status-row">
            <StatusBadge status="success">Núcleo local online</StatusBadge>
            <StatusBadge status={weather ? 'info' : 'pending'}>{weather ? 'Clima sincronizado' : 'Sincronizando clima'}</StatusBadge>
          </div>
          <button type="button" className="hero-tool" onClick={onOpenCinema}>
            ◉ Abrir mídia
          </button>
        </div>
      </section>
      <section className="weather-card">
        <p className="eyebrow">AMBIENTE</p>
        <strong>{weather?.temp_c !== undefined ? `${Math.round(weather.temp_c)}°` : '—'}</strong>
        <span>{weather?.city || 'Clima local'}</span>
        <small>{weather?.description || 'Atualizando condições'}</small>
      </section>
    </div>
  )
}
