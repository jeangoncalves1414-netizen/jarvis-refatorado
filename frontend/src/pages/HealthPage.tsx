import { RefreshCw } from 'lucide-react'
import type { OperationalState } from '../hooks/useOperationalSnapshot'
import type { LiveAudioDiagnostics } from '../hooks/useMediaAssistant'

export function HealthPage({ operational, audio }: { operational: OperationalState; audio?: LiveAudioDiagnostics | null }) {
  const { snapshot, error, updatedAt, refresh } = operational
  const health = snapshot?.health
  const mic = health?.microphone
  const verified = health?.last_verified_action
  const failures = snapshot?.recent_actions.filter(action => action.status === 'failed') ?? []
  const stamp = (time: number) => new Date(time * 1000).toLocaleString('pt-BR')
  return <section className="ws-content-page">
    <div className="ws-page-heading"><div><span className="ws-overline">DIAGNÓSTICO</span><h1>Saúde do Jarvis</h1><p>{updatedAt ? `Atualizado às ${new Date(updatedAt).toLocaleTimeString('pt-BR')}` : 'Consultando o servidor…'}</p></div><button className="ws-button" onClick={refresh}><RefreshCw size={15} /> Atualizar</button></div>
    {(error || health?.error) && <div className="ws-error" role="alert">{error || health?.error}{snapshot && ' Os dados exibidos podem estar desatualizados.'}</div>}
    <section className="ws-panel"><h2>IA e voz</h2>{snapshot?.capabilities?.filter(item => item.group === 'ia').map(item => <article className="ws-goal" key={item.id}><div><h3>{item.label}</h3><p>{item.provider || 'Provedor desconhecido'} · {item.model || 'Modelo não informado'}</p><p>{item.last_success_at ? `Último sucesso: ${stamp(item.last_success_at)}` : 'Rota configurada; ainda sem chamada bem-sucedida nesta sessão.'}</p>{item.fallback && <p>Fallback: {item.fallback.from} → {item.fallback.to}. {item.fallback.reason}</p>}{item.last_failure_reason && <p role="status">Último erro: {item.last_failure_reason}</p>}</div><span className="ws-tag">{item.reachable === true ? 'Respondeu' : item.reachable === false ? 'Falhou' : item.configured ? 'Não verificado' : 'Indisponível'}</span></article>)}</section>
    <section className="ws-panel"><h2>Microfone</h2>{mic ? <><p>Configuração: {mic.configured_engine} · {mic.configured_device || 'Dispositivo padrão'}</p><p>Captura atual: {audio?.mode || (mic.active ? 'backend-sr' : 'Inativa neste navegador e no PC')}</p>{mic.active && <p>PC: {mic.device || 'Microfone padrão'} · {mic.state}</p>}{audio?.note && <p>{audio.note}</p>}</> : <p>Estado indisponível.</p>}</section>
    <section className="ws-panel"><h2>Ferramentas e MCP</h2><details><summary>{health?.tools?.length ?? '—'} ferramentas registradas</summary><p>{health?.tools?.join(', ')}</p></details><p>Registro indica disponibilidade no agente; a execução depende do modo e da conexão.</p>{health?.mcp_error && <p role="alert">{health.mcp_error}</p>}{health?.mcp_servers?.length ? health.mcp_servers.map(server => <article className="ws-goal" key={server.id}><div><strong>{server.name}</strong><p>{server.tools_count} ferramentas · {server.status}</p>{server.error && <p>{server.error}</p>}</div></article>) : <p>Nenhum servidor MCP informado.</p>}</section>
    <section className="ws-panel"><h2>Última ação com efeito verificado</h2>{verified ? <><strong>{verified.tool_name}</strong><p>{verified.effect_evidence}</p><p>{stamp(verified.updated_at)}</p></> : <p>Ainda não há confirmação de efeito registrada. Ações antigas não foram marcadas como verificadas retroativamente.</p>}</section>
    <section className="ws-panel"><h2>Falhas recentes</h2>{failures.length ? failures.map(action => <article className="ws-goal" key={action.id}><div><strong>{action.tool_name}</strong><p>{action.result_summary || 'Sem detalhe registrado.'}</p><small>{stamp(action.updated_at)}</small></div></article>) : <p>Nenhuma falha nas últimas ações recebidas.</p>}</section>
  </section>
}
