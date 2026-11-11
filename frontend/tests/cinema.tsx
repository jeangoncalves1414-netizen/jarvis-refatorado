import { useState } from 'react'
import { createRoot } from 'react-dom/client'
import { CinemaModal } from '../src/components/CinemaModal'
import { useCinema } from '../src/hooks/useCinema'
import { VideoPlayer } from '../src/components/VideoPlayer'
import '../src/styles.css'

function Harness() {
  const cinema = useCinema()
  const [played, setPlayed] = useState('')
  const [playerOpen, setPlayerOpen] = useState(false)
  return <>
    <button onClick={() => cinema.setCinemaLauncherOpen(true)}>Abrir Cinema</button>
    <button onClick={() => cinema.openCinemaPayload({ title: 'Série do agente', catalog_results: [{ id: 'tt9876543', title: 'Série do agente', type: 'tv', year: '2026', description: 'Sinopse preservada.' }] })}>Resultado do agente</button>
    <output data-testid="played">{played}</output>
    <button onClick={() => setPlayerOpen(true)}>Testar player HLS</button>
    {playerOpen && <VideoPlayer src="/tests/fixtures/cinema/master.m3u8" onClose={() => setPlayerOpen(false)} mediaType="tv" currentSeason={1} currentEpisode={1} episodes={[{ season: 1, episode: 1 }, { season: 2, episode: 3 }]} onSelectEpisode={async (season, episode) => { setPlayed(`T${season}E${episode}`); return true }} />}
    <CinemaModal {...cinema} open={cinema.cinemaLauncherOpen} onClose={() => cinema.setCinemaLauncherOpen(false)} onPlay={setPlayed} />
  </>
}
createRoot(document.getElementById('root')!).render(<Harness />)
