import { useCallback, useEffect, useState } from 'react'
import { panelRequest } from '../utils/panelApi'

type Bank = { id: string; name: string; checked: number; bank_updated?: string; error: string }
type Data = { configured: boolean; enabled: boolean; minutes: number; running: boolean; connections: Bank[]; held: { id: string; account: string; state: string; payload: { description: string; amount: number } }[] }
type Widget = { init: () => void; destroy?: () => void }
type WidgetOptions = { connectToken: string; itemId?: string; includeSandbox: boolean; onSuccess: (data: { item: { id: string } }) => void; onError: () => void; onClose: () => void }
let sdk: Promise<void> | undefined
function loadSDK() {
  if (!sdk) sdk = new Promise<void>((resolve, reject) => {
    const script = document.createElement('script')
    script.src = 'https://cdn.pluggy.ai/pluggy-connect/v2.8.2/pluggy-connect.js'
    script.onload = () => resolve()
    script.onerror = () => { sdk = undefined; script.remove(); reject(new Error('Não foi possível carregar a conexão bancária.')) }
    document.head.appendChild(script)
  })
  return sdk
}
const call = <T,>(body: object) => panelRequest<T>('/api/finance/banks', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
const when = (date: string | number | undefined) => date ? new Date(typeof date === 'number' ? date * 1000 : date).toLocaleString('pt-BR') : 'Ainda não realizada'
const states: Record<string, string> = { pending: 'Aguardando efetivação', transfer: 'Transferência entre contas próprias', card_payment: 'Pagamento de fatura', review_transfer: 'Conferir transferência', review_currency_or_type: 'Conferir moeda ou tipo' }

export function BankConnections() {
  const [data, setData] = useState<Data | null>(null)
  const [minutes, setMinutes] = useState(30)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const load = useCallback(async () => {
    const result = await panelRequest<Data>('/api/finance/banks')
    setData(result)
    return result
  }, [])
  useEffect(() => {
    void load().then(result => setMinutes(result.minutes)).catch(err => setMessage(err.message))
    const timer = window.setInterval(() => { void load().catch(() => {}) }, 5000)
    return () => clearInterval(timer)
  }, [load])
  async function act(body: object) {
    setBusy(true); setMessage('')
    try { await call(body); await load() } catch (err) { setMessage(err instanceof Error ? err.message : 'Falha ao salvar.') }
    finally { setBusy(false) }
  }
  async function connect(itemId?: string) {
    setBusy(true); setMessage('')
    try {
      const token = await call<{ accessToken: string }>({ action: 'connect_token', item_id: itemId })
      await loadSDK()
      const Constructor = (window as unknown as { PluggyConnect: new (options: WidgetOptions) => Widget }).PluggyConnect
      const widget = new Constructor({ connectToken: token.accessToken, itemId, includeSandbox: false,
        onSuccess: ({ item }) => { widget.destroy?.(); void act({ action: 'attach', item_id: item.id }) },
        onError: () => { setMessage('A conexão não foi concluída. Tente novamente no banco.'); setBusy(false) },
        onClose: () => setBusy(false),
      })
      widget.init()
    } catch (err) { setMessage(err instanceof Error ? err.message : 'Falha ao conectar.'); setBusy(false) }
  }
  return <details className="ws-bank-connections"><summary>Contas bancárias · sincronização automática</summary>
    <p>Conecte várias contas com autorização no banco. O Jarvis consulta os dados disponíveis ao abrir e no intervalo escolhido. A atualização pelo banco segue os limites do provedor.</p>
    {data && !data.configured && <p>Configure PLUGGY_CLIENT_ID e PLUGGY_CLIENT_SECRET no .env do servidor e reinicie. A conexão requer uma conta Pluggy com acesso aos bancos desejados.</p>}
    <p>A categorização usa a categoria do provedor e, quando necessário, o agente. Você pode corrigir as categorias em Finanças. Descrições podem ser enviadas ao provedor de IA configurado.</p>
    <label>Consultar a cada (minutos) <input type="number" min={5} max={1440} value={minutes} onChange={e => setMinutes(Number(e.target.value))} /></label>
    <button disabled={busy || !data?.configured} onClick={() => void act({ action: 'settings', enabled: !data?.enabled, minutes })}>{data?.enabled ? 'Desativar sincronização' : 'Ativar sincronização'}</button>
    <button disabled={busy || !data?.enabled} onClick={() => void act({ action: 'settings', enabled: true, minutes })}>Salvar intervalo</button>
    <button disabled={busy || !data?.configured} onClick={() => void connect()}>Conectar banco</button>
    <button disabled={busy || data?.running || !data?.connections.length} onClick={() => void act({ action: 'sync' })}>{data?.running ? 'Consultando…' : 'Consultar agora'}</button>
    {message && <p role="alert">{message}</p>}
    {data?.connections.map(bank => <article key={bank.id}>
      <strong>{bank.name}</strong><p>Consulta do Jarvis: {when(bank.checked)}<br />Atualização no banco: {when(bank.bank_updated)}</p>
      {bank.error && <p role="status">{bank.error}</p>}
      <button disabled={busy} onClick={() => void connect(bank.id)}>Renovar conexão</button>
      <button disabled={busy || data.running} onClick={() => { if (window.confirm('Desconectar este banco e encerrar o acesso no provedor? Os registros já importados serão mantidos.')) void act({ action: 'disconnect', item_id: bank.id }) }}>Desconectar</button>
    </article>)}
    {!!data?.held.length && <details><summary>Movimentos fora dos totais ({data.held.length}, até 100)</summary><p>Pendentes, transferências e pagamentos de fatura ficam separados dos gastos. Confira os casos marcados para revisão antes de registrá-los manualmente.</p>{data.held.map(row => <p key={row.id}>{row.account}: {row.payload.description} · {row.payload.amount.toLocaleString('pt-BR')} · {states[row.state] || row.state}</p>)}</details>}
  </details>
}
