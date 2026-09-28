type MatrixScanlineEffectProps = {
  active: boolean
}

export function MatrixScanlineEffect({ active }: MatrixScanlineEffectProps) {
  if (!active) return null

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100vw',
        height: '100vh',
        pointerEvents: 'none',
        zIndex: 9999,
        background: 'linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 255, 120, 0.05) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.03), rgba(0, 255, 0, 0.01), rgba(0, 0, 255, 0.03))',
        backgroundSize: '100% 3px, 6px 100%',
        mixBlendMode: 'screen',
        opacity: 0.85,
      }}
    />
  )
}
