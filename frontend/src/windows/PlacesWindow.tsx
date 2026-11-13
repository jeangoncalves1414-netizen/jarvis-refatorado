import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { ExternalLink, MapPin, Search, Star } from 'lucide-react'
import { panelRequest } from '../utils/panelApi'
import { OSM_ATTRIBUTION, PROVIDER_LABEL, osmEmbedUrl, osmLink, parseBbox, parsePlace, type PlaceBbox, type PlaceProvider, type PlaceResult } from '../utils/places'
import type { PlacesWindowParams, WindowComponentProps } from './registry'

// Janela "Lugares": busca no OpenStreetMap (ou Google Places, se houver chave) sem IA.
// A busca só sai quando a usuária envia (Enter ou botão), nunca enquanto digita. Cada busca passa
// pelo Action Kernel (GET /api/places) e aparece na Central. Abrir com `query` (comando /lugares ou
// agente) já conta como envio.

type PlacesResponse = { ok: boolean; query: string; near: string; provider: PlaceProvider; results: unknown[]; bbox: unknown; attribution: string; notice: string }
type SearchState =
  | { kind: 'idle' }
  | { kind: 'loading'; label: string }
  | { kind: 'error'; message: string }
  | { kind: 'done'; label: string; provider: PlaceProvider; results: PlaceResult[]; bbox: PlaceBbox | null; notice: string }

function describeError(error: unknown) {
  if (error instanceof TypeError) return 'Sem conexão com o servidor.'
  return error instanceof Error ? error.message : 'Erro desconhecido.'
}

export function PlacesWindow({ params }: WindowComponentProps<PlacesWindowParams>) {
  const [query, setQuery] = useState(params.query ?? '')
  const [near, setNear] = useState(params.near ?? '')
  const [state, setState] = useState<SearchState>({ kind: 'idle' })
  const [selected, setSelected] = useState(0)
  const [copyNotice, setCopyNotice] = useState('')
  const controllerRef = useRef<AbortController | null>(null)

  const search = useCallback(async (rawQuery: string, rawNear: string) => {
    const q = rawQuery.trim()
    const n = rawNear.trim()
    if (!q) { setState({ kind: 'error', message: 'Digite o que procurar.' }); return }
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    const label = n ? `${q} perto de ${n}` : q
    setState({ kind: 'loading', label })
    try {
      const qs = new URLSearchParams({ q, ...(n ? { near: n } : {}) })
      const data = await panelRequest<PlacesResponse>(`/api/places?${qs.toString()}`, { signal: controller.signal })
      if (controller.signal.aborted) return
      const results = (Array.isArray(data.results) ? data.results : []).map(parsePlace)
      const bbox = parseBbox(data.bbox)
      if (results.some(item => item === null) || bbox === undefined) throw new Error('O servidor devolveu resultados inválidos.')
      setSelected(0)
      setCopyNotice('')
      setState({ kind: 'done', label, provider: data.provider === 'google' ? 'google' : 'osm', results: results as PlaceResult[], bbox, notice: typeof data.notice === 'string' ? data.notice : '' })
    } catch (error) {
      if (controller.signal.aborted) return
      setState({ kind: 'error', message: describeError(error) })
    }
  }, [])

  // Abrir com `query` busca uma vez só (a janela é remontada quando reaberta com outros parâmetros).
  // Sem abortar ao desmontar: no modo estrito do React o efeito roda duas vezes e a busca não pode repetir.
  const initialSearched = useRef(false)
  useEffect(() => {
    if (params.query && !initialSearched.current) {
      initialSearched.current = true
      void search(params.query, params.near ?? '')
    }
  }, [params.query, params.near, search])

  const submit = (event: FormEvent) => {
    event.preventDefault()
    void search(query, near)
  }

  const done = state.kind === 'done' ? state : null
  const current = done?.results[selected] ?? null
  const mapUrl = done ? osmEmbedUrl(done.bbox, current) : ''

  return (
    <div className="ws-places">
      <form className="ws-places-form" onSubmit={submit} role="search">
        <label>
          O que procurar
          <input value={query} maxLength={120} onChange={event => setQuery(event.target.value)} placeholder="padaria, farmácia 24h, Rua Augusta 100" aria-label="O que procurar" />
        </label>
        <label>
          Perto de (opcional)
          <input value={near} maxLength={80} onChange={event => setNear(event.target.value)} placeholder="bairro ou cidade" aria-label="Perto de" />
        </label>
        <button type="submit" className="ws-button primary" disabled={state.kind === 'loading'}><Search size={14} /> Buscar</button>
      </form>
      <p className="ws-muted ws-places-hint">Funciona sem IA. A busca só é enviada quando você confirma e fica registrada na Central.</p>

      <div className={`ws-places-status ${state.kind}`} role={state.kind === 'error' ? 'alert' : 'status'} aria-live="polite">
        {state.kind === 'idle' && 'Digite o lugar e confirme para buscar.'}
        {state.kind === 'loading' && `Buscando “${state.label}”…`}
        {state.kind === 'error' && state.message}
        {done && (done.results.length
          ? `${done.results.length} lugar(es) para “${done.label}” · ${PROVIDER_LABEL[done.provider]}`
          : `Nenhum lugar encontrado para “${done.label}”.`)}
      </div>
      {done?.notice && <p className="ws-places-notice">{done.notice}</p>}

      {done && done.results.length > 0 && (
        <div className="ws-places-body">
          <ul className="ws-places-list" aria-label="Resultados">
            {done.results.map((place, index) => (
              <li key={`${place.lat},${place.lon},${index}`}>
                <button type="button" className={index === selected ? 'selected' : ''} aria-pressed={index === selected} onClick={() => { setSelected(index); setCopyNotice('') }}>
                  <MapPin size={14} aria-hidden="true" />
                  <span className="ws-places-what">
                    <strong>{place.name}</strong>
                    <small>{place.address}</small>
                  </span>
                  {place.rating !== undefined && <span className="ws-places-rating"><Star size={11} aria-hidden="true" /> {place.rating.toFixed(1)}</span>}
                </button>
              </li>
            ))}
          </ul>
          <div className="ws-places-map">
            {mapUrl && <iframe title={current ? `Mapa: ${current.name}` : 'Mapa dos resultados'} src={mapUrl} loading="lazy" referrerPolicy="no-referrer" />}
            <div className="ws-places-map-foot">
              <span className="ws-places-attribution">Mapa: {OSM_ATTRIBUTION}{done.provider === 'google' ? ' · Resultados: Google Places' : ''}</span>
              {current && <a href={osmLink(current)} target="_blank" rel="noopener noreferrer"><ExternalLink size={12} /> Abrir no mapa</a>}
              {current && <>
                <span>{current.lat}, {current.lon}</span>
                <button type="button" onClick={() => {
                  void navigator.clipboard.writeText(`${current.lat}, ${current.lon}`).then(() => setCopyNotice('Coordenadas copiadas.')).catch(() => setCopyNotice('Não foi possível copiar. Selecione as coordenadas acima.'))
                }}>Copiar coordenadas</button>
                <a href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${current.lat},${current.lon}`)}`} target="_blank" rel="noopener noreferrer">Google Maps</a>
                <a href={`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(`${current.lat},${current.lon}`)}`} target="_blank" rel="noopener noreferrer">Traçar rota</a>
                <span role="status">{copyNotice}</span>
              </>}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
