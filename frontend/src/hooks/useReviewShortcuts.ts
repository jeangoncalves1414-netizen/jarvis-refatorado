import { useEffect, useRef } from 'react'

type ReviewShortcutOptions = {
  enabled: boolean
  revealed: boolean
  onFlip: () => void
  onGrade: (grade: number) => void
  onUndo?: () => void
}

function isTypingTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false
  if (target.isContentEditable) return true
  return Boolean(target.closest('input, textarea, select, [contenteditable]:not([contenteditable="false"])'))
}

// Atalhos de revisão: Espaço/Enter vira o cartão, 1-4 avaliam (após revelar), Z ou Ctrl+Z desfaz.
export function useReviewShortcuts(options: ReviewShortcutOptions) {
  const latest = useRef(options)
  latest.current = options
  const { enabled } = options

  useEffect(() => {
    if (!enabled) return
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.repeat || event.defaultPrevented || event.altKey || event.metaKey) return
      if (isTypingTarget(event.target)) return
      const { revealed, onFlip, onGrade, onUndo } = latest.current
      const key = event.key
      if (!event.ctrlKey && (key === ' ' || key === 'Enter')) {
        event.preventDefault()
        onFlip()
        return
      }
      if (!event.ctrlKey && key >= '1' && key <= '4' && key.length === 1) {
        if (!revealed) return
        event.preventDefault()
        onGrade(Number(key) - 1)
        return
      }
      if (key.toLowerCase() === 'z' && !event.shiftKey && onUndo) {
        event.preventDefault()
        onUndo()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [enabled])
}
