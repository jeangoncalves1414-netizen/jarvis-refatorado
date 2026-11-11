import type { NoteFormat } from '../popups/registry'

export const NOTES_CHANGED = 'jarvis:notes-changed'
export const DRAFTS_CHANGED = 'jarvis:note-drafts-changed'
export const OPEN_NOTE = 'jarvis:open-personal-note'
export const DRAFT_PREFIX = 'lifeos_live_note_'
export const NOTEBOOK = 'lifeos_infinite_notes'
export type Draft = { title: string; format: NoteFormat; content: string; modified?: number }
export type VaultNote = { path: string; title: string; modified: number }
export type NoteTarget = { title: string; path: string } | { title: string; content: string }

export function openPersonalNote(target: NoteTarget) {
  window.dispatchEvent(new CustomEvent(OPEN_NOTE, { detail: target }))
}

export function readDraft(draftId: string): Draft | null {
  try {
    const raw = JSON.parse(localStorage.getItem(DRAFT_PREFIX + draftId) || 'null')
    if (!raw || typeof raw.content !== 'string' || typeof raw.title !== 'string' || !['text', 'bullets', 'checklist'].includes(raw.format)) return null
    return { title: raw.title.slice(0, 80), format: raw.format, content: raw.content.slice(0, 20_000), modified: Number(raw.modified) || 0 }
  } catch {
    return null
  }
}

export function readLocalNotes() {
  const drafts: { id: string; draft: Draft }[] = []
  let notebook = '', modified = 0
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (!key?.startsWith(DRAFT_PREFIX)) continue
      const id = key.slice(DRAFT_PREFIX.length)
      if (!/^[a-z0-9]{8,32}$/.test(id)) continue
      const draft = readDraft(id)
      if (draft?.content.trim()) drafts.push({ id, draft })
    }
    const raw = localStorage.getItem(NOTEBOOK) || ''
    try {
      const value = JSON.parse(raw)
      if (typeof value === 'string') notebook = value
    } catch {
      notebook = raw
    }
    modified = Number(localStorage.getItem(NOTEBOOK + '_modified')) || 0
  } catch { /* Armazenamento indisponível. O cofre permanece acessível. */ }
  return { drafts, notebook, modified }
}
