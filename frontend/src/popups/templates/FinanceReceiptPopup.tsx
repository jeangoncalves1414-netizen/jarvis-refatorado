import { useWindows } from '../../windows/WindowManager'
import { WINDOW_FINANCE } from '../../windows/registry'
import { CountUp } from '../motion'
import { usePopups } from '../PopupProvider'
import type { FinanceEntry, FinanceReceipt, PopupComponentProps } from '../registry'

const money = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })
const month = new Intl.DateTimeFormat('pt-BR', { month: 'long', year: 'numeric' })

export function FinanceReceiptPopup({ popup }: PopupComponentProps<FinanceReceipt>) {
  const { entries, period, before, after } = popup.data
  const windows = useWindows()
  const { dismiss } = usePopups()
  const caption = period === 'all' ? 'Saldo de todos os períodos' : `Saldo de ${month.format(new Date(period + '-15T12:00:00'))}`

  function view(editId?: string) {
    const mounted = windows.windows.some(item => item.id === WINDOW_FINANCE)
    if (mounted) {
      windows.focus(WINDOW_FINANCE)
      if (editId) window.dispatchEvent(new CustomEvent('jarvis:finance-edit', { detail: editId }))
    } else {
      const now = new Date()
      const thisMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
      windows.open(WINDOW_FINANCE, { period: period === thisMonth ? 'month' : 'all', ...(editId ? { edit_id: editId } : {}) })
    }
    dismiss(popup.id)
  }

  function row(entry: FinanceEntry) {
    return (
      <li key={entry.id} className="ws-finance-receipt-row">
        <span>{entry.description || entry.category}</span>
        <strong className={`ws-finance-amount ${entry.type}`}>{entry.type === 'income' ? '+' : '−'} {money.format(entry.amount)}</strong>
        <button type="button" className="ws-popup-action" onClick={() => view(entry.id)} aria-label={`Corrigir ${entry.description || entry.category}`}>Corrigir</button>
      </li>
    )
  }

  return (
    <div className="ws-finance-receipt">
      {entries.length > 1 && <strong>{entries.length} lançamentos registrados</strong>}
      {entries.length > 0 && <ul className="ws-popup-list">{entries.slice(0, 3).map(row)}</ul>}
      {entries.length > 3 && <details><summary>Mais {entries.length - 3} lançamentos</summary><ul className="ws-popup-list">{entries.slice(3).map(row)}</ul></details>}
      <div><small>{caption}</small>
        <div aria-label={`${caption}. De ${money.format(before)} para ${money.format(after)}.`}>
          <span aria-hidden="true">{before !== after && <>{money.format(before)} → </>}<strong><CountUp key={popup.id} from={before} to={after} format={money.format} durationMs={480} /></strong></span>
        </div>
      </div>
      <button type="button" className="ws-popup-action" onClick={() => view()}>Ver finanças</button>
    </div>
  )
}
