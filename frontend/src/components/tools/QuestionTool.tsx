import { useState } from 'react'

export type QuestionOption = {
  id: string
  label: string
  description?: string
}

export type QuestionToolProps = {
  question: string
  options: QuestionOption[]
  multiSelect?: boolean
  onAnswer?: (selectedIds: string[]) => void
}

export function QuestionTool({
  question,
  options = [],
  multiSelect = false,
  onAnswer,
}: QuestionToolProps) {
  const [selected, setSelected] = useState<string[]>([])
  const [submitted, setSubmitted] = useState(false)

  const handleSelect = (id: string) => {
    if (submitted) return
    if (multiSelect) {
      setSelected((prev) =>
        prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
      )
    } else {
      setSelected([id])
    }
  }

  const handleSubmit = () => {
    if (selected.length === 0 || submitted) return
    setSubmitted(true)
    onAnswer?.(selected)
  }

  return (
    <div className="qt-container">
      <div className="qt-header">
        <span className="qt-icon">💬</span>
        <span className="qt-question">{question}</span>
        {multiSelect && <small className="qt-multi-tag">(Múltipla escolha)</small>}
      </div>

      <div className="qt-options-grid">
        {options.map((opt) => {
          const isSelected = selected.includes(opt.id)
          return (
            <button
              key={opt.id}
              type="button"
              disabled={submitted}
              onClick={() => handleSelect(opt.id)}
              className={`qt-option-card ${isSelected ? 'is-selected' : ''} ${submitted ? 'is-disabled' : ''}`}
            >
              <div className="qt-option-check">{isSelected ? '✓' : '○'}</div>
              <div className="qt-option-text">
                <strong className="qt-option-label">{opt.label}</strong>
                {opt.description && <span className="qt-option-desc">{opt.description}</span>}
              </div>
            </button>
          )
        })}
      </div>

      {!submitted ? (
        <div className="qt-footer">
          <button
            type="button"
            disabled={selected.length === 0}
            onClick={handleSubmit}
            className="qt-submit-btn"
          >
            Confirmar Seleção ({selected.length})
          </button>
        </div>
      ) : (
        <div className="qt-submitted-badge">
          <span>✓ Resposta enviada ao Jarvis</span>
        </div>
      )}
    </div>
  )
}
