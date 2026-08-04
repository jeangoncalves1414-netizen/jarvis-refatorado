import React from 'react'

export type BentoCardProps = {
  title?: string
  eyebrow?: string
  meta?: string
  children: React.ReactNode
  className?: string
  span?: 1 | 2 | 3
}

export function BentoCard({
  title,
  eyebrow,
  meta,
  children,
  className = '',
  span = 1,
}: BentoCardProps) {
  const spanClass = span === 2 ? 'bento-span-2' : span === 3 ? 'bento-span-3' : ''

  return (
    <div className={`bento-card ${spanClass} ${className}`}>
      <div className="bento-hover-grid" aria-hidden="true" />
      {(eyebrow || title || meta) && (
        <div className="bento-card-header">
          {eyebrow && <span className="bento-eyebrow">{eyebrow}</span>}
          {title && <h3 className="bento-title">{title}</h3>}
          {meta && <span className="bento-meta">{meta}</span>}
        </div>
      )}
      <div className="bento-card-body">{children}</div>
    </div>
  )
}
