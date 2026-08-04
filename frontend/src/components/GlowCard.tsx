import React, { useEffect, useRef, ReactNode } from 'react'

interface GlowCardProps {
  children: ReactNode
  className?: string
  glowColor?: 'purple' | 'blue' | 'green' | 'red' | 'fuchsia'
}

const colorHueMap = {
  purple: 270,
  blue: 210,
  green: 140,
  red: 0,
  fuchsia: 300,
}

export function GlowCard({
  children,
  className = '',
  glowColor = 'purple',
}: GlowCardProps) {
  const cardRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handlePointerMove = (e: PointerEvent) => {
      if (!cardRef.current) return
      const rect = cardRef.current.getBoundingClientRect()
      const x = e.clientX - rect.left
      const y = e.clientY - rect.top
      cardRef.current.style.setProperty('--glow-x', `${x}px`)
      cardRef.current.style.setProperty('--glow-y', `${y}px`)
      cardRef.current.style.setProperty('--glow-opacity', '1')
    }

    const handlePointerLeave = () => {
      if (!cardRef.current) return
      cardRef.current.style.setProperty('--glow-opacity', '0')
    }

    const card = cardRef.current
    if (card) {
      card.addEventListener('pointermove', handlePointerMove)
      card.addEventListener('pointerleave', handlePointerLeave)
    }

    return () => {
      if (card) {
        card.removeEventListener('pointermove', handlePointerMove)
        card.removeEventListener('pointerleave', handlePointerLeave)
      }
    }
  }, [])

  const hue = colorHueMap[glowColor]

  return (
    <div
      ref={cardRef}
      className={`glow-card-wrapper ${className}`}
      style={
        {
          '--glow-hue': hue,
        } as React.CSSProperties
      }
    >
      <div className="glow-card-border" aria-hidden="true" />
      <div className="glow-card-inner">{children}</div>
    </div>
  )
}
