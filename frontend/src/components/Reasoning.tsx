import React, { createContext, useContext, useEffect, useRef, useState } from 'react'

type ReasoningContextType = {
  isOpen: boolean
  onOpenChange: (open: boolean) => void
}

const ReasoningContext = createContext<ReasoningContextType | undefined>(undefined)

function useReasoningContext() {
  const context = useContext(ReasoningContext)
  if (!context) {
    throw new Error('useReasoningContext must be used within a Reasoning provider')
  }
  return context
}

export type ReasoningProps = {
  children: React.ReactNode
  className?: string
  open?: boolean
  onOpenChange?: (open: boolean) => void
  isStreaming?: boolean
  defaultOpen?: boolean
}

export function Reasoning({ children, className = '', open, onOpenChange, isStreaming, defaultOpen = false }: ReasoningProps) {
  const [internalOpen, setInternalOpen] = useState(defaultOpen)
  const [wasAutoOpened, setWasAutoOpened] = useState(false)

  const isControlled = open !== undefined
  const isOpen = isControlled ? open : internalOpen

  const handleOpenChange = (newOpen: boolean) => {
    if (!isControlled) {
      setInternalOpen(newOpen)
    }
    onOpenChange?.(newOpen)
  }

  useEffect(() => {
    // Auto-open while streaming starts producing reasoning, but never force-close
    // after the stream ends — the user may want to keep reading the reasoning.
    if (isStreaming && !wasAutoOpened) {
      if (!isControlled) setInternalOpen(true)
      setWasAutoOpened(true)
    }
  }, [isStreaming, wasAutoOpened, isControlled])

  return (
    <ReasoningContext.Provider value={{ isOpen, onOpenChange: handleOpenChange }}>
      <div className={`reasoning-container ${className}`.trim()}>{children}</div>
    </ReasoningContext.Provider>
  )
}

export type ReasoningTriggerProps = {
  children?: React.ReactNode
  className?: string
  label?: string
} & React.ButtonHTMLAttributes<HTMLButtonElement>

export function ReasoningTrigger({ children, className = '', label = 'Raciocínio & Planejamento', ...props }: ReasoningTriggerProps) {
  const { isOpen, onOpenChange } = useReasoningContext()

  return (
    <button
      type="button"
      className={`reasoning-trigger ${isOpen ? 'is-open' : ''} ${className}`.trim()}
      onClick={() => onOpenChange(!isOpen)}
      {...props}
    >
      <span className="reasoning-icon">🧠</span>
      <span className="reasoning-label">{children || label}</span>
      <span className={`reasoning-chevron ${isOpen ? 'rotate' : ''}`}>▼</span>
    </button>
  )
}

export type ReasoningContentProps = {
  children: React.ReactNode
  className?: string
  contentClassName?: string
} & React.HTMLAttributes<HTMLDivElement>

export function ReasoningContent({ children, className = '', contentClassName = '', ...props }: ReasoningContentProps) {
  const contentRef = useRef<HTMLDivElement>(null)
  const innerRef = useRef<HTMLDivElement>(null)
  const { isOpen } = useReasoningContext()

  useEffect(() => {
    if (!contentRef.current || !innerRef.current) return

    const observer = new ResizeObserver(() => {
      if (contentRef.current && innerRef.current && isOpen) {
        contentRef.current.style.maxHeight = `${innerRef.current.scrollHeight}px`
      }
    })

    observer.observe(innerRef.current)

    if (isOpen) {
      contentRef.current.style.maxHeight = `${innerRef.current.scrollHeight}px`
    } else {
      contentRef.current.style.maxHeight = '0px'
    }

    return () => observer.disconnect()
  }, [isOpen])

  return (
    <div
      ref={contentRef}
      className={`reasoning-content-wrapper ${className}`.trim()}
      style={{
        maxHeight: isOpen ? `${innerRef.current?.scrollHeight || 300}px` : '0px',
      }}
      {...props}
    >
      <div ref={innerRef} className={`reasoning-content-inner ${contentClassName}`.trim()}>
        {children}
      </div>
    </div>
  )
}

