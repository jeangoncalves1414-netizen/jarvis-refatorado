import { useCallback, useEffect, useState } from 'react'

type Action = { id: string; tool_name: string; preview: string; risk: string; status: string; result_summary?: string | null; updated_at: number }
type Goal = { id: string; title: string; next_action: string; status: string }
type Snapshot = { components: { id: string; label: string; status: string; reason: string }[]; summary: { pending_actions: number; failed_actions: number; devices: number; active_goals?: number }; pending_actions: Action[]; recent_actions: Action[]; goals: Goal[] }

const labels: Record<string, string> = { awaiting_confirmation: 'Aguardando confirmação', authorized: 'Confirmada', running: 'Em execução', succeeded: 'Concluída', failed: 'Falhou', cancelled: 'Cancelada', proposed: 'Proposta' }

export function MissionControlPage() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [error, setError] = useState('')
  const [goalTitle, setGoalTitle] = useState('')
  const [goalStep, setGoalStep] = useState('')
  const refresh = useCallback(async () => {
    try {
      const response = await fetch('/api/mission-control')
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || 'Não foi possível atualizar a central.')
      setSnapshot(data); setError('')
    } catch (err) { setError(err instanceof Error ? err.message : 'Falha ao atualizar.') }
  }, [])
  useEffect(() => { void refresh(); const timer = window.setInterval(() => void refresh(), 8000); return () => window.clearInterval(timer) }, [refresh])
  const decide = async (action: Action, command: 'approve' | 'reject') => {
    await fetch(`/api/actions/${action.id}/${command}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })
    await refresh()
  }
  const createGoal = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!goalTitle.trim()) return
    await fetch('/api/goals', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'create', title: goalTitle, next_action: goalStep }) })
    setGoalTitle(''); setGoalStep(''); await refresh()
  }
  const reviewGoal = async (goal: Goal) => { await fetch('/api/goals', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'suggest', goal_id: goal.id }) }); await refresh() }
  return <section className="mission-control">
    <header><div><p className="eyebrow">MISSION CONTROL</p><h1>Central operacional</h1><p>Estado real do Jarvis — sem expor conversas, áudio ou credenciais.</p></div><button onClick={() => void refresh()}>Atualizar</button></header>
    {error && <p className="mission-error">{error}</p>}
    <div className="mission-stats"><article><b>{snapshot?.summary.pending_actions ?? 0}</b><span>ações pendentes</span></article><article><b>{snapshot?.summary.active_goals ?? 0}</b><span>metas ativas</span></article><article><b>{snapshot?.summary.devices ?? 0}</b><span>dispositivos</span></article></div>
    <div className="mission-grid"><article className="mission-card"><h2>Sistemas</h2>{snapshot?.components.map(item => <div className="mission-row" key={item.id}><span className={`mission-dot ${item.status}`} /><div><strong>{item.label}</strong><small>{item.reason}</small></div></div>)}</article>
      <article className="mission-card"><h2>Confirmações</h2>{snapshot?.pending_actions.length ? snapshot.pending_actions.map(action => <div className="mission-action" key={action.id}><strong>{action.preview}</strong><small>{labels[action.status] || action.status} · risco {action.risk}</small>{action.status === 'awaiting_confirmation' && <div><button onClick={() => void decide(action, 'approve')}>Confirmar</button><button className="secondary" onClick={() => void decide(action, 'reject')}>Cancelar</button></div>}</div>) : <p>Nenhuma ação exige sua atenção.</p>}</article>
      <article className="mission-card mission-wide"><h2>Histórico recente</h2>{snapshot?.recent_actions.map(action => <div className="mission-action" key={action.id}><strong>{action.tool_name.replaceAll('_', ' ')}</strong><small>{labels[action.status] || action.status} · {action.result_summary || action.preview}</small></div>)}</article>
      <article className="mission-card mission-wide"><h2>Objetivos</h2><form className="mission-goal-form" onSubmit={createGoal}><input value={goalTitle} onChange={event => setGoalTitle(event.target.value)} placeholder="Objetivo, por exemplo: estudar programação" /><input value={goalStep} onChange={event => setGoalStep(event.target.value)} placeholder="Próxima ação concreta" /><button>Criar objetivo</button></form>{snapshot?.goals.length ? snapshot.goals.map(goal => <div className="mission-action" key={goal.id}><strong>{goal.title}</strong><small>{goal.next_action || 'Defina o próximo passo na revisão.'}</small><div><button onClick={() => void reviewGoal(goal)}>Revisar plano</button></div></div>) : <p>Crie uma meta para o Jarvis acompanhar com intervenções consentidas.</p>}</article>
    </div>
  </section>
}
