import { useEffect, useState } from 'react'

// ─── Types ───────────────────────────────────────────────────────────────────
export type AiLoaderVariant = 'shimmer-text' | 'dots' | 'loading-line' | 'spinner' | 'pulse-ring'

export interface AiLoaderProps {
  variant?: AiLoaderVariant
  text?: string
  className?: string
}

// ─── Shared keyframes injected once ──────────────────────────────────────────
const STYLES_ID = 'jarvis-ai-loader-kf'
const KEYFRAMES = `
@keyframes jarvis-shimmer-slide {
  0%   { background-position: 200% center; }
  100% { background-position: -200% center; }
}
@keyframes jarvis-dot-bounce {
  0%,100% { transform: translateY(0) scale(0.82); opacity: 0.28; }
  50%      { transform: translateY(-5px) scale(1.18); opacity: 1; }
}
@keyframes jarvis-line-sweep {
  0%   { transform: translateX(-100%); }
  100% { transform: translateX(400%); }
}
@keyframes jarvis-ring-dash {
  0%   { stroke-dasharray: 1,200;  stroke-dashoffset: 0;    }
  50%  { stroke-dasharray: 90,200; stroke-dashoffset: -35;  }
  100% { stroke-dasharray: 90,200; stroke-dashoffset: -124; }
}
@keyframes jarvis-ring-spin  { to { transform: rotate(360deg); } }
@keyframes jarvis-pulse-grow {
  0%,100% { transform: scale(1);    opacity: 0.55; }
  50%      { transform: scale(1.22); opacity: 1; }
}
@keyframes jarvis-reveal-in {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}
.jarvis-shimmer-text {
  background: linear-gradient(
    90deg,
    #787a8e 0%, #787a8e 25%,
    #c4b5fd 42%, #f0abfc 50%, #c4b5fd 58%,
    #787a8e 75%, #787a8e 100%
  );
  background-size: 200% auto;
  background-clip: text;
  -webkit-background-clip: text;
  color: transparent;
  animation: jarvis-shimmer-slide 2.4s linear infinite;
  font-weight: 600;
  letter-spacing: 0.02em;
}
.jarvis-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: #a78bfa;
  box-shadow: 0 0 6px rgba(167,139,250,0.45);
  animation: jarvis-dot-bounce 1.4s ease-in-out infinite;
}
.reveal-anim {
  transition: opacity 0.4s ease, transform 0.4s cubic-bezier(0.16,1,0.3,1);
}
.reveal-hidden { opacity: 0; transform: translateY(12px); }
.reveal-visible { opacity: 1; transform: translateY(0); }
`

function ensureKeyframes() {
  if (typeof document === 'undefined') return
  if (document.getElementById(STYLES_ID)) return
  const el = document.createElement('style')
  el.id = STYLES_ID
  el.textContent = KEYFRAMES
  document.head.appendChild(el)
}

// ─── AiLoader ────────────────────────────────────────────────────────────────
export function AiLoader({
  variant = 'shimmer-text',
  text = 'Processando…',
  className = '',
}: AiLoaderProps) {
  useEffect(ensureKeyframes, [])

  /* shimmer-text: sparkle icon + animated gradient text */
  if (variant === 'shimmer-text') {
    return (
      <div className={`ai-loader-shimmer-row ${className}`}>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" className="ai-loader-sparkle-icon">
          <path d="M12 2 9.5 9.5 2 12l7.5 2.5L12 22l2.5-7.5L22 12l-7.5-2.5z" />
        </svg>
        <span className="jarvis-shimmer-text">{text}</span>
      </div>
    )
  }

  /* dots: three bouncing circles */
  if (variant === 'dots') {
    return (
      <div className={`ai-loader-dots-row ${className}`}>
        <div className="jarvis-dot" style={{ animationDelay: '0ms' }} />
        <div className="jarvis-dot" style={{ animationDelay: '180ms' }} />
        <div className="jarvis-dot" style={{ animationDelay: '360ms' }} />
      </div>
    )
  }

  /* loading-line: sweeping glow across a track */
  if (variant === 'loading-line') {
    return (
      <div className={`ai-loader-line-track ${className}`}>
        <div
          className="ai-loader-line-sweep"
          style={{ animation: 'jarvis-line-sweep 2s cubic-bezier(0.4,0,0.2,1) infinite' }}
        />
      </div>
    )
  }

  /* spinner: SVG arc spin */
  if (variant === 'spinner') {
    return (
      <div className={`ai-loader-spinner-wrap ${className}`}>
        <svg
          className="ai-loader-spinner-svg"
          viewBox="0 0 50 50"
          style={{ animation: 'jarvis-ring-spin 2s linear infinite' }}
        >
          <circle
            className="ai-loader-spinner-arc"
            strokeLinecap="round"
            cx="25" cy="25" r="20"
            style={{ animation: 'jarvis-ring-dash 1.5s ease-in-out infinite' }}
          />
        </svg>
      </div>
    )
  }

  /* pulse-ring */
  if (variant === 'pulse-ring') {
    return (
      <div
        className={`ai-loader-pulse-ring ${className}`}
        style={{ animation: 'jarvis-pulse-grow 1.4s ease-in-out infinite' }}
      />
    )
  }

  return null
}

// ─── RevealAnimation ─────────────────────────────────────────────────────────
export interface RevealAnimationProps {
  children: React.ReactNode
  delay?: number
  className?: string
}

export function RevealAnimation({ children, delay = 0, className = '' }: RevealAnimationProps) {
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    ensureKeyframes()
    const t = setTimeout(() => setVisible(true), delay)
    return () => clearTimeout(t)
  }, [delay])
  return (
    <div className={`reveal-anim ${visible ? 'reveal-visible' : 'reveal-hidden'} ${className}`}>
      {children}
    </div>
  )
}
