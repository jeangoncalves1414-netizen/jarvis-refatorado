import { useEffect, useState } from 'react'
import type { CapabilityRoute } from '../types'

const modes = [['chat', 'Conversa padrão'], ['voice', 'Voz padrão'], ['thinking', 'Thinking'], ['planning', 'Planejamento'], ['research', 'Pesquisa aprofundada'], ['coder', 'Código'], ['browser', 'Navegação'], ['react', 'Execução por etapas'], ['lifeos', 'Life OS'], ['tutor', 'Tutor'], ['swarm', 'Especialistas']] as const
type Choice = { provider: string; model: string }

export function ModeModelSettings({ onSaved, catalog = [] }: { onSaved?: () => void; catalog?: string[] }) {
  const [choices, setChoices] = useState<Record<string, Choice>>({})
  const [routes, setRoutes] = useState<Record<string, CapabilityRoute>>({})
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const accept = (data: { routes: Record<string, CapabilityRoute & { inherited?: boolean }> }) => {
    setRoutes(data.routes)
    setChoices(Object.fromEntries(modes.map(([id]) => [id, { provider: data.routes[id]?.inherited ? '' : data.routes[id]?.primary?.provider || '', model: data.routes[id]?.inherited ? '' : data.routes[id]?.primary?.model || '' }])))
  }
  useEffect(() => {
    let active = true
    fetch('/api/settings/ai').then(async r => { if (!r.ok) throw Error('Não foi possível carregar os modelos.'); return r.json() }).then(data => { if (active) accept(data) }).catch(e => { if (active) setNotice(e.message) })
    return () => { active = false }
  }, [])
  const save = async () => {
    setBusy(true); setNotice('')
    try {
      const response = await fetch('/api/settings/ai', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ routes: Object.fromEntries(modes.map(([id]) => [id, choices[id]?.provider ? choices[id] : { inherit: true }])) }) })
      const data = await response.json()
      if (!response.ok || data.ok === false) throw Error(data.error || 'Não foi possível salvar os modelos.')
      accept(data); onSaved?.(); setNotice('Modelos salvos. Serão usados nos próximos pedidos.')
    } catch (error) { setNotice(error instanceof Error ? error.message : 'Não foi possível salvar.') }
    finally { setBusy(false) }
  }
  const modelsFor = (provider: string) => [...new Set([...Object.values(routes).flatMap(r => [r.primary, r.effective, ...(r.fallback || [])]).filter(r => r?.provider === provider).map(r => r!.model), ...(provider === 'oxyy' ? catalog : [])])].filter(Boolean)
  return <article className="settings-card"><h3>Modelo por modo</h3><p>Selecione um modelo conhecido ou digite seu identificador. No automático, vale o modo identificado. Voz padrão controla a resposta; a voz de leitura continua nas configurações de áudio.</p>
    {['gemini', 'groq', 'oxyy'].map(provider => <datalist id={`mode-models-${provider}`} key={provider}>{modelsFor(provider).map(model => <option value={model} key={model} />)}</datalist>)}
    <div className="ws-model-routes">{modes.map(([id, label]) => <div key={id} className="ws-model-route"><strong>{label}</strong><select aria-label={`Provedor de ${label}`} disabled={busy || !choices[id]} value={choices[id]?.provider || ''} onChange={e => setChoices(c => ({ ...c, [id]: { provider: e.target.value, model: '' } }))}>{id !== 'chat' && <option value="">Usar conversa padrão</option>}<option value="gemini">Gemini</option><option value="groq">Groq</option><option value="oxyy">Oxyy</option></select><input list={`mode-models-${choices[id]?.provider}`} aria-label={`Modelo de ${label}`} disabled={busy || !choices[id]?.provider} value={choices[id]?.model || ''} placeholder="Modelo padrão do provedor" onChange={e => setChoices(c => ({ ...c, [id]: { ...c[id], model: e.target.value } }))} /><small>{routes[id]?.effective ? `Disponível: ${routes[id].effective?.provider} · ${routes[id].effective?.model}` : 'Sem provedor configurado'}{routes[id]?.fallback_used ? ' · usando alternativa' : ''}</small></div>)}</div>
    <button className="ws-button" disabled={busy || !choices.chat} onClick={() => void save()}>{busy ? 'Salvando…' : 'Salvar modelos por modo'}</button>{notice && <p role="status">{notice}</p>}
  </article>
}
