import { ArrowUpRight, BookOpen, MessageSquare, Plug, RefreshCw, ShieldCheck, Workflow } from 'lucide-react'
import { TodayPanel } from '../components/TodayPanel'
import type { Capability, OperationalState } from '../hooks/useOperationalSnapshot'

type Props = { operational: OperationalState; onNavigate: (id: string) => void }
export function WorkspaceHome({ operational, onNavigate }: Props) {
  const { snapshot, error } = operational
  const sections = [
    { id: 'Central', icon: ShieldCheck, title: 'Execuções e aprovações', description: snapshot && !error ? `${snapshot.summary.pending_actions} ações em andamento ou aguardando decisão.` : 'Histórico de ações e propostas.' },
    { id: 'Memórias', icon: BookOpen, title: 'Seu conhecimento', description: 'Memórias e contexto salvo do agente.' },
    { id: 'Automações', icon: Workflow, title: 'Rotinas e automações', description: 'Lembretes e controles disponíveis.' },
    { id: 'Integrações', icon: Plug, title: 'Conexões do workspace', description: 'Estado das integrações.' },
  ]
  return (
    <section className="ws-content-page">
      <header className="ws-page-heading">
        <h1>Início</h1>
        <button className="ws-button primary" onClick={() => onNavigate('Chat')}><MessageSquare size={16} /> Abrir conversa</button>
      </header>
      <TodayPanel />
      <div className="ws-overview-grid">
        {sections.map(item => (
          <button className="ws-overview-card" key={item.id} onClick={() => onNavigate(item.id)}>
            <item.icon size={21} /><ArrowUpRight size={16} /><h3>{item.title}</h3><p>{item.description}</p>
          </button>
        ))}
      </div>
    </section>
  )
}

const capabilityLabels: Record<string, string> = { healthy: 'Funcionando', configured: 'Configurado', degraded: 'Com falha', off: 'Desligado', unknown: 'Não verificado', unavailable: 'Indisponível' }
const groups: [string, string][] = [['ia', 'IA e voz'], ['dispositivos', 'Dispositivos'], ['integracao', 'Integrações e aplicativos']]
const when = (seconds: number) => new Date(seconds * 1000).toLocaleString('pt-BR')
const yesNo = (value: boolean | null, unknown: string) => value === true ? 'Sim' : value === false ? 'Não' : unknown

function CapabilityCard({ item, since, stale, onNavigate }: { item: Capability; since?: number; stale: boolean; onNavigate: (id: string) => void }) {
  const sinceText = since ? `desde ${when(since)}` : 'desde que o servidor iniciou'
  return <article className="ws-integration-card" aria-label={item.label}>
    <div className="ws-section-title"><Plug size={22} /><span className="ws-tag"><i className={`ws-dot ${stale ? '' : item.status}`} />{stale ? 'Desatualizado' : capabilityLabels[item.status] || 'Não verificado'}</span></div>
    <h2>{item.label}</h2>
    <p>{item.reason || 'Sem diagnóstico adicional.'}</p>
    <dl className="ws-capability-facts">
      <dt>Configurado</dt><dd>{yesNo(item.configured, 'Não verificado')}</dd>
      {item.configured !== false && <><dt>Alcançável</dt><dd>{yesNo(item.reachable, `Sem chamada ${sinceText}`)}</dd></>}
      {item.configured !== false && <><dt>Último sucesso</dt><dd>{item.last_success_at ? when(item.last_success_at) : `Nenhum ${sinceText}`}</dd></>}
      {item.last_failure_at && <><dt>Última falha</dt><dd>{when(item.last_failure_at)}{item.last_failure_reason ? `: ${item.last_failure_reason}` : ''}</dd></>}
      {item.provider && <><dt>{item.last_success_at ? 'Respondeu' : 'Rota'}</dt><dd>{[item.provider, item.model, item.latency_ms ? `${item.latency_ms} ms` : ''].filter(Boolean).join(' · ')}</dd></>}
      {item.fallback && <><dt>Última troca</dt><dd>{item.fallback.from} → {item.fallback.to}{item.fallback.model ? ` (${item.fallback.model})` : ''} em {when(item.fallback.at)}. Motivo: {item.fallback.reason}</dd></>}
    </dl>
    <button className="ws-text-button" onClick={() => onNavigate(item.target || 'Configurações')}>Abrir controles <ArrowUpRight size={14} /></button>
  </article>
}

export function IntegrationsPage({ operational, onNavigate }: Props) {
  const { snapshot, error, refresh } = operational
  const capabilities = snapshot?.capabilities
  if (capabilities?.length) {
    return <section className="ws-content-page"><div className="ws-page-heading"><div><span className="ws-overline">CAPACIDADES CONECTADAS</span><h1>Integrações</h1><p>Estado real de cada capacidade: configuração, última chamada e quem respondeu.</p></div><button className="ws-button" onClick={refresh}><RefreshCw size={15} /> Atualizar</button></div>
      {error && <div className="ws-error" role="alert">{error} Os estados anteriores podem estar desatualizados.</div>}
      {groups.map(([group, title]) => {
        const items = capabilities.filter(item => item.group === group)
        return items.length ? <div key={group}><h3 className="ws-capability-group">{title}</h3><div className="ws-overview-grid">{items.map(item => <CapabilityCard key={item.id} item={item} since={snapshot?.health_since} stale={!!error} onNavigate={onNavigate} />)}</div></div> : null
      })}
      <div className="ws-info-note"><ShieldCheck size={18} /><span>"Alcançável" e "último sucesso" vêm das chamadas reais desde que o servidor iniciou; nada é testado em segundo plano. Disponibilidade não equivale a permissão para executar: as propostas que exigem aprovação ficam em Execuções.</span></div>
    </section>
  }
  return <section className="ws-content-page"><div className="ws-page-heading"><div><span className="ws-overline">CAPACIDADES CONECTADAS</span><h1>Integrações</h1><p>Disponibilidade informada pela central de controle.</p></div><button className="ws-button" onClick={refresh}><RefreshCw size={15} /> Atualizar</button></div>{error && <div className="ws-error" role="alert">{error} Os estados anteriores podem estar desatualizados.</div>}<div className="ws-overview-grid">{snapshot?.components.map(item => <article className="ws-integration-card" key={item.id}><div className="ws-section-title"><Plug size={22} /><span className="ws-tag"><i className={`ws-dot ${error ? '' : item.status}`} />{error ? 'Desatualizado' : ({ healthy: 'Disponível', degraded: 'Requer atenção', unavailable: 'Indisponível', off: 'Desligado' }[item.status] || 'Não verificado')}</span></div><h2>{item.label}</h2><p>{item.reason || 'Sem diagnóstico adicional.'}</p><button className="ws-text-button" onClick={() => onNavigate(item.id === 'providers' || item.id === 'voice_capture' ? 'Configurações' : item.id === 'bridge' ? 'Automações' : 'Central')}>Abrir controles <ArrowUpRight size={14} /></button></article>)}</div>{!snapshot && <div className="ws-empty"><Plug size={28} /><h3>Sem dados de conexão</h3><p>Conecte o aplicativo ao servidor para consultar as integrações.</p></div>}<div className="ws-info-note"><ShieldCheck size={18} /><span>Disponibilidade não equivale a permissão para executar. As propostas que exigem aprovação ficam em Execuções. O registro de um dispositivo não comprova que ele esteja online.</span></div></section>
}
