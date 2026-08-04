import React, { useEffect } from 'react'

const SHIMMER_STYLE_ID = 'an-tool-status-shimmer-styles'
const SHIMMER_STYLES = `
@keyframes an-tool-shimmer {
  from { background-position: 100% center; }
  to { background-position: 0% center; }
}
.an-tool-shimmer {
  display: inline-flex;
  align-items: center;
  height: 1.2rem;
  background-size: 250% 100%;
  background-clip: text;
  -webkit-background-clip: text;
  color: transparent;
  background-image: linear-gradient(90deg, #a78bfa 0%, #ffffff 50%, #a78bfa 100%);
  animation: an-tool-shimmer 1.4s linear infinite;
}
`

function ensureShimmerStyles() {
  if (typeof document === 'undefined') return
  if (document.getElementById(SHIMMER_STYLE_ID)) return
  const el = document.createElement('style')
  el.id = SHIMMER_STYLE_ID
  el.textContent = SHIMMER_STYLES
  document.head.appendChild(el)
}

export type ToolStatusProps = {
  toolName: string
  status?: 'pending' | 'completed' | 'error'
  detail?: string
  icon?: string
}

export function ToolStatus({
  toolName,
  status = 'pending',
  detail,
  icon = '⚙️',
}: ToolStatusProps) {
  useEffect(() => {
    ensureShimmerStyles()
  }, [])

  const isPending = status === 'pending'
  const isError = status === 'error'

  return (
    <div className={`tool-status-container status-${status}`}>
      <span className="tool-status-icon">{isError ? '⚠️' : isPending ? '⏳' : icon}</span>
      <span className={isPending ? 'an-tool-shimmer' : 'tool-status-title'}>
        {isPending ? `Executando ${toolName}…` : isError ? `Erro em ${toolName}` : `${toolName} concluído`}
      </span>
      {detail && <span className="tool-status-detail">{detail}</span>}
    </div>
  )
}
