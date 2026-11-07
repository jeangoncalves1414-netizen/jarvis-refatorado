import { useCallback, useState } from 'react'
import type { ProcessQuest, ProcessStepItem, ProcessStepStatus } from '../types'

export function useQuestLog() {
  const [isOpen, setIsOpen] = useState(false)
  const [quests, setQuests] = useState<ProcessQuest[]>([])

  const openQuestLog = useCallback(() => setIsOpen(true), [])
  const closeQuestLog = useCallback(() => setIsOpen(false), [])
  const toggleQuestLog = useCallback(() => setIsOpen(prev => !prev), [])

  const startQuest = useCallback((title: string): string => {
    const id = 'quest_' + Date.now() + '_' + Math.random().toString(36).slice(2, 6)
    const newQuest: ProcessQuest = {
      id,
      title,
      steps: [],
      status: 'active',
      startedAt: Date.now(),
    }
    setQuests(prev => [newQuest, ...prev])
    return id
  }, [])

  const addStep = useCallback((questId: string, stepTitle: string, toolName?: string, detail?: string): string => {
    const stepId = 'step_' + Date.now() + '_' + Math.random().toString(36).slice(2, 6)
    const newStep: ProcessStepItem = {
      id: stepId,
      title: stepTitle,
      toolName,
      detail,
      status: 'active',
      startedAt: Date.now(),
    }

    setQuests(prev =>
      prev.map(q => {
        if (q.id !== questId) return q
        // mark previous active step as done
        const updatedSteps = q.steps.map(s => (s.status === 'active' ? { ...s, status: 'done' as ProcessStepStatus, endedAt: Date.now() } : s))
        return { ...q, steps: [...updatedSteps, newStep] }
      })
    )
    return stepId
  }, [])

  const updateStepStatus = useCallback((questId: string, stepId: string, status: ProcessStepStatus, detail?: string) => {
    setQuests(prev =>
      prev.map(q => {
        if (q.id !== questId) return q
        const updatedSteps = q.steps.map(s => {
          if (s.id !== stepId) return s
          return { ...s, status, detail: detail || s.detail, endedAt: Date.now() }
        })
        return { ...q, steps: updatedSteps }
      })
    )
  }, [])

  const completeQuest = useCallback((questId: string, status: 'completed' | 'failed' | 'aborted' = 'completed') => {
    setQuests(prev =>
      prev.map(q => {
        if (q.id !== questId) return q
        const updatedSteps = q.steps.map(s => (s.status === 'active' ? { ...s, status: (status === 'failed' ? 'error' : 'done') as ProcessStepStatus, endedAt: Date.now() } : s))
        return { ...q, status, steps: updatedSteps }
      })
    )
  }, [])

  return {
    isOpen,
    openQuestLog,
    closeQuestLog,
    toggleQuestLog,
    quests,
    startQuest,
    addStep,
    updateStepStatus,
    completeQuest,
  }
}
