import type { ReactNode } from 'react'
import { useEffect, useRef } from 'react'
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
  headerExtra,
  hero,
  children,
  quickActions,
}: AppShellProps) {
  const parallaxRef = useRef<HTMLDivElement>(null)

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
      <main className="app-shell">
        <aside className={`sidebar ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
          <div className="brand">
            <JarvisOrb size={36} />
            {!sidebarCollapsed && <span>jarvis</span>}
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

        <section className="workspace">
          <header>
            <div>
              <p className="eyebrow">ASSISTENTE PESSOAL</p>
              <h1>{active}</h1>
            </div>
            <div className="header-tools">
              {headerExtra}
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
    </>
  )
}
