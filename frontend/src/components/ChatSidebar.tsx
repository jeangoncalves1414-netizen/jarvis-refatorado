import { useState, useEffect } from 'react'

type ChatSidebarProps = {
  children: React.ReactNode
}

const SIDEBAR_STORAGE_KEY = 'jarvis-chat-sidebar-open'

export function ChatSidebar({ children }: ChatSidebarProps) {
  const [isOpen, setIsOpen] = useState(() => {
    try {
      const stored = localStorage.getItem(SIDEBAR_STORAGE_KEY)
      if (stored !== null) return JSON.parse(stored)
    } catch {
      // localStorage failed, try sessionStorage
      try {
        const sessionStored = sessionStorage.getItem(SIDEBAR_STORAGE_KEY)
        return sessionStored !== null ? JSON.parse(sessionStored) : true
      } catch {
        return true
      }
    }
    return true
  })

  useEffect(() => {
    try {
      localStorage.setItem(SIDEBAR_STORAGE_KEY, JSON.stringify(isOpen))
    } catch {
      // localStorage failed, try sessionStorage
      try {
        sessionStorage.setItem(SIDEBAR_STORAGE_KEY, JSON.stringify(isOpen))
      } catch {
        // Both failed, state will reset on reload
      }
    }
  }, [isOpen])

  return (
    <div className={`chat-sidebar-container ${isOpen ? 'sidebar-open' : 'sidebar-closed'}`}>
      <button
        className="chat-sidebar-toggle"
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        aria-label={isOpen ? 'Ocultar histórico' : 'Mostrar histórico'}
      >
        {isOpen ? '◀' : '▶'}
      </button>
      {isOpen && <div className="chat-sidebar-content">{children}</div>}
    </div>
  )
}
