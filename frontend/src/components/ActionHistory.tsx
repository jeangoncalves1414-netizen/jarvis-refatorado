import { useEffect, useState } from 'react'
import { Activity, ArrowUpRight, Check, ChevronLeft, ChevronRight, Search, X } from 'lucide-react'
import { actionLabels, type AgentAction } from '../hooks/useOperationalSnapshot'
import { panelRequest } from '../utils/panelApi'
import { AlwaysAllowButton } from './AutoApprovals'

type ActionEvent = { id: number; kind: string; status: string; timestamp: number; summary?: string | null }
type ActionDetail = { action: AgentAction; events: ActionEvent[] }
type ActionPage = { actions: AgentAction[]; next_cursor: number | null }
export type Decisions = { onDecide: (action: AgentAction, command: 'approve' | 'reject') => void; busy: string[]; unavailable: boolean }
const when = (timestamp: number) => new Date(timestamp * 1000).toLocaleString('pt-BR')
// Origem gravada pelo Action Kernel (C10): "voice:" vem da voz; "api:" e "panel:" de rotas e janelas.
const originLabels: [string, string][] = [['voice:', 'Voz'], ['panel:', 'Janela do painel'], ['api:browser', 'Navegador automatizado (rota direta)'], ['api:script', 'Script confirmado no chat'], ['api:terminal', 'Terminal'], ['react:', 'Execução por etapas'], ['function:', 'Conversa'], ['marker:', 'Conversa'], ['shortcut:', 'Conversa (atalho)']]
const originLabel = (source?: string) => !source ? 'Não registrada' : originLabels.find(([prefix]) => source.startsWith(prefix))?.[1] || source

export function ActionDetails({ id, revision, onClose, onDecide, busy, unavailable }: { id: string; revision: number | string | null; onClose: () => void } & Decisions) {
  const [detail, setDetail] = useState<ActionDetail | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    let disposed = false
    const timeout = setTimeout(() => controller.abort(), 10000)
    panelRequest<ActionDetail>(`/api/actions/${encodeURIComponent(id)}`, { signal: controller.signal })
      .then(data => {
        if (!data.action || !Array.isArray(data.events)) throw new Error('Este servidor ainda não fornece a linha do tempo.')
        if (!disposed) { setDetail(data); setError('') }
      }).catch(err => { if (!disposed) setError(err.name === 'AbortError' ? 'A linha do tempo não respondeu a tempo.' : err.message) })
      .finally(() => clearTimeout(timeout))
    return () => { disposed = true; clearTimeout(timeout); controller.abort() }
  }, [id, revision])
  const action = detail?.action
  const start = detail?.events.find(event => event.status === 'running')
  const terminal = action && ['succeeded', 'failed', 'cancelled', 'expired'].includes(action.status)
  return <section className="ws-action-detail" aria-label="Detalhes da ação">
    <div className="ws-section-title"><h3>Detalhes da ação</h3><button className="ws-icon-button" aria-label="Fechar detalhes" onClick={onClose}><X size={16} /></button></div>
    {error && <p className="ws-error" role="alert">{error}{detail && ' Os detalhes exibidos podem estar desatualizados.'}</p>}
    {!detail && !error && <p role="status">Carregando linha do tempo…</p>}
    {action && <><dl><dt>Identificador</dt><dd>{action.id}</dd><dt>Estado registrado</dt><dd>{actionLabels[action.status] || action.status}</dd><dt>Origem</dt><dd>{originLabel(action.source)}</dd><dt>Proposta</dt><dd>{action.preview}</dd><dt>Resultado registrado</dt><dd>{action.result_summary || 'Ainda não disponível.'}</dd><dt>Atualização</dt><dd>{when(action.updated_at)}</dd>{start && terminal && <><dt>Duração da execução</dt><dd>{Math.max(0, action.updated_at - start.timestamp).toLocaleString('pt-BR', { maximumFractionDigits: 2 })} s</dd></>}</dl>
      <p><strong>Verificação do efeito: </strong>{action.effect_status === 'confirmed' ? 'Confirmado' : action.effect_status === 'unconfirmed' ? 'Não confirmado' : action.effect_status === 'not_applicable' ? 'Sem verificação aplicável' : 'Não registrada'}{action.effect_evidence && ` — ${action.effect_evidence}`}</p>
      <h4>Linha do tempo</h4>
      <ol className="ws-action-timeline">{detail.events.map(event => <li key={event.id}><span className={`ws-dot ${event.status}`} /><div><strong>{event.kind === 'legacy_import' ? 'Registro anterior importado' : actionLabels[event.status] || event.status}</strong><time dateTime={new Date(event.timestamp * 1000).toISOString()}>{when(event.timestamp)}</time>{event.summary && <p>{event.summary}</p>}</div></li>)}</ol>
      {!detail.events.length && <p className="ws-muted">Nenhum evento disponível para esta ação.</p>}
      {action.status === 'awaiting_confirmation' && <div className="ws-approval-buttons"><button className="ws-button" disabled={busy.includes(id) || unavailable || !!error} onClick={() => onDecide(action, 'reject')}><X size={15} /> Recusar</button><button className="ws-button primary" disabled={busy.includes(id) || unavailable || !!error} onClick={() => onDecide(action, 'approve')}><Check size={15} />{busy.includes(id) ? 'Processando…' : 'Autorizar uma vez'}</button></div>}
      {action.status === 'awaiting_confirmation' && <AlwaysAllowButton actionId={action.id} disabled={busy.includes(id) || unavailable || !!error} onAllowed={() => onDecide(action, 'approve')} />}
      {action.run_id && <p className="ws-footnote">Pedido: {action.run_id}</p>}
      {action.status === 'running' && <p className="ws-warning">Uma etapa já iniciada pode precisar terminar antes que o cancelamento do pedido seja confirmado.</p>}
    </>}
  </section>
}

export function ActionHistory({ revision, ...decisions }: { revision: number | string | null } & Decisions) {
  const [filter, setFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [showReads, setShowReads] = useState(false)
  const [cursors, setCursors] = useState<(number | null)[]>([null])
  const [page, setPage] = useState<ActionPage | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [selectedId, setSelectedId] = useState('')
  const cursor = cursors[cursors.length - 1]
  const reset = () => { setCursors([null]); setPage(null); setSelectedId(''); setError('') }
  useEffect(() => {
    const controller = new AbortController()
    let disposed = false
    let timeout: ReturnType<typeof setTimeout>
    setLoading(true)
    const debounce = setTimeout(async () => {
      timeout = setTimeout(() => controller.abort(), 10000)
      const params = new URLSearchParams({ limit: '30', q: query })
      if (filter !== 'all') params.set('status', filter)
      if (showReads) params.set('include_reads', '1')
      if (cursor !== null) params.set('before', String(cursor))
      try {
        const data = await panelRequest<ActionPage>(`/api/actions?${params}`, { signal: controller.signal })
        if (!Array.isArray(data.actions) || !(data.next_cursor === null || typeof data.next_cursor === 'number')) throw new Error('Este servidor ainda não fornece o histórico paginado.')
        if (!disposed) { setPage(data); setError('') }
      } catch (err) {
        if (!disposed) setError(err instanceof Error && err.name !== 'AbortError' ? err.message : 'O histórico não respondeu a tempo.')
      } finally { clearTimeout(timeout); if (!disposed) setLoading(false) }
    }, 250)
    return () => { disposed = true; clearTimeout(debounce); clearTimeout(timeout); controller.abort() }
  }, [filter, query, showReads, cursor, revision])
  return <section className="ws-panel">
    <div className="ws-section-title"><h2>Histórico de ações</h2><span className="ws-muted">{loading ? 'Atualizando…' : 'Ordenado por criação'}</span></div>
    <div className="ws-filters"><label><Search size={15} /><input aria-label="Buscar ações" placeholder="Buscar por ferramenta ou proposta…" value={query} maxLength={200} onChange={event => { setQuery(event.target.value); reset() }} /></label><select aria-label="Filtrar ações por estado" value={filter} onChange={event => { setFilter(event.target.value); reset() }}><option value="all">Todos os estados</option>{Object.entries(actionLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><button className="ws-button" aria-pressed={showReads} onClick={() => { setShowReads(!showReads); reset() }}>{showReads ? 'Com leituras das janelas' : 'Ocultar leituras das janelas'}</button></div>
    {error && <p className="ws-error" role="alert">{error}{page && ' Exibindo a última página recebida.'}</p>}
    <div className="ws-execution-list" aria-busy={loading}>{page?.actions.map(action => <button key={action.id} className={`ws-execution-row ${selectedId === action.id ? 'selected' : ''}`} onClick={() => setSelectedId(selectedId === action.id ? '' : action.id)} aria-expanded={selectedId === action.id}><span className={`ws-dot ${action.status}`} /><div><strong>{action.tool_name.replaceAll('_', ' ')}</strong><span>{action.result_summary || action.preview}</span></div><span className="ws-tag">{actionLabels[action.status] || action.status}</span><ArrowUpRight size={15} /></button>)}{!loading && !error && !page?.actions.length && <div className="ws-empty"><Activity size={25} /><h3>Nenhuma ação nesta seleção</h3><p>As ações registradas pelo agente aparecerão aqui.</p></div>}</div>
    <nav className="ws-history-pagination" aria-label="Páginas do histórico"><button className="ws-button" disabled={loading || cursors.length === 1} onClick={() => { setCursors(cursors.slice(0, -1)); setPage(null); setSelectedId('') }}><ChevronLeft size={15} /> Anterior</button><span className="ws-muted">Página {cursors.length}</span><button className="ws-button" disabled={loading || !!error || page?.next_cursor == null} onClick={() => { if (page?.next_cursor != null) { setCursors([...cursors, page.next_cursor]); setPage(null); setSelectedId('') } }}>Próxima <ChevronRight size={15} /></button></nav>
    {selectedId && <ActionDetails key={selectedId} id={selectedId} revision={revision} onClose={() => setSelectedId('')} {...decisions} />}
    <p className="ws-footnote">Eventos preservados para as ações mantidas no registro local. Registros antigos incluem apenas o estado conhecido na importação. A conclusão informa o retorno da ferramenta; não comprova por si só o efeito externo.</p>
  </section>
}
