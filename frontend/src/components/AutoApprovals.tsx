import { pollVisible } from '../utils/panelVisibility'
import { useCallback, useEffect, useState } from 'react'
import { ShieldAlert, ShieldCheck, Trash2 } from 'lucide-react'
import { panelRequest } from '../utils/panelApi'
import { Switch } from './Switch'

export type ApprovalRule = { id: string; tool: string; operation: string; target: string; label: string; duration: string; expires_at: number | null; uses: number; last_used_at: number | null; active: boolean }
type ApprovalState = { mode: { enabled: boolean; persist: boolean; until?: number | null }; categories: Record<string, boolean>; category_labels: Record<string, string>; rules: ApprovalRule[]; durations: Record<string, string>; validities?: Record<string, string> }
const DEFAULT_VALIDITIES: Record<string, string> = { forever: 'Até desligar', '1h': '1 hora', today: 'Hoje' }

const post = (path: string, payload: object) => panelRequest<ApprovalState>(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
const when = (timestamp: number | null) => timestamp ? new Date(timestamp * 1000).toLocaleString('pt-BR') : '—'
const MODE_EVENT = 'jarvis-approval-mode'

export async function autoAllows(category: string) {
  try {
    const { mode, categories } = await panelRequest<ApprovalState>('/api/approvals')
    return mode.enabled && categories?.[category] === true
  } catch { return false }
}

export async function confirmRemoval(count: number, message: string) {
  return await autoAllows(count > 1 ? 'bulk' : 'remove') || window.confirm(message)
}

export function useApprovals() {
  const [state, setState] = useState<ApprovalState | null>(null)
  const [error, setError] = useState('')
  const apply = useCallback((next: ApprovalState) => { setState(next); setError(''); window.dispatchEvent(new CustomEvent(MODE_EVENT, { detail: next.mode.enabled })) }, [])
  const refresh = useCallback(() => panelRequest<ApprovalState>('/api/approvals').then(next => { setState(next); setError('') }).catch(err => setError(err instanceof Error ? err.message : 'Não foi possível consultar as aprovações.')), [])
  useEffect(() => {
    const stopPolling = pollVisible(refresh, 15000, true)
    const listener = (event: Event) => setState(current => current && current.mode.enabled !== (event as CustomEvent<boolean>).detail ? { ...current, mode: { ...current.mode, enabled: (event as CustomEvent<boolean>).detail } } : current)
    window.addEventListener(MODE_EVENT, listener)
    return () => { stopPolling(); window.removeEventListener(MODE_EVENT, listener) }
  }, [refresh])
  const run = (request: Promise<ApprovalState>) => request.then(apply).catch(err => setError(err instanceof Error ? err.message : 'Não foi possível salvar.'))
  return {
    state, error, refresh,
    setMode: (enabled: boolean, persist?: boolean, validity?: string, categories?: Record<string, boolean>) => run(post('/api/approvals/mode', { enabled, persist, validity, categories })),
    addRule: (rule: { tool: string; operation: string; target: string; duration: string; confirm_broad?: boolean }) => run(post('/api/approvals/rules', rule)),
    setDuration: (id: string, duration: string) => run(post(`/api/approvals/rules/${encodeURIComponent(id)}`, { duration })),
    revoke: (id: string) => run(post(`/api/approvals/rules/${encodeURIComponent(id)}`, { revoke: true })),
  }
}

/** Selo sempre visível no cabeçalho; ativo, mostra "Modo liberado" e desliga com um clique. */
export function LiberatedModeBadge() {
  const { state, setMode } = useApprovals()
  if (!state?.mode.enabled) return null
  const until = state.mode.until ? ` Vale até ${new Date(state.mode.until * 1000).toLocaleString('pt-BR')}.` : ''
  return <button type="button" className="ws-liberated-badge" title={`Modo liberado: as categorias selecionadas estão autoaprovadas.${until} Clique para desligar.`}
    style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 10px', borderRadius: 999, border: '1px solid #ff5a5f', background: 'rgba(255,90,95,.16)', color: '#ff8a8e', fontWeight: 700, fontSize: 12, cursor: 'pointer' }}
    onClick={() => void setMode(false)}><ShieldAlert size={14} />Modo liberado · desligar</button>
}

/** Botão "Sempre permitir" da tela de aprovação: cria a regra a partir da proposta e depois autoriza. */
export function AlwaysAllowButton({ actionId, disabled, onAllowed }: { actionId: string; disabled?: boolean; onAllowed: () => void }) {
  const [duration, setDuration] = useState('now')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const allow = async () => {
    setSaving(true); setError('')
    try { await post('/api/approvals/rules', { action_id: actionId, duration }); onAllowed() }
    catch (err) { setError(err instanceof Error ? err.message : 'Não foi possível criar a regra.') }
    finally { setSaving(false) }
  }
  return <span className="ws-always-allow" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
    <select aria-label="Duração da permissão" value={duration} onChange={event => setDuration(event.target.value)}><option value="now">Só agora</option><option value="today">Hoje</option><option value="30d">30 dias</option><option value="always">Sempre</option></select>
    <button className="ws-button" disabled={disabled || saving} onClick={() => void allow()}><ShieldCheck size={15} />{saving ? 'Salvando…' : 'Permitir e autorizar'}</button>
    {error && <small className="ws-error" role="alert">{error}</small>}
  </span>
}

/** Gerenciador reutilizável: Modo liberado e lista de regras (adicionar, mudar duração, revogar). */
export function AutoApprovalsManager() {
  const { state, error, setMode, addRule, setDuration, revoke } = useApprovals()
  const [draft, setDraft] = useState({ tool: '', operation: '', target: '', duration: 'now', confirm_broad: false })
  const [validity, setValidity] = useState('forever')
  const validities = state?.validities || DEFAULT_VALIDITIES
  const durations = state?.durations || { now: 'Só agora (10 min)', today: 'Hoje', '30d': '30 dias', always: 'Sempre' }
  return <article className="settings-card" aria-label="Aprovações automáticas">
    <p className="eyebrow">AÇÕES DO AGENTE</p>
    <h2>Aprovações automáticas</h2>
    {error && <p className="ws-error" role="alert">{error}</p>}
    <Switch label="Modo liberado" description="Autoaprova as categorias selecionadas, inclusive ações de risco alto e crítico." checked={!!state?.mode.enabled} disabled={!state} onChange={checked => void setMode(checked, undefined, checked ? validity : undefined)} glowColor="purple" />
    {state?.mode.enabled && Object.entries(state.category_labels || {}).map(([key, label]) =>
      <Switch key={key} label={label} checked={state.categories[key]} onChange={checked => void setMode(true, undefined, undefined, { [key]: checked })} />)}
    <label className="ws-muted" style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>Ao ligar, vale por
      <select aria-label="Validade do modo liberado" value={validity} onChange={event => setValidity(event.target.value)}>{Object.entries(validities).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
    </label>
    {state?.mode.enabled && <p className="ws-muted">{state.mode.until ? `Ligado até ${when(state.mode.until)}.` : 'Ligado até você desligar.'}</p>}
    <Switch label="Manter o modo liberado após reiniciar" description="Desligado: o backend sempre volta com o modo liberado desativado." checked={!!state?.mode.persist} disabled={!state} onChange={checked => void setMode(!!state?.mode.enabled, checked)} glowColor="blue" />
    <h3>Comandos auto-aprovados</h3>
    {!state?.rules.length && <p className="ws-muted">Nenhuma regra ativa. Use “Permitir e autorizar” numa aprovação pendente ou adicione abaixo.</p>}
    {state?.rules.map(rule => <div key={rule.id} className="ws-goal" style={{ display: 'flex', gap: 8, alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap' }}>
      <div><strong>{rule.label}</strong><p className="ws-muted">Usos: {rule.uses}{rule.last_used_at ? ` · último: ${when(rule.last_used_at)}` : ''} · válida até {rule.expires_at ? when(rule.expires_at) : 'sem validade'}</p></div>
      <span style={{ display: 'inline-flex', gap: 6 }}>
        <select aria-label={`Duração de ${rule.label}`} value={rule.duration} onChange={event => void setDuration(rule.id, event.target.value)}>{Object.entries(durations).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
        <button className="ws-button" onClick={() => void revoke(rule.id)}><Trash2 size={14} /> Revogar</button>
      </span>
    </div>)}
    <h4>Adicionar regra</h4>
    <form style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }} onSubmit={event => { event.preventDefault(); if (draft.tool.trim()) void addRule(draft).then(() => setDraft({ ...draft, tool: '', operation: '', target: '', confirm_broad: false })) }}>
      <input aria-label="Ferramenta" placeholder="Ferramenta (ex.: open_windows_app)" value={draft.tool} onChange={event => setDraft({ ...draft, tool: event.target.value })} />
      <input aria-label="Operação" placeholder="Operação (opcional, ex.: close)" value={draft.operation} onChange={event => setDraft({ ...draft, operation: event.target.value })} />
      <input aria-label="Alvo" placeholder="Alvo (opcional, ex.: Spotify.exe)" value={draft.target} onChange={event => setDraft({ ...draft, target: event.target.value })} />
      <select aria-label="Duração" value={draft.duration} onChange={event => setDraft({ ...draft, duration: event.target.value })}>{Object.entries(durations).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
      <label className="ws-muted" style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}><input type="checkbox" aria-label="Vale para qualquer alvo" checked={draft.confirm_broad} onChange={event => setDraft({ ...draft, confirm_broad: event.target.checked })} />Vale para qualquer alvo</label>
      <button className="ws-button primary" disabled={!draft.tool.trim()}>Adicionar</button>
    </form>
    <p className="ws-footnote">Operação e alvo vazios valem para qualquer um; em ferramentas de risco alto sem alvo, marque </p>
  </article>
}
