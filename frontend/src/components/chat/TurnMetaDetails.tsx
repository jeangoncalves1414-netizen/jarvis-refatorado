import type { TurnMeta } from '../../types'

export function TurnMetaDetails({ meta }: { meta?: TurnMeta }) {
  const lookup = meta?.memory_lookup
  const usage = meta?.context_usage || []
  if (!lookup && !usage.length) return null
  const last = usage[usage.length - 1]
  const format = (value: number) => value.toLocaleString('pt-BR')
  return <details className="ws-turn-meta">
    <summary>Contexto usado{last ? ` · ≈ ${format(last.estimated_tokens)} tokens na última chamada medida` : ' · consulta à memória'}{usage.some(item => item.reduced) ? ' · reduzido' : ''}</summary>
    {usage.length > 0 && <><p>Estimativa de entrada por chamada medida. Não representa cobrança, consumo acumulado ou capacidade máxima do modelo. Medição disponível no chat Groq; outros caminhos podem não aparecer.</p>
      {usage.map((item, i) => <p key={i}><strong>Chamada medida {i + 1} · {item.provider} · {item.model}</strong><br />≈ {format(item.estimated_tokens)} tokens{item.budget ? ` / ${format(item.budget)} de orçamento local` : ''}{item.reduced ? ` · reduzido de ≈ ${format(item.before_tokens)}` : ''}</p>)}
      {usage.some(item => item.reduced) && <p>A redução omite partes do pedido enviado; o histórico salvo não foi apagado. Não é um resumo automático.</p>}</>}
    {lookup && <><p>{lookup.summary}</p>{lookup.items.map((item, i) => <p key={i}><strong>{item.title}</strong><br />{item.text}</p>)}</>}
  </details>
}
