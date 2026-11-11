import type { ToolActivityEntry } from '../../types'

const labels: Record<string, [string, string]> = {
  web_search: ['Pesquisando na web', 'Pesquisou na web'], browser: ['Navegando', 'Navegou'], browser_agent: ['Investigando páginas', 'Investigou páginas'],
  vault_search: ['Consultando memórias', 'Consultou memórias'], memory_tool: ['Consultando memória', 'Consultou memória'],
  video_analyst: ['Analisando vídeo', 'Analisou vídeo'], finance_tool: ['Atualizando finanças', 'Executou ação em finanças'],
  habit_tool: ['Atualizando hábitos', 'Executou ação em hábitos'], open_window: ['Abrindo janela', 'Abriu janela'],
}
const statuses: Record<string, string> = { running: 'Em andamento', succeeded: 'Concluída', failed: 'Falhou', cancelled: 'Cancelada', awaiting_confirmation: 'Aguardando aprovação', interrupted: 'Interrompida' }
export function ToolActivity({ entries = [], live = false }: { entries?: ToolActivityEntry[]; live?: boolean }) {
  if (!entries.length) return null
  const sources = [...new Map(entries.flatMap(e => e.sources || []).map(s => [s.url, s])).values()]
  const read = new Set(entries.flatMap(e => (e.sources || []).filter(s => s.read).map(s => s.url))).size
  const current = entries.at(-1)!
  const phrase = (e: ToolActivityEntry) => {
    const label = labels[e.tool] || [`Executando ${e.tool.replaceAll('_', ' ')}`, `Executou ${e.tool.replaceAll('_', ' ')}`]
    if (e.status === 'failed') return `Falha em ${e.tool.replaceAll('_', ' ')}`
    if (e.status === 'cancelled') return `Cancelou ${e.tool.replaceAll('_', ' ')}`
    if (e.status === 'awaiting_confirmation') return 'Aguardando aprovação'
    if (e.status === 'running' && e.detail) return e.detail
    if (e.status === 'running' && e.speech) return e.speech
    return e.status === 'succeeded' ? label[1] : `${label[0]}…`
  }
  const used = entries.filter(e => ['running', 'succeeded', 'failed', 'interrupted'].includes(e.status) || (e.status === 'cancelled' && e.speech)).length
  const summary = [used ? `Usou ${used} ferramenta${used === 1 ? '' : 's'}` : 'Ferramentas propostas', read ? `Acessou ${read} página${read === 1 ? '' : 's'}` : '', entries.some(e => e.status === 'failed') ? 'Houve falhas' : ''].filter(Boolean).join(' · ')
  return <details className="ws-tool-activity"><summary><span role={live ? 'status' : undefined}>{live ? phrase(current) : summary}</span></summary><ol>{entries.map(e => <li key={e.id}><span>{e.label || phrase(e)} · <code>{e.tool}</code></span>{e.label && <small> · {statuses[e.status] || e.status}</small>}{e.result && <p>{e.result}</p>}</li>)}</ol>{sources.length > 0 && <ul>{sources.map(s => <li key={s.url}><a href={s.url} target="_blank" rel="noopener noreferrer">{s.title || s.url}</a><small>{s.read ? ' · página lida' : ' · link encontrado'}</small></li>)}</ul>}</details>
}
