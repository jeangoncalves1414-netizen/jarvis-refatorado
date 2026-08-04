import type { Memory } from '../types'

type MemoriesPageProps = {
  memories: Memory[]
  memoryCollection: 'conversations' | 'user_memory'
  notice: string
  onRefresh: () => void
  onClearTechnical: () => void
  onSelectCollection: (collection: 'conversations' | 'user_memory') => void
}

export function MemoriesPage({
  memories,
  memoryCollection,
  notice,
  onRefresh,
  onClearTechnical,
  onSelectCollection,
}: MemoriesPageProps) {
  return (
    <section className="memories-card">
      <div className="section-heading">
        <div>
          <p className="eyebrow">MEMÓRIA SEMÂNTICA</p>
          <h2>O que o Jarvis lembra</h2>
        </div>
        <div className="memory-actions">
          <button type="button" onClick={onRefresh}>
            Atualizar
          </button>
          <button type="button" onClick={onClearTechnical}>
            Limpar erros técnicos
          </button>
        </div>
      </div>
      <div className="memory-tabs">
        {(['conversations', 'user_memory'] as const).map(collection => (
          <button
            key={collection}
            type="button"
            className={memoryCollection === collection ? 'memory-tab-active' : ''}
            onClick={() => onSelectCollection(collection)}
          >
            {collection === 'conversations' ? 'Conversas' : 'Sobre você'}
          </button>
        ))}
      </div>
      {notice && <p className="settings-notice">{notice}</p>}
      {memories.length ? (
        <div className="memory-list">
          {memories.map((memory, index) => (
            <article key={memory.id || index}>
              <span>
                {memory.metadata?.timestamp
                  ? new Date(Number(memory.metadata.timestamp) * 1000).toLocaleString('pt-BR')
                  : memoryCollection === 'conversations'
                    ? 'CONVERSA'
                    : 'MEMÓRIA'}
              </span>
              <p>{memory.text || 'Memória sem conteúdo.'}</p>
            </article>
          ))}
        </div>
      ) : (
        <p className="empty-state">
          Nenhuma memória nesta coleção. O núcleo adiciona memórias conforme usa o Jarvis.
        </p>
      )}
    </section>
  )
}
