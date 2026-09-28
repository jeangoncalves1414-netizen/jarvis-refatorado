import { JarvisOrb3D, type AgentState } from './JarvisOrb3D'

export type { AgentState }

type JarvisOrbProps = {
  size?: number
  listening?: boolean
  speaking?: boolean
  state?: AgentState
  className?: string
  use3D?: boolean
  interactive?: boolean
  onClick?: () => void
}

export function JarvisOrb({
  size = 112,
  listening = false,
  speaking = false,
  state = 'idle',
  className = '',
  use3D = true,
  interactive = false,
  onClick,
}: JarvisOrbProps) {
  if (use3D) {
    return (
      <JarvisOrb3D
        size={size}
        listening={listening}
        speaking={speaking}
        state={state}
        className={className}
        interactive={interactive}
        onClick={onClick}
      />
    )
  }

  const stateClass = listening ? 'jarvis-orb-listening' : speaking ? 'jarvis-orb-speaking' : ''

  return (
    <div
      className={`jarvis-orb-wrap ${stateClass} ${className}`}
      style={{
        width: size,
        height: size,
        cursor: interactive ? 'pointer' : 'default',
        background: 'radial-gradient(circle, rgba(245, 158, 11, 0.25) 0%, rgba(16, 185, 129, 0.15) 50%, transparent 75%)',
        borderRadius: '50%',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        position: 'relative',
      }}
      onClick={interactive ? onClick : undefined}
    >
      <div
        className="jarvis-orb-core"
        style={{
          color: '#ffffff',
          textShadow: '0 0 12px #fbbf24, 0 0 24px #f59e0b',
          fontSize: Math.max(14, size * 0.25),
          fontWeight: 700,
        }}
      >
        解
      </div>
      <div
        className="jarvis-orb-ring"
        style={{
          borderColor: 'rgba(251, 191, 36, 0.75)',
          boxShadow: '0 0 14px rgba(245, 158, 11, 0.4), inset 0 0 14px rgba(16, 185, 129, 0.2)',
        }}
        aria-hidden="true"
      />
      <div
        className="jarvis-orb-ring jarvis-orb-ring-2"
        style={{
          borderColor: 'rgba(16, 185, 129, 0.45)',
        }}
        aria-hidden="true"
      />
    </div>
  )
}
