import { navigation } from '../navigation'
import React, { useEffect, useMemo, useRef, useState } from 'react'
import {
  Search,
  MessageSquare,
  Zap,
  Droplets,
  Volume2,
  VolumeX,
  Film,
  Eye,
  Camera,
  CornerDownLeft,
  Download,
  Flame,
} from 'lucide-react'
import { playClick, playSuccess, playOpen, playToggle, toggleSfx, isSfxEnabled } from '../utils/sfx'

export type CommandItem = {
  id: string
  title: string
  subtitle?: string
  icon: React.ReactNode
  category: 'Navegação' | 'Ações Rápidas' | 'Life OS' | 'Mídia & Ferramentas' | 'Sistema'
  action: () => void
  shortcut?: string
}

type CommandPaletteProps = {
  isOpen: boolean
  onClose: () => void
  onNavigate: (screen: string) => void
  onOpenEvolute?: () => void
  onNewChat?: () => void
  onAddWater?: (ml: number) => void
  onTriggerBriefing?: () => void
  onOpenCinema?: () => void
  onCaptureVision?: () => void
  onOpenCameras?: () => void
  onTriggerBackup?: () => void
}

export function CommandPalette({
  isOpen,
  onClose,
  onNavigate,
  onOpenEvolute,
  onNewChat,
  onAddWater,
  onTriggerBriefing,
  onOpenCinema,
  onCaptureVision,
  onOpenCameras,
  onTriggerBackup,
}: CommandPaletteProps) {
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const dialogRef = useRef<HTMLDialogElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  const items: CommandItem[] = useMemo(() => [
    ...navigation.map(item => ({
      id: `nav-${item.id}`,
      title: `Abrir ${item.label}`,
      subtitle: item.description,
      icon: <item.icon size={16} />,
      category: 'Navegação' as const,
      action: () => { onNavigate(item.id); onClose() },
    })),

    // Life OS
    {
      id: 'lifeos-open',
      title: 'Abrir Painel de Evolução (Life OS)',
      subtitle: 'Janela dedicada de hábitos, treinos e rotina',
      icon: <Zap size={16} />,
      category: 'Life OS',
      action: () => { onOpenEvolute?.(); onClose() },
    },
    {
      id: 'lifeos-vice',
      title: 'Ver Blindagem & Foco (Anti-Vício)',
      subtitle: 'Acompanhar dias limpos e metas de sobriedade',
      icon: <Flame size={16} color="#f97316" />,
      category: 'Life OS',
      action: () => { onOpenEvolute?.(); onClose() },
    },
    {
      id: 'lifeos-water',
      title: 'Registrar +250ml de Água',
      subtitle: 'Computar copo de água na meta diária',
      icon: <Droplets size={16} />,
      category: 'Life OS',
      action: () => { onAddWater?.(250); onClose() },
    },

    // Ações Rápidas
    {
      id: 'action-new-chat',
      title: 'Nova Conversa',
      subtitle: 'Iniciar um diálogo limpo no chat',
      icon: <MessageSquare size={16} />,
      category: 'Ações Rápidas',
      action: () => { onNewChat?.(); onNavigate('Chat'); onClose() },
    },
    {
      id: 'action-briefing',
      title: 'Disparar Briefing Matinal',
      subtitle: 'Ouvir o resumo falado do dia pelo Jarvis',
      icon: <Volume2 size={16} />,
      category: 'Ações Rápidas',
      action: () => { onTriggerBriefing?.(); onClose() },
    },

    // Sistema
    {
      id: 'system-backup',
      title: 'Exportar Backup Completo (ZIP)',
      subtitle: 'Baixar memórias, bancos de hábitos e configurações',
      icon: <Download size={16} />,
      category: 'Sistema',
      action: () => {
        if (onTriggerBackup) {
          onTriggerBackup()
        } else {
          window.location.href = '/api/system/backup'
        }
        onClose()
      },
    },
    {
      id: 'system-sfx-toggle',
      title: isSfxEnabled() ? 'Silenciar Sons Táticos (Mudo)' : 'Ativar Sons Táticos (SFX)',
      subtitle: 'Feedback auditivo procedural da interface',
      icon: isSfxEnabled() ? <VolumeX size={16} /> : <Volume2 size={16} />,
      category: 'Sistema',
      action: () => {
        playToggle()
        toggleSfx()
        onClose()
      },
    },

    // Mídia & Ferramentas
    {
      id: 'tool-cinema',
      title: 'Abrir Cinema & Mídia',
      subtitle: 'Catálogo de filmes e player integrado',
      icon: <Film size={16} />,
      category: 'Mídia & Ferramentas',
      action: () => { onOpenCinema?.(); onClose() },
    },
    {
      id: 'tool-vision',
      title: 'Analisar Tela Atual (Visão)',
      subtitle: 'Captura o monitor e analisa via IA',
      icon: <Eye size={16} />,
      category: 'Mídia & Ferramentas',
      action: () => { onCaptureVision?.(); onClose() },
    },
    {
      id: 'tool-cameras',
      title: 'Abrir Painel de Câmeras',
      subtitle: 'Monitoramento de vídeo e streams',
      icon: <Camera size={16} />,
      category: 'Mídia & Ferramentas',
      action: () => { onOpenCameras?.(); onClose() },
    },
  ], [onNavigate, onOpenEvolute, onNewChat, onAddWater, onTriggerBriefing, onOpenCinema, onCaptureVision, onOpenCameras, onTriggerBackup, onClose])

  const filteredItems = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return items
    return items.filter(
      item =>
        item.title.toLowerCase().includes(q) ||
        (item.subtitle && item.subtitle.toLowerCase().includes(q)) ||
        item.category.toLowerCase().includes(q)
    )
  }, [items, query])

  // Reset selected index when query changes
  useEffect(() => {
    setSelectedIndex(0)
  }, [query])

  // Focus input and play open sound when opened
  useEffect(() => {
    if (isOpen) {
      dialogRef.current?.showModal()
      playOpen()
      setQuery('')
      setSelectedIndex(0)
      inputRef.current?.focus()
    } else {
      dialogRef.current?.close()
    }
  }, [isOpen])

  // Keyboard navigation
  useEffect(() => {
    if (!isOpen) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      } else if (e.key === 'ArrowDown') {
        e.preventDefault()
        playClick()
        setSelectedIndex(prev => (prev < filteredItems.length - 1 ? prev + 1 : 0))
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        playClick()
        setSelectedIndex(prev => (prev > 0 ? prev - 1 : filteredItems.length - 1))
      } else if (e.key === 'Enter') {
        e.preventDefault()
        if (filteredItems[selectedIndex]) {
          playSuccess()
          filteredItems[selectedIndex].action()
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, filteredItems, selectedIndex, onClose])

  // Scroll selected item into view
  useEffect(() => {
    if (!listRef.current) return
    const selectedEl = listRef.current.querySelector<HTMLElement>(`[data-cmd-index="${selectedIndex}"]`)
    if (selectedEl) {
      selectedEl.scrollIntoView({ block: 'nearest' })
    }
  }, [selectedIndex])

  return (
    <dialog ref={dialogRef} className="cmd-palette-backdrop ws-command-dialog" aria-label="Buscar no workspace" onCancel={event => { event.preventDefault(); onClose() }} onClick={onClose}>
      <div className="cmd-palette-container" onClick={e => e.stopPropagation()}>
        {/* Search Header */}
        <div className="cmd-palette-header">
          <Search size={18} className="cmd-search-icon" />
          <input
            ref={inputRef}
            type="text"
            className="cmd-palette-input"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Buscar páginas e ações…"
          />
          <button type="button" className="cmd-close-btn" onClick={onClose} aria-label="Fechar">
            <kbd>ESC</kbd>
          </button>
        </div>

        {/* Results List */}
        <div className="cmd-palette-list" ref={listRef}>
          {filteredItems.length === 0 ? (
            <div className="cmd-empty-state">
              <span>🔍</span>
              <p>Nenhum comando encontrado para "{query}"</p>
            </div>
          ) : (
            filteredItems.map((item, idx) => {
              const isSelected = idx === selectedIndex
              return (
                <div
                  key={item.id}
                  data-cmd-index={idx}
                  className={`cmd-item ${isSelected ? 'selected' : ''}`}
                  onClick={() => item.action()}
                  onMouseEnter={() => setSelectedIndex(idx)}
                >
                  <div className="cmd-item-icon">{item.icon}</div>
                  <div className="cmd-item-body">
                    <span className="cmd-item-title">{item.title}</span>
                    {item.subtitle && <span className="cmd-item-subtitle">{item.subtitle}</span>}
                  </div>
                  <span className="cmd-item-category">{item.category}</span>
                  {isSelected && (
                    <span className="cmd-item-enter" title="Executar">
                      <CornerDownLeft size={13} />
                    </span>
                  )}
                </div>
              )
            })
          )}
        </div>

        {/* Footer info */}
        <div className="cmd-palette-footer">
          <div className="cmd-footer-hints">
            <span><kbd>↑</kbd> <kbd>↓</kbd> Navegar</span>
            <span><kbd>↵</kbd> Executar</span>
            <span><kbd>ESC</kbd> Fechar</span>
          </div>
          <span className="cmd-footer-tag">Workspace · Comandos</span>
        </div>
      </div>
    </dialog>
  )
}
