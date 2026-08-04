import { FormEvent, useMemo, useState } from 'react'
import type { CinemaEpisode, CinemaItem, CinemaMedia, CinemaResult, CinemaSource } from '../types'

export function useCinema() {
  const [cinemaLauncherOpen, setCinemaLauncherOpen] = useState(false)
  const [videoUrl, setVideoUrl] = useState('')
  const [cinemaQuery, setCinemaQuery] = useState('')
  const [cinemaResults, setCinemaResults] = useState<CinemaResult[]>([])
  const [cinemaMedia, setCinemaMedia] = useState<CinemaMedia[]>([])
  const [cinemaStatus, setCinemaStatus] = useState('')
  const [cinemaLibrary, setCinemaLibrary] = useState<CinemaItem[]>([])
  const [selectedLibraryId, setSelectedLibraryId] = useState('')
  const [selectedSeason, setSelectedSeason] = useState<number | null>(null)
  const [selectedEpisode, setSelectedEpisode] = useState<number | null>(null)
  const [selectedSourceUrl, setSelectedSourceUrl] = useState('')

  const refreshCinemaLibrary = async () => {
    const response = await fetch('/api/cinema/library')
    const data = await response.json()
    if (!response.ok || !data.ok) throw new Error(data.error || 'Não foi possível carregar a biblioteca.')
    const items = data.items || []
    setCinemaLibrary(items)
    if (selectedLibraryId && !items.some((item: CinemaItem) => item.id === selectedLibraryId)) setSelectedLibraryId('')
  }

  const selectedLibraryItem = useMemo(() => cinemaLibrary.find(item => item.id === selectedLibraryId), [cinemaLibrary, selectedLibraryId])
  const availableSeasons = useMemo(() => [...new Set((selectedLibraryItem?.episodes || []).map(item => item.season || 1))].sort((a, b) => a - b), [selectedLibraryItem])
  const availableEpisodes = useMemo(() => (selectedLibraryItem?.episodes || []).filter(item => (item.season || 1) === (selectedSeason || availableSeasons[0])).sort((a, b) => (a.episode || 1) - (b.episode || 1)), [availableSeasons, selectedLibraryItem, selectedSeason])
  const selectedLibraryEpisode = useMemo<CinemaEpisode | undefined>(() => availableEpisodes.find(item => (item.episode || 1) === (selectedEpisode || availableEpisodes[0]?.episode || 1)), [availableEpisodes, selectedEpisode])
  const selectedLibrarySources = useMemo<CinemaSource[]>(() => selectedLibraryItem?.type === 'tv' ? selectedLibraryEpisode?.sources || [] : selectedLibraryItem?.sources || [], [selectedLibraryEpisode, selectedLibraryItem])

  const selectLibraryItem = (id: string) => {
    const item = cinemaLibrary.find(entry => entry.id === id)
    const firstEpisode = [...(item?.episodes || [])].sort((a, b) => (a.season || 1) - (b.season || 1) || (a.episode || 1) - (b.episode || 1))[0]
    setSelectedLibraryId(id)
    setSelectedSeason(firstEpisode?.season || null)
    setSelectedEpisode(firstEpisode?.episode || null)
    setSelectedSourceUrl(firstEpisode?.sources?.[0]?.url || item?.sources?.[0]?.url || '')
  }

  const selectSeason = (season: number) => {
    const firstEpisode = (selectedLibraryItem?.episodes || []).filter(item => (item.season || 1) === season).sort((a, b) => (a.episode || 1) - (b.episode || 1))[0]
    setSelectedSeason(season)
    setSelectedEpisode(firstEpisode?.episode || null)
    setSelectedSourceUrl(firstEpisode?.sources?.[0]?.url || '')
  }

  const selectEpisode = (episode: number) => {
    const entry = availableEpisodes.find(item => (item.episode || 1) === episode)
    setSelectedEpisode(episode)
    setSelectedSourceUrl(entry?.sources?.[0]?.url || '')
  }

  const selectLibrarySource = (url: string) => setSelectedSourceUrl(url)

  const selectNextEpisode = () => {
    if (selectedLibraryItem?.type !== 'tv') return ''
    const episodes = [...(selectedLibraryItem.episodes || [])].sort((a, b) => (a.season || 1) - (b.season || 1) || (a.episode || 1) - (b.episode || 1))
    const currentIndex = episodes.findIndex(item => (item.season || 1) === selectedSeason && (item.episode || 1) === selectedEpisode)
    const next = episodes[currentIndex + 1]
    if (!next?.sources?.[0]?.url) {
      setCinemaStatus('Não há próximo episódio salvo nesta série.')
      return ''
    }
    setSelectedSeason(next.season || 1)
    setSelectedEpisode(next.episode || 1)
    setSelectedSourceUrl(next.sources[0].url)
    return next.sources[0].url
  }

  const openCinemaPayload = (payload: { title?: string; detect_url?: string; discovery_results?: Array<{ title?: string; url?: string; source?: string; snippet?: string }>; catalog_results?: Array<{ id?: string; title?: string; year?: string | number; description?: string }> }) => {
    const title = String(payload.title || '').trim()
    if (title) setCinemaQuery(title)
    const results = (payload.discovery_results || []).filter(item => item.url).map(item => ({ ...item, url: item.url as string })).concat((payload.catalog_results || []).map(item => ({
      title: item.title,
      url: item.id ? `https://www.imdb.com/title/${item.id}/` : '',
      source: 'IMDb',
      snippet: item.description || (item.year ? `Ano ${item.year}` : ''),
    })).filter(item => item.url))
    if (Array.isArray(results)) {
      setCinemaResults(results)
      setCinemaStatus(results.length ? 'Escolha uma fonte e o Jarvis tentará detectar o player automaticamente.' : 'Nenhuma fonte encontrada.')
    }
    if (payload.detect_url) {
      setVideoUrl(payload.detect_url)
      void probeCinema(payload.detect_url)
    }
    setCinemaLauncherOpen(true)
  }

  const searchCinema = async (event: FormEvent) => {
    event.preventDefault()
    if (!cinemaQuery.trim()) return
    setCinemaStatus('Pesquisando fontes públicas aprovadas…'); setCinemaResults([]); setCinemaMedia([])
    try {
      const response = await fetch(`/api/cinema/discovery/search?q=${encodeURIComponent(cinemaQuery.trim())}`)
      const data = await response.json()
      if (!response.ok || !data.ok) throw new Error(data.error || 'Não foi possível pesquisar.')
      setCinemaResults(data.results || []); setCinemaStatus(data.results?.length ? 'Escolha uma página para detectar a mídia exposta.' : 'Nenhum resultado público encontrado.')
    } catch (error) { setCinemaStatus(error instanceof Error ? error.message : 'Falha na pesquisa.') }
  }

  const probeCinema = async (url: string): Promise<CinemaMedia[]> => {
    setCinemaStatus('Detectando mídia pública…'); setCinemaMedia([])
    try {
      const response = await fetch('/api/cinema/discovery/probe', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url }) })
      const data = await response.json()
      if (!response.ok || !data.ok) throw new Error(data.error || 'Não foi possível detectar mídia.')
      const media = (data.media || []) as CinemaMedia[]
      setCinemaMedia(media); setCinemaStatus(data.message || (media.length ? 'Mídia detectada.' : 'Nenhuma mídia pública encontrada.'))
      return media
    } catch (error) { setCinemaStatus(error instanceof Error ? error.message : 'Falha na detecção.'); return [] }
  }

  const saveCinemaUrl = async () => {
    const title = cinemaQuery.trim() || 'Mídia sem título'; const url = videoUrl.trim()
    if (!url) return
    // Default to movie for now - modal UI would be needed for proper selection
    const isSeries = false
    const season = 1
    const episode = 1
    const response = await fetch('/api/cinema/library', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title, type: isSeries ? 'tv' : 'movie', url, label: 'URL direta', season, episode }) })
    const data = await response.json()
    setCinemaStatus(response.ok && data.ok ? 'Fonte salva na biblioteca.' : data.error || 'Não foi possível salvar a fonte.')
    if (response.ok && data.ok) refreshCinemaLibrary().catch(() => undefined)
  }

  return { availableEpisodes, availableSeasons, cinemaLauncherOpen, setCinemaLauncherOpen, videoUrl, setVideoUrl, cinemaQuery, setCinemaQuery, cinemaResults, cinemaMedia, cinemaStatus, setCinemaStatus, cinemaLibrary, refreshCinemaLibrary, searchCinema, probeCinema, saveCinemaUrl, openCinemaPayload, selectEpisode, selectLibraryItem, selectLibrarySource, selectNextEpisode, selectSeason, selectedEpisode, selectedLibraryItem, selectedLibraryId, selectedLibrarySources, selectedSeason, selectedSourceUrl }
}
