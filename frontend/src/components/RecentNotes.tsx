import { useEffect, useMemo, useRef, useState } from 'react'
import { NotebookPen, X } from 'lucide-react'
import { usePopups } from '../popups/PopupProvider'
import { panelRequest } from '../utils/panelApi'
import {
  DRAFT_PREFIX, DRAFTS_CHANGED, NOTEBOOK, NOTES_CHANGED, OPEN_NOTE,
  openPersonalNote, readLocalNotes, type Draft, type NoteTarget, type VaultNote,
} from '../utils/personalNotes'
import './recentNotes.css'

type Saved = { id: string; title: string; timestamp: number }
type Row = { id: string; title: string; destination: string; modified: number; draft?: Draft; target?: NoteTarget }
const folders: Record<string, string> = {
  '05-Notas': 'Cofre', '01-Daily-Notes': 'Diário', '03-Priming-Notes': 'Cofre · contexto', '04-Projects': 'Cofre · projetos',
}

export function RecentNotes({ onRecentSaved }: { onRecentSaved?: (items: Saved[]) => void } = {}) {
  const { show } = usePopups()
  const [local, setLocal] = useState(readLocalNotes)
  const [vault, setVault] = useState<VaultNote[]>([])
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [expanded, setExpanded] = useState(false)
  const [refresh, setRefresh] = useState(0)
  const savedCallback = useRef(onRecentSaved)
  savedCallback.current = onRecentSaved

  useEffect(() => {
    const controller = new AbortController()
    panelRequest<{ notes: VaultNote[] }>('/api/notes/recent', { signal: controller.signal })
      .then(data => {
        if (!Array.isArray(data.notes)) throw new Error('Resposta inválida')
        if (!controller.signal.aborted) { setVault(data.notes); setStatus('ready') }
      })
      .catch(() => { if (!controller.signal.aborted) setStatus('error') })
    return () => controller.abort()
  }, [refresh])

  useEffect(() => {
    const loadLocal = () => setLocal(readLocalNotes())
    const loadAll = () => { loadLocal(); setRefresh(n => n + 1) }
    const storageChanged = (event: StorageEvent) => {
      if (!event.key || event.key.startsWith(DRAFT_PREFIX) || event.key.startsWith(NOTEBOOK)) loadLocal()
    }
    window.addEventListener('storage', storageChanged)
    window.addEventListener('focus', loadAll)
    window.addEventListener('jarvis-sync-applied', loadAll)
    window.addEventListener(DRAFTS_CHANGED, loadLocal)
    window.addEventListener(NOTES_CHANGED, loadAll)
    return () => {
      window.removeEventListener('storage', storageChanged)
      window.removeEventListener('focus', loadAll)
      window.removeEventListener('jarvis-sync-applied', loadAll)
      window.removeEventListener(DRAFTS_CHANGED, loadLocal)
      window.removeEventListener(NOTES_CHANGED, loadAll)
    }
  }, [])

  const rows = useMemo(() => {
    const items: Row[] = vault.map(note => ({
      id: note.path, title: note.title, destination: folders[note.path.split('/')[0]] || 'Cofre',
      modified: note.modified, target: { title: note.title, path: note.path },
    }))
    if (local.notebook.trim()) {
      // A nota rápida acrescenta blocos com hora. O leitor preserva o caderno original inteiro.
      const entries = local.notebook.split(/^• \[\d{2}:\d{2}\] /m)
      const title = entries[entries.length - 1].trim().split('\n')[0]?.slice(0, 100) || 'Nota rápida'
      items.push({ id: NOTEBOOK, title, destination: 'Caderno Infinito', modified: local.modified, target: { title: 'Caderno Infinito', content: local.notebook } })
    }
    for (const { id, draft } of local.drafts) {
      items.push({ id, title: draft.title || 'Sem título', destination: 'Rascunho neste aparelho', modified: draft.modified || 0, draft })
    }
    return items.sort((a, b) => b.modified - a.modified)
  }, [local, vault])

  useEffect(() => {
    savedCallback.current?.(rows.filter(row => !row.draft && row.modified > 0).map(row => ({
      id: row.id, title: row.title, timestamp: row.modified / 1000,
    })))
  }, [rows])

  function openRow(row: Row) {
    if (row.target) openPersonalNote(row.target)
    if (row.draft) show({
      id: 'pop_' + Array.from(crypto.getRandomValues(new Uint32Array(3)), value => value.toString(16)).join(''), key: 'notes:' + row.id,
      template: 'live_notes', version: 1, title: 'Anotação ao vivo', origin: 'command', created_at: Date.now() / 1000,
      ttl_ms: 0, pinned: false, animate: {}, data: { ...row.draft, draft_id: row.id, dictate: false },
    })
  }

  return (
    <section className="recent-personal-notes" aria-label="Últimas anotações">
      <h3><NotebookPen size={15} aria-hidden="true" />Últimas anotações</h3>
      {(expanded ? rows : rows.slice(0, 1)).map(row => (
        <div className="recent-note-row" key={row.id}>
          <div><strong title={row.title}>{row.title}</strong><small>{row.destination}</small></div>
          <button type="button" onClick={() => openRow(row)}>{row.draft ? 'Retomar' : 'Abrir'}</button>
        </div>
      ))}
      {!rows.length && status !== 'error' && <p>{status === 'loading' ? 'Consultando o cofre…' : 'Nenhuma anotação ainda.'}</p>}
      {status === 'error' && <p role="status">Cofre indisponível. <button type="button" onClick={() => setRefresh(n => n + 1)}>Tentar de novo</button></p>}
      {rows.length > 1 && <button type="button" aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>{expanded ? 'Recolher' : `Ver mais (${rows.length - 1})`}</button>}
    </section>
  )
}

export function NoteViewer() {
  const [note, setNote] = useState<NoteTarget | null>(null)
  const [content, setContent] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const open = (event: Event) => {
      const target = (event as CustomEvent<NoteTarget>).detail
      if (!target) return
      setContent('content' in target ? target.content : '')
      setLoading('path' in target)
      setError('')
      setNote(target)
    }
    window.addEventListener(OPEN_NOTE, open)
    return () => window.removeEventListener(OPEN_NOTE, open)
  }, [])
  useEffect(() => {
    if (!note) return
    if (!dialog.current?.open) dialog.current?.showModal()
    if (!('path' in note)) return
    const controller = new AbortController()
    panelRequest<{ content: string }>(`/api/notes/read?path=${encodeURIComponent(note.path)}`, { signal: controller.signal })
      .then(data => {
        if (typeof data.content !== 'string') throw new Error('O cofre retornou uma resposta inválida.')
        if (!controller.signal.aborted) setContent(data.content)
      })
      .catch((err: Error) => { if (!controller.signal.aborted) setError(err.message) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [note])
  if (!note) return null
  return (
    <dialog className="personal-note-reader" ref={dialog} aria-labelledby="personal-note-title" onClose={() => setNote(null)}>
      <header><h2 id="personal-note-title">{note.title}</h2><button type="button" aria-label="Fechar anotação" onClick={() => dialog.current?.close()}><X size={18} /></button></header>
      {loading ? <p role="status">Abrindo…</p> : error ? <p role="alert">{error}</p> : <pre>{content}</pre>}
    </dialog>
  )
}
