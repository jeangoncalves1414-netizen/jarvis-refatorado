import { AlertCircle, CheckCircle2, Clock3, Info, MinusCircle, XCircle } from 'lucide-react'
import type { ReactNode } from 'react'

export type StatusBadgeState = 'success' | 'error' | 'warning' | 'info' | 'pending' | 'default'

const statusIcons = {
  success: CheckCircle2,
  error: XCircle,
  warning: AlertCircle,
  info: Info,
  pending: Clock3,
  default: MinusCircle,
} as const

export function StatusBadge({
  status,
  children,
  className = '',
}: {
  status: StatusBadgeState
  children: ReactNode
  className?: string
}) {
  const Icon = statusIcons[status]
  return (
    <span className={`status-badge status-badge-${status} ${className}`} role={status === 'error' || status === 'warning' ? 'alert' : 'status'}>
      <Icon aria-hidden="true" />
      <span>{children}</span>
    </span>
  )
}
