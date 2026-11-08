import { useEffect, useMemo, useRef, useState } from 'react'
import { Search, CornerDownLeft } from 'lucide-react'
import { commands, describeCommand, runCommand, searchCommands, type CommandDef, type CommandHandlers } from '../commands/registry'
import { playClick, playSuccess, playOpen, isSfxEnabled } from '../utils/sfx'

type CommandPaletteProps = {
  isOpen: boolean
  onClose: () => void
  handlers: CommandHandlers
  recording?: boolean
}

export function CommandPalette({ isOpen, onClose, handlers, recording = false }: CommandPaletteProps) {
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const dialogRef = useRef<HTMLDialogElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  const sfxEnabled = isSfxEnabled()
  const describe = (command: CommandDef) => describeCommand(command, { recording, sfxEnabled })

  const filteredItems = useMemo(
    () => searchCommands(commands, query, command => describeCommand(command, { recording, sfxEnabled })),
    [query, recording, sfxEnabled],
  )

  const execute = (command: CommandDef) => {
    runCommand(command, handlers)
    onClose()
  }

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
          runCommand(filteredItems[selectedIndex], handlers)
          onClose()
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, filteredItems, selectedIndex, onClose, handlers])

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
              const text = describe(item)
              return (
                <div
                  key={item.id}
                  data-cmd-index={idx}
                  className={`cmd-item ${isSelected ? 'selected' : ''}`}
                  onClick={() => execute(item)}
                  onMouseEnter={() => setSelectedIndex(idx)}
                >
                  <div className="cmd-item-icon"><item.icon size={16} color={item.id === 'lifeos-vice' ? '#f97316' : undefined} /></div>
                  <div className="cmd-item-body">
                    <span className="cmd-item-title">{text.title}</span>
                    <span className="cmd-item-subtitle">{text.description}</span>
                  </div>
                  <span className="cmd-item-category">{item.group}</span>
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
