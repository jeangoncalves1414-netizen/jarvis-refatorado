import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Mic, PencilLine, Save, Square } from 'lucide-react'
import { useLiveDictation } from '../../hooks/useLiveDictation'
import { TypewriterText } from '../motion'
import { NOTE_FORMAT_LABELS, appendPhrase, reformatNote } from '../noteFormat'
import { DRAFT_PREFIX, DRAFTS_CHANGED, NOTES_CHANGED, readDraft, type Draft } from '../../utils/personalNotes'
import type { LiveNotesPopupData, NoteFormat, PopupComponentProps } from '../registry'

// Anotação ao vivo (decisões 11 e 12): a fala vira texto com efeito de digitação; Texto, Lista ou
// Checklist; salva no cofre (05-Notas) pelo Action Kernel ao parar o ditado, ao fechar e em
// "Salvar". Até o servidor confirmar, o rascunho fica em localStorage. Dá para escrever à mão.

type SaveState = { state: 'idle' | 'saving' | 'saved' | 'local' | 'error'; message: string }

const FORMATS: NoteFormat[] = ['text', 'bullets', 'checklist']

export function LiveNotesPopup({ popup, setHold }: PopupComponentProps<LiveNotesPopupData>) {
  const draftId = popup.data.draft_id
  const initial = useMemo<{ draft: Draft; restored: boolean }>(() => {
    const stored = readDraft(draftId)
    return stored
      ? { draft: stored, restored: true }
      : { draft: { title: popup.data.title, format: popup.data.format, content: popup.data.content }, restored: false }
    // O rascunho é lido só na abertura do popup.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draftId])
  const [title, setTitleState] = useState(initial.draft.title)
  const [format, setFormatState] = useState<NoteFormat>(initial.draft.format)
  const [content, setContentState] = useState(initial.draft.content)
  const [interim, setInterim] = useState('')
  const [editing, setEditing] = useState(true)
  const [typedFrom, setTypedFrom] = useState(0)
  const [save, setSave] = useState<SaveState>(initial.restored ? { state: 'local', message: 'Rascunho local recuperado (ainda não salvo no cofre).' } : { state: 'idle', message: '' })
  // Refs com o valor mais recente: a frase de parada salva logo depois da última fala.
  const draftRef = useRef<Draft>(initial.draft)
  const dirtyRef = useRef(initial.restored)
  const mounted = useRef(false)

  const persist = () => {
    try {
      localStorage.setItem(DRAFT_PREFIX + draftId, JSON.stringify({ ...draftRef.current, modified: Date.now() }))
      window.dispatchEvent(new Event(DRAFTS_CHANGED))
    } catch { /* armazenamento cheio */ }
  }
  const update = (patch: Partial<Draft>) => {
    draftRef.current = { ...draftRef.current, ...patch }
    dirtyRef.current = true
    persist()
    if (patch.title !== undefined) setTitleState(patch.title)
    if (patch.format !== undefined) setFormatState(patch.format)
    if (patch.content !== undefined) setContentState(patch.content)
    setSave(previous => previous.state === 'saving' ? previous : { state: 'local', message: 'Rascunho local (ainda não salvo no cofre).' })
  }

  const saveNow = useCallback(async (keepalive = false) => {
    const sent = draftRef.current
    if (!sent.content.trim()) return
    setSave({ state: 'saving', message: 'Salvando no cofre…' })
    try {
      const response = await fetch('/api/notes/live', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ draft_id: draftId, title: sent.title.trim() || 'Anotação', format: sent.format, content: sent.content }),
        keepalive,
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok || !data.ok) throw new Error(typeof data.error === 'string' && data.error ? data.error : `o servidor respondeu ${response.status}.`)
      // Só limpa o rascunho local se nada mudou enquanto salvava.
      const stored = readDraft(draftId)
      const sameContent = !stored || (stored.title === sent.title && stored.format === sent.format && stored.content === sent.content)
      if (draftRef.current === sent && sameContent) {
        dirtyRef.current = false
        try { localStorage.removeItem(DRAFT_PREFIX + draftId) } catch { /* ignore */ }
      }
      window.dispatchEvent(new Event(NOTES_CHANGED))
      setSave(dirtyRef.current ? { state: 'local', message: 'Há alterações no rascunho que ainda precisam ser salvas.' }
        : { state: 'saved', message: `Salvo no cofre${typeof data.path === 'string' ? ` (${data.path})` : ''}.` })
    } catch (error) {
      if (!readDraft(draftId) && mounted.current) persist()
      const reason = error instanceof Error && error.message && error.message !== 'Failed to fetch' ? error.message : 'o backend não respondeu.'
      setSave({ state: 'error', message: `Não foi possível salvar: ${reason} O rascunho continua guardado neste aparelho.` })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draftId])

  const dictation = useLiveDictation({
    onPhrase: text => update({ content: appendPhrase(draftRef.current.content, text, draftRef.current.format) }),
    onInterim: setInterim,
    onStopped: () => { setEditing(true); void saveNow() },
  })

  const startDictation = () => {
    setTypedFrom(draftRef.current.content.length)
    setEditing(false)
    void dictation.start()
  }
  const stopDictation = () => dictation.stop('user')

  // Ditado pedido pelo agente começa sozinho; pelo comando /nota, só quando a usuária clica.
  useEffect(() => {
    if (popup.data.dictate) startDictation()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draftId])

  // Sem motor de ditado: volta para a edição manual.
  useEffect(() => { if (dictation.engine === 'manual') setEditing(true) }, [dictation.engine])

  // Gravando, o popup nunca expira.
  useEffect(() => { setHold(dictation.active) }, [dictation.active, setHold])

  // Fechar o popup salva o que ainda não foi salvo.
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      // StrictMode remonta os efeitos imediatamente. Só salva ao fechar de fato.
      queueMicrotask(() => { if (!mounted.current && dirtyRef.current && draftRef.current.content.trim()) void saveNow(true) })
    }
  }, [saveNow])

  const changeFormat = (next: NoteFormat) => {
    if (next === draftRef.current.format) return
    update({ format: next, content: reformatNote(draftRef.current.content, draftRef.current.format, next) })
  }

  const showTypewriter = dictation.active && !editing
  return (
    <div className="ws-popup-notes" data-recording={dictation.active ? 'true' : 'false'}>
      <input
        className="ws-popup-notes-title"
        aria-label="Título da anotação"
        value={title}
        maxLength={80}
        onChange={event => update({ title: event.target.value })}
      />
      <div className="ws-popup-notes-formats" role="group" aria-label="Formato da anotação">
        {FORMATS.map(item => (
          <button key={item} type="button" className="ws-popup-chip" aria-pressed={format === item} onClick={() => changeFormat(item)}>
            {NOTE_FORMAT_LABELS[item]}
          </button>
        ))}
      </div>
      {showTypewriter
        ? (
          <div className="ws-popup-notes-live">
            {content || interim
              ? <TypewriterText committed={content} interim={interim} startAt={typedFrom} />
              : <p className="ws-popup-empty">Pode falar: cada frase entra na anotação.</p>}
            <button type="button" className="ws-popup-link" onClick={() => { stopDictation(); setEditing(true) }}>
              <PencilLine size={12} aria-hidden="true" /> Editar texto
            </button>
          </div>
        )
        : (
          <textarea
            className="ws-popup-notes-text"
            aria-label="Texto da anotação"
            value={content}
            maxLength={20_000}
            rows={6}
            placeholder={format === 'text' ? 'Escreva ou dite a anotação…' : 'Um item por linha…'}
            onChange={event => update({ content: event.target.value })}
          />
        )}
      {dictation.notice && <p className="ws-popup-notes-notice">{dictation.notice}</p>}
      <div className="ws-popup-notes-actions">
        {dictation.active
          ? <button type="button" className="ws-popup-action recording" aria-label="Parar ditado" onClick={stopDictation}><Square size={12} aria-hidden="true" /> Parar</button>
          : <button type="button" className="ws-popup-action" aria-label="Gravar ditado" onClick={startDictation}><Mic size={12} aria-hidden="true" /> Gravar</button>}
        <button type="button" className="ws-popup-action primary" aria-label="Salvar anotação" disabled={!content.trim() || save.state === 'saving'} onClick={() => void saveNow()}>
          <Save size={12} aria-hidden="true" /> Salvar
        </button>
        <span className={`ws-popup-notes-status ${save.state}`} role="status">{save.message}</span>
      </div>
    </div>
  )
}
