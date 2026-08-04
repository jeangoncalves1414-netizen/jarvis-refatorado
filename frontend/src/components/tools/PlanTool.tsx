import { useState } from 'react'

export type PlanStep = {
  id: string | number
  title: string
  status: 'completed' | 'in-progress' | 'pending'
  targetFile?: string
  description?: string
}

export type PlanToolProps = {
  title?: string
  steps: PlanStep[]
  defaultOpen?: boolean
}

export function PlanTool({
  title = 'Plano de Execução do Jarvis',
  steps = [],
  defaultOpen = true,
}: PlanToolProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen)

  const completedCount = steps.filter((s) => s.status === 'completed').length
  const totalCount = steps.length
  const progressPercent = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0

  return (
    <div className="pt-container">
      {/* Header bar */}
      <div className="pt-header">
        <button
          type="button"
          onClick={() => setIsOpen((prev) => !prev)}
          className="pt-header-btn"
        >
          <div className="pt-header-left">
            <span className="pt-icon">🧠</span>
            <span className="pt-title">{title}</span>
            <span className="pt-badge">{completedCount}/{totalCount} Concluídos</span>
          </div>
          <span className={`pt-chevron ${isOpen ? 'is-open' : ''}`}>▼</span>
        </button>

        {/* Progress Bar */}
        <div className="pt-progress-track">
          <div
            className="pt-progress-fill"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      {/* Steps Container */}
      {isOpen && (
        <div className="pt-steps-body">
          {steps.map((step, idx) => (
            <div key={step.id || idx} className={`pt-step-item pt-step-${step.status}`}>
              <div className="pt-step-status-icon">
                {step.status === 'completed' ? '✓' : step.status === 'in-progress' ? '⏳' : '○'}
              </div>
              <div className="pt-step-info">
                <div className="pt-step-header">
                  <strong className="pt-step-title">{step.title}</strong>
                  {step.targetFile && <code className="pt-step-file">{step.targetFile}</code>}
                </div>
                {step.description && <p className="pt-step-desc">{step.description}</p>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
