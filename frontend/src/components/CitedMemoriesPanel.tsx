import { useCallback, useEffect, useState } from 'react'
import { ConfirmDialog } from './ConfirmDialog'

/** Memória com fonte (fase contexto 2): mesmo formato de data/memory_facts.json. */
type CitedFact = {
  id: string
  text: string
  slot: string | null
  value: string | null
  when: string | null
  source: { created_at: number; session_id: string; run_id: string; origin: string; kind: string }
  updated_at: number
}

export const MEMORY_FOCUS_KEY = 'jarvis.memoryFocus'

const KIND_LABEL: Record<string, string> = { gatilho: 'pedido explícito', extracao: 'extraída da conversa', manual: 'adicionada aqui' }

function sourceLine(fact: CitedFact) {
  const when = fact.source?.created_at ? new Date(fact.source.created_at * 1000).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' }) : 'sem data'
  const parts = [fact.source?.origin || 'chat', when]
  if (fact.source?.session_id) parts.push(`conversa ${fact.source.session_id.slice(0, 8)}`)
  if (fact.source?.kind) parts.push(KIND_LABEL[fact.source.kind] || fact.source.kind)
  return parts.join(' · ')
}

/** Aba "Com fonte" da tela Memórias: ver, editar, remover e adicionar memórias citáveis. */
export function CitedMemoriesPanel() {
  const [facts, setFacts] = useState<CitedFact[]>([])
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [newText, setNewText] = useState('')
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [confirmId, setConfirmId] = useState<string | null>(null)
  const [focusId, setFocusId] = useState<string | null>(() => {
    try {
      const value = sessionStorage.getItem(MEMORY_FOCUS_KEY)
      sessionStorage.removeItem(MEMORY_FOCUS_KEY)
      return value
    } catch { return null }
  })

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const response = await fetch('/api/memories/facts')
      const data = await response.json()
      if (!response.ok || !data.ok) throw new Error(data.error || 'Não foi possível carregar as memórias.')
      setFacts(data.facts || [])
      setDrafts({})
      setError('')
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Não foi possível carregar as memórias.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  // O link "editar" da citação no chat pode chegar com a aba já aberta.
  useEffect(() => {
    const onOpen = () => {
      try {
        const value = sessionStorage.getItem(MEMORY_FOCUS_KEY)
        sessionStorage.removeItem(MEMORY_FOCUS_KEY)
        if (value) setFocusId(value)
      } catch { /* sem sessionStorage */ }
    }
    window.addEventListener('jarvis:open-memory', onOpen)
    return () => window.removeEventListener('jarvis:open-memory', onOpen)
  }, [])

  useEffect(() => {
    if (!focusId || loading) return
    document.getElementById(`mem-fact-${focusId}`)?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [focusId, loading])

  const send = async (payload: Record<string, string>, done: string) => {
    setBusy(true)
    setInfo('')
    try {
      const response = await fetch('/api/memories/facts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      const data = await response.json()
      if (!response.ok || !data.ok) throw new Error(data.error || 'Não foi possível gravar a memória.')
      setError('')
      setInfo(`${done} Registro na Central.`)
      await load()
      return true
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Não foi possível gravar a memória.')
      return false
    } finally {
      setBusy(false)
    }
  }

  const addFact = async () => {
    if (!newText.trim()) return
    if (await send({ operation: 'save', text: newText }, 'Memória salva.')) setNewText('')
  }

  return (
    <div className="mem-panel">
      <p className="mem-intro">Memórias com data e origem. O Jarvis usa estas preferências para completar pedidos (por exemplo, a playlist da manhã ou a sua cidade) e mostra no chat quando usou uma delas.</p>
      <div className="mem-composer">
        <textarea value={newText} maxLength={300} onChange={event => setNewText(event.target.value)} placeholder="Nova memória, por exemplo: de manhã prefiro a playlist Foco" aria-label="Nova memória" />
        <button type="button" className="ws-button primary" disabled={busy || !newText.trim()} onClick={() => void addFact()}>Salvar memória</button>
      </div>
      {error && <p className="mem-error" role="alert">{error}</p>}
      {info && !error && <p className="mem-info">{info}</p>}
      {loading ? <p className="empty-state">Carregando…</p> : facts.length ? (
        <div className="mem-list">
          {facts.map(fact => {
            const draft = drafts[fact.id] ?? fact.text
            const changed = draft.trim() !== fact.text
            return (
              <article key={fact.id} id={`mem-fact-${fact.id}`} className={`mem-item ${focusId === fact.id ? 'mem-item-focus' : ''}`}>
                <span className="mem-source">{sourceLine(fact)}</span>
                <textarea value={draft} maxLength={300} aria-label="Texto da memória" onChange={event => setDrafts(current => ({ ...current, [fact.id]: event.target.value }))} />
                {fact.slot && fact.value && <span className="mem-slot">Preenche: {fact.slot === 'music' ? 'música' : fact.slot === 'city' ? 'cidade' : 'app'} = {fact.value}{fact.when ? ` (${fact.when === 'manha' ? 'manhã' : fact.when})` : ''}</span>}
                <div className="mem-actions">
                  <button type="button" className="ws-button" disabled={busy || !changed || !draft.trim()} onClick={() => void send({ operation: 'update', id: fact.id, text: draft }, 'Memória atualizada.')}>Salvar</button>
                  <button type="button" className="ws-button danger" disabled={busy} onClick={() => setConfirmId(fact.id)}>Remover</button>
                </div>
              </article>
            )
          })}
        </div>
      ) : <p className="empty-state">Nenhuma memória com fonte ainda. Diga "lembra que…" ou "prefiro…" no chat, ou adicione aqui.</p>}
      {confirmId && (
        <ConfirmDialog
          title="Remover memória?"
          message="O Jarvis deixa de usar esta preferência. A remoção fica registrada na Central."
          confirmLabel="Remover"
          danger
          busy={busy}
          onCancel={() => setConfirmId(null)}
          onConfirm={async () => { await send({ operation: 'delete', id: confirmId }, 'Memória removida.'); setConfirmId(null) }}
        />
      )}
    </div>
  )
}
