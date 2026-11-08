import { useCallback, useEffect, useState } from 'react'
import { panelRequest } from '../utils/panelApi'

export type AgentAction = { id: string; tool_name: string; preview: string; risk: string; status: string; result_summary?: string | null; updated_at: number; run_id?: string | null; source?: string }
export type AgentGoal = { id: string; title: string; next_action: string; status: string }
// Estado real de cada capacidade (O1, O2). "reachable" vem da última chamada real desde que o servidor iniciou.
export type CapabilityFallback = { from: string; to: string; model?: string | null; reason: string; at: number }
export type Capability = {
  id: string; label: string; group: string; status: string; configured: boolean | null; reachable: boolean | null
  last_success_at: number | null; last_failure_at: number | null; last_failure_reason: string | null
  provider?: string | null; model?: string | null; latency_ms?: number | null; fallback?: CapabilityFallback | null; reason: string; target?: string
}
export type OperationalSnapshot = {
  components: { id: string; label: string; status: string; reason: string }[]
  capabilities?: Capability[]; health_since?: number
  summary: { pending_actions: number; awaiting_approvals?: number; running_actions?: number; failed_actions: number; devices: number; active_goals?: number }
  pending_actions: AgentAction[]; recent_actions: AgentAction[]; goals: AgentGoal[]
}
export const actionLabels: Record<string, string> = { awaiting_confirmation: 'Aguardando aprovação', authorized: 'Autorizada', running: 'Em execução', succeeded: 'Concluída', failed: 'Falhou', cancelled: 'Recusada / cancelada', proposed: 'Proposta', expired: 'Expirada', interrupted: 'Interrompida; efeito desconhecido' }

export function useOperationalSnapshot() {
  const [snapshot, setSnapshot] = useState<OperationalSnapshot | null>(null)
  const [error, setError] = useState('')
  const [updatedAt, setUpdatedAt] = useState<number | null>(null)
  const [revision, setRevision] = useState(0)
  const refresh = useCallback(() => setRevision(value => value + 1), [])
  useEffect(() => {
    let disposed = false
    let timer: ReturnType<typeof setTimeout>
    let controller: AbortController
    const poll = async () => {
      controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 10000)
      try {
        const data = await panelRequest<OperationalSnapshot>('/api/mission-control', { signal: controller.signal })
        if (!Array.isArray(data.components) || !Array.isArray(data.pending_actions) || !Array.isArray(data.recent_actions) || !Array.isArray(data.goals) || !data.summary) throw new Error('A central de controle não está disponível neste servidor.')
        if (!disposed) { setSnapshot(data); setUpdatedAt(Date.now()); setError('') }
      } catch (err) {
        if (!disposed) setError(err instanceof Error && err.name !== 'AbortError' ? err.message : 'O servidor não respondeu a tempo.')
      } finally {
        clearTimeout(timeout)
        if (!disposed) timer = setTimeout(poll, 8000)
      }
    }
    void poll()
    return () => { disposed = true; clearTimeout(timer); controller?.abort() }
  }, [revision])
  return { snapshot, error, updatedAt, refresh, revision }
}
export type OperationalState = ReturnType<typeof useOperationalSnapshot>
