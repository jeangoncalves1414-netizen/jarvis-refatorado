import type { TurnMeta } from '../../types'

export function TurnMetaDetails({ meta }: { meta?: TurnMeta }) {
  const lookup = meta?.memory_lookup
  if (!lookup) return null
  return <details className="ws-turn-meta"><summary>Contexto usado · consulta à memória</summary><p>{lookup.summary}</p>{lookup.items.map((item, i) => <p key={i}><strong>{item.title}</strong><br />{item.text}</p>)}</details>
}
