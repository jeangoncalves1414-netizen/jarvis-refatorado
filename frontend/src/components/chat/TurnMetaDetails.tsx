import type { TurnMeta } from '../../types'
import { MEMORY_FOCUS_KEY } from '../CitedMemoriesPanel'

function openMemory(id: string) {
  try { sessionStorage.setItem(MEMORY_FOCUS_KEY, id) } catch { /* sem sessionStorage */ }
  window.dispatchEvent(new CustomEvent('jarvis:open-memory'))
}

/**
 * Metadados do turno no balão do assistente: memórias citadas ("usei: …", fase contexto 2)
 * e o detalhe "Contexto usado" com as fontes do contexto da situação (fase contexto 1).
 */
export function TurnMetaDetails({ meta }: { meta?: TurnMeta }) {
  const context = meta?.situational_context
  const citations = meta?.memory_used || []
  if (!citations.length && (!context || !context.text)) return null
  const labels = context ? context.sources.map(source => source.label).join(', ') : ''
  return (
    <>
      {citations.length > 0 && (
        <ul className="ws-turn-memory" aria-label="Memórias usadas">
          {citations.map(citation => (
            <li key={citation.id}>
              <span>usei: {citation.text} ({citation.label})</span>
              <button type="button" className="ws-turn-memory-edit" onClick={() => openMemory(citation.id)}>editar</button>
            </li>
          ))}
        </ul>
      )}
      {context && context.text && (
        <details className="ws-turn-meta">
          <summary>Contexto usado</summary>
          {labels && <p className="ws-turn-meta-sources">Fontes: {labels}</p>}
          <pre className="ws-turn-meta-text">{context.text}</pre>
        </details>
      )}
    </>
  )
}
