import React from 'react'

export type PromptSuggestionItem = {
  icon: string
  label: string
  prompt: string
  highlight?: string
}

const DEFAULT_SUGGESTIONS: PromptSuggestionItem[] = [
  { icon: '🎬', label: 'Jarvis Cinema', prompt: 'Coloca o filme Matrix no Jarvis Cinema', highlight: 'Matrix' },
  { icon: '🌤️', label: 'Previsão do Clima', prompt: 'Qual a temperatura e previsão do tempo em São Paulo hoje?', highlight: 'São Paulo' },
  { icon: '🧠', label: 'Plano de Estudos', prompt: 'Planejar uma rotina de estudos focada em exatas para o ENEM', highlight: 'ENEM' },
  { icon: '📈', label: 'Mercado Financeiro', prompt: 'Como estão as cotações do Dólar, Euro e Bitcoin agora?', highlight: 'Bitcoin' },
  { icon: '👁️', label: 'Visão de Tela', prompt: 'Analisar a tela atual e resumir o conteúdo principal', highlight: 'tela' },
]

export function PromptSuggestions({
  onSelect,
  suggestions = DEFAULT_SUGGESTIONS,
}: {
  onSelect: (prompt: string) => void
  suggestions?: PromptSuggestionItem[]
}) {
  return (
    <div className="prompt-suggestions-container">
      <div className="prompt-suggestions-scroll">
        {suggestions.map((item, idx) => (
          <button
            key={idx}
            type="button"
            className="prompt-suggestion-pill"
            onClick={() => onSelect(item.prompt)}
          >
            <span className="prompt-suggestion-icon">{item.icon}</span>
            <span className="prompt-suggestion-label">{item.label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
