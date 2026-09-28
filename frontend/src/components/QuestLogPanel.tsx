import { useEffect, useState } from 'react'
import type { ProcessQuest, ProcessStepItem } from '../types'

type QuestLogPanelProps = {
  isOpen: boolean
  onClose: () => void
  quests: ProcessQuest[]
  onAbortQuest?: (questId: string) => void
}

export function QuestLogPanel({ isOpen, onClose, quests, onAbortQuest }: QuestLogPanelProps) {
  const [elapsed, setElapsed] = useState<Record<string, number>>({})

  useEffect(() => {
    if (!isOpen) return
    const interval = setInterval(() => {
      const now = Date.now()
      const updated: Record<string, number> = {}
      for (const q of quests) {
        if (q.status === 'active') {
          updated[q.id] = Math.floor((now - q.startedAt) / 1000)
        }
      }
      setElapsed(updated)
    }, 1000)
    return () => clearInterval(interval)
  }, [isOpen, quests])

  if (!isOpen) return null

  return (
    <div className={`quest-log-overlay ${isOpen ? 'is-open' : ''}`} onClick={onClose}>
      <aside className="quest-log-drawer" onClick={e => e.stopPropagation()}>
        <header className="quest-log-header">
          <div className="quest-log-title">
            <span className="quest-log-icon">📜</span>
            <h2>Quests & Processos</h2>
          </div>
          <button className="quest-log-close-btn" onClick={onClose} title="Fechar painel">
            ✕
          </button>
        </header>

        <div className="quest-log-content">
          {quests.length === 0 ? (
            <div className="quest-log-empty">
              <span className="quest-log-empty-icon">✨</span>
              <p>Nenhuma tarefa ou quest em execução no momento.</p>
              <span className="quest-log-empty-sub">As etapas de raciocínio e execução de ferramentas aparecerão aqui em tempo real.</span>
            </div>
          ) : (
            quests.map(quest => (
              <div key={quest.id} className={`quest-card quest-status-${quest.status}`}>
                <div className="quest-card-header">
                  <div className="quest-card-info">
                    <span className={`quest-badge quest-badge-${quest.status}`}>
                      {quest.status === 'active' && '⏳ Em Execução'}
                      {quest.status === 'completed' && '✅ Concluído'}
                      {quest.status === 'failed' && '❌ Falhou'}
                      {quest.status === 'aborted' && '🛑 Abortado'}
                    </span>
                    <h3>{quest.title}</h3>
                  </div>
                  {quest.status === 'active' && (
                    <div className="quest-timer">
                      ⏱️ {elapsed[quest.id] || 0}s
                    </div>
                  )}
                </div>

                <div className="quest-steps-list">
                  {quest.steps.map((step, idx) => (
                    <ProcessStepRow key={step.id || idx} step={step} index={idx + 1} />
                  ))}
                </div>

                {quest.status === 'active' && onAbortQuest && (
                  <button
                    className="quest-abort-btn"
                    onClick={() => onAbortQuest(quest.id)}
                  >
                    🛑 Abortar Quest
                  </button>
                )}
              </div>
            ))
          )}
        </div>
      </aside>
    </div>
  )
}

function ProcessStepRow({ step, index }: { step: ProcessStepItem; index: number }) {
  const getIcon = () => {
    switch (step.status) {
      case 'active':
        return '🔄'
      case 'done':
        return '✅'
      case 'error':
        return '❌'
      case 'pending':
      default:
        return '⚪'
    }
  }

  return (
    <div className={`process-step-row step-status-${step.status}`}>
      <span className="step-icon">{getIcon()}</span>
      <div className="step-content">
        <div className="step-header">
          <span className="step-index">#{index}</span>
          <span className="step-title">{step.title}</span>
          {step.toolName && <span className="step-tool-tag">{step.toolName}</span>}
        </div>
        {step.detail && <p className="step-detail">{step.detail}</p>}
      </div>
    </div>
  )
}
