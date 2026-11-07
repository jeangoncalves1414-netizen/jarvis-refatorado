import { useRef, useState, type FormEvent } from 'react'
import { Activity, ArrowUpRight, Check, Clock3, RefreshCw, ShieldCheck, X } from 'lucide-react'
import { type AgentAction, type AgentGoal, type OperationalState } from '../hooks/useOperationalSnapshot'
import { panelRequest } from '../utils/panelApi'
import { ActionHistory } from '../components/ActionHistory'
import { RunHistory } from '../components/RunHistory'

export function MissionControlPage({ operational, sessionId, onOpenSession, initialRunId }: { operational: OperationalState; sessionId: string; onOpenSession: (id: string) => void; initialRunId?: string }) {
  const { snapshot, error, updatedAt, refresh } = operational
  const [mutationError, setMutationError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState<string[]>([])
  const locks = useRef(new Set<string>())
  const [goalTitle, setGoalTitle] = useState('')
  const [goalStep, setGoalStep] = useState('')
  const actions = [...new Map([...(snapshot?.pending_actions || []), ...(snapshot?.recent_actions || [])].map(item => [item.id, item])).values()]
  const mutate = async (key: string, path: string, payload: object, success: () => void) => {
    if (locks.current.has(key)) return
    locks.current.add(key); setBusy([...locks.current]); setMutationError(''); setNotice('')
    try { await panelRequest(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }); success() }
    catch (err) { setMutationError(err instanceof Error ? err.message : 'Não foi possível concluir a ação.') }
    finally { locks.current.delete(key); setBusy([...locks.current]); refresh() }
  }
  const decide = (action: AgentAction, command: 'approve' | 'reject') => void mutate(action.id, `/api/actions/${encodeURIComponent(action.id)}/${command}`, {}, () => setNotice(command === 'approve' ? 'Solicitação processada. Confira o resultado no histórico.' : 'Proposta recusada.'))
  const createGoal = (event: FormEvent) => {
    event.preventDefault()
    if (goalTitle.trim()) void mutate('goal', '/api/goals', { action: 'create', title: goalTitle.trim(), next_action: goalStep.trim() }, () => { setGoalTitle(''); setGoalStep(''); setNotice('Objetivo criado.') })
  }
  const reviewGoal = (goal: AgentGoal) => void mutate(goal.id, '/api/goals', { action: 'suggest', goal_id: goal.id }, () => setNotice('Revisão solicitada.'))
  const pending = snapshot?.pending_actions.filter(item => item.status === 'awaiting_confirmation') || []
  return <section className="ws-content-page">
    <div className="ws-page-heading"><div><span className="ws-overline">CENTRAL DE CONTROLE</span><h1>Execuções</h1><p>Da proposta ao resultado. Acompanhe cada ação do agente.</p></div><button className="ws-button" onClick={refresh}><RefreshCw size={15} /> Atualizar</button></div>
    {(error || mutationError) && <div className="ws-error" role="alert">{mutationError || error}{error && snapshot && ' Exibindo o último estado recebido.'}</div>}
    {notice && <div className="ws-feedback" role="status">{notice}</div>}
    <div className="ws-stats"><article><ShieldCheck size={19} /><strong>{snapshot ? snapshot.summary.awaiting_approvals ?? pending.length : '—'}</strong><span>Aprovações pendentes</span></article><article><Activity size={19} /><strong>{snapshot ? snapshot.summary.running_actions ?? actions.filter(item => ['running', 'authorized'].includes(item.status)).length : '—'}</strong><span>Ações em andamento</span></article><article><Clock3 size={19} /><strong>{snapshot?.summary.failed_actions ?? '—'}</strong><span>Falhas no histórico</span></article></div>
    {!!pending.length && <section className="ws-approvals"><div className="ws-section-title"><h2>Precisam da sua atenção</h2><span className="ws-tag amber">{pending.length} pendentes</span></div>{pending.map(action => <article className="ws-approval" key={action.id}><div><span className="ws-overline">{action.tool_name.replaceAll('_', ' ')}</span><h3>{action.preview}</h3><span className="ws-tag">Risco: {action.risk}</span></div><div className="ws-approval-buttons"><button className="ws-button" disabled={busy.includes(action.id) || !!error} onClick={() => decide(action, 'reject')}><X size={15} /> Recusar</button><button className="ws-button primary" disabled={busy.includes(action.id) || !!error} onClick={() => decide(action, 'approve')}><Check size={15} />{busy.includes(action.id) ? 'Processando…' : 'Autorizar uma vez'}</button></div></article>)}</section>}
    <RunHistory initialRunId={initialRunId} revision={`${updatedAt}:${operational.revision}`} sessionId={sessionId} onOpenSession={onOpenSession} onRefresh={refresh} onDecide={decide} busy={busy} unavailable={!!error || !snapshot} />
    <ActionHistory revision={`${updatedAt}:${operational.revision}`} onDecide={decide} busy={busy} unavailable={!!error || !snapshot} />
    <section className="ws-panel"><div className="ws-section-title"><h2>Objetivos</h2><span className="ws-muted">Próximos passos do agente</span></div><form className="ws-goal-form" onSubmit={createGoal}><input aria-label="Título do objetivo" placeholder="O que você quer alcançar?" value={goalTitle} onChange={event => setGoalTitle(event.target.value)} disabled={busy.includes('goal')} required /><input aria-label="Próximo passo" placeholder="Qual é o primeiro passo?" value={goalStep} onChange={event => setGoalStep(event.target.value)} disabled={busy.includes('goal')} /><button className="ws-button" disabled={busy.includes('goal') || !goalTitle.trim() || !!error}>{busy.includes('goal') ? 'Criando…' : 'Criar objetivo'}</button></form>{snapshot?.goals.map(goal => <div className="ws-goal" key={goal.id}><div><strong>{goal.title}</strong><p>{goal.next_action || 'Próximo passo a definir.'}</p></div><button className="ws-text-button" disabled={busy.includes(goal.id) || !!error} onClick={() => reviewGoal(goal)}>Revisar plano <ArrowUpRight size={14} /></button></div>)}</section>
  </section>
}
