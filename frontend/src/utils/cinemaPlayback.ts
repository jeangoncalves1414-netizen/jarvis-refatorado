import Hls from 'hls.js'
import type { CinemaMedia } from '../types'

/** Confirma metadados no mesmo navegador/origem do player, incluindo CORS do HLS. */
export function checkCinemaMedia(media: CinemaMedia, signal: AbortSignal, timeoutMs = 6500): Promise<CinemaMedia> {
  if (signal.aborted || media.direct === false) return Promise.resolve({ ...media, compatible: false, verification: signal.aborted ? 'cancelled' : 'embedded' })
  return new Promise(resolve => {
    const video = document.createElement('video')
    video.muted = true
    // loadeddata requires a decoded frame; metadata-only preload may never emit it.
    video.preload = 'auto'
    let hls: Hls | undefined
    let done = false
    const finish = (compatible: boolean, verification: CinemaMedia['verification'] = compatible ? 'confirmed' : 'failed') => {
      if (done) return
      done = true
      const qualities = hls?.levels.map(level => `${level.height}p`).filter(label => label !== '0p') || []
      const audio_tracks = hls?.audioTracks.map(track => track.name || track.lang || 'Áudio') || []
      clearTimeout(timer)
      signal.removeEventListener('abort', abort)
      video.onloadeddata = null; video.onerror = null
      hls?.destroy()
      video.pause(); video.removeAttribute('src'); video.load()
      resolve({ ...media, compatible, verification, qualities: [...new Set(qualities)], audio_tracks: [...new Set(audio_tracks)] })
    }
    const abort = () => finish(false, 'cancelled')
    const timer = window.setTimeout(() => finish(false, 'timeout'), timeoutMs)
    signal.addEventListener('abort', abort, { once: true })
    video.onloadeddata = () => finish(video.videoWidth > 0)
    video.onerror = () => finish(false)
    if ((media.kind === 'HLS' || /\.m3u8(?:$|[?#])/i.test(media.url)) && Hls.isSupported()) {
      hls = new Hls({ enableWorker: false, maxBufferLength: 1, maxMaxBufferLength: 2, maxBufferSize: 2_000_000 })
      hls.on(Hls.Events.ERROR, (_, data) => { if (data.fatal) finish(false) })
      hls.attachMedia(video); hls.loadSource(media.url)
    } else {
      video.src = media.url; video.load()
    }
  })
}
