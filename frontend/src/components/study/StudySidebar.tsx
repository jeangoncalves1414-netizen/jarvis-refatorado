import { useMemo, useState } from 'react'
import type { ChatSession, StudyCategory } from '../../types'
import { StudyDialog } from './StudyDialog'

type StudySidebarProps = {
  sessions: ChatSession[]
  categories: StudyCategory[]
  trashedSessions: ChatSession[]
  activeSessionId: string
  onSelectSession: (id: string) => void
  onNewSession: () => void
  onRenameSession: (id: string, title: string) => void
  onDeleteSession: (id: string) => void
  onRestoreSession: (id: string) => void
  onPurgeSession: (id: string) => void
  onCreateCategory: (name: string, color: string) => Promise<StudyCategory | null>
  onAssignCategory: (id: string, categoryId?: string) => void
  progressLabel: string
  weakSpots?: string[]
  dueCards: number
  enemCount: number
}

export function StudySidebar({ sessions, categories, trashedSessions, activeSessionId, onSelectSession, onNewSession, onRenameSession, onDeleteSession, onRestoreSession, onPurgeSession, onCreateCategory, onAssignCategory, progressLabel, weakSpots, dueCards, enemCount }: StudySidebarProps) {
  const grouped = useMemo(() => categories.map(category => ({ category, sessions: sessions.filter(session => session.category_id === category.id) })), [categories, sessions])
  const uncategorized = sessions.filter(session => !session.category_id)
  const [dialog, setDialog] = useState<{ kind: 'rename' | 'category' | 'delete' | 'purge'; session?: ChatSession } | null>(null)
  const [trashOpen, setTrashOpen] = useState(false)
  const [dragOverCategory, setDragOverCategory] = useState('')

  const submitDialog = async (value: string, color?: string) => {
    if (!dialog) return
    if (dialog.kind === 'rename' && dialog.session) onRenameSession(dialog.session.id, value)
    if (dialog.kind === 'category') await onCreateCategory(value, color || '#00daf8')
    if (dialog.kind === 'delete' && dialog.session) onDeleteSession(dialog.session.id)
    if (dialog.kind === 'purge' && dialog.session) onPurgeSession(dialog.session.id)
    setDialog(null)
  }

  const renderSession = (session: ChatSession) => (
    <div key={session.id} className={`study-session-row${session.id === activeSessionId ? ' study-session-row-active' : ''}`} draggable onDragStart={event => { event.dataTransfer.setData('text/study-session', session.id); event.dataTransfer.effectAllowed = 'move' }}>
      <button type="button" className="study-session-select" onClick={() => onSelectSession(session.id)} title={session.title || 'Sessão de estudos'}><span className="study-session-dot" /><span>{session.title || 'Sessão de estudos'}</span></button>
      <select aria-label="Categoria da sessão" value={session.category_id || ''} onChange={event => onAssignCategory(session.id, event.target.value || undefined)}><option value="">·</option>{categories.map(category => <option key={category.id} value={category.id}>{category.name}</option>)}</select>
      <button type="button" className="study-session-action" onClick={() => setDialog({ kind: 'rename', session })} title="Renomear">✎</button>
      <button type="button" className="study-session-action danger" onClick={() => setDialog({ kind: 'delete', session })} title="Mover para a lixeira">×</button>
    </div>
  )

  const renderCategory = (category: StudyCategory, categorySessions: ChatSession[]) => <div className={`study-session-group${dragOverCategory === category.id ? ' study-category-drag-over' : ''}`} key={category.id} onDragOver={event => { event.preventDefault(); setDragOverCategory(category.id) }} onDragLeave={() => setDragOverCategory('')} onDrop={event => { event.preventDefault(); const id = event.dataTransfer.getData('text/study-session'); if (id) onAssignCategory(id, category.id); setDragOverCategory('') }}>
    <div className="study-category-label"><span style={{ backgroundColor: category.color }} />{category.name}<small>{categorySessions.length}</small></div>
    {categorySessions.map(renderSession)}
  </div>

  return <aside className="study-sidebar">
    <div className="study-sidebar-header"><div><p className="eyebrow">CENTRO DE ESTUDOS</p><h3 className="study-sidebar-title">Seu espaço</h3></div><button type="button" className="outline-button study-new-btn" onClick={onNewSession}>+ Nova sessão</button></div>
    <p className="study-progress-label">{progressLabel}</p><div className="study-sidebar-stats"><span><b>{dueCards}</b> cards</span><span><b>{enemCount}</b> ENEM</span></div><p className="weak-spots">{weakSpots?.length ? `Revisar: ${weakSpots.join(' · ')}` : 'Continue estudando para identificar pontos fracos.'}</p>
    <div className="study-category-heading"><p className="sidebar-section-label">SESSÕES</p><button type="button" onClick={() => setDialog({ kind: 'category' })}>+ categoria</button></div>
    <div className="study-session-list">{grouped.map(({ category, sessions: categorySessions }) => renderCategory(category, categorySessions))}{uncategorized.map(renderSession)}{!sessions.length && <p className="empty-state">Nenhuma sessão de estudo.</p>}</div>
    <button type="button" className="study-trash-toggle" onClick={() => setTrashOpen(value => !value)}>♜ Lixeira <b>{trashedSessions.length}</b></button>
    {trashOpen && <div className="study-trash-panel"><p>SESSÕES REMOVIDAS</p>{trashedSessions.length ? trashedSessions.map(session => <div className="study-trash-row" key={session.id}><span title={session.title}>{session.title || 'Sessão'}</span><button type="button" onClick={() => onRestoreSession(session.id)} title="Restaurar">↶</button><button type="button" className="danger" onClick={() => setDialog({ kind: 'purge', session })} title="Apagar permanentemente">×</button></div>) : <small>A lixeira está vazia.</small>}</div>}
    <StudyDialog open={Boolean(dialog)} kind={dialog?.kind === 'category' ? 'category' : dialog?.kind === 'rename' ? 'text' : 'confirm'} title={dialog?.kind === 'category' ? 'Nova categoria' : dialog?.kind === 'rename' ? 'Renomear sessão' : dialog?.kind === 'purge' ? 'Apagar permanentemente?' : 'Mover para a lixeira?'} description={dialog?.kind === 'category' ? 'Escolha um nome e uma cor para organizar seu espaço.' : dialog?.kind === 'rename' ? 'Dê um nome claro para encontrar esta sessão depois.' : dialog?.kind === 'purge' ? 'Essa ação não pode ser desfeita.' : 'A sessão poderá ser restaurada pela lixeira.'} initialValue={dialog?.session?.title || ''} confirmLabel={dialog?.kind === 'category' ? 'Criar categoria' : dialog?.kind === 'rename' ? 'Salvar nome' : dialog?.kind === 'purge' ? 'Apagar' : 'Mover'} onClose={() => setDialog(null)} onSubmit={submitDialog} />
  </aside>
}
