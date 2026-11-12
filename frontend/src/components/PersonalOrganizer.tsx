import { useCallback, useEffect, useRef, useState } from 'react'
import { autoAllows, confirmRemoval } from './AutoApprovals'
import { panelRequest } from '../utils/panelApi'
import { onSyncEvent } from '../utils/syncChannel'
import { personalRequest, PERSONAL_CHANGED, PERSONAL_OPEN, consumeOrganizerOpen, type PersonalPreferences, type PersonalReceipt as Receipt } from '../utils/personalRecords'
import { PersonalReceipt } from './PersonalReceipt'
import './personalOrganizer.css'

const kinds: Record<string, string> = { note: 'Anotação', task: 'Tarefa', habit: 'Hábito', finance: 'Finanças', workout: 'Treino realizado', workout_plan: 'Plano de treino', sleep: 'Sono', mood: 'Humor', personal: 'Registro pessoal', checklist: 'Lista', recurrence: 'Conta recorrente', transfer: 'Transferência', rule: 'Relação entre áreas' }
const blockLabels: Record<string, string> = { habits: 'Hábitos', tasks: 'Tarefas', workout: 'Treino', finance: 'Finanças', notes: 'Anotações' }
const defaults: PersonalPreferences = { blocks: Object.keys(blockLabels), reduced_motion: false, review: 'off' }
type Row = Record<string, any> & { id: string; title: string }
type Overview = { tasks: Row[]; plans: Row[]; workouts: Row[]; accounts: Record<string, number>; recurring_due: Row[]; preferences: PersonalPreferences; history: Receipt[] }
const money = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })

export function PersonalOrganizer({ onPreferences }: { onPreferences: (p: PersonalPreferences) => void }) {
  const [overview, setOverview] = useState<Overview | null>(null)
  const [status, setStatus] = useState('')
  const [busy, setBusy] = useState(false)
  const busyRef = useRef(false)
  const [kind, setKind] = useState('note')
  const [editor, setEditor] = useState<Row | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [browse, setBrowse] = useState(false)
  const [rows, setRows] = useState<Row[]>([])
  const [query, setQuery] = useState('')
  const [preview, setPreview] = useState<{ token: string; results: Row[] } | null>(null)
  const [receipt, setReceipt] = useState<Receipt | null>(null)
  const prefsRef = useRef(onPreferences)
  prefsRef.current = onPreferences
  const load = useCallback(async () => {
    try {
      const data = await panelRequest<Overview>('/api/personal')
      if (!data.preferences || !Array.isArray(data.history) || !Array.isArray(data.tasks) || !Array.isArray(data.plans) || !Array.isArray(data.workouts)) throw new Error('Não foi possível consultar a organização pessoal. Tente novamente.')
      setOverview(data); prefsRef.current(data.preferences)
      document.documentElement.classList.toggle('personal-reduced-motion', data.preferences.reduced_motion)
    } catch (err) { setStatus(err instanceof Error ? err.message : 'Falha ao atualizar Hoje.') }
  }, [])
  useEffect(() => {
    void load()
    const update = () => void load()
    const off = onSyncEvent('HABIT_UPDATED', update)
    const open = () => {
      const detail = consumeOrganizerOpen()
      if (!detail) return
      setBrowse(true); setFormOpen(false)
      if (detail.kind && detail.kind in kinds) {
        setKind(detail.kind); setQuery(detail.query || '')
        return
      }
      if (detail.bulk) {
        setKind(detail.bulk.kind); setQuery(detail.bulk.query || '')
        personalRequest({ action: 'bulk_preview', kind: detail.bulk.kind, query: detail.bulk.query || '' }).then(setPreview).catch(err => setStatus(err.message))
        return
      }
      const change = (detail as Receipt)?.changes?.find(c => ['habits', 'tasks', 'finance_transactions', 'notes', 'personal_records', 'lifeos'].includes(c.store))
      const inferred: Record<string, string> = { habits: 'habit', tasks: 'task', finance_transactions: 'finance', notes: 'note', lifeos: 'workout' }
      let next = inferred[change?.store || ''] || 'personal'
      if (change?.store === 'personal_records') next = (change.after ?? change.before)?.kind || 'personal'
      if (!(next in kinds)) next = 'personal'
      setKind(next); setQuery('')
      document.getElementById('personal-organizer')?.scrollIntoView({ block: 'nearest' })
    }
    window.addEventListener(PERSONAL_CHANGED, update)
    window.addEventListener('jarvis:finance-changed', update)
    window.addEventListener('jarvis:notes-changed', update)
    window.addEventListener(PERSONAL_OPEN, open)
    const visible = () => { if (!document.hidden) void load() }
    document.addEventListener('visibilitychange', visible)
    open()
    return () => { off(); document.removeEventListener('visibilitychange', visible); window.removeEventListener(PERSONAL_CHANGED, update); window.removeEventListener('jarvis:finance-changed', update); window.removeEventListener('jarvis:notes-changed', update); window.removeEventListener(PERSONAL_OPEN, open) }
  }, [load])
  const loadRows = useCallback(async () => {
    const result = await personalRequest({ action: 'list', kind, query })
    setRows(result.results)
  }, [kind, query])
  useEffect(() => {
    if (!browse) return
    let live = true
    personalRequest({ action: 'list', kind, query }).then(data => { if (live) setRows(data.results) }).catch(err => { if (live) setStatus(String(err.message)) })
    return () => { live = false }
  }, [browse, kind, query, overview])
  async function act(payload: Record<string, unknown>) {
    if (busyRef.current) return
    busyRef.current = true; setBusy(true); setStatus('')
    try {
      const result = await personalRequest(payload)
      setStatus(result.message || 'Salvo.'); setReceipt(result.personal_receipt ?? null)
      await load()
      if (browse) await loadRows()
      return result
    } catch (err) { setStatus(err instanceof Error ? err.message : 'Não foi possível salvar.') }
    finally { busyRef.current = false; setBusy(false) }
  }
  const prefs = overview?.preferences ?? defaults
  async function preference(fields: Partial<PersonalPreferences>) {
    if (busyRef.current) return
    const next = { ...prefs, ...fields }
    setOverview(previous => previous ? { ...previous, preferences: next } : previous)
    prefsRef.current(next)
    document.documentElement.classList.toggle('personal-reduced-motion', next.reduced_motion)
    const result = await act({ action: 'preferences_set', fields })
    if (!result) await load()
  }
  return <section id="personal-organizer" className="personal-organizer" aria-label="Organização pessoal">
    <div className="personal-today-extra">
      {prefs.blocks.includes('tasks') && <details className="today-cell" open><summary>Próxima tarefa</summary>
        {overview?.tasks[0] ? <><strong>{overview.tasks[0].title}</strong><small>{overview.tasks[0].due_date ? `Prazo: ${overview.tasks[0].due_date}` : 'Sem prazo'}</small><button disabled={busy} onClick={() => void act({ action: 'complete', kind: 'task', record_id: overview.tasks[0].id })}>Concluir tarefa</button></> : <p>{overview ? 'Nenhuma tarefa pendente.' : 'Carregando…'}</p>}
      </details>}
      {prefs.blocks.includes('workout') && <details className="today-cell" open><summary>Treino de hoje</summary>
        {overview?.plans.map(plan => <div key={plan.id}><strong>{plan.title}</strong><button disabled={busy} onClick={() => void act({ action: 'start', kind: 'workout_plan', record_id: plan.id })}>Iniciar sessão</button></div>)}
        {overview?.workouts.map(workout => <div key={workout.id}><span>{workout.title} · {workout.completed === false ? 'Em andamento' : 'Concluído'}</span>{workout.completed === false && <button disabled={busy} onClick={() => void act({ action: 'complete', kind: 'workout', record_id: workout.id })}>Concluir treino</button>}</div>)}
        {overview && !overview.plans.length && !overview.workouts.length && <p>Sem treino planejado para hoje.</p>}
      </details>}
    </div>
    <div className="today-actions"><button onClick={() => { setEditor(null); setFormOpen(v => !v) }}>Registrar agora</button><button onClick={() => setBrowse(v => !v)}>Consultar registros</button></div>
    {(formOpen || browse) && <label>Tipo de registro<select aria-label="Tipo de registro" value={kind} onChange={e => { setKind(e.target.value); setEditor(null); setPreview(null); setQuery('') }}>{Object.entries(kinds).map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></label>}
    {formOpen && <RecordForm key={kind + (editor?.id || 'new')} kind={kind} initial={editor} busy={busy} onCancel={() => { setEditor(null); setFormOpen(false) }} onSave={async fields => {
      const result = await act({ action: editor ? 'update' : 'create', kind, ...(editor ? { record_id: editor.id } : {}), fields })
      if (result) { setFormOpen(false); setEditor(null) }
    }} />}
    {status && <p role="status">{status}</p>}
    {receipt && <PersonalReceipt key={receipt.id} receipt={receipt} onChanged={() => void load()} />}
    {browse && <div className="personal-browser"><label>Buscar registros<input value={query} onChange={e => { setQuery(e.target.value); setPreview(null) }} /></label>
      {!rows.length && <p>Nenhum registro encontrado.</p>}
      <ul>{rows.map(row => <li key={row.id}><div><strong>{row.title}</strong><small>{row.date_str || row.date || row.due_date || ''}{row.amount != null ? ' · ' + money.format(row.amount) : ''}{row.account ? ' · ' + row.account : ''}{row.archived || row.enabled === false ? ' · Pausado' : ''}</small></div>
        {kind === 'habit' && <HabitProgress row={row} disabled={busy} save={value => void act({ action: 'progress', kind, record_id: row.id, fields: { value } })} />}
        {kind === 'task' && row.subtasks?.map((step: any, index: number) => <label className="personal-check" key={step.id}><input type="checkbox" disabled={busy} checked={!!step.completed} onChange={e => void act({ action: 'update', kind, record_id: row.id, fields: { subtasks: row.subtasks.map((s: any, i: number) => ({ title: s.title, completed: i === index ? e.target.checked : !!s.completed })) } })} />{step.title}</label>)}
        <div className="today-actions"><button disabled={busy} onClick={() => { setEditor(row); setFormOpen(true) }}>Corrigir</button>
          {['habit', 'workout_plan', 'rule', 'recurrence'].includes(kind) && <button disabled={busy} onClick={() => void act({ action: row.archived || row.enabled === false ? 'resume' : 'pause', kind, record_id: row.id })}>{row.archived || row.enabled === false ? 'Retomar' : 'Pausar'}</button>}
          {kind === 'habit' && <button disabled={busy} onClick={() => void act({ action: 'complete', kind, record_id: row.id })}>Concluir</button>}
          {kind === 'task' && <button disabled={busy} onClick={() => void act({ action: row.completed ? 'reopen' : 'complete', kind, record_id: row.id })}>{row.completed ? 'Reabrir' : 'Concluir'}</button>}
          {kind === 'note' && <button disabled={busy} onClick={() => void act({ action: 'to_task', kind, record_id: row.id })}>Criar tarefa</button>}
          {kind === 'finance' && <button disabled={busy} onClick={() => void act({ action: 'refund', kind, record_id: row.id })}>Registrar estorno</button>}
          <button disabled={busy} onClick={async () => { if (await confirmRemoval(1, `Excluir ${row.title}?`)) await act({ action: 'delete', kind, record_id: row.id }) }}>Excluir</button>
        </div></li>)}</ul>
      {rows.length > 1 && <button disabled={busy} onClick={async () => { const result = await act({ action: 'bulk_preview', kind, query }); if (result && await autoAllows('bulk')) await act({ action: 'bulk_confirm', token: result.token }); else if (result) setPreview(result) }}>Excluir resultados</button>}
      {preview && <section role="region" aria-label="Confirmar exclusão"><strong>Excluir estes {preview.results.length} registros?</strong><ul>{preview.results.map(row => <li key={row.id}>{row.title}</li>)}</ul><button disabled={busy} onClick={async () => { await act({ action: 'bulk_confirm', token: preview.token }); setPreview(null) }}>Confirmar exclusão</button><button onClick={() => setPreview(null)}>Cancelar</button></section>}
    </div>}
    {prefs.blocks.includes('finance') && <details><summary>Contas e pagamentos pendentes</summary><small>Saldos dos registros até hoje. Transferências não contam como receita ou despesa.</small>
      {Object.entries(overview?.accounts ?? {}).map(([account, amount]) => <p key={account}>{account}: <b>{money.format(amount)}</b></p>)}
      {overview?.recurring_due.map(item => <div key={item.id}>{item.title} · {money.format(item.amount)} · {item.next_date}<button disabled={busy} onClick={() => void act({ action: 'pay', kind: 'recurrence', record_id: item.id })}>Registrar pagamento</button></div>)}
      {overview && !overview.recurring_due.length && <p>Nenhuma recorrência pendente.</p>}
    </details>}
    {prefs.review !== 'off' && <details><summary>Minha revisão {prefs.review === 'daily' ? 'do dia' : 'da semana'}</summary><p>Confira suas pendências, organize as anotações e escolha uma próxima ação. Você pode retomar os hábitos no seu ritmo.</p><p>{overview?.tasks.length ?? 0} tarefas pendentes · {overview?.recurring_due.length ?? 0} pagamentos para conferir.</p><button onClick={() => { setBrowse(true); setKind('note') }}>Revisar anotações</button></details>}
    <details><summary>Histórico e desfazer</summary>{overview?.history.map(item => <PersonalReceipt key={item.id + item.undone} receipt={item} onChanged={() => void load()} />)}{overview && !overview.history.length && <p>As próximas alterações aparecerão aqui.</p>}</details>
    <details><summary>Personalizar Hoje</summary>
      {Object.entries(blockLabels).map(([key, name]) => <label className="personal-check" key={key}><input type="checkbox" disabled={busy} checked={prefs.blocks.includes(key)} onChange={e => void preference({ blocks: e.target.checked ? [...prefs.blocks, key] : prefs.blocks.filter(b => b !== key) })} />{name}</label>)}
      <label className="personal-check"><input type="checkbox" disabled={busy} checked={prefs.reduced_motion} onChange={e => void preference({ reduced_motion: e.target.checked })} />Reduzir animações</label>
      <label>Revisão opcional no Hoje<select disabled={busy} value={prefs.review} onChange={e => void preference({ review: e.target.value as PersonalPreferences['review'] })}><option value="off">Desativada</option><option value="daily">Diária</option><option value="weekly">Semanal</option></select></label>
    </details>
  </section>
}

function RecordForm({ kind, initial, busy, onSave, onCancel }: { kind: string; initial: Row | null; busy: boolean; onSave: (fields: Record<string, any>) => Promise<void>; onCancel: () => void }) {
  const initialFields = () => ({ ...initial, title: initial?.title || '', description: initial?.description || '', date: initial?.date_str || initial?.date || '', exercises: initial?.exercises || [], type: initial?.type || 'expense', frequency: initial?.frequency || 'monthly', source: initial?.source || 'workout', target_kind: initial?.target_kind || 'habit' })
  const [fields, setFields] = useState<Record<string, any>>(initialFields)
  const [targets, setTargets] = useState<Row[]>([])
  const changed = useRef(new Set<string>())
  const set = (key: string, value: any) => { changed.current.add(key); setFields(f => ({ ...f, [key]: value })) }
  useEffect(() => {
    if (kind !== 'rule') return
    personalRequest({ action: 'list', kind: fields.target_kind }).then(data => setTargets(data.results)).catch(() => setTargets([]))
  }, [kind, fields.target_kind])
  function input(key: string, label: string, type = 'text', required = false, options?: { min?: number; max?: number; step?: number }) {
    return <label key={key}>{label}<input type={type} required={required} value={fields[key] ?? ''} {...options} onChange={e => set(key, type === 'number' && e.target.value !== '' ? Number(e.target.value) : e.target.value)} /></label>
  }
  async function submit(e: React.FormEvent) {
    e.preventDefault()
    const values = Object.fromEntries(Object.entries(fields).filter(([key]) => changed.current.has(key)))
    if (!initial) {
      if (['finance', 'recurrence'].includes(kind)) values.type = fields.type
      if (kind === 'recurrence') values.frequency = fields.frequency
      if (kind === 'rule') { values.source = fields.source; values.target_kind = fields.target_kind; values.enabled = true }
      if (kind === 'note' && !values.title) values.title = String(values.content || 'Anotação').split('\n')[0].slice(0, 80)
    }
    if (initial && !changed.current.size) return
    if (kind === 'finance') delete values.title
    await onSave(values)
  }
  return <form className="personal-form" onSubmit={e => void submit(e)} aria-label={initial ? 'Corrigir registro' : 'Captura rápida'}>
    {kind !== 'finance' && input('title', 'Título', 'text', !['note', 'sleep', 'mood', 'transfer', 'rule'].includes(kind))}
    {['note', 'personal'].includes(kind) && <label>{kind === 'note' ? 'Anotação' : 'Conteúdo'}<textarea required value={fields.content || ''} onChange={e => set('content', e.target.value)} /></label>}
    {kind === 'note' && input('tags', 'Etiquetas (separadas por vírgula)')}
    {kind === 'checklist' && <label>Itens, um por linha<textarea value={fields.text || ''} onChange={e => set('text', e.target.value)} /></label>}
    {['finance', 'recurrence', 'transfer'].includes(kind) && input('amount', kind === 'finance' ? 'Valor total (R$)' : 'Valor (R$)', 'number', true, { min: .01, step: .01 })}
    {['finance', 'recurrence'].includes(kind) && <>
      <label>Tipo<select value={fields.type} onChange={e => set('type', e.target.value)}><option value="expense">Despesa</option><option value="income">Receita</option></select></label>
      {kind === 'finance' && input('description', 'Descrição')}{input('account', 'Conta ou cartão (opcional)')}{input('category', 'Categoria (opcional)')}
      {!initial && kind === 'finance' && input('installments', 'Parcelas (opcional)', 'number', false, { min: 1, max: 60, step: 1 })}
    </>}
    {kind === 'transfer' && <>{input('from_account', 'Conta de origem', 'text', true)}{input('to_account', 'Conta de destino', 'text', true)}</>}
    {kind === 'recurrence' && <>{input('next_date', 'Próximo vencimento', 'date', true)}<label>Frequência<select value={fields.frequency} onChange={e => set('frequency', e.target.value)}><option value="monthly">Mensal</option><option value="weekly">Semanal</option></select></label><small>Não registra pagamento automaticamente.</small></>}
    {kind === 'task' && <>{input('due_date', 'Prazo (opcional)', 'date')}{input('priority', 'Prioridade: 1 urgente a 4 baixa', 'number', false, { min: 1, max: 4, step: 1 })}{input('project', 'Projeto (opcional)')}<label>Etapas, uma por linha<textarea value={(fields.subtasks || []).map((s: any) => typeof s === 'string' ? s : s.title).join('\n')} onChange={e => set('subtasks', e.target.value.split('\n').filter(Boolean))} /></label></>}
    {kind === 'habit' && <>{input('start_time', 'Horário (opcional)', 'time')}{input('target_value', 'Meta (opcional)', 'number', false, { min: .01, step: .01 })}{input('unit', 'Unidade (copos, minutos…)')}<DayPicker selected={fields.days_of_week || ['mon','tue','wed','thu','fri','sat','sun']} onChange={days => set('days_of_week', days)} /></>}
    {kind === 'sleep' && input('hours', 'Horas de sono', 'number', true, { min: 0, max: 24, step: .25 })}
    {kind === 'mood' && input('score', 'Como você está? 1 ruim a 5 muito bem', 'number', true, { min: 1, max: 5, step: 1 })}
    {['workout', 'workout_plan'].includes(kind) && <fieldset><legend>Exercícios</legend>
      {fields.exercises.map((exercise: Record<string, any>, index: number) => <div className="personal-exercise" key={index}>
        {(['name', 'sets', 'reps', 'weight'] as const).map((key, i) => <label key={key}>{['Exercício', 'Séries', 'Repetições', 'Carga (kg)'][i]}<input required={key === 'name'} type={key === 'name' ? 'text' : 'number'} min={0} step={key === 'weight' ? .25 : 1} value={exercise[key] ?? ''} onChange={e => set('exercises', fields.exercises.map((item: any, at: number) => at === index ? { ...item, [key]: key === 'name' ? e.target.value : Number(e.target.value) } : item))} /></label>)}
        <button type="button" onClick={() => set('exercises', fields.exercises.filter((_: unknown, at: number) => at !== index))}>Remover exercício</button>
      </div>)}<button type="button" onClick={() => set('exercises', [...fields.exercises, { name: '' }])}>Adicionar exercício</button>
      {kind === 'workout_plan' && <DayPicker selected={(fields.days || []).map((d: number) => ['mon','tue','wed','thu','fri','sat','sun'][d])} onChange={days => set('days', days.map(d => ['mon','tue','wed','thu','fri','sat','sun'].indexOf(d)))} />}
    </fieldset>}
    {kind === 'rule' && <><label>Quando registrar<select value={fields.source} onChange={e => set('source', e.target.value)}><option value="workout">Treino concluído</option><option value="finance">Pagamento com descrição exata</option></select></label>{fields.source === 'finance' && input('match_description', 'Descrição exata do pagamento', 'text', true)}<label>Concluir<select value={fields.target_kind} onChange={e => { set('target_kind', e.target.value); set('target_id', '') }}><option value="habit">Hábito</option><option value="task">Tarefa</option></select></label><label>Registro relacionado<select required value={fields.target_id || ''} onChange={e => set('target_id', e.target.value)}><option value="">Escolha…</option>{targets.map(row => <option key={row.id} value={row.id}>{row.title}</option>)}</select></label></>}
    {!['task', 'habit', 'rule', 'checklist', 'note'].includes(kind) && input('date', 'Data (opcional)', 'date')}
    <div className="today-actions"><button type="submit" disabled={busy}>{busy ? 'Salvando…' : initial ? 'Salvar correção' : 'Salvar registro'}</button><button type="button" onClick={onCancel}>Cancelar</button></div>
  </form>
}

function DayPicker({ selected, onChange }: { selected: string[]; onChange: (days: string[]) => void }) {
  return <fieldset><legend>Dias da semana</legend>{['mon','tue','wed','thu','fri','sat','sun'].map((day, index) => <label className="personal-check" key={day}><input type="checkbox" checked={selected.includes(day)} onChange={e => onChange(e.target.checked ? [...selected, day] : selected.filter(d => d !== day))} />{['Seg','Ter','Qua','Qui','Sex','Sáb','Dom'][index]}</label>)}</fieldset>
}

function HabitProgress({ row, disabled, save }: { row: Row; disabled: boolean; save: (value: number) => void }) {
  const [value, setValue] = useState('')
  return <form className="today-actions" onSubmit={e => { e.preventDefault(); if (value !== '') save(Number(value)) }}>
    <label>Progresso de {row.title} (meta {row.target_value || 1} {row.unit || ''})<input aria-label={`Progresso de ${row.title}`} type="number" required min={0} max={1000000} step="any" value={value} onChange={e => setValue(e.target.value)} /></label>
    <button disabled={disabled}>Salvar progresso</button>
  </form>
}
