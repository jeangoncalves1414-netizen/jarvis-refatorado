import type { NoteFormat } from './registry'

// Formatos da anotação ao vivo (decisão 11): Texto (frases unidas), Lista ("- item" por fala) e
// Checklist ("- [ ] item" por fala). Trocar o formato reformata o conteúdo inteiro.

const LINE_PREFIX = /^\s*(?:-\s\[[ xX]\]\s*|[-*•]\s+)/

export const NOTE_FORMAT_LABELS: Record<NoteFormat, string> = { text: 'Texto', bullets: 'Lista', checklist: 'Checklist' }

export function noteItems(content: string, format: NoteFormat): string[] {
  if (format === 'text') return content.split(/(?<=[.!?])\s+|\n+/).map(item => item.trim()).filter(Boolean)
  return content.split('\n').map(line => line.replace(LINE_PREFIX, '').trim()).filter(Boolean)
}

function asSentence(text: string) {
  const clean = text.trim()
  if (!clean) return ''
  const capital = clean.charAt(0).toUpperCase() + clean.slice(1)
  return /[.!?…]$/.test(capital) ? capital : `${capital}.`
}

export function formatItems(items: string[], format: NoteFormat): string {
  if (format === 'text') return items.map(asSentence).filter(Boolean).join(' ')
  const prefix = format === 'checklist' ? '- [ ] ' : '- '
  return items.map(item => `${prefix}${item}`).join('\n')
}

export function reformatNote(content: string, from: NoteFormat, to: NoteFormat) {
  if (from === to) return content
  return formatItems(noteItems(content, from), to)
}

/** Acrescenta uma fala ao fim da nota no formato atual. */
export function appendPhrase(content: string, phrase: string, format: NoteFormat) {
  const clean = phrase.trim()
  if (!clean) return content
  const base = content.replace(/\s+$/, '')
  if (format === 'text') {
    const sentence = asSentence(clean)
    return base ? `${base} ${sentence}` : sentence
  }
  const line = formatItems([clean], format)
  return base ? `${base}\n${line}` : line
}
