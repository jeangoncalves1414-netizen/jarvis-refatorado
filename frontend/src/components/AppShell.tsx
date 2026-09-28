import type { ReactNode } from 'react'
import { useEffect, useRef, useState } from 'react'
import { AnimatedDock } from './AnimatedDock'
import { BackgroundPattern } from './BackgroundPattern'
import { JarvisOrb } from './JarvisOrb'
import { TransitionPanel } from './TransitionPanel'

export type NavItem = {
  id: string
  icon: string
}

type AppShellProps = {
  active: string
  navItems: NavItem[]
  sidebarCollapsed: boolean
  onToggleSidebar: () => void
  onNavigate: (id: string) => void
  onOpenQuestLog?: () => void
  onOpenToolForge?: () => void
  activeQuestsCount?: number
  headerExtra?: ReactNode
  hero?: ReactNode
  children: ReactNode
  quickActions: ReactNode
}

export function AppShell({
  active,
  navItems,
  sidebarCollapsed,
  onToggleSidebar,
  onNavigate,
  onOpenQuestLog,
  onOpenToolForge,
  activeQuestsCount = 0,
  headerExtra,
  hero,
  children,
  quickActions,
}: AppShellProps) {
  const parallaxRef = useRef<HTMLDivElement>(null)
  const [pingMs, setPingMs] = useState<number | null>(null)
  const [isOnline, setIsOnline] = useState(true)

  useEffect(() => {
    if (typeof window !== 'undefined' && (window.location.hostname === 'appassets.androidplatform.net' || window.location.protocol === 'file:')) {
      setIsOnline(true)
      setPingMs(0)
      return
    }
    let mounted = true
    const checkPing = async () => {
      const start = performance.now()
      try {
        const res = await fetch('/api/evolute/status', { method: 'GET' })
        if (!mounted) return
        const duration = Math.round(performance.now() - start)
        if (res.ok) {
          setPingMs(duration)
          setIsOnline(true)
        } else {
          setIsOnline(false)
        }
      } catch {
        if (mounted) setIsOnline(false)
      }
    }

    checkPing()
    const interval = setInterval(checkPing, 25000)
    return () => {
      mounted = false
      clearInterval(interval)
    }
  }, [])

  useEffect(() => {
    const handleScroll = () => {
      const scrollY = window.scrollY
      if (parallaxRef.current) {
        parallaxRef.current.style.transform = `translateY(${scrollY * 0.3}px)`
      }
    }

    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  return (
    <>
      <BackgroundPattern variant="grid" mask="fade-edges" parallax ref={parallaxRef} />
      <div className="app-bg-pattern" aria-hidden="true">
        <BackgroundPattern variant="dots" mask="fade-center" />
      </div>
      <main className={`app-shell ${active === 'Chat' ? 'app-shell-chat' : ''} ${active === 'Evolução' ? 'app-shell-evolute' : ''}`}>
        <aside className={`sidebar ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
          <div className="brand">
            <JarvisOrb size={36} use3D={typeof window === 'undefined' || window.innerWidth > 768} />
            {!sidebarCollapsed && <span>Jarvis</span>}
            <button
              className="sidebar-toggle-btn"
              onClick={onToggleSidebar}
              title={sidebarCollapsed ? 'Expandir menu' : 'Recolher menu'}
            >
              {sidebarCollapsed ? '»' : '«'}
            </button>
          </div>

          <nav className="sidebar-nav">
            {navItems.map(item => (
              <button
                className={active === item.id ? 'nav-active' : ''}
                key={item.id}
                onClick={() => onNavigate(item.id)}
                title={sidebarCollapsed ? item.id : undefined}
              >
                <span className="nav-icon">{item.icon}</span>
                {!sidebarCollapsed && item.id}
              </button>
            ))}
          </nav>

          <div className="sidebar-quick">
            <p className="sidebar-section-label">AÇÕES RÁPIDAS</p>
            {quickActions}
          </div>

          <div className="sidebar-bottom">
            <p>SISTEMA LOCAL</p>
            <strong><b /> ONLINE</strong>
          </div>
        </aside>

        <section className={`workspace ${active === 'Chat' ? 'workspace-chat' : ''} ${active === 'Evolução' ? 'workspace-evolute' : ''}`}>
          <header>
            <div>
              <p className="eyebrow">ASSISTENTE PESSOAL</p>
              <h1>{active}</h1>
            </div>
            <div className="header-tools">
              <div className="header-ping-badge" title={isOnline ? `Conexão Local: ${pingMs}ms` : 'Servidor Offline'}>
                <span className={`ping-dot ${isOnline ? (pingMs && pingMs < 150 ? 'online' : 'slow') : 'offline'}`} />
                <span className="ping-text">{isOnline ? `${pingMs ?? '—'}ms` : 'Offline'}</span>
              </div>
              {headerExtra}
              {onOpenQuestLog && activeQuestsCount > 0 && (
                <button className="quest-log-trigger-btn" onClick={onOpenQuestLog} title="Abrir Quests & Processos">
                  📜 Quests <span className="quest-count-badge">{activeQuestsCount}</span>
                </button>
              )}
              <div className="profile">M</div>
            </div>
          </header>
          {hero}
          <TransitionPanel activeKey={active}>{children}</TransitionPanel>
        </section>
      </main>

      <AnimatedDock
        items={navItems.map(item => ({
          id: item.id,
          label: item.id,
          icon: item.icon,
          active: active === item.id,
          onClick: () => onNavigate(item.id),
        }))}
      />

      {/* Dedicated Mobile Bottom Navbar for Moto E20 / Smartphones */}
      <nav className="mobile-bottom-nav">
        {[
          { id: 'Chat', icon: '✦', label: 'Chat' },
          { id: 'Dashboard', icon: '◈', label: 'Início' },
          { id: 'Estudos', icon: '◎', label: 'Estudos' },
          { id: 'Evolução', icon: '⚡', label: 'Evoluir' },
          { id: 'Memórias', icon: '◇', label: 'Memórias' },
          { id: 'Configurações', icon: '⚙', label: 'Config' },
        ].map(tab => (
          <button
            key={tab.id}
            type="button"
            onClick={() => onNavigate(tab.id)}
            className={`mobile-nav-item ${active === tab.id ? 'active' : ''}`}
          >
            <span>{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </nav>
    </>
  )
}
