import { Activity, ArrowUpRight, AudioLines, Cpu, Plug, ShieldCheck } from 'lucide-react'
import type { LlmSettings } from '../types'
import { actionLabels, type OperationalState } from '../hooks/useOperationalSnapshot'

export function AgentControls({ operational, llm, speakEnabled, onToggleSpeech, onNavigate }: {
  operational: OperationalState; llm: LlmSettings | null; speakEnabled: boolean; onToggleSpeech: () => void; onNavigate: (id: string) => void
}) {
  const { snapshot, error, updatedAt } = operational
  const pending = snapshot?.summary.awaiting_approvals ?? snapshot?.pending_actions.filter(item => item.status === 'awaiting_confirmation').length
  return <div className="agent-controls">
    <div className="control-intro"><span className="ws-overline">VISIBILIDADE E CONTROLE</span><p>Acompanhe o agente.<br />Decida os próximos passos.</p></div>
    <section className="control-section"><h3><Cpu size={15} /> Modelo de conversa</h3>
      <strong className="control-model">{llm?.effective_model || 'Modelo não informado'}</strong><span className="control-caption">{llm?.effective_provider || 'Provedor não verificado'}</span>
      {llm?.fallback_used && <p className="ws-warning">Fallback em uso: {llm.fallback_reason || 'rota alternativa selecionada pelo servidor'}</p>}
      <button className="ws-text-button" onClick={() => onNavigate('Configurações')}>Gerenciar modelos <ArrowUpRight size={14} /></button>
    </section>
    <section className="control-section"><h3><ShieldCheck size={15} /> Aprovações</h3><div className="control-count"><strong>{snapshot ? pending : '—'}</strong><span>{error ? 'último estado recebido' : 'aguardando sua decisão'}</span></div><p>Revise a proposta e o risco antes de autorizar uma ação.</p><button className="ws-button full" onClick={() => onNavigate('Central')}>Abrir execuções <ArrowUpRight size={14} /></button></section>
    <section className="control-section"><h3><Activity size={15} /> Atividade recente</h3>{snapshot?.recent_actions.length ? snapshot.recent_actions.slice(0, 3).map(item => <div className="control-activity" key={item.id}><span className={`ws-dot ${item.status}`} /><div><strong>{item.tool_name.replaceAll('_', ' ')}</strong><small>{actionLabels[item.status] || item.status}</small></div></div>) : <p>{snapshot ? 'As ações do agente aparecerão aqui.' : 'Aguardando dados da central.'}</p>}<button className="ws-text-button" onClick={() => onNavigate('Central')}>Ver histórico <ArrowUpRight size={14} /></button></section>
    <section className="control-section"><h3><Plug size={15} /> Conexões</h3>{snapshot?.components.map(item => <div className="control-connection" key={item.id}><span>{item.label}</span><span className={`ws-dot ${error ? '' : item.status}`} title={error ? 'Estado desatualizado' : item.reason} /></div>)}<small className="control-caption">{error ? 'Sem atualização. Confira a conexão.' : updatedAt ? `Atualizado às ${new Date(updatedAt).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}` : 'Conectando à central…'}</small><button className="ws-text-button" onClick={() => onNavigate('Integrações')}>Ver integrações <ArrowUpRight size={14} /></button></section>
    <button className="control-speech" aria-pressed={speakEnabled} onClick={onToggleSpeech}><AudioLines size={17} /><span>Respostas em voz</span><span className={`ws-switch ${speakEnabled ? 'on' : ''}`} /></button>
  </div>
}
