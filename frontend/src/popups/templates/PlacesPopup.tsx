import { Map as MapIcon, MapPin, Star } from 'lucide-react'
import { StaggerList } from '../motion'
import type { PlacesPopupData, PopupComponentProps, PopupPlace } from '../registry'
import { useWindows } from '../../windows/WindowManager'
import { WINDOW_PLACES } from '../../windows/registry'
import { OSM_ATTRIBUTION, PROVIDER_LABEL } from '../../utils/places'

// Resultado de uma busca de lugares: os resultados entram um a um (StaggerList) e "Ver no mapa"
// abre a janela Lugares com a mesma busca (o backend responde do cache, sem nova consulta ao mapa).

const idList = (value: unknown) => Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []

export function PlacesPopup({ popup }: PopupComponentProps<PlacesPopupData>) {
  const windows = useWindows()
  const { query, near, provider, results, notice } = popup.data
  const added = idList(popup.animate.added_ids)
  const openMap = () => { windows.open(WINDOW_PLACES, near ? { query, near } : { query }) }
  return (
    <div className="ws-popup-places">
      <p className="ws-popup-summary">
        {results.length ? `${results.length} lugar(es)` : 'Nenhum lugar'} para “{query}”{near ? ` perto de ${near}` : ''} · {PROVIDER_LABEL[provider]}
      </p>
      {notice && <p className="ws-popup-places-notice">{notice}</p>}
      {results.length > 0 && (
        <StaggerList items={results} getId={item => item.id} newIds={added} renderItem={item => <PlaceRow place={item} />} />
      )}
      <div className="ws-popup-places-foot">
        <button type="button" className="ws-popup-action primary" onClick={openMap}><MapIcon size={13} /> Ver no mapa</button>
        <span className="ws-popup-places-attribution">Mapa: {OSM_ATTRIBUTION}{provider === 'google' ? ' · Resultados: Google' : ''}</span>
      </div>
    </div>
  )
}

function PlaceRow({ place }: { place: PopupPlace }) {
  return (
    <div className="ws-popup-place">
      <MapPin size={13} aria-hidden="true" />
      <span className="ws-popup-place-what">
        <strong>{place.name}</strong>
        {place.address && <small>{place.address}</small>}
      </span>
      {place.rating !== undefined && <span className="ws-popup-place-rating"><Star size={10} aria-hidden="true" /> {place.rating.toFixed(1)}</span>}
    </div>
  )
}
