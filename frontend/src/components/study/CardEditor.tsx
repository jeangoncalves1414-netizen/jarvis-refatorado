import { FormEvent, useState } from 'react'

type Draft = { front: string; back: string }

export async function tutorPost(path: string, payload: unknown) {
  const response = await fetch('/api/tutor/' + path, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  })
  const data = await response.json()
  if (!response.ok) throw new Error(data.error || 'Falha ao salvar.')
  return data
}

export function CardEditor({ onSaved, session }: { onSaved: () => Promise<unknown>; session?: string }) {
  const [kind, setKind] = useState('basic')
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')
  async function perform(action: () => Promise<void>) {
    setBusy(true)
    setStatus('')
    try { await action() } catch (err) { setStatus(err instanceof Error ? err.message : 'Tente novamente.') }
    finally { setBusy(false) }
  }
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const payload = Object.fromEntries(new FormData(form))
    await perform(async () => {
      const data = await tutorPost('flashcards', payload)
      form.reset()
      setKind('basic')
      setStatus(data.ids.length + ' cartão(ões) salvo(s).')
      await onSaved()
    })
  }
  return <details><summary>{session ? 'Cartões desta aula' : 'Criar cartões'}</summary>
    {session ? <>
      <button disabled={busy} onClick={() => perform(async () => {
        setDrafts((await tutorPost('flashcards/suggest', { session_id: session })).cards)
      })}>Sugerir cartões da sessão</button>
      {drafts.map((card, index) => <div key={index}><strong>{card.front}</strong><p>{card.back}</p>
        <button disabled={busy} onClick={() => perform(async () => {
          await tutorPost('flashcards', card)
          setDrafts(current => current.filter((_, i) => i !== index))
          setStatus('Cartão salvo.')
          await onSaved()
        })}>Adicionar à revisão</button></div>)}
    </> : <form className="lang-add-form" onSubmit={create}>
      <label>Formato <select name="kind" value={kind} onChange={e => setKind(e.target.value)}>
        <option value="basic">Básico</option><option value="reversed">Básico e inverso</option><option value="cloze">Lacunas</option>
      </select></label>
      <textarea required maxLength={4000} name="front" aria-label="Frente" placeholder={kind === 'cloze' ? 'A mitocôndria é a {{c1::usina}} da célula.' : 'Pergunta'} />
      {kind !== 'cloze' && <textarea required maxLength={4000} name="back" placeholder="Resposta" aria-label="Verso" />}
      <input name="deck" maxLength={200} placeholder="Baralho (Matéria::Capítulo)" aria-label="Baralho" />
      <input name="tags" maxLength={500} placeholder="Tags separadas por vírgulas" aria-label="Tags" />
      <button disabled={busy}>Salvar cartões</button>
    </form>}
    <p role="status">{busy ? 'Aguarde…' : status}</p>
  </details>
}
