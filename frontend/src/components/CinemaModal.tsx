import { FormEvent, useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import type { CinemaItem, CinemaMedia, CinemaResult } from '../types'

const demoVideo = 'https://videos.pexels.com/video-files/30333849/13003128_2560_1440_25fps.mp4'

type DiscoveryMeta = {
  title?: string
  type?: 'movie' | 'tv'
  poster?: string
  imdb_id?: string
  trailer_url?: string
  watch_url?: string
}

export type CinemaModalProps = {
  open: boolean
  onClose: () => void
  onPlay: (url: string) => void
  cinemaQuery: string
  setCinemaQuery: (q: string) => void
  videoUrl: string
  setVideoUrl: (url: string) => void
  cinemaResults: CinemaResult[]
  cinemaMedia: CinemaMedia[]
  cinemaStatus: string
  setCinemaStatus: (s: string) => void
  cinemaLibrary: CinemaItem[]
  refreshCinemaLibrary: () => Promise<void>
  searchCinema: (e: FormEvent) => void
  probeCinema: (url: string) => Promise<CinemaMedia[]>
  saveCinemaUrl: () => void
  selectedLibraryItem?: CinemaItem
  selectedLibraryId: string
  selectLibraryItem: (id: string) => void
  availableSeasons: number[]
  availableEpisodes: { season?: number; episode?: number; title?: string }[]
  selectedSeason: number | null
  selectedEpisode: number | null
  selectedSourceUrl: string
  selectSeason: (s: number) => void
  selectEpisode: (e: number) => void
  selectLibrarySource: (url: string) => void
  selectNextEpisode: () => string
  selectedLibrarySources: { label?: string; url: string }[]
}

export function CinemaModal(props: CinemaModalProps) {
  const {
    open, onClose, onPlay, cinemaQuery, setCinemaQuery, videoUrl, setVideoUrl,
    cinemaResults, cinemaMedia, cinemaStatus, setCinemaStatus, cinemaLibrary,
    refreshCinemaLibrary, searchCinema, probeCinema, saveCinemaUrl,
    selectedLibraryItem, selectedLibraryId, selectLibraryItem,
    availableSeasons, availableEpisodes, selectedSeason, selectedEpisode,
    selectedSourceUrl, selectSeason, selectEpisode, selectLibrarySource,
    selectNextEpisode, selectedLibrarySources,
  } = props

  const [discovery, setDiscovery] = useState<DiscoveryMeta | null>(null)
  const [playerUrl, setPlayerUrl] = useState('')

  useEffect(() => {
    if (!open) {
      setDiscovery(null)
      setPlayerUrl('')
    }
  }, [open])

  if (!open) return null

  const badge = discovery?.type === 'tv' ? 'SÉRIE' : 'FILME'
  const imdbLink = discovery?.imdb_id ? `https://www.imdb.com/title/${discovery.imdb_id}/` : ''

  const playDiscovery = async (result: CinemaResult) => {
    // Primeiro procuramos uma fonte pública exposta pela própria página.
    // Se não houver, o VideoPlayer tenta incorporar a página respeitando CSP/X-Frame-Options.
    const media = await probeCinema(result.url)
    onPlay(media[0]?.url || result.url)
    onClose()
  }

  return (
    <div className="tool-modal cinema-modal-overlay" role="dialog" aria-modal="true" aria-label="Cinema">
      <motion.section
        className="cinema-modal cinema-modal-rich"
        initial={{ opacity: 0, scale: 0.96, y: 12 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.25 }}
      >
        <button className="modal-close" onClick={onClose} aria-label="Fechar">×</button>
        <header className="cinema-modal-header">
          <div>
            <p className="eyebrow">FERRAMENTA · CINEMA</p>
            <div className="cinema-title-row">
              <span className="cinema-type-badge">{badge}</span>
              <h2>{discovery?.title || 'Encontrar e abrir mídia'}</h2>
            </div>
          </div>
        </header>
        <div className="cinema-modal-body">
          <aside className="cinema-poster-panel">
            {discovery?.poster ? (
              <img src={discovery.poster} alt="Poster" className="cinema-poster" />
            ) : (
              <div className="cinema-poster cinema-poster-placeholder">◉</div>
            )}
            <p className="cinema-poster-hint">Pesquisa somente fontes públicas aprovadas.</p>
            {(discovery?.trailer_url || discovery?.watch_url || imdbLink) && (
              <div className="cinema-link-row">
                {discovery?.trailer_url && <a href={discovery.trailer_url} target="_blank" rel="noopener noreferrer" className="cinema-link-btn primary">Trailer</a>}
                {discovery?.watch_url && <a href={discovery.watch_url} target="_blank" rel="noopener noreferrer" className="cinema-link-btn">Onde assistir</a>}
                {imdbLink && <a href={imdbLink} target="_blank" rel="noopener noreferrer" className="cinema-link-btn muted">IMDb</a>}
              </div>
            )}
          </aside>
          <div className="cinema-main-panel">
            {playerUrl ? (
              <div className="cinema-player-embed">
                <video src={playerUrl} controls playsInline className="cinema-inline-video" />
              </div>
            ) : (
              <div className="cinema-discovery-state">
                <span className="cinema-discovery-icon">◉</span>
                <p>Jarvis Cinema</p>
                <small>Detecte mídia ou cole uma URL para reproduzir.</small>
              </div>
            )}
            <form className="cinema-search" onSubmit={searchCinema}>
              <input autoFocus value={cinemaQuery} onChange={e => setCinemaQuery(e.target.value)} placeholder="Pesquisar título…" />
              <button type="submit">Pesquisar</button>
            </form>
            <div className="source-row">
              <input value={videoUrl} onChange={e => setVideoUrl(e.target.value)} placeholder="Ou cole URL MP4, WebM ou HLS" />
              <button type="button" onClick={() => { onPlay(videoUrl); onClose() }}>Reproduzir</button>
              <button type="button" className="save-source" onClick={saveCinemaUrl}>Salvar</button>
            </div>
            {cinemaStatus && <p className="cinema-status">{cinemaStatus}</p>}
            <div className="cinema-results">
              {cinemaResults.map((result, index) => (
                <article key={`${result.url}-${index}`}>
                  <div><b>{result.title || result.source || 'Resultado'}</b><small>{result.source}</small><p>{result.media_hint || result.snippet}</p></div>
                  <div className="cinema-result-actions">
                    <button type="button" onClick={() => { void playDiscovery(result) }}>Assistir integrado</button>
                    <button type="button" className="text-button" onClick={() => probeCinema(result.url)}>Detectar mídia</button>
                  </div>
                </article>
              ))}
              {cinemaMedia.map((media, index) => (
                <article className="detected-media" key={`${media.url}-${index}`}>
                  <div><b>{media.label || media.kind || 'Vídeo'}</b><small>{media.url}</small></div>
                  <button type="button" onClick={() => { onPlay(media.url); onClose() }}>Assistir</button>
                </article>
              ))}
            </div>
            <div className="library-row">
              <button type="button" className="text-button" onClick={() => refreshCinemaLibrary().catch(() => setCinemaStatus('Não foi possível carregar a biblioteca.'))}>Minha biblioteca</button>
              <button type="button" className="text-button" onClick={() => { onPlay(demoVideo); onClose() }}>Vídeo de teste</button>
            </div>
            {cinemaLibrary.length > 0 && (
              <div className="cinema-library">
                <select value={selectedLibraryId} onChange={e => selectLibraryItem(e.target.value)}>
                  <option value="">Selecione uma mídia salva</option>
                  {cinemaLibrary.map(item => <option key={item.id} value={item.id}>{item.type === 'tv' ? 'Série' : 'Filme'} · {item.title}</option>)}
                </select>
                {selectedLibraryItem?.type === 'tv' && (
                  <div className="library-controls">
                    <select value={selectedSeason || ''} onChange={e => selectSeason(Number(e.target.value))}>
                      {availableSeasons.map(season => <option key={season} value={season}>Temporada {season}</option>)}
                    </select>
                    <select value={selectedEpisode || ''} onChange={e => selectEpisode(Number(e.target.value))}>
                      {availableEpisodes.map(episode => (
                        <option key={`${episode.season}-${episode.episode}`} value={episode.episode || 1}>{episode.title || `Episódio ${episode.episode || 1}`}</option>
                      ))}
                    </select>
                  </div>
                )}
                {selectedLibraryItem && (
                  <>
                    <select value={selectedSourceUrl} onChange={e => selectLibrarySource(e.target.value)}>
                      {selectedLibrarySources.map(source => <option key={source.url} value={source.url}>{source.label || 'Fonte / qualidade'}</option>)}
                    </select>
                    <div className="library-actions">
                      <button type="button" disabled={!selectedSourceUrl} onClick={() => { onPlay(selectedSourceUrl); onClose() }}>Reproduzir</button>
                      {selectedLibraryItem.type === 'tv' && (
                        <button type="button" disabled={!selectedSourceUrl} onClick={() => { const next = selectNextEpisode(); if (next) { onPlay(next); onClose() } }}>Próximo episódio</button>
                      )}
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
        <footer className="cinema-modal-footer"><span>{discovery?.imdb_id ? `IMDb: ${discovery.imdb_id}` : 'IMDb: —'}</span></footer>
      </motion.section>
    </div>
  )
}
