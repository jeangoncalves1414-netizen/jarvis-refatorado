import { PersonalReceipt } from '../../components/PersonalReceipt'
import type { PersonalReceipt as Receipt } from '../../utils/personalRecords'
import { getPopupDef, type PopupComponentProps, type FinanceReceipt } from '../registry'
import type { PopupEnvelope } from '../types'
import { Suspense } from 'react'
import { openOrganizer } from '../../utils/personalRecords'
import { CountUp } from '../motion'

export type PersonalReceiptData = { receipts: Receipt[]; finance?: FinanceReceipt | null; preview?: PopupEnvelope | null; bulk?: { kind: string; query: string; count: number } | null }
const money = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })
export function PersonalReceiptPopup({ popup, revision, setHold }: PopupComponentProps<PersonalReceiptData>) {
  const preview = popup.data.preview
  const Preview = preview ? getPopupDef(preview.template)?.component : null
  return <div className="personal-popup">
    {popup.data.bulk && <div><p>{popup.data.bulk.count} registros encontrados. Confira os títulos antes de excluir.</p><button onClick={() => openOrganizer({ bulk: popup.data.bulk })}>Revisar exclusão</button></div>}
    {Preview && preview && <Suspense fallback={<p>Carregando registro…</p>}><Preview popup={preview} revision={revision} setHold={setHold} /></Suspense>}
    {!Preview && popup.data.finance && <p aria-live="polite">Saldo {popup.data.finance.period === 'all' ? 'de todos os períodos' : popup.data.finance.period}: {money.format(popup.data.finance.before)} → <strong><CountUp from={popup.data.finance.before} to={popup.data.finance.after} format={money.format} durationMs={450} /></strong></p>}
    {popup.data.receipts.map(receipt => <PersonalReceipt key={receipt.id} receipt={receipt} />)}
  </div>
}
