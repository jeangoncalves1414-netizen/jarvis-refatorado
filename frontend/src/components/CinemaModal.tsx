import { FormEvent, useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import type { CinemaItem, CinemaMedia, CinemaResult } from '../types'

import type { useCinema } from '../hooks/useCinema'
import { Clapperboard, ExternalLink, Globe, Search, Tv, X } from 'lucide-react'
import './cinemaSearch.css'

function webUrl(value?: string): string {
  try {
    const url = new URL(value || '')
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : ''
  } catch { return '' }
}

function directMediaUrl(value?: string): string {
  const url = webUrl(value)
  return /\.(?:m3u8|mp4|webm|ogv|mov|m4v)(?:$|[?#])/i.test(url) || /\/api\/cinema\/session\/media\//.test(url) ? url : ''
}

export type CinemaModalProps = {
  cinemaSearch: ReturnType<typeof useCinema>['cinemaSearch']
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
    cinemaSearch, open, onClose, onPlay, cinemaQuery, setCinemaQuery, videoUrl, setVideoUrl,
    cinemaResults, cinemaMedia, cinemaStatus, setCinemaStatus, cinemaLibrary,
    refreshCinemaLibrary, searchCinema, probeCinema, saveCinemaUrl,
    selectedLibraryItem, selectedLibraryId, selectLibraryItem,
    availableSeasons, availableEpisodes, selectedSeason, selectedEpisode,
    selectedSourceUrl, selectSeason, selectEpisode, selectLibrarySource,
    selectNextEpisode, selectedLibrarySources,
  } = props

  const [domain, setDomain] = useState('')
  const [showUnconfirmed, setShowUnconfirmed] = useState(false)
  const dialogRef = useRef<HTMLElement>(null)
  const urlEntryRef = useRef<HTMLDetailsElement>(null)
  const { mode, source, sources, catalog, selection, selectTitle, recent, busy, probeBusy, search, clearHistory,
    maxPages, changeMaxPages, loadingMore, stopSearch,
    scanLimit, setScanLimit,
    page, pageCount, pageResults, changePage, onlyCompatible, filterCompatible, scanBusy, scanProgress, checked,
    detectedEpisodes, detectedSeason, setDetectedSeason, sessions, sessionBusy, openSession, closeSession, inspectSession } = cinemaSearch
  const siteMode = mode === 'sites' || mode === 'anime'
  const unconfirmedCount = pageResults.filter(result => webUrl(result.url) && !checked[result.url]?.media.some(media => media.compatible)).length
  const visibleResults = pageResults.filter(result => webUrl(result.url) && (!onlyCompatible || scanBusy || showUnconfirmed || checked[result.url]?.media.some(media => media.compatible)))
    .sort((left, right) => {
      if (!onlyCompatible) return 0
      const rank = (result: CinemaResult) => checked[result.url]?.media.some(media => media.compatible) ? 0 : checked[result.url] ? 2 : 1
      return rank(left) - rank(right)
    })

  useEffect(() => {
    if (!open) return
    const previous = document.activeElement as HTMLElement | null
    dialogRef.current?.querySelector<HTMLInputElement>('input')?.focus()
    return () => previous?.focus()
  }, [open])

  if (!open) return null

  const play = (url: string, verified = false) => {
    const safe = verified ? webUrl(url) : directMediaUrl(url)
    if (!safe) { setCinemaStatus('O player aceita somente mídia MP4/HLS confirmada. Use “Detectar vídeos” ou abra uma sessão isolada do site.'); return }
    onPlay(safe); onClose()
  }
  const titleQuery = encodeURIComponent(selection?.title || '')
  const imdbLink = /^tt\d+$/.test(selection?.id || '') ? `https://www.imdb.com/title/${selection!.id}/` : ''
  const poster = webUrl(selection?.poster)

  return (
    <div className="tool-modal cinema-modal-overlay" role="dialog" aria-modal="true" aria-label="Cinema e sites"
      onKeyDown={event => {
        if (event.key === 'Escape') { event.stopPropagation(); onClose() }
        if (event.key === 'Tab') {
          const controls = Array.from(dialogRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), summary') || []).filter(el => el.getClientRects().length > 0)
          const first = controls[0], last = controls[controls.length - 1]
          if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
          else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
        }
      }}>
      <motion.section ref={dialogRef} className="cinema-modal cinema-modal-rich cinema-search-workspace"
        initial={{ opacity: 0, scale: 0.98, y: 12 }} animate={{ opacity: 1, scale: 1, y: 0 }} transition={{ duration: 0.2 }}>
        <button className="modal-close" onClick={onClose} aria-label="Fechar cinema"><X size={20} /></button>
        <header className="cinema-modal-header">
          <p className="eyebrow">JARVIS · EXPLORAR</p>
          <h2>Filmes, séries e animes</h2>
          <p>Encontre um título, explore as fontes e escolha onde assistir.</p>
        </header>
        <div className="cinema-modal-body">
          <aside className="cinema-poster-panel">
            {poster ? <img src={poster} alt={`Capa de ${selection?.title}`} className="cinema-poster" referrerPolicy="no-referrer" />
              : <div className="cinema-poster cinema-poster-placeholder"><Clapperboard size={44} /></div>}
            <h3>{selection?.title || 'Sua próxima descoberta'}</h3>
            {selection ? <>
              <small>{selection.type === 'tv' ? 'Série' : 'Filme'} · {selection.year || 'Ano não informado'}</small>
              <p>{selection.description || 'Sinopse não disponível.'}</p>
              {!!selection.genres?.length && <small>{selection.genres.join(' · ')}</small>}
              <button type="button" onClick={() => { void search(`${selection.title} ${selection.year || ''}`, 'sites', 'web'); selectTitle(selection) }}>Buscar fontes deste título</button>
              <div className="cinema-link-row">
                <a href={`https://www.justwatch.com/br/busca?q=${titleQuery}`} target="_blank" rel="noopener noreferrer" className="cinema-link-btn primary">Onde assistir</a>
                <a href={`https://www.youtube.com/results?search_query=${titleQuery}%20trailer%20oficial`} target="_blank" rel="noopener noreferrer" className="cinema-link-btn">Trailer</a>
                {imdbLink && <a href={imdbLink} target="_blank" rel="noopener noreferrer" className="cinema-link-btn">IMDb</a>}
              </div>
            </> : <p>Pesquise no catálogo ou procure páginas na web. Os resultados mostram a fonte antes de você abrir.</p>}
            {!!recent.length && <div className="cinema-history">
              <div><b>Pesquisas recentes</b><button type="button" onClick={clearHistory}>Limpar histórico</button></div>
              {recent.map(item => <button type="button" key={`${item.mode}:${item.source}:${item.query}`} onClick={() => void search(item.query, item.mode, item.source)}>
                <span>{item.query}</span><small>{item.mode === 'movie' ? 'Filmes' : item.mode === 'series' ? 'Séries' : item.mode === 'anime' ? 'Animes' : 'Sites'}</small>
              </button>)}
            </div>}
          </aside>
          <div className="cinema-main-panel">
            <div className="cinema-search-tabs" role="group" aria-label="Tipo de pesquisa">
              <button type="button" aria-pressed={mode === 'movie'} onClick={() => void search(cinemaQuery, 'movie')}><Clapperboard size={16} />Filmes</button>
              <button type="button" aria-pressed={mode === 'series'} onClick={() => void search(cinemaQuery, 'series')}><Tv size={16} />Séries</button>
              <button type="button" aria-pressed={mode === 'anime'} onClick={() => void search(cinemaQuery, 'anime', mode === 'anime' ? source : 'web')}><Tv size={16} />Animes</button>
              <button type="button" aria-pressed={mode === 'sites'} onClick={() => void search(cinemaQuery, 'sites', mode === 'sites' ? source : 'web')}><Globe size={16} />Sites</button>
            </div>
            <form className="cinema-search" onSubmit={searchCinema}>
              <input aria-label="Pesquisar filmes, séries ou sites" maxLength={160} value={cinemaQuery} onChange={e => setCinemaQuery(e.target.value)} placeholder={mode === 'anime' ? 'Nome do anime…' : mode === 'sites' ? 'Título, assunto ou nome de um site…' : 'Nome do filme ou série…'} />
              <button type="submit"><Search size={16} />Pesquisar</button>
            </form>
            {siteMode && <label className="cinema-source-filter">Pesquisar em
              <select value={source} onChange={e => void search(cinemaQuery, mode, e.target.value)}>
                <option value="web">Busca na web</option>
                <option value="approved">Somente plataformas cadastradas</option>
                {source.startsWith('domain:') && <option value={source}>{source.slice(7)}</option>}
                {sources.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </label>}
            {siteMode && <>
              <label className="cinema-source-filter">Máximo de páginas
                <select value={maxPages} onChange={event => changeMaxPages(Number(event.target.value))}>
                  {Array.from({ length: 50 }, (_, i) => i + 1).map(count => <option key={count} value={count}>{count} {count === 1 ? 'página' : 'páginas'} · até {count * 12} resultados</option>)}
                </select>
              </label>
              <small>Salvo neste dispositivo. Vale para a próxima pesquisa; a quantidade disponível depende dos buscadores.</small>
              {loadingMore && <button type="button" onClick={stopSearch}>Parar de carregar resultados</button>}
              <form className="cinema-domain-filter" onSubmit={event => { event.preventDefault(); if (domain.trim()) void search(cinemaQuery, mode, `domain:${domain.trim().replace(/^https?:\/\//, '').split('/')[0]}`) }}>
                <input aria-label="Filtrar por domínio" value={domain} onChange={event => setDomain(event.target.value)} placeholder="Domínio específico, ex.: archive.org" />
                <button type="submit" disabled={!domain.trim()}>Buscar neste site</button>
              </form>
              <label className="cinema-compatible-filter"><input type="checkbox" checked={onlyCompatible} disabled={busy || !pageResults.length} onChange={event => filterCompatible(event.target.checked)} />Só vídeos compatíveis detectados nesta página</label>
              <label className="cinema-source-filter">Quantidade a verificar
                <select value={scanLimit} disabled={scanBusy} onChange={event => setScanLimit(Number(event.target.value))}>
                  <option value={12}>Esta página (até 12 sites)</option>
                  <option value={50}>Até 50 sites a partir desta página</option>
                  <option value={100}>Até 100 sites a partir desta página</option>
                </select>
              </label>
              {onlyCompatible && !scanBusy && unconfirmedCount > 0 && <button type="button" onClick={() => setShowUnconfirmed(value => !value)}>{showUnconfirmed ? 'Ocultar não confirmados' : `Mostrar ${unconfirmedCount} não confirmados nesta página`}</button>}
              {onlyCompatible && <p className="cinema-scan-progress" role="status">{scanBusy ? 'Verificando' : 'Verificação concluída'}: {scanProgress.done}/{scanProgress.total} sites · {scanBusy ? ' os cartões continuam visíveis enquanto a checagem ocorre.' : `${pageResults.filter(result => checked[result.url]?.media.some(media => media.compatible)).length} com vídeo compatível nesta página. Não confirmado não significa que o site não tem vídeo.`}{scanBusy ? ' Desmarque para cancelar.' : ''}</p>}
            </>}
            <p className="cinema-status" role="status" aria-live="polite">{cinemaStatus || 'Digite um título para começar.'}</p>
            <div aria-busy={busy}>
              {!siteMode && <div className="cinema-catalog">
                {catalog.map(item => <button type="button" className="cinema-catalog-card" key={`${item.type}:${item.id}`} aria-pressed={selection?.id === item.id} onClick={() => selectTitle(item)}>
                  {webUrl(item.poster) ? <img src={webUrl(item.poster)} alt="" loading="lazy" referrerPolicy="no-referrer" /> : <span className="cinema-cover-placeholder"><Clapperboard size={30} /></span>}
                  <b>{item.title}</b><small>{item.type === 'tv' ? 'Série' : 'Filme'} · {item.year || 'Ano não informado'}</small>
                </button>)}
              </div>}
              {siteMode && <div className="cinema-results">
                {visibleResults.map((result, index) => (
                  <article key={`${result.url}-${index}`}>
                    <div><small>{result.source || new URL(result.url).hostname}</small><b>{result.title || 'Resultado'}</b><p>{result.snippet}</p><small className="cinema-result-hint">{checked[result.url] ? checked[result.url].error || (checked[result.url].media.some(media => media.compatible) ? 'Vídeo compatível verificado' : checked[result.url].message || 'Compatibilidade não confirmada') : onlyCompatible && scanBusy ? 'Verificando player nesta página…' : result.media_hint}</small></div>
                    <div className="cinema-result-actions">
                      <button type="button" disabled={sessionBusy} onClick={() => void openSession(result.url)}>Abrir sessão do site</button>
                      <a href={webUrl(result.url)} target="_blank" rel="noopener noreferrer" className="cinema-link-btn">Abrir site <ExternalLink size={12} /></a>
                      <button type="button" disabled={probeBusy || busy} onClick={() => void probeCinema(result.url)}>{checked[result.url]?.media.some(media => media.compatible) ? 'Ver vídeos' : 'Detectar vídeos'}</button>
                    </div>
                  </article>
                ))}
              </div>}
            </div>
            {siteMode && <nav className="cinema-pagination" aria-label="Páginas da pesquisa">
              <button type="button" disabled={page <= 1} onClick={() => changePage(page - 1)}>Anterior</button><span>Página {page} de {pageCount}</span>
              <button type="button" disabled={page >= pageCount} onClick={() => changePage(page + 1)}>Próxima</button>
            </nav>}
            {detectedEpisodes.length > 0 && <div className="cinema-detected-episodes">
              <label>Temporada detectada <select value={detectedSeason} onChange={event => setDetectedSeason(Number(event.target.value))}>{[...new Set(detectedEpisodes.map(item => item.season))].sort((a,b) => a-b).map(season => <option key={season} value={season}>Temporada {season}</option>)}</select></label>
              <div>{detectedEpisodes.filter(item => item.season === detectedSeason && webUrl(item.url)).map(item => <button type="button" disabled={probeBusy} key={item.url} title={item.title} onClick={() => void probeCinema(item.url)} aria-label={`Detectar episódio ${item.episode}`}>{item.episode}</button>)}</div>
            </div>}
            <div className="cinema-results" aria-busy={probeBusy}>
              {cinemaMedia.filter(media => webUrl(media.url)).map((media, index) => (
                <article className="detected-media" key={`${media.url}-${index}`}>
                  <div><b>{media.label || media.kind || 'Vídeo'}</b><span>{[media.quality, media.audio, ...(media.qualities || []), ...(media.audio_tracks || [])].filter(Boolean).join(' · ')}</span><small>{media.url}</small><p>{media.suspected_ad ? 'Possível anúncio detectado; reprodução automática bloqueada.' : media.compatible ? 'Vídeo compatível verificado neste navegador.' : media.direct === false ? 'Player da página; a incorporação depende do site.' : 'URL de vídeo detectada; a reprodução será verificada ao abrir.'}</p></div>
                  <button type="button" disabled={media.direct === false || media.suspected_ad} onClick={() => play(media.url, media.direct === true)}>Assistir</button>
                  <button type="button" disabled={sessionBusy} onClick={() => void openSession(media.source_url || videoUrl || media.url)}>Abrir sessão do site</button>
                  <button type="button" onClick={() => { setVideoUrl(media.url); if (urlEntryRef.current) urlEntryRef.current.open = true; setCinemaStatus('Vídeo selecionado. Use Salvar para guardar na biblioteca.') }}>Selecionar para salvar</button>
                </article>
              ))}
            </div>
            <details ref={urlEntryRef} className="cinema-url-entry">
              <summary>Abrir por URL</summary>
              <div className="source-row">
                <input aria-label="URL de página ou vídeo" value={videoUrl} onChange={e => setVideoUrl(e.target.value)} placeholder="https://…" />
                <button type="button" disabled={!videoUrl.trim() || probeBusy || busy} onClick={() => void probeCinema(videoUrl)}>Detectar vídeos</button>
                <button type="button" disabled={!directMediaUrl(videoUrl)} onClick={() => play(videoUrl)}>Reproduzir URL direta</button>
                <button type="button" disabled={!webUrl(videoUrl) || sessionBusy} onClick={() => void openSession(videoUrl)}>Abrir sessão do site</button>
              </div>
              <button type="button" className="text-button" disabled={!webUrl(videoUrl)} onClick={saveCinemaUrl}>Salvar na biblioteca</button>
            </details>
            {sessions.length > 0 && <div className="cinema-sessions">
              <p>Inicie o vídeo na janela do site. As fontes capturadas podem ser abertas no Jarvis mantendo essa janela aberta.</p>
              {sessions.map(session => <div key={session.id}><span>{new URL(session.url).hostname} · {session.mediaCount || 0} fontes capturadas</span> <button type="button" disabled={probeBusy} onClick={() => void inspectSession(session.id)}>Ver vídeos da sessão</button> <button type="button" onClick={() => void closeSession(session.id)}>Fechar sessão</button></div>)}
            </div>}
            <div className="library-row">
              <button type="button" className="text-button" onClick={() => refreshCinemaLibrary().catch(() => setCinemaStatus('Não foi possível carregar a biblioteca.'))}>Minha biblioteca</button>
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
                      <button type="button" disabled={!directMediaUrl(selectedSourceUrl)} onClick={() => { play(selectedSourceUrl) }}>Reproduzir</button>
                      {selectedLibraryItem.type === 'tv' && (
                        <button type="button" disabled={!directMediaUrl(selectedSourceUrl)} onClick={() => { const next = selectNextEpisode(); if (next) play(next) }}>Próximo episódio</button>
                      )}
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
        <footer className="cinema-modal-footer">Catálogo, páginas e vídeos são consultados separadamente. A disponibilidade depende de cada fonte.</footer>
      </motion.section>
    </div>
  )
}
