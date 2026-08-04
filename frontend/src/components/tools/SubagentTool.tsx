import React, { useEffect } from 'react'

const SHIMMER_STYLE_ID = 'an-subagent-tool-shimmer-styles'
const SHIMMER_STYLES = `
@keyframes an-subagent-shimmer {
  from { background-position: 100% center; }
  to { background-position: 0% center; }
}
.an-subagent-shimmer {
  display: inline-flex;
  align-items: center;
  height: 1rem;
  background-size: 250% 100%;
  background-clip: text;
  -webkit-background-clip: text;
  color: transparent;
  background-image: linear-gradient(90deg, #a3a3a3 0%, #ffffff 50%, #a3a3a3 100%);
  animation: an-subagent-shimmer 1.5s linear infinite;
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

export type SubagentToolProps = {
  state?: 'completed' | 'pending' | 'interrupted'
  description?: string
  elapsedTime?: string
}

export function SubagentTool({
  state = 'completed',
  description = 'Subagente executando tarefa',
  elapsedTime,
}: SubagentToolProps) {
  useEffect(() => {
    ensureShimmerStyles()
  }, [])

  const isPending = state === 'pending'
  const label = isPending ? '⚡ Subagente em Execução' : '✅ Subagente Concluído'

  return (
    <div className="subagent-tool-container">
      <div className="subagent-tool-content">
        <span className={isPending ? 'an-subagent-shimmer' : 'subagent-label'}>
          {label}
        </span>
        {description && <span className="subagent-desc">{description}</span>}
        {elapsedTime && <span className="subagent-time">{elapsedTime}</span>}
      </div>
    </div>
  )
}
