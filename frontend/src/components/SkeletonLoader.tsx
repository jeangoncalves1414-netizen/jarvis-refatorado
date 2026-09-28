import React from 'react'

export function SkeletonBox({
  width = '100%',
  height = '16px',
  borderRadius = '8px',
  className = '',
  style = {},
}: {
  width?: string | number
  height?: string | number
  borderRadius?: string | number
  className?: string
  style?: React.CSSProperties
}) {
  return (
    <div
      className={`skeleton-shimmer ${className}`}
      style={{
        width,
        height,
        borderRadius,
        ...style,
      }}
    />
  )
}

export function SkeletonCard({ lines = 3, height = 120 }: { lines?: number; height?: number }) {
  return (
    <div className="skeleton-card" style={{ minHeight: height }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
        <SkeletonBox width={28} height={28} borderRadius={8} />
        <SkeletonBox width="40%" height={14} borderRadius={4} />
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {Array.from({ length: lines }).map((_, i) => (
          <SkeletonBox
            key={i}
            width={i === lines - 1 ? '60%' : '100%'}
            height={12}
            borderRadius={4}
          />
        ))}
      </div>
    </div>
  )
}

export function SkeletonDashboard() {
  return (
    <div className="skeleton-dashboard-grid">
      {/* Top Banner Skeleton */}
      <div style={{ gridColumn: '1 / -1' }}>
        <div className="skeleton-card" style={{ height: 90, display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, width: '60%' }}>
            <SkeletonBox width={36} height={36} borderRadius={10} />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, width: '80%' }}>
              <SkeletonBox width="30%" height={14} />
              <SkeletonBox width="70%" height={10} />
            </div>
          </div>
          <SkeletonBox width={90} height={28} borderRadius={8} />
        </div>
      </div>

      {/* Row of 3 mini HUD cards */}
      <SkeletonCard height={90} lines={2} />
      <SkeletonCard height={90} lines={2} />
      <SkeletonCard height={90} lines={2} />

      {/* Progress & Stat Cards */}
      <div style={{ gridColumn: 'span 2' }}>
        <SkeletonCard height={160} lines={4} />
      </div>
      <SkeletonCard height={160} lines={4} />

      {/* Wide Bottom Card */}
      <div style={{ gridColumn: '1 / -1' }}>
        <SkeletonCard height={140} lines={3} />
      </div>
    </div>
  )
}

export function SkeletonLoader({ variant = 'dashboard' }: { variant?: 'dashboard' | 'card' }) {
  if (variant === 'card') return <SkeletonCard />
  return <SkeletonDashboard />
}
