// Busca de lugares (lote 6): tipos e mapa do OpenStreetMap usados pela janela e pelo popup Lugares.
// O mapa é o iframe oficial de exportação do OSM (sem biblioteca nova). A atribuição fica sempre visível.

export type PlaceProvider = 'osm' | 'google'

export type PlaceResult = {
  id?: string
  name: string
  address: string
  lat: number
  lon: number
  category: string
  rating?: number
}

// [oeste, sul, leste, norte], a ordem do parâmetro bbox do mapa embutido do OSM.
export type PlaceBbox = [number, number, number, number]

export const OSM_ATTRIBUTION = '© colaboradores do OpenStreetMap'
export const PROVIDER_LABEL: Record<PlaceProvider, string> = { osm: 'OpenStreetMap', google: 'Google Places' }

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value)
const isCoord = (value: unknown, limit: number): value is number => typeof value === 'number' && Number.isFinite(value) && Math.abs(value) <= limit

export function parsePlace(raw: unknown): PlaceResult | null {
  if (!isRecord(raw)) return null
  const { id, name, address, lat, lon, category, rating } = raw
  if (typeof name !== 'string' || name.length > 120 || typeof address !== 'string' || address.length > 300) return null
  if (!isCoord(lat, 90) || !isCoord(lon, 180) || typeof category !== 'string' || category.length > 60) return null
  if (id !== undefined && (typeof id !== 'string' || id.length > 20)) return null
  if (rating !== undefined && !(typeof rating === 'number' && rating >= 0 && rating <= 5)) return null
  return { ...(id ? { id } : {}), name, address, lat, lon, category, ...(rating !== undefined ? { rating } : {}) }
}

export function parseBbox(raw: unknown): PlaceBbox | null | undefined {
  if (raw === null || raw === undefined) return null
  if (!Array.isArray(raw) || raw.length !== 4) return undefined
  const [west, south, east, north] = raw
  if (!isCoord(west, 180) || !isCoord(east, 180) || !isCoord(south, 90) || !isCoord(north, 90)) return undefined
  return [west, south, east, north]
}

const fixed = (value: number) => value.toFixed(6).replace(/0+$/, '').replace(/\.$/, '')

// Mapa centrado no lugar escolhido (ou no conjunto de resultados).
export function osmEmbedUrl(bbox: PlaceBbox | null, marker?: PlaceResult | null) {
  const area: PlaceBbox | null = marker
    ? [marker.lon - 0.006, marker.lat - 0.004, marker.lon + 0.006, marker.lat + 0.004]
    : bbox
  if (!area) return ''
  const params = new URLSearchParams({ bbox: area.map(fixed).join(','), layer: 'mapnik' })
  if (marker) params.set('marker', `${fixed(marker.lat)},${fixed(marker.lon)}`)
  return `https://www.openstreetmap.org/export/embed.html?${params.toString()}`
}

export function osmLink(place: PlaceResult) {
  return `https://www.openstreetmap.org/?mlat=${fixed(place.lat)}&mlon=${fixed(place.lon)}#map=17/${fixed(place.lat)}/${fixed(place.lon)}`
}
