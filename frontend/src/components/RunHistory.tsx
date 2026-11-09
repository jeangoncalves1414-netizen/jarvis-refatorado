import { useEffect, useRef, useState } from 'react'
import { ArrowUpRight, ChevronLeft, ChevronRight, Layers, Square, X } from 'lucide-react'
import { actionLabels, type AgentAction } from '../hooks/useOperationalSnapshot'
import { panelRequest } from '../utils/panelApi'
import { ActionDetails, type Decisions } from './ActionHistory'

type Run = { id: string; session_id: string | null; mode: string; status: string; created_at: number; finished_at: number | null; result_summary: string | null; source?: string; origin?: string; reply?: string | null; progress?: RunProgress | null }
// Contador do loop agêntico (lote 6): etapa e chamadas ao modelo do pedido.
type RunProgress = { step?: number; max_steps?: number; model_calls?: number; max_model_calls?: number; phase?: string; wait_remaining?: number; wait_total?: number }
const progressPhases: Record<string, string> = { planning: 'planejando', acting: 'executando', verifying: 'verificando', waiting: 'aguardando', waiting_approval: 'aguardando aprovação', resumed: 'retomando', limit: 'limite atingido', done: 'concluído', cancelled: 'cancelado' }
// Espera real entre ações (ferramenta wait): "Aguardando 42 s de 50".
const waitText = (progress?: RunProgress | null) => progress?.phase === 'waiting' && typeof progress.wait_remaining === 'number' && typeof progress.wait_total === 'number' ? `Aguardando ${progress.wait_remaining} s de ${progress.wait_total}${progress.max_steps ? ` · etapa ${progress.step ?? 0} de ${progress.max_steps}` : ''}` : ''
const progressText = (progress?: RunProgress | null) => waitText(progress) || (progress && typeof progress.step === 'number' && typeof progress.max_steps === 'number' ? `Etapa ${progress.step} de ${progress.max_steps}${typeof progress.model_calls === 'number' ? ` · modelo ${progress.model_calls}/${progress.max_model_calls ?? '?'}` : ''}${progress.phase ? ` · ${progressPhases[progress.phase] || progress.phase}` : ''}` : '')
type RunEvent = { id: number; kind: string; status: string; timestamp: number; summary: string | null; action_id: string | null }
type RunDetail = { run: Run; actions: AgentAction[]; events: RunEvent[] }
type RunPage = { runs: Run[]; next_cursor: number | null }
const labels: Record<string, string> = { running: 'Em andamento', awaiting_confirmation: 'Aguardando aprovação', cancel_requested: 'Cancelamento solicitado', cancelled: 'Cancelado', succeeded: 'Concluído', failed: 'Encerrado com falha', interrupted: 'Interrompido após reinício' }
const modes: Record<string, string> = { general: 'Conversa', planning: 'Planejamento', research: 'Pesquisa', tutor: 'Estudo', react: 'Execução por etapas', swarm: 'Especialista', memory: 'Memória em segundo plano', controls: 'Controles do PC', browser: 'Navegador automatizado', script: 'Script confirmado', terminal: 'Terminal', direct: 'Ação direta' }
// Quem disparou o pedido (C6). Rotina, palma e celular ficam prontos para os gatilhos futuros.
const runOrigins: Record<string, string> = { chat: 'Chat', voice: 'Voz', routine: 'Rotina', clap: 'Palma', window: 'Janela', mobile: 'Celular', system: 'Segundo plano' }
// Etapas internas sem ferramenta (Swarm, Racing, memória) aparecem com o próprio rótulo.
const eventKinds: Record<string, string> = { step: 'Etapa interna', failure: 'Etapa com falha', background: 'Segundo plano', background_failed: 'Segundo plano com falha', fallback: 'Troca de modelo', resume_pending: 'Aguardando aprovação para continuar', resume_cleared: 'Sequência retomada', resume_finished: 'Continuação encerrada' }
const terminal = new Set(['succeeded', 'failed', 'cancelled', 'interrupted'])
const when = (timestamp: number) => new Date(timestamp * 1000).toLocaleString('pt-BR')

// Each request keeps its last successful response when a refresh fails.
function useRunData<T>(path: string, revision: string, validate: (data: T) => boolean) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const previousPath = useRef(path)
  useEffect(() => {
    const controller = new AbortController()
    let disposed = false
    if (previousPath.current !== path) { setData(null); previousPath.current = path }
    setLoading(true); setError('')
    const timeout = setTimeout(() => controller.abort(), 10000)
    panelRequest<T>(path, { signal: controller.signal }).then(value => {
      if (!validate(value)) throw new Error('O servidor ainda não fornece os pedidos de execução.')
      if (!disposed) setData(value)
    }).catch(err => { if (!disposed) setError(err.name === 'AbortError' ? 'O servidor não respondeu a tempo.' : err.message) })
      .finally(() => { clearTimeout(timeout); if (!disposed) setLoading(false) })
    return () => { disposed = true; clearTimeout(timeout); controller.abort() }
  }, [path, revision, validate])
  return { data, error, loading }
}
const validPage = (data: RunPage) => Array.isArray(data.runs) && (data.next_cursor === null || typeof data.next_cursor === 'number')
const validDetail = (data: RunDetail) => !!data.run && Array.isArray(data.actions) && Array.isArray(data.events)

function RunDetails({ id, revision, onClose, onOpenSession, onRefresh, ...decisions }: { id: string; revision: string; onClose: () => void; onOpenSession: (id: string) => void; onRefresh: () => void } & Decisions) {
  const { data, error, loading } = useRunData<RunDetail>(`/api/runs/${encodeURIComponent(id)}`, revision, validDetail)
  const [cancelError, setCancelError] = useState('')
  const [cancelling, setCancelling] = useState(false)
  const cancelLock = useRef(false)
  const [selectedAction, setSelectedAction] = useState('')
  const [requested, setRequested] = useState(false)
  const run = data?.run
  const cancel = async () => {
    if (cancelLock.current) return
    cancelLock.current = true; setCancelling(true); setCancelError('')
    try {
      const response = await panelRequest<{ run: Run }>(`/api/runs/${encodeURIComponent(id)}/cancel`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })
      if (!response.run || !['cancel_requested', 'cancelled'].includes(response.run.status)) throw new Error('O servidor não confirmou a solicitação.')
      setRequested(true)
    } catch (err) { setCancelError(err instanceof Error ? err.message : 'Não foi possível solicitar o cancelamento.') }
    finally { cancelLock.current = false; setCancelling(false); onRefresh() }
  }
  return <section className="ws-action-detail" aria-label="Detalhes do pedido">
    <div className="ws-section-title"><h3>Detalhes do pedido</h3><button className="ws-icon-button" aria-label="Fechar pedido" onClick={onClose}><X size={16} /></button></div>
    {(error || cancelError) && <p className="ws-error" role="alert">{cancelError || error}{error && data && ' Exibindo o último estado recebido.'}</p>}
    {!data && loading && <p role="status">Carregando pedido…</p>}
    {run && <>
      <dl><dt>Estado registrado</dt><dd>{labels[run.status] || run.status}</dd><dt>Origem</dt><dd>{runOrigins[run.origin || 'chat'] || run.origin}</dd><dt>Iniciado</dt><dd>{when(run.created_at)}</dd><dt>Resultado</dt><dd>{run.result_summary || 'Ainda em processamento.'}</dd>{progressText(run.progress) && <><dt>Progresso</dt><dd>{progressText(run.progress)}</dd></>}{run.reply && <><dt>Resposta do agente</dt><dd>{run.reply}</dd></>}<dt>Conversa</dt><dd>{run.session_id ? <button className="ws-text-button" onClick={() => onOpenSession(run.session_id!)}>Abrir conversa <ArrowUpRight size={14} /></button> : 'Sem conversa vinculada'}</dd>{run.finished_at && <><dt>Duração total</dt><dd>{Math.max(0, run.finished_at - run.created_at).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} s</dd></>}</dl>
      {(run.status === 'cancel_requested' || (requested && !terminal.has(run.status))) && <p className="ws-warning" role="status">Cancelamento solicitado. Aguardando confirmação do encerramento; uma etapa já iniciada pode continuar até retornar.</p>}
      {!terminal.has(run.status) && <button className="ws-button" disabled={cancelling || requested || run.status === 'cancel_requested' || decisions.unavailable || !!error} onClick={() => void cancel()}><Square size={14} />{cancelling ? 'Solicitando…' : 'Cancelar pedido'}</button>}
      <h4>Etapas do pedido</h4>
      {data.actions.map(action => <button className="ws-run-action" key={action.id} aria-expanded={selectedAction === action.id} onClick={() => setSelectedAction(selectedAction === action.id ? '' : action.id)}><span className={`ws-dot ${action.status}`} /><span>{action.tool_name.replaceAll('_', ' ')}</span><span className="ws-tag">{actionLabels[action.status] || action.status}</span><ArrowUpRight size={14} /></button>)}
      {!data.actions.length && <p className="ws-muted">Nenhuma ferramenta registrada neste pedido.</p>}
      {selectedAction && <ActionDetails key={selectedAction} id={selectedAction} revision={revision} onClose={() => setSelectedAction('')} {...decisions} />}
      <h4>Eventos do pedido</h4>
      <ol className="ws-action-timeline">{data.events.map(event => <li key={event.id}><span className={`ws-dot ${event.status}`} /><div><strong>{event.action_id ? actionLabels[event.status] || event.status : eventKinds[event.kind] || labels[event.status] || event.status}</strong><time dateTime={new Date(event.timestamp * 1000).toISOString()}>{when(event.timestamp)}</time>{event.summary && <p>{event.summary}</p>}</div></li>)}</ol>
      <p className="ws-footnote">Cancelar impede novas etapas. Não desfaz efeitos anteriores. Identificador: {run.id}</p>
    </>}
  </section>
}

export function RunHistory({ revision, sessionId, onOpenSession, onRefresh, initialRunId = '', ...decisions }: { revision: string; sessionId: string; onOpenSession: (id: string) => void; onRefresh: () => void; initialRunId?: string } & Decisions) {
  const [status, setStatus] = useState('all')
  const [onlyCurrent, setOnlyCurrent] = useState(false)
  const [showReads, setShowReads] = useState(false)
  const [cursors, setCursors] = useState<(number | null)[]>([null])
  const [selectedId, setSelectedId] = useState(initialRunId)
  const detailAnchor = useRef<HTMLDivElement>(null)
  useEffect(() => { if (initialRunId) detailAnchor.current?.focus() }, [initialRunId])
  const params = new URLSearchParams({ limit: '20' })
  const cursor = cursors[cursors.length - 1]
  if (cursor !== null) params.set('before', String(cursor))
  if (status !== 'all') params.set('status', status)
  if (onlyCurrent && sessionId) params.set('session_id', sessionId)
  if (showReads) params.set('include_reads', '1')
  const { data, error, loading } = useRunData<RunPage>(`/api/runs?${params}`, revision, validPage)
  const reset = () => { setCursors([null]); setSelectedId('') }
  return <section className="ws-panel" aria-label="Pedidos de execução">
    <div className="ws-section-title"><h2>Pedidos de execução</h2><span className="ws-muted">{loading ? 'Atualizando…' : 'Cada pedido, suas etapas'}</span></div>
    <div className="ws-filters"><select aria-label="Filtrar pedidos por estado" value={status} onChange={event => { setStatus(event.target.value); reset() }}><option value="all">Todos os estados</option>{Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><button className="ws-button" aria-pressed={onlyCurrent} disabled={!sessionId} onClick={() => { setOnlyCurrent(!onlyCurrent); reset() }}>{onlyCurrent ? 'Conversa atual' : 'Todas as conversas'}</button><button className="ws-button" aria-pressed={showReads} onClick={() => { setShowReads(!showReads); reset() }}>{showReads ? 'Com leituras das janelas' : 'Ocultar leituras das janelas'}</button></div>
    {error && <p className="ws-error" role="alert">{error}{data && ' Exibindo a última lista recebida.'}</p>}
    <div aria-busy={loading}>{data?.runs.map(run => <button key={run.id} className={`ws-run-row ${selectedId === run.id ? 'selected' : ''}`} aria-expanded={selectedId === run.id} onClick={() => setSelectedId(selectedId === run.id ? '' : run.id)}><span className={`ws-dot ${run.status}`} /><div><strong>{modes[run.mode] || 'Pedido do agente'}</strong><span>{runOrigins[run.origin || 'chat'] || run.origin} · {when(run.created_at)}{!terminal.has(run.status) && progressText(run.progress) ? ' · ' + progressText(run.progress) : ''}</span></div><span className="ws-tag">{labels[run.status] || run.status}</span><ArrowUpRight size={15} /></button>)}</div>
    {!loading && !error && !data?.runs.length && <div className="ws-empty"><Layers size={25} /><h3>Nenhum pedido nesta seleção</h3><p>Novos pedidos processados pela Central aparecerão aqui. Ações anteriores continuam no histórico abaixo.</p></div>}
    <nav className="ws-history-pagination" aria-label="Páginas dos pedidos"><button className="ws-button" disabled={loading || cursors.length === 1} onClick={() => { setCursors(cursors.slice(0, -1)); setSelectedId('') }}><ChevronLeft size={15} /> Pedidos anteriores</button><span className="ws-muted">{cursors.length}</span><button className="ws-button" disabled={loading || !!error || data?.next_cursor == null} onClick={() => { if (data?.next_cursor != null) { setCursors([...cursors, data.next_cursor]); setSelectedId('') } }}>Mais pedidos <ChevronRight size={15} /></button></nav>
    {selectedId && <div ref={detailAnchor} tabIndex={-1}><RunDetails key={selectedId} id={selectedId} revision={revision} onClose={() => setSelectedId('')} onOpenSession={onOpenSession} onRefresh={onRefresh} {...decisions} /></div>}
  </section>
}
