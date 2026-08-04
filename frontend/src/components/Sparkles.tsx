import { useMemo } from 'react'

type SparklesProps = {
  count?: number
  className?: string
}

export function Sparkles({ count = 24, className = '' }: SparklesProps) {
  const particles = useMemo(
    () =>
      Array.from({ length: count }, (_, i) => ({
        id: i,
        left: `${(i * 37 + 11) % 100}%`,
        top: `${(i * 53 + 7) % 100}%`,
        delay: `${(i % 7) * 0.4}s`,
        size: 2 + (i % 3),
      })),
    [count],
  )

  return (
    <div className={`sparkles-layer ${className}`} aria-hidden="true">
      {particles.map(p => (
        <span
          key={p.id}
          className="sparkle-particle"
          style={{ left: p.left, top: p.top, animationDelay: p.delay, width: p.size, height: p.size }}
        />
      ))}
    </div>
  )
}
