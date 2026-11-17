import { useEffect, useRef, useState, type ReactNode } from 'react'
import { ChevronDown, Command, Menu, PanelLeftClose, PanelLeftOpen, Trash2, Search, SlidersHorizontal, Sparkles, SquarePen, X } from 'lucide-react'
import { navigation } from '../navigation'
import type { ChatSession } from '../types'
import type { OperationalState } from '../hooks/useOperationalSnapshot'
import { confirmRemoval, LiberatedModeBadge } from './AutoApprovals'
import { WindowHost } from '../windows/WindowManager'

type AppShellProps = {
  active: string; sidebarCollapsed: boolean; onToggleSidebar: () => void; onNavigate: (id: string) => void
  sessions: ChatSession[]; sessionId: string; onSelectSession: (id: string) => void; onNewChat: () => void
  changeChatTrash?: (ids: string[], restore?: boolean) => Promise<string[]>; chatBusy?: boolean
  onOpenCommands: () => void; operational: OperationalState; controls: ReactNode
  hero?: ReactNode; children: ReactNode; quickActions: ReactNode
  openRun?: (id: string) => void
}

const build = __PANEL_BUILD__
const builtAt = new Date(build.builtAt)
const commitLabel = build.commit && `${build.commit}${build.dirty ? '*' : ''}`
const panelVersion = [`v${build.version}`, commitLabel, import.meta.env.DEV ? 'dev' : builtAt.toLocaleDateString('pt-BR')].filter(Boolean).join(' · ')
const panelVersionTitle = `Versão do painel ${build.version}${build.commit ? `, commit ${build.commit}${build.dirty ? ' com alterações não commitadas' : ''}` : ''}, ${import.meta.env.DEV ? 'servidor de desenvolvimento iniciado' : 'gerada'} em ${builtAt.toLocaleString('pt-BR')}`

  export function AppShell({ active, sidebarCollapsed, onToggleSidebar, onNavigate, sessions, sessionId, onSelectSession, onNewChat, changeChatTrash, chatBusy, onOpenCommands, operational, controls, hero, children, quickActions, openRun }: AppShellProps) {
    const [search, setSearch] = useState('')
    const [selected, setSelected] = useState<string[]>([])
    const [selecting, setSelecting] = useState(false)
    const [undoIds, setUndoIds] = useState<string[]>([])
    const [historyNotice, setHistoryNotice] = useState('')
    const [changing, setChanging] = useState(false)
    const changeHistory = async (ids: string[], restore = false) => {
      if (!changeChatTrash || changing || !ids.length) return
      setChanging(true)
      try {
        if (!restore && !await confirmRemoval(ids.length, `Mover ${ids.length} conversa(s) para a lixeira?`)) return
        const changed = await changeChatTrash(ids, restore)
        setUndoIds(restore ? [] : changed)
        setHistoryNotice(`${changed.length} conversa(s) ${restore ? 'restaurada(s)' : 'na lixeira'}.`)
        setSelected([]); setSelecting(false)
      } catch { setHistoryNotice('Não foi possível atualizar as conversas. Tente novamente.') }
      finally { setChanging(false) }
    }
    const [navHeight, setNavHeight] = useState(() => { const n = Number(localStorage.getItem('jarvis-nav-height')); return n >= 100 ? Math.min(500, n) : 250 })
    const resizeFrame = useRef(0)
    const pendingHeight = useRef(navHeight)
    const clampHeight = (height: number) => Math.max(100, Math.min(window.innerHeight - 350, height))
    const resizeNav = (height: number) => {
      const n = clampHeight(height)
      setNavHeight(n)
      localStorage.setItem('jarvis-nav-height', String(n))
    }
    useEffect(() => () => cancelAnimationFrame(resizeFrame.current), [])

    const [controlsOpen, setControlsOpen] = useState(true)
    const navDialog = useRef<HTMLDialogElement>(null)
    const controlDialog = useRef<HTMLDialogElement>(null)
    const route = navigation.find(item => item.id === active)
    const { snapshot, error } = operational
    const status = error ? 'offline' : snapshot ? 'connected' : 'unknown'
    const statusLabel = error ? 'Sem conexão com a central' : snapshot ? 'Central conectada' : 'Conectando à central'
    useEffect(() => { navDialog.current?.close(); controlDialog.current?.close() }, [active, sessionId])
    const navigate = (id: string) => { onNavigate(id); navDialog.current?.close(); controlDialog.current?.close() }
    const newChat = () => { onNewChat(); navDialog.current?.close() }
    const navButton = (item: typeof navigation[number]) => <button key={item.id} className={`ws-nav-item ${active === item.id ? 'selected' : ''}`} aria-current={active === item.id ? 'page' : undefined} title={item.label} onClick={() => navigate(item.id)}><item.icon size={17} /><span>{item.label}</span>{item.id === 'Central' && !!snapshot?.pending_actions.length && <small>{snapshot.pending_actions.length}</small>}</button>
    const sidebarContent = <>
      <div className="ws-brand"><span className="ws-brand-mark"><Sparkles size={19} /></span><strong>Workspace<span>Seu agente pessoal</span></strong><button className="ws-icon-button ws-desktop-toggle" aria-label={sidebarCollapsed ? 'Expandir navegação' : 'Recolher navegação'} onClick={onToggleSidebar}>{sidebarCollapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}</button><button className="ws-icon-button ws-mobile-close" aria-label="Fechar navegação" onClick={() => navDialog.current?.close()}><X size={19} /></button></div>
      <button className="ws-new-chat" onClick={newChat} aria-label="Nova conversa" title="Nova conversa"><SquarePen size={17} /><span>Nova conversa</span><small aria-hidden="true">＋</small></button>
      <button className="ws-command-search" onClick={() => { navDialog.current?.close(); onOpenCommands() }} title="Buscar comandos"><Search size={16} /><span>Buscar no workspace</span><kbd>Ctrl K</kbd></button>
      <div className="ws-nav-resizable" style={{ height: navHeight }}><nav aria-label="Navegação principal" className="ws-navigation">{navigation.filter(item => item.group === 'workspace').map(navButton)}</nav>
      <details className="ws-modules"><summary><span>Módulos pessoais</span><ChevronDown size={14} /></summary><nav aria-label="Módulos pessoais">{navigation.filter(item => item.group === 'modules').map(navButton)}</nav></details>
      </div>
      <div className="ws-nav-divider" role="separator" aria-label="Redimensionar navegação e conversas" aria-orientation="horizontal" aria-valuenow={navHeight} tabIndex={0} onKeyDown={e => { if (e.key === 'ArrowUp' || e.key === 'ArrowDown') { e.preventDefault(); resizeNav(navHeight + (e.key === 'ArrowUp' ? -20 : 20)) } }} onPointerDown={e => { pendingHeight.current = navHeight; e.currentTarget.setPointerCapture(e.pointerId); e.currentTarget.dataset.start = String(e.clientY - navHeight) }} onPointerMove={e => {
        if (!e.currentTarget.hasPointerCapture(e.pointerId)) return
        pendingHeight.current = clampHeight(e.clientY - Number(e.currentTarget.dataset.start))
        const divider = e.currentTarget
        if (!resizeFrame.current) resizeFrame.current = requestAnimationFrame(() => {
          resizeFrame.current = 0
          const nav = divider.previousElementSibling as HTMLElement
          nav.style.height = `${pendingHeight.current}px`
          divider.setAttribute('aria-valuenow', String(pendingHeight.current))
        })
      }} onLostPointerCapture={() => { cancelAnimationFrame(resizeFrame.current); resizeFrame.current = 0; resizeNav(pendingHeight.current) }} onPointerUp={e => { if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId) }} onPointerCancel={e => { if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId) }} />
      <div className="ws-history"><div className="ws-section-heading"><span>CONVERSAS RECENTES</span><span>{sessions.length}</span></div><label className="ws-history-search"><Search size={13} /><input aria-label="Buscar conversas" placeholder="Filtrar conversas…" value={search} onChange={event => setSearch(event.target.value)} /></label>{changeChatTrash && !!sessions.length && <div className="mem-actions">
        <button disabled={changing || chatBusy} onClick={() => { setSelecting(!selecting); setSelected([]) }}>{selecting ? 'Cancelar' : 'Selecionar'}</button>
        {selecting && <button disabled={changing || chatBusy || !selected.length} onClick={() => void changeHistory(selected)}>Excluir ({selected.length})</button>}
        <button disabled={changing || chatBusy} onClick={() => void changeHistory(sessions.map(s => s.id))}>Apagar todos</button>
      </div>}
      {historyNotice && <p role="status">{historyNotice} {!!undoIds.length && <button disabled={changing} onClick={() => void changeHistory(undoIds, true)}>Desfazer</button>}</p>}
      <div className="ws-chat-list">{sessions.filter(item => (item.title || 'Nova conversa').toLocaleLowerCase('pt-BR').includes(search.toLocaleLowerCase('pt-BR'))).map(item =>
        <div key={item.id} className="ws-chat-row">
          {selecting && <input type="checkbox" aria-label={`Selecionar ${item.title}`} checked={selected.includes(item.id)} onChange={e => setSelected(current => e.target.checked ? [...current, item.id] : current.filter(id => id !== item.id))} />}
          <button style={{ flex: 1, minWidth: 0 }} className={active === 'Chat' && item.id === sessionId ? 'selected' : ''} onClick={() => { onSelectSession(item.id); navigate('Chat') }} title={item.title || 'Nova conversa'}>{item.title || 'Nova conversa'}</button>
          {changeChatTrash && <button style={{ width: 'auto' }} aria-label={`Excluir ${item.title || 'conversa'}`} title="Mover para a lixeira" disabled={changing || chatBusy} onClick={() => void changeHistory([item.id])}><Trash2 size={14} /></button>}
        </div>)}{!sessions.length && <p>Suas conversas ficam aqui.</p>}</div></div>
      <div className="ws-sidebar-footer">{navigation.filter(item => item.group === 'settings').map(navButton)}<div className="ws-local-status" title={statusLabel}><span className={`ws-dot ${status}`} /><span>{statusLabel}</span><Command size={13} /></div><p className="ws-build-version" title={panelVersionTitle}>{panelVersion}</p></div>
    </>
    return <div className={`agent-workspace ${sidebarCollapsed ? 'nav-collapsed' : ''} ${controlsOpen ? 'controls-open' : ''}`}>
      <a className="ws-skip" href="#workspace-content">Ir para o conteúdo</a>
      <aside className="ws-sidebar">{sidebarContent}</aside>
      <dialog ref={navDialog} className="ws-drawer ws-nav-drawer" aria-label="Navegação" onClick={event => { if (event.target === event.currentTarget) navDialog.current?.close() }}><div className="ws-drawer-inner">{sidebarContent}</div></dialog>
      <main className="ws-main" id="workspace-content" tabIndex={-1}>
        <header className="ws-topbar"><div className="ws-topbar-title"><button className="ws-icon-button ws-mobile-menu" aria-label="Abrir navegação" onClick={() => navDialog.current?.showModal()}><Menu size={20} /></button><span className="ws-breadcrumb">Workspace <span>/</span></span><strong>{route?.label || active}</strong></div><div className="ws-topbar-actions"><LiberatedModeBadge /><span className={`ws-connection-label ${status}`}><i className={`ws-dot ${status}`} />{status === 'connected' ? 'Conectado' : status === 'offline' ? 'Desconectado' : 'Conectando'}</span><button className="ws-control-toggle" aria-label="Controle do agente" onClick={() => { if (window.innerWidth <= 1200) controlDialog.current?.showModal(); else setControlsOpen(value => !value) }}><SlidersHorizontal size={16} /><span>Controle do agente</span></button></div></header>
        <div className={`ws-page ${active === 'Chat' ? 'ws-page-chat' : ''}`}>{hero}{children}</div>
      </main>
      {controlsOpen && <aside className="ws-control-rail"><div className="ws-control-heading"><strong>Controle do agente</strong><button className="ws-icon-button" aria-label="Recolher controles" onClick={() => setControlsOpen(false)}><X size={16} /></button></div>{controls}<details className="ws-extra-tools"><summary>Mais ferramentas</summary>{quickActions}</details></aside>}
      <dialog ref={controlDialog} className="ws-drawer ws-control-drawer" aria-label="Controle do agente" onClick={event => { if (event.target === event.currentTarget) controlDialog.current?.close() }}><div className="ws-drawer-inner"><div className="ws-control-heading"><strong>Controle do agente</strong><button className="ws-icon-button" aria-label="Fechar controles" onClick={() => controlDialog.current?.close()}><X size={18} /></button></div>{controls}<details className="ws-extra-tools"><summary>Mais ferramentas</summary>{quickActions}</details></div></dialog>
      <WindowHost operational={operational} openRun={openRun} />
    </div>
  }
