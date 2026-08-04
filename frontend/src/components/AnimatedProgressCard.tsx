import { motion } from 'framer-motion'
import type { ReactNode } from 'react'

export function AnimatedProgressCard({
  icon,
  title,
  label,
  subLabel,
  currentValue,
  maxValue,
}: {
  icon: ReactNode
  title: string
  label: string
  subLabel: string
  currentValue: number
  maxValue: number
}) {
  const safeMax = Math.max(maxValue, 1)
  const percentage = Math.min(100, Math.max(0, (currentValue / safeMax) * 100))

  return (
    <article className="animated-progress-card">
      <div className="animated-progress-header">
        <span className="animated-progress-icon">{icon}</span>
        <strong>{title}</strong>
      </div>
      <div className="animated-progress-track" role="progressbar" aria-valuenow={currentValue} aria-valuemin={0} aria-valuemax={safeMax} aria-label={title}>
        <motion.span
          className="animated-progress-fill"
          initial={{ width: 0 }}
          animate={{ width: `${percentage}%` }}
          transition={{ duration: 0.9, ease: 'easeOut' }}
        />
      </div>
      <div className="animated-progress-footer">
        <div>
          <span>{label}</span>
          <small>{subLabel}</small>
        </div>
        <b>{currentValue}<em> / {maxValue}</em></b>
      </div>
    </article>
  )
}
