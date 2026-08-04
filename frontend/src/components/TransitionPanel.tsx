import { AnimatePresence, motion } from 'framer-motion'
import type { ReactNode } from 'react'

interface TransitionPanelProps {
  children: ReactNode
  activeKey: string
  className?: string
}

export function TransitionPanel({ children, activeKey, className = '' }: TransitionPanelProps) {
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={activeKey}
        className={`transition-panel-wrapper ${className}`}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -6 }}
        transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  )
}
