import { useCallback, useEffect, useRef, useState } from 'react'
import Hls from 'hls.js'

type VideoEpisode = { season?: number; episode?: number; title?: string }

type VideoPlayerProps = {
  src: string
  onClose: () => void
  title?: string
  mediaType?: 'movie' | 'tv'
  currentSeason?: number | null
  currentEpisode?: number | null
  episodes?: VideoEpisode[]
  onNextEpisode?: () => void
}

function formatTime(seconds: number) {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00'
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const remainder = Math.floor(seconds % 60).toString().padStart(2, '0')
  return hours ? `${hours}:${minutes.toString().padStart(2, '0')}:${remainder}` : `${minutes}:${remainder}`
}

function isDirectMedia(url: string) {
  return /\.(?:m3u8|mp4|webm|ogv|mov|m4v)(?:$|[?#])/i.test(url)
}

export function VideoPlayer({
  src,
  onClose,
  title = 'Jarvis Cinema',
  mediaType = 'movie',
  currentSeason,
  currentEpisode,
  episodes = [],
  onNextEpisode,
}: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const playerRef = useRef<HTMLElement>(null)
  const hlsRef = useRef<Hls | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [volume, setVolume] = useState(0.8)
  const [muted, setMuted] = useState(false)
  const [speed, setSpeed] = useState(1)
  const [error, setError] = useState('')
  const direct = isDirectMedia(src)

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) void playerRef.current?.requestFullscreen?.()
    else void document.exitFullscreen?.()
  }

  useEffect(() => {
    const video = videoRef.current
    if (!video || !direct) return
    setError('')
    setCurrentTime(0)
    setDuration(0)
    const isHls = /\.m3u8(?:$|[?#])/i.test(src)
    if (isHls && !video.canPlayType('application/vnd.apple.mpegurl')) {
      if (!Hls.isSupported()) {
        setError('Este navegador não possui suporte a HLS.')
        return
      }
      const hls = new Hls({ enableWorker: true, lowLatencyMode: true, maxBufferLength: 30 })
      hls.loadSource(src)
      hls.attachMedia(video)
      hls.on(Hls.Events.ERROR, (_, data) => {
        if (data.fatal) setError('Não foi possível carregar esta fonte HLS. A URL pode exigir sessão ou estar expirada.')
      })
      hlsRef.current = hls
    } else {
      video.src = src
      video.load()
    }
    return () => {
      hlsRef.current?.destroy()
      hlsRef.current = null
      video.pause()
      video.removeAttribute('src')
      video.load()
    }
  }, [src, direct])

  const togglePlay = useCallback(async () => {
    const video = videoRef.current
    if (!video || !direct) return
    try {
      if (video.paused) await video.play()
      else video.pause()
    } catch {
      setError('O navegador bloqueou a reprodução automática. Clique em reproduzir para iniciar.')
    }
  }, [direct])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement) return
      if (event.key === 'Escape') onClose()
      if (event.key === ' ' && direct) { event.preventDefault(); void togglePlay() }
      if (event.key.toLowerCase() === 'f') toggleFullscreen()
      if (event.key === 'ArrowRight' && videoRef.current) videoRef.current.currentTime += 10
      if (event.key === 'ArrowLeft' && videoRef.current) videoRef.current.currentTime -= 10
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [direct, onClose, togglePlay])

  const episodeLabel = mediaType === 'tv' && currentSeason && currentEpisode
    ? `T${currentSeason}:E${currentEpisode}`
    : ''
  const hasNext = mediaType === 'tv' && episodes.some(item =>
    (item.season || 1) > (currentSeason || 1) || ((item.season || 1) === (currentSeason || 1) && (item.episode || 1) > (currentEpisode || 1)),
  )

  return <section ref={playerRef} className="video-player player-layout" data-player-kind={direct ? 'media' : 'embedded-page'}>
    {direct ? (
      <video
        ref={videoRef}
        playsInline
        preload="metadata"
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onTimeUpdate={event => setCurrentTime(event.currentTarget.currentTime)}
        onLoadedMetadata={event => setDuration(event.currentTarget.duration)}
        onEnded={() => { if (hasNext) onNextEpisode?.() }}
        onError={() => setError('A fonte não respondeu como um vídeo direto compatível.')}
      />
    ) : (
      <iframe
        className="cinema-page-frame"
        src={src}
        title={title}
        allow="autoplay; fullscreen; picture-in-picture; encrypted-media"
        allowFullScreen
        referrerPolicy="strict-origin-when-cross-origin"
      />
    )}
    <div className="video-vignette" />
    <div className="player-topbar player-controls-top">
      <div><strong>{title}</strong>{episodeLabel && <small>{episodeLabel}</small>}</div>
      <div className="player-top-actions">
        {!direct && <button type="button" onClick={() => window.open(src, '_blank', 'noopener,noreferrer')} title="Abrir fonte">Abrir fonte</button>}
        <button type="button" onClick={toggleFullscreen} title="Tela cheia">⛶</button>
        <button type="button" onClick={onClose} aria-label="Fechar player">×</button>
      </div>
    </div>
    {!direct && <div className="cinema-embed-hint">Página incorporada. Se ficar vazia, o site bloqueia iframe ou exige DRM/login; o Jarvis não contorna essa proteção.</div>}
    {direct && <button className="video-big-play" onClick={() => void togglePlay()} aria-label={isPlaying ? 'Pausar' : 'Reproduzir'}>{isPlaying ? 'Ⅱ' : '▶'}</button>}
    {error && <p className="player-error" role="alert">{error}</p>}
    {direct && <div className="player-controls player-controls-bottom">
      <div className="player-progress-row">
        <span>{formatTime(currentTime)}</span>
        <input aria-label="Progresso" type="range" min="0" max={duration || 0} step="0.1" value={currentTime} onChange={event => { const value = Number(event.target.value); if (videoRef.current) videoRef.current.currentTime = value; setCurrentTime(value) }} />
        <span>{formatTime(duration)}</span>
      </div>
      <div className="player-action-row">
        <button type="button" onClick={() => void togglePlay()}>{isPlaying ? 'Pausar' : 'Reproduzir'}</button>
        <button type="button" onClick={() => { const next = !muted; setMuted(next); if (videoRef.current) videoRef.current.muted = next }}>{muted ? 'Som off' : 'Som'}</button>
        <input className="volume" aria-label="Volume" type="range" min="0" max="1" step="0.05" value={volume} onChange={event => { const next = Number(event.target.value); setVolume(next); if (videoRef.current) { videoRef.current.volume = next; videoRef.current.muted = false }; setMuted(false) }} />
        <select aria-label="Velocidade" value={speed} onChange={event => { const next = Number(event.target.value); setSpeed(next); if (videoRef.current) videoRef.current.playbackRate = next }}>{[0.5, 1, 1.25, 1.5, 2].map(option => <option value={option} key={option}>{option}x</option>)}</select>
        {hasNext && <button className="player-next" type="button" onClick={onNextEpisode}>Próximo episódio ›</button>}
      </div>
    </div>}
  </section>
}
