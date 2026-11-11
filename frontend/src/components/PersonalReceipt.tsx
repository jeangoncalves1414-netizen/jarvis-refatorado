import { useState } from 'react'
import { personalRequest, openOrganizer, changeTitle, type PersonalReceipt as Receipt } from '../utils/personalRecords'

export function PersonalReceipt({ receipt, onChanged }: { receipt: Receipt; onChanged?: () => void }) {
  const [undone, setUndone] = useState(!!receipt.undone)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function undo() {
    setBusy(true); setError('')
    try { await personalRequest({ action: 'undo', receipt_id: receipt.id }); setUndone(true); onChanged?.() }
    catch (err) { setError(err instanceof Error ? err.message : 'Não foi possível desfazer.') }
    finally { setBusy(false) }
  }
  return <article className={`personal-receipt ${undone ? 'is-undone' : ''}`}>
    <strong>{receipt.success ? '✓ ' : 'Atenção: '}{receipt.message}</strong>
    <ul>{receipt.changes.slice(0, 4).map(change => <li key={change.store + change.key}>
      <span>{changeTitle(change)}</span><small>{change.after == null ? 'Removido' : change.before == null ? 'Adicionado' : 'Atualizado'}</small>
    </li>)}</ul>
    <details><summary>Ver alterações ({receipt.changes.length})</summary>
      {receipt.changes.map(change => <div key={change.store + change.key}><b>{changeTitle(change)}</b>
        <div className="personal-before-after"><div><small>Antes</small><pre>{readable(change.before)}</pre></div><div><small>Depois</small><pre>{readable(change.after)}</pre></div></div>
      </div>)}
    </details>
    <div className="today-actions">
      <button type="button" disabled={busy || undone || receipt.can_undo === false} onClick={() => void undo()}>{undone ? 'Desfeito' : busy ? 'Desfazendo…' : 'Desfazer'}</button>
      <button type="button" onClick={() => openOrganizer(receipt)}>Corrigir / Abrir</button>
    </div>
    {error && <p role="alert">{error}</p>}
  </article>
}

function readable(value: any): string {
  if (value == null) return '—'
  if (typeof value === 'string') return value
  if (value.body) { try { return readable(JSON.parse(value.body)) } catch { /* fallback */ } }
  if (Array.isArray(value)) return value.map(readable).join('\n')
  const labels: Record<string, string> = { title: 'Título', name: 'Nome', description: 'Descrição', amount: 'Valor', account: 'Conta', content: 'Conteúdo', completed: 'Concluído', date: 'Data', date_str: 'Data', exercises: 'Exercícios', sets: 'Séries', reps: 'Repetições', weight: 'Carga', value: 'Progresso', hours: 'Horas', score: 'Humor', category: 'Categoria', due_date: 'Prazo', enabled: 'Ativo', next_date: 'Próxima data' }
  const lines = Object.entries(value).filter(([key]) => key in labels).map(([key, item]) => `${labels[key]}: ${typeof item === 'boolean' ? item ? 'Sim' : 'Não' : typeof item === 'object' ? readable(item) : String(item)}`)
  return lines.join('\n') || 'Configuração atualizada'
}
