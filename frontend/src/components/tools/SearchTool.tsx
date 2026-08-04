import { useState, useEffect } from 'react'

export type SearchResult = {
  title: string
  source: string
  url?: string
  snippet?: string
  excerpt?: string
  date?: string
}

export type SearchStep = {
  label: string
  status?: 'pending' | 'running' | 'completed' | 'error'
  detail?: string
}

export type SearchPayload = {
  query: string
  results: SearchResult[]
  steps?: SearchStep[]
  workflow?: 'search' | 'research'
}

export type SearchToolProps = {
  state?: 'searching' | 'done'
  query: string
  results?: SearchResult[]
  steps?: SearchStep[]
  workflow?: 'search' | 'research'
  defaultOpen?: boolean
  className?: string
}

export function SearchTool({
  state = 'done',
  query,
  results = [],
  steps = [],
  workflow = 'search',
  defaultOpen = workflow !== 'research',
  className = '',
}: SearchToolProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen)
  const isSearching = state === 'searching'
  const totalResults = results.length
  const expandable = totalResults > 0

  return (
    <div className={`st-container ${className}`}>
      {/* Header bar */}
      <button
        type="button"
        onClick={() => expandable && setIsOpen((prev) => !prev)}
        className={`st-header-btn ${expandable ? 'is-clickable' : ''}`}
        aria-expanded={expandable ? isOpen : undefined}
        aria-controls={expandable ? 'search-sources-panel' : undefined}
      >
        <div className="st-header-left">
          <span className="st-icon">🔍</span>
          {isSearching ? (
            <span className="st-shimmer-text">Pesquisando na web por "{query}"…</span>
          ) : (
            <span className="st-done-text">
              {workflow === 'research' ? 'Workflow concluído: ' : 'Encontrados '}<strong>{totalResults}</strong> fonte{totalResults === 1 ? '' : 's'} para "{query}"
            </span>
          )}
        </div>
        {expandable && (
          <span className={`st-chevron ${isOpen ? 'is-open' : ''}`}>▼</span>
        )}
      </button>

      {/* Expandable Results Card */}
      {expandable && isOpen && (
          <div className="st-card" id="search-sources-panel">
          {steps.length > 0 && (
            <div className="st-workflow" aria-label="Etapas da pesquisa">
              {steps.map((step, index) => (
                <div className="st-workflow-step" key={`${step.label}-${index}`}>
                  <span className={`st-step-dot st-step-${step.status || 'completed'}`} />
                  <div>
                    <strong>{step.label}</strong>
                    {step.detail && <small>{step.detail}</small>}
                  </div>
                </div>
              ))}
            </div>
          )}
          <div className="st-card-header">
            <span>{workflow === 'research' ? 'Fontes consultadas' : 'Fontes encontradas'}</span>
            <small>{totalResults} link(s) verificado(s)</small>
          </div>
          <div className="st-results-list">
            {results.map((res, idx) => (
              <a
                key={idx}
                href={res.url || '#'}
                target="_blank"
                rel="noopener noreferrer"
                className="st-result-item"
                onClick={(e) => !res.url && e.preventDefault()}
              >
                <div className="st-result-icon">📄</div>
                <div className="st-result-body">
                  <div className="st-result-title">{res.title}</div>
                  <div className="st-result-domain">{res.source} {res.date ? `• ${res.date}` : ''}</div>
                  {res.snippet && <div className="st-result-snippet">{res.snippet}</div>}
                  {res.excerpt && <div className="st-result-excerpt">Trecho consultado: {res.excerpt}</div>}
                </div>
                {res.url && <span className="st-link-arrow">↗</span>}
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
