import { FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import type { CinemaCatalogItem, CinemaDetectedEpisode, CinemaEpisode, CinemaItem, CinemaMedia, CinemaResult, CinemaSearchMode, CinemaSearchSource, CinemaSource } from '../types'

import { checkCinemaMedia } from '../utils/cinemaPlayback'

type ProbeResult = { media: CinemaMedia[]; episodes: CinemaDetectedEpisode[]; error?: string; status?: string; message?: string }
type RecentSearch = { query: string; mode: CinemaSearchMode; source: string }
const historyKey = 'jarvis:cinema:search-history:v1'
const maxPagesKey = 'jarvis:cinema:max-pages:v1'

function readHistory(): RecentSearch[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(historyKey) || '[]')
    return Array.isArray(value) ? value.filter((item): item is RecentSearch => item && typeof item.query === 'string' && item.query.length <= 160 && ['movie', 'series', 'anime', 'sites'].includes(item.mode) && typeof item.source === 'string').slice(0, 8) : []
  } catch { return [] }
}

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
  const [mode, setMode] = useState<CinemaSearchMode>('movie')
  // A pesquisa por Sites começa ampla; a opção de fontes verificáveis continua
  // disponível para quem quiser uma lista curada e ordenada.
  const [source, setSource] = useState('web')
  const [sources, setSources] = useState<CinemaSearchSource[]>([])
  const [catalog, setCatalog] = useState<CinemaCatalogItem[]>([])
  const [selection, setSelection] = useState<CinemaCatalogItem | null>(null)
  const [recent, setRecent] = useState<RecentSearch[]>(readHistory)
  const [busy, setBusy] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [maxPages, setMaxPages] = useState(() => {
    try {
      const saved = Number(localStorage.getItem(maxPagesKey))
      return Number.isInteger(saved) && saved >= 1 && saved <= 50 ? saved : 17
    } catch { return 17 }
  })
  const changeMaxPages = (value: number) => {
    if (!Number.isInteger(value) || value < 1 || value > 50) return
    setMaxPages(value)
    try { localStorage.setItem(maxPagesKey, String(value)) } catch { /* Storage may be unavailable. */ }
  }
  const [probeBusy, setProbeBusy] = useState(false)
  const [sessionBusy, setSessionBusy] = useState(false)
  const [sessions, setSessions] = useState<{ id: string; url: string; mediaCount?: number }[]>([])
  const [detectedEpisodes, setDetectedEpisodes] = useState<CinemaDetectedEpisode[]>([])
  const [detectedSeason, setDetectedSeason] = useState(1)
  const [detectedEpisode, setDetectedEpisode] = useState<CinemaDetectedEpisode | null>(null)
  const [page, setPage] = useState(1)
  const [onlyCompatible, setOnlyCompatible] = useState(false)
  const [scanBusy, setScanBusy] = useState(false)
  const [scanLimit, setScanLimit] = useState(12)
  const [scanProgress, setScanProgress] = useState({ done: 0, total: 0 })
  const [checked, setChecked] = useState<Record<string, ProbeResult>>({})
  const scanRequest = useRef<AbortController | null>(null)
  const probeCache = useRef(new Map<string, { time: number; result: ProbeResult }>())
  const pageSize = 12
  const pageResults = cinemaResults.slice((page - 1) * pageSize, page * pageSize)
  const pageCount = Math.max(1, Math.ceil(cinemaResults.length / pageSize))
  const searchRequest = useRef<AbortController | null>(null)
  const probeRequest = useRef<AbortController | null>(null)

  useEffect(() => {
    if (!cinemaLauncherOpen) {
      searchRequest.current?.abort()
      probeRequest.current?.abort()
      scanRequest.current?.abort()
      setScanBusy(false)
      setBusy(false)
      setLoadingMore(false)
      setProbeBusy(false)
      return
    }
    const controller = new AbortController()
    fetch('/api/cinema/discovery/sources', { signal: controller.signal })
      .then(response => response.json()).then(data => {
        if (!controller.signal.aborted && data.ok && Array.isArray(data.sources)) setSources(data.sources.filter((item: CinemaSearchSource) => item.enabled !== false))
      }).catch(() => undefined)
    return () => controller.abort()
  }, [cinemaLauncherOpen])

  useEffect(() => () => { searchRequest.current?.abort(); probeRequest.current?.abort(); scanRequest.current?.abort() }, [])

  const sessionIds = sessions.map(item => item.id).join(',')
  useEffect(() => {
    if (!cinemaLauncherOpen || !sessionIds) return
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    const poll = async () => {
      await Promise.all(sessionIds.split(',').map(async id => {
        try {
          const response = await fetch(`/api/cinema/session/status/${encodeURIComponent(id)}`, { signal: controller.signal })
          const data = await response.json()
          if (!response.ok || !data.ok || controller.signal.aborted) return
          setSessions(previous => data.status === 'closed' ? previous.filter(item => item.id !== id) : previous.map(item => item.id === id ? { ...item, mediaCount: data.media?.length || 0 } : item))
        } catch { /* Keep sessions during transient connection failures. */ }
      }))
      if (!controller.signal.aborted) timer = setTimeout(poll, 2500)
    }
    void poll()
    return () => { controller.abort(); clearTimeout(timer) }
  }, [cinemaLauncherOpen, sessionIds])

  const remember = (entry?: RecentSearch) => {
    setRecent(previous => {
      const next = entry ? [entry, ...previous.filter(item => item.query.toLowerCase() !== entry.query.toLowerCase() || item.mode !== entry.mode || item.source !== entry.source)].slice(0, 8) : []
      try { localStorage.setItem(historyKey, JSON.stringify(next)) } catch { /* Storage may be unavailable. */ }
      return next
    })
  }


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

  const selectEpisode = (episode: number, season = selectedSeason || 1) => {
    const entry = selectedLibraryItem?.episodes?.find(item => (item.episode || 1) === episode && (item.season || 1) === season)
    setSelectedSeason(season)
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

  const openCinemaPayload = (payload: { title?: string; type?: string; poster?: string; imdb_id?: string; detect_url?: string; scope?: string; source_id?: string; discovery_results?: Partial<CinemaResult>[]; catalog_results?: Partial<CinemaCatalogItem>[] }) => {
    searchRequest.current?.abort(); probeRequest.current?.abort(); scanRequest.current?.abort()
    setScanBusy(false); setOnlyCompatible(false); setPage(1); setChecked({}); setDetectedEpisodes([])
    setBusy(false); setProbeBusy(false); setCinemaMedia([])
    const title = String(payload.title || '').trim()
    setCinemaQuery(title)
    const items = (payload.catalog_results || []).filter(item => item.id && item.title).map(item => ({ ...item, id: item.id!, title: item.title!, type: item.type === 'tv' ? 'tv' as const : 'movie' as const }))
    const results = (payload.discovery_results || []).filter(item => item.url).map(item => ({ ...item, url: item.url! }))
    setCatalog(items); setCinemaResults(results)
    setMode(items.length ? (items[0].type === 'tv' ? 'series' : 'movie') : 'sites')
    setSource(payload.source_id || (payload.scope === 'web' ? 'web' : 'approved'))
    setSelection(payload.imdb_id ? { id: payload.imdb_id, title, type: payload.type === 'tv' ? 'tv' : 'movie', poster: payload.poster } : null)
    setCinemaStatus(items.length || results.length ? 'Escolha um título ou uma página para continuar.' : 'Pesquise um título ou assunto.')
    setCinemaLauncherOpen(true)
    if (payload.detect_url) {
      setVideoUrl(payload.detect_url)
      void probeCinema(payload.detect_url)
    }
  }

  const search = async (query = cinemaQuery, nextMode = mode, nextSource = source) => {
    searchRequest.current?.abort(); probeRequest.current?.abort(); scanRequest.current?.abort()
    setLoadingMore(false)
    setScanBusy(false); setOnlyCompatible(false); setPage(1); setChecked({}); setDetectedEpisodes([])
    setProbeBusy(false)
    setSelectedLibraryId(''); setDetectedEpisode(null)
    setMode(nextMode); setSource(nextSource); setSelection(null)
    const clean = query.trim().slice(0, 160)
    setCinemaQuery(clean); setCinemaResults([]); setCinemaMedia([]); setCatalog([])
    if (!clean) { setBusy(false); setCinemaStatus('Informe um título ou assunto.'); return }
    const controller = new AbortController()
    searchRequest.current = controller
    setBusy(true); setCinemaStatus('Pesquisando…')
    remember({ query: clean, mode: nextMode, source: nextSource })
    const params = new URLSearchParams({ q: clean })
    let endpoint = '/api/cinema/search'
    if (nextMode === 'sites' || nextMode === 'anime') {
      endpoint = '/api/cinema/discovery/search'
      params.set('scope', nextSource === 'web' || nextSource.startsWith('domain:') ? 'web' : 'approved')
      if (nextMode === 'anime') params.set('q', `${clean} anime assistir online grátis`)
      if (!['web', 'approved'].includes(nextSource)) params.set('source', nextSource)
    } else params.set('type', nextMode)
    const accumulated: CinemaResult[] = []
    try {
      if (nextMode === 'sites' || nextMode === 'anime') {
        const target = maxPages * pageSize
        const seen = new Set<string>()
        let providerPage = 1, staleBatches = 0
        const warnings = new Set<string>()
        setLoadingMore(true)
        // A batch has a fixed size: changing it between provider pages can skip results.
        params.set('limit', '24')
        while (accumulated.length < target) {
          params.set('page', String(providerPage))
          const response = await fetch(`${endpoint}?${params}`, { signal: controller.signal })
          const data = await response.json()
          if (controller.signal.aborted) return
          if (!response.ok || !data.ok) throw new Error(data.error || 'Não foi possível carregar mais resultados.')
          const previousCount = accumulated.length
          for (const item of (data.results || []) as CinemaResult[]) {
            if (item.url && !seen.has(item.url) && accumulated.length < target) {
              seen.add(item.url); accumulated.push(item)
            }
          }
          for (const warning of data.warnings || []) warnings.add(String(warning))
          setCinemaResults([...accumulated]); setBusy(false)
          staleBatches = accumulated.length === previousCount ? staleBatches + 1 : 0
          setCinemaStatus(`${accumulated.length} resultados. Buscando mais, até ${maxPages} páginas…`)
          if (!Number.isInteger(data.next_page) || data.next_page <= providerPage || data.next_page > 100 || staleBatches >= 2) break
          providerPage = data.next_page
        }
        setCinemaStatus(`${accumulated.length} resultados. ${accumulated.length >= target ? `Limite de ${maxPages} páginas atingido.` : 'Busca concluída; os provedores não retornaram mais resultados novos nesta consulta.'} ${[...warnings].join(' ')}`.trim())
        return
      }
      const response = await fetch(`${endpoint}?${params}`, { signal: controller.signal })
      const data = await response.json()
      if (controller.signal.aborted) return
      if (!response.ok || !data.ok) throw new Error(data.error || 'Não foi possível pesquisar.')
      const items = data.results || []
      setCatalog(items)
      const warnings = [...(data.warnings || []), ...(data.partial ? ['Parte do catálogo está indisponível.'] : [])].join(' ')
      setCinemaStatus(`${items.length ? `${items.length} resultados. Escolha um título para ver detalhes e fontes.` : 'Nenhum resultado encontrado. Tente outro termo ou fonte.'}${warnings ? ` ${warnings}` : ''}`)
    } catch (error) {
      if (!controller.signal.aborted) setCinemaStatus(`${accumulated.length ? `${accumulated.length} resultados preservados. ` : ''}${error instanceof Error ? error.message : 'Falha na pesquisa.'}`)
    } finally { if (!controller.signal.aborted) { setBusy(false); setLoadingMore(false) } }
  }

  const stopSearch = () => {
    searchRequest.current?.abort()
    setBusy(false); setLoadingMore(false)
    setCinemaStatus(`${cinemaResults.length} resultados. Carregamento interrompido.`)
  }

  const searchCinema = (event: FormEvent) => { event.preventDefault(); void search() }

  const fetchProbe = async (url: string, signal: AbortSignal, fast = false): Promise<ProbeResult> => {
    const cacheKey = `${fast ? 'fast:' : 'full:'}${url}`
    const cached = probeCache.current.get(cacheKey)
    if (cached && Date.now() - cached.time < (cached.result.status === 'detected' ? 180000 : 15000)) return cached.result
    const response = await fetch('/api/cinema/discovery/probe', { method: 'POST', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url, fast }) })
    const data = await response.json()
    if (!response.ok || !data.ok) throw new Error(data.error || 'Não foi possível detectar mídia.')
    const result = { media: (data.media || []).map((item: CinemaMedia) => ({ ...item, url: item.playback_url ? new URL(item.playback_url, window.location.origin).href : item.url })), episodes: data.episodes || [], status: data.status, message: data.message } as ProbeResult
    if (!signal.aborted) {
      if (probeCache.current.size >= 72) probeCache.current.delete(probeCache.current.keys().next().value!)
      probeCache.current.set(cacheKey, { time: Date.now(), result })
    }
    return result
  }

  const probeCinema = async (url: string): Promise<CinemaMedia[]> => {
    probeRequest.current?.abort()
    const controller = new AbortController()
    probeRequest.current = controller
    setVideoUrl(url); setProbeBusy(true)
    const episode = detectedEpisodes.find(item => item.url === url)
    setDetectedEpisode(episode || null)
    if (!episode) setDetectedEpisodes([])
    setCinemaStatus('Detectando vídeos e episódios nesta página…'); setCinemaMedia([])
    try {
      const fetched = await fetchProbe(url, controller.signal)
      const data = { ...fetched, media: fetched.media.map(item => checked[url]?.media.find(verified => verified.url === item.url && verified.compatible) || item) }
      if (controller.signal.aborted) return []
      if (data.error) throw new Error(data.error)
      setCinemaMedia(data.media)
      if (data.episodes.length) {
        // Episode pages often expose only previous/next; preserve the series index.
        const episodes = episode ? [...new Map([...detectedEpisodes, ...data.episodes].map(item => [item.url, item])).values()].sort((a, b) => a.season - b.season || a.episode - b.episode) : data.episodes
        setDetectedEpisodes(episodes)
        const current = episode || episodes.find(item => item.url === url)
        setDetectedEpisode(current || null)
        setDetectedSeason(current?.season || episodes[0].season)
      }
      setCinemaStatus(data.message || (data.media.length ? 'Fontes detectadas. Escolha um vídeo para assistir.' : data.episodes.length ? 'Selecione um episódio para detectar o vídeo.' : 'Nenhum vídeo confirmado. Abra a sessão do site para interagir com o player.'))
      return data.media
    } catch (error) {
      if (!controller.signal.aborted) setCinemaStatus(error instanceof Error ? error.message : 'Falha na detecção.')
      return []
    } finally { if (!controller.signal.aborted) setProbeBusy(false) }
  }

  const scanPage = async () => {
    scanRequest.current?.abort()
    const controller = new AbortController()
    scanRequest.current = controller
    const candidates = cinemaResults.slice((page - 1) * pageSize, (page - 1) * pageSize + scanLimit).filter(row => {
      try {
        const parsed = new URL(row.url)
        return ['http:', 'https:'].includes(parsed.protocol) && !parsed.username && !parsed.password
      } catch { return false }
    })
    setScanBusy(true); setOnlyCompatible(true); setScanProgress({ done: 0, total: candidates.length })
    let cursor = 0, completed = 0
    const worker = async () => {
      while (cursor < candidates.length && !controller.signal.aborted) {
        const row = candidates[cursor++]
        let result: ProbeResult
        try {
          result = await fetchProbe(row.url, controller.signal, true)
          const media = result.media.filter(item => !item.suspected_ad)
          // Quatro páginas em paralelo; uma confirmação curta basta para manter o filtro responsivo.
          for (let index = 0; index < Math.min(media.length, 3) && !controller.signal.aborted; index++) {
            if (media[index].compatible) break
            if (media[index].direct === false) continue
            media[index] = await checkCinemaMedia(media[index], controller.signal, 2500)
            if (media[index].compatible) break
          }
          result = { ...result, media }
          if (!controller.signal.aborted && media.some(item => item.compatible)) {
            probeCache.current.set(`fast:${row.url}`, { time: Date.now(), result: { ...result, status: 'detected' } })
          }
        } catch (error) { result = { media: [], episodes: [], error: error instanceof Error ? error.message : 'Falha na verificação.' } }
        if (controller.signal.aborted) return
        setChecked(previous => ({ ...previous, [row.url]: result }))
        setScanProgress({ done: ++completed, total: candidates.length })
      }
    }
    await Promise.all(Array.from({ length: Math.min(4, candidates.length) }, worker))
    if (!controller.signal.aborted) setScanBusy(false)
  }

  const changePage = (value: number) => {
    scanRequest.current?.abort(); setScanBusy(false); setOnlyCompatible(false)
    setPage(Math.max(1, Math.min(pageCount, value)))
  }
  const filterCompatible = (enabled: boolean) => {
    if (enabled) void scanPage()
    else { scanRequest.current?.abort(); setScanBusy(false); setOnlyCompatible(false) }
  }
  const playDetectedEpisode = async (url: string) => {
    const media = await probeCinema(url)
    return (media.find(item => item.compatible) || media.find(item => item.direct) || media[0])?.url || ''
  }
  const openSession = async (url: string) => {
    if (sessionBusy) return
    setSessionBusy(true)
    try {
      const response = await fetch('/api/cinema/session/open', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url }) })
      const data = await response.json()
      if (!response.ok || !data.ok) throw new Error(data.error || 'Não foi possível abrir a sessão.')
      setSessions(previous => [...previous, { id: data.session_id, url }])
      setCinemaStatus(data.message)
    } catch (error) { setCinemaStatus(error instanceof Error ? error.message : 'Falha ao abrir sessão.') }
    finally { setSessionBusy(false) }
  }
  const closeSession = async (id: string) => {
    try {
      const response = await fetch('/api/cinema/session/close', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: id }) })
      if (!response.ok) throw new Error()
      setSessions(previous => previous.filter(item => item.id !== id))
    } catch { setCinemaStatus('Não foi possível fechar a sessão. Feche a janela do navegador.') }
  }
  const inspectSession = async (id: string) => {
    probeRequest.current?.abort()
    const controller = new AbortController()
    probeRequest.current = controller
    setProbeBusy(true)
    try {
      const response = await fetch(`/api/cinema/session/status/${encodeURIComponent(id)}`, { signal: controller.signal })
      const data = await response.json()
      if (controller.signal.aborted) return
      if (!response.ok || !data.ok) throw new Error('Não foi possível consultar a sessão.')
      if (data.status === 'closed') throw new Error('Sessão encerrada. Abra novamente o site.')
      const media = (data.media || []).map((item: CinemaMedia) => ({ ...item, url: new URL(item.url, window.location.origin).href }))
      setCinemaMedia(media)
      const session = sessions.find(item => item.id === id)
      const message = data.message || (media.length ? 'Fontes da sessão disponíveis. Selecione Assistir abaixo e mantenha a janela do site aberta.' : 'Nenhuma fonte capturada ainda. Inicie o vídeo na janela do site e consulte novamente.')
      setChecked(previous => ({ ...previous, ...Object.fromEntries([session?.url, data.page_url].filter(Boolean).map(url => [url, { media, episodes: data.episodes || [], message }])) }))
      setVideoUrl(data.page_url || '')
      setSelectedLibraryId('')
      const knownEpisode = detectedEpisodes.find(item => item.url === data.page_url)
      const currentEpisode = knownEpisode || data.episodes?.find((item: CinemaDetectedEpisode) => item.url === data.page_url)
      const episodes: CinemaDetectedEpisode[] = knownEpisode ? [...new Map([...detectedEpisodes, ...(data.episodes || [])].map(item => [item.url, item])).values()].sort((a, b) => a.season - b.season || a.episode - b.episode) : data.episodes || []
      setDetectedEpisodes(episodes)
      setDetectedEpisode(currentEpisode || null)
      if (episodes.length) setDetectedSeason(currentEpisode?.season || episodes[0].season)
      setCinemaStatus(message)
    } catch (error) { if (!controller.signal.aborted) setCinemaStatus(error instanceof Error ? error.message : 'Falha na sessão.') }
    finally { if (!controller.signal.aborted) setProbeBusy(false) }
  }
  const cinemaSearch = { sessions, sessionBusy, openSession, closeSession, inspectSession, mode, source, sources, catalog, selection, selectTitle: setSelection, recent, busy, probeBusy, search, clearHistory: () => remember(),
    maxPages, changeMaxPages, loadingMore, stopSearch,
    scanLimit, setScanLimit,
    page, pageCount, pageResults, changePage, onlyCompatible, filterCompatible, scanBusy, scanProgress, checked,
    detectedEpisodes, detectedSeason, setDetectedSeason, detectedEpisode, playDetectedEpisode }

  const saveCinemaUrl = async () => {
    const title = selection?.title || cinemaQuery.trim() || 'Mídia sem título'
    const selectedMedia = cinemaMedia.find(item => item.url === videoUrl)
    const url = (selectedMedia?.session_id ? selectedMedia.source_url : videoUrl)?.trim() || ''
    if (!url) return
    const isSeries = selection?.type === 'tv' || Boolean(detectedEpisode)
    const season = detectedEpisode?.season || 1
    const episode = detectedEpisode?.episode || 1
    try {
    const response = await fetch('/api/cinema/library', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title, type: isSeries ? 'tv' : 'movie', url, label: cinemaMedia.find(item => item.url === url)?.label || 'Fonte selecionada', season, episode }) })
    const data = await response.json()
    setCinemaStatus(response.ok && data.ok ? 'Fonte salva na biblioteca.' : data.error || 'Não foi possível salvar a fonte.')
    if (response.ok && data.ok) refreshCinemaLibrary().catch(() => undefined)
    } catch { setCinemaStatus('Não foi possível salvar a fonte. Tente novamente.') }
  }

  return { cinemaSearch, availableEpisodes, availableSeasons, cinemaLauncherOpen, setCinemaLauncherOpen, videoUrl, setVideoUrl, cinemaQuery, setCinemaQuery, cinemaResults, cinemaMedia, cinemaStatus, setCinemaStatus, cinemaLibrary, refreshCinemaLibrary, searchCinema, probeCinema, saveCinemaUrl, openCinemaPayload, selectEpisode, selectLibraryItem, selectLibrarySource, selectNextEpisode, selectSeason, selectedEpisode, selectedLibraryItem, selectedLibraryId, selectedLibrarySources, selectedSeason, selectedSourceUrl }
}
