import type { TurnMeta } from '../../types'

/** Detalhe "Contexto usado" no balão do assistente: fontes e texto do contexto da situação enviado ao modelo. */
export function TurnMetaDetails({ meta }: { meta?: TurnMeta }) {
  const context = meta?.situational_context
  if (!context || !context.text) return null
  const labels = context.sources.map(source => source.label).join(', ')
  return (
    <details className="ws-turn-meta">
      <summary>Contexto usado</summary>
      {labels && <p className="ws-turn-meta-sources">Fontes: {labels}</p>}
      <pre className="ws-turn-meta-text">{context.text}</pre>
    </details>
  )
}
