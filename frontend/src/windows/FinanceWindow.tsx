import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { Pencil, Trash2 } from 'lucide-react'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { panelRequest } from '../utils/panelApi'
import type { FinanceWindowParams, WindowComponentProps } from './registry'

// Janela Finanças. Todo número exibido vem da API (/api/finance); o registro manual nunca chama o
// modelo. O formulário guarda um rascunho local até o servidor confirmar a gravação.

type EntryType = 'expense' | 'income'
type Transaction = { id: string; type: EntryType; amount: number; category: string; description: string; date_str: string }
type Totals = { income: number; expense: number; net: number; count: number; by_category: { category: string; type: EntryType; total: number }[] }
type ListResponse = { ok: boolean; transactions: Transaction[]; totals: Totals; categories: string[]; truncated: boolean }
type Period = 'week' | 'month' | 'all' | 'custom'
type Filters = { period: Period; from: string; to: string; type: '' | EntryType; category: string }
type Form = { id: string; editingId: string; type: EntryType; amount: string; category: string; description: string; date: string }
type Pending = { kind: 'delete'; tx: Transaction } | { kind: 'edit'; tx: Transaction }

const DRAFT_KEY = 'jarvis-finance-draft'
const JSON_HEADERS = { 'Content-Type': 'application/json' }
const money = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })

const pad = (value: number) => String(value).padStart(2, '0')
const isoDate = (date: Date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
const todayIso = () => isoDate(new Date())
const newEntryId = () => `fin_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`
const showDate = (value: string) => /^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value.slice(8)}/${value.slice(5, 7)}/${value.slice(0, 4)}` : value

function periodRange(filters: Filters) {
  const now = new Date()
  if (filters.period === 'month') return { from: `${now.getFullYear()}-${pad(now.getMonth() + 1)}-01`, to: isoDate(new Date(now.getFullYear(), now.getMonth() + 1, 0)) }
  if (filters.period === 'week') return { from: isoDate(new Date(now.getFullYear(), now.getMonth(), now.getDate() - 6)), to: isoDate(now) }
  if (filters.period === 'custom') return { from: filters.from, to: filters.to }
  return { from: '', to: '' }
}

// Aceita "1.234,56", "1234,56" e "1234.56".
function parseAmount(text: string) {
  const cleaned = text.trim().replace(/\s/g, '')
  if (!cleaned) return null
  const normalized = cleaned.includes(',') ? cleaned.replace(/\./g, '').replace(',', '.') : cleaned
  if (!/^\d+(\.\d{1,2})?$/.test(normalized)) return null
  const value = Number(normalized)
  return Number.isFinite(value) && value > 0 ? value : null
}

const blankForm = (): Form => ({ id: newEntryId(), editingId: '', type: 'expense', amount: '', category: '', description: '', date: todayIso() })
const isDirty = (form: Form) => Boolean(form.editingId || form.amount.trim() || form.category.trim() || form.description.trim())

function readDraft(): Form | null {
  try {
    const raw = JSON.parse(localStorage.getItem(DRAFT_KEY) || 'null')
    if (!raw || typeof raw !== 'object') return null
    const text = (value: unknown) => typeof value === 'string' ? value : ''
    const form: Form = {
      id: text(raw.id) || newEntryId(), editingId: text(raw.editingId), type: raw.type === 'income' ? 'income' : 'expense',
      amount: text(raw.amount), category: text(raw.category), description: text(raw.description), date: text(raw.date) || todayIso(),
    }
    return isDirty(form) ? form : null
  } catch {
    return null
  }
}

function writeDraft(form: Form) {
  try {
    if (isDirty(form)) localStorage.setItem(DRAFT_KEY, JSON.stringify(form))
    else localStorage.removeItem(DRAFT_KEY)
  } catch { /* armazenamento indisponível: o formulário continua na tela */ }
}

function clearDraft() {
  try { localStorage.removeItem(DRAFT_KEY) } catch { /* ignorar */ }
}

function prefillForm(params: FinanceWindowParams): Form {
  const form = blankForm()
  if (params.type) form.type = params.type
  if (params.category) form.category = params.category
  if (params.amount) form.amount = String(params.amount).replace('.', ',')
  if (params.description) form.description = params.description
  if (params.date) form.date = params.date
  return form
}

function describeError(error: unknown, action: string) {
  if (error instanceof TypeError) return `${action}: sem conexão com o servidor.`
  return `${action}: ${error instanceof Error ? error.message : 'erro desconhecido.'}`
}

export function FinanceWindow({ params, operational }: WindowComponentProps<FinanceWindowParams>) {
  const [filters, setFilters] = useState<Filters>(() => ({ period: params.period ?? 'month', from: '', to: '', type: '', category: '' }))
  const [data, setData] = useState<ListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [listError, setListError] = useState('')
  const [form, setForm] = useState<Form>(() => readDraft() ?? prefillForm(params))
  const [restored, setRestored] = useState(() => readDraft() !== null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [formError, setFormError] = useState('')
  const [savedNotice, setSavedNotice] = useState('')
  const [pending, setPending] = useState<Pending | null>(null)
  const [pendingBusy, setPendingBusy] = useState(false)

  const providers = operational.snapshot?.components.find(item => item.id === 'providers')
  const manualMode = Boolean(providers && providers.status !== 'healthy')

  const range = useMemo(() => periodRange(filters), [filters])

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true)
    try {
      const response = await panelRequest<ListResponse>('/api/finance', {
        method: 'POST', headers: JSON_HEADERS, signal,
        body: JSON.stringify({ action: 'list', date_from: range.from, date_to: range.to, type: filters.type, category: filters.category }),
      })
      if (signal?.aborted) return
      setData(response)
      setListError('')
    } catch (error) {
      if (signal?.aborted) return
      setListError(describeError(error, 'Não foi possível carregar os lançamentos'))
    } finally {
      if (!signal?.aborted) setLoading(false)
    }
  }, [range, filters.type, filters.category])

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [load])

  const updateForm = (patch: Partial<Form>) => {
    const next = { ...form, ...patch }
    setForm(next)
    writeDraft(next)
    setFormError('')
    setSavedNotice('')
  }

  const discardDraft = () => {
    clearDraft()
    setForm(blankForm())
    setRestored(false)
    setSaveError('')
    setFormError('')
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (saving) return
    const amount = parseAmount(form.amount)
    if (amount === null) { setFormError('Informe um valor maior que zero, por exemplo 25,90.'); return }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(form.date)) { setFormError('Informe uma data válida.'); return }
    setSaving(true)
    setSaveError('')
    try {
      await panelRequest('/api/finance', {
        method: 'POST', headers: JSON_HEADERS,
        body: JSON.stringify({ action: form.editingId ? 'update' : 'add', id: form.editingId || form.id, type: form.type, amount, category: form.category.trim(), description: form.description.trim(), date: form.date }),
      })
      // Só aqui, com a gravação confirmada pelo servidor, o rascunho é apagado.
      clearDraft()
      setForm(blankForm())
      setRestored(false)
      setSavedNotice(form.editingId ? 'Lançamento atualizado.' : 'Lançamento salvo.')
      await load()
    } catch (error) {
      setSaveError(`${describeError(error, 'Não foi possível salvar')} O rascunho foi mantido; tente novamente.`)
    } finally {
      setSaving(false)
    }
  }

  const applyEdit = (tx: Transaction) => {
    const next: Form = { id: tx.id, editingId: tx.id, type: tx.type, amount: String(tx.amount).replace('.', ','), category: tx.category, description: tx.description, date: tx.date_str }
    setForm(next)
    writeDraft(next)
    setRestored(false)
    setSaveError('')
    setFormError('')
    setSavedNotice('')
  }

  const requestEdit = (tx: Transaction) => {
    if (isDirty(form) && form.editingId !== tx.id) setPending({ kind: 'edit', tx })
    else applyEdit(tx)
  }

  const confirmPending = async () => {
    if (!pending) return
    if (pending.kind === 'edit') { applyEdit(pending.tx); setPending(null); return }
    setPendingBusy(true)
    try {
      await panelRequest('/api/finance', { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify({ action: 'delete', id: pending.tx.id }) })
      if (form.editingId === pending.tx.id) discardDraft()
      setSavedNotice('Lançamento excluído.')
      setPending(null)
      await load()
    } catch (error) {
      setPending(null)
      setListError(describeError(error, 'Não foi possível excluir o lançamento'))
    } finally {
      setPendingBusy(false)
    }
  }

  const categories = data?.categories ?? []
  const totals = data?.totals

  return (
    <div className="ws-finance">
      <div className="ws-finance-head">
        {manualMode && <span className="ws-finance-mode" title={providers?.reason || 'A IA está indisponível; o registro manual segue funcionando.'}>Modo manual · IA indisponível</span>}
        <span className="ws-muted">Valores calculados pelo servidor</span>
      </div>

      <form className="ws-finance-form" onSubmit={submit} aria-label={form.editingId ? 'Editar lançamento' : 'Novo lançamento'}>
        <div className="ws-finance-form-title">
          <strong>{form.editingId ? 'Editar lançamento' : 'Novo lançamento'}</strong>
          {restored && <span className="ws-muted">Rascunho restaurado</span>}
        </div>
        <div className="ws-finance-segment" role="group" aria-label="Tipo">
          <button type="button" aria-pressed={form.type === 'expense'} className={form.type === 'expense' ? 'selected' : ''} onClick={() => updateForm({ type: 'expense' })}>Despesa</button>
          <button type="button" aria-pressed={form.type === 'income'} className={form.type === 'income' ? 'selected' : ''} onClick={() => updateForm({ type: 'income' })}>Receita</button>
        </div>
        <div className="ws-finance-grid">
          <label>Valor (R$)<input inputMode="decimal" autoComplete="off" placeholder="0,00" value={form.amount} onChange={event => updateForm({ amount: event.target.value })} /></label>
          <label>Data<input type="date" value={form.date} onChange={event => updateForm({ date: event.target.value })} /></label>
          <label>Categoria<input list="ws-finance-categories" maxLength={60} placeholder="Outros" value={form.category} onChange={event => updateForm({ category: event.target.value })} /></label>
          <label>Descrição<input maxLength={300} placeholder="Opcional" value={form.description} onChange={event => updateForm({ description: event.target.value })} /></label>
        </div>
        <datalist id="ws-finance-categories">{categories.map(name => <option key={name} value={name} />)}</datalist>
        {formError && <p className="ws-finance-error" role="alert">{formError}</p>}
        {saveError && <p className="ws-finance-error" role="alert">{saveError}</p>}
        {savedNotice && <p className="ws-finance-ok" role="status">{savedNotice}</p>}
        <div className="ws-finance-actions">
          <button type="submit" className="ws-button primary" disabled={saving}>{saving ? 'Salvando…' : saveError ? 'Tentar novamente' : form.editingId ? 'Salvar alterações' : 'Salvar lançamento'}</button>
          {isDirty(form) && <button type="button" className="ws-button" disabled={saving} onClick={discardDraft}>{form.editingId ? 'Cancelar edição' : 'Descartar rascunho'}</button>}
        </div>
      </form>

      <div className="ws-finance-filters" role="group" aria-label="Filtros">
        <label>Período
          <select value={filters.period} onChange={event => setFilters({ ...filters, period: event.target.value as Period })}>
            <option value="month">Este mês</option>
            <option value="week">Últimos 7 dias</option>
            <option value="all">Tudo</option>
            <option value="custom">Personalizado</option>
          </select>
        </label>
        {filters.period === 'custom' && (
          <>
            <label>De<input type="date" value={filters.from} onChange={event => setFilters({ ...filters, from: event.target.value })} /></label>
            <label>Até<input type="date" value={filters.to} onChange={event => setFilters({ ...filters, to: event.target.value })} /></label>
          </>
        )}
        <label>Tipo
          <select value={filters.type} onChange={event => setFilters({ ...filters, type: event.target.value as Filters['type'] })}>
            <option value="">Todos</option>
            <option value="expense">Despesas</option>
            <option value="income">Receitas</option>
          </select>
        </label>
        <label>Categoria
          <select value={filters.category} onChange={event => setFilters({ ...filters, category: event.target.value })}>
            <option value="">Todas</option>
            {categories.map(name => <option key={name} value={name}>{name}</option>)}
          </select>
        </label>
      </div>

      {listError && <p className="ws-finance-error" role="alert">{listError} <button type="button" className="ws-text-button" onClick={() => void load()}>Tentar de novo</button></p>}

      <div className="ws-finance-totals" aria-live="polite">
        <article><span>Receitas</span><strong className="income">{totals ? money.format(totals.income) : '—'}</strong></article>
        <article><span>Despesas</span><strong className="expense">{totals ? money.format(totals.expense) : '—'}</strong></article>
        <article><span>Saldo do período</span><strong>{totals ? money.format(totals.net) : '—'}</strong></article>
      </div>

      <div className="ws-finance-list" aria-busy={loading}>
        {totals && <p className="ws-muted">{totals.count} lançamento(s) no filtro{data?.truncated ? `; mostrando os ${data.transactions.length} mais recentes (os totais incluem todos)` : ''}</p>}
        {!loading && data && !data.transactions.length && <p className="ws-finance-empty">Nenhum lançamento neste filtro.</p>}
        <ul>
          {data?.transactions.map(tx => (
            <li key={tx.id} className={form.editingId === tx.id ? 'editing' : ''}>
              <span className="ws-finance-date">{showDate(tx.date_str)}</span>
              <span className="ws-finance-what"><strong>{tx.description || tx.category}</strong><small>{tx.category}</small></span>
              <span className={`ws-finance-amount ${tx.type}`}>{tx.type === 'income' ? '+' : '−'} {money.format(tx.amount)}</span>
              <button type="button" className="ws-icon-button" aria-label={`Editar lançamento de ${tx.category}`} title="Editar" onClick={() => requestEdit(tx)}><Pencil size={14} /></button>
              <button type="button" className="ws-icon-button" aria-label={`Excluir lançamento de ${tx.category}`} title="Excluir" onClick={() => setPending({ kind: 'delete', tx })}><Trash2 size={14} /></button>
            </li>
          ))}
        </ul>
      </div>

      {pending?.kind === 'delete' && (
        <ConfirmDialog
          title="Excluir lançamento?"
          message={`${pending.tx.type === 'income' ? 'Receita' : 'Despesa'} de ${money.format(pending.tx.amount)} em ${pending.tx.category} (${showDate(pending.tx.date_str)}). Esta ação não pode ser desfeita.`}
          confirmLabel="Excluir"
          danger
          busy={pendingBusy}
          onConfirm={() => void confirmPending()}
          onCancel={() => setPending(null)}
        />
      )}
      {pending?.kind === 'edit' && (
        <ConfirmDialog
          title="Substituir o rascunho?"
          message="O formulário tem um rascunho não salvo. Editar este lançamento substitui o conteúdo atual."
          confirmLabel="Substituir"
          onConfirm={() => void confirmPending()}
          onCancel={() => setPending(null)}
        />
      )}
    </div>
  )
}
