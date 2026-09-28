import { useState, useEffect } from 'react'

type BiometricScannerModalProps = {
  isOpen: boolean
  actionTitle: string
  onConfirm: () => void
  onCancel: () => void
}

export function BiometricScannerModal({ isOpen, actionTitle, onConfirm, onCancel }: BiometricScannerModalProps) {
  const [scanning, setScanning] = useState(false)
  const [success, setSuccess] = useState(false)

  useEffect(() => {
    if (isOpen) {
      setScanning(true)
      setSuccess(false)
      const timer = setTimeout(() => {
        setScanning(false)
        setSuccess(true)
        setTimeout(() => {
          onConfirm()
        }, 800)
      }, 1800)
      return () => clearTimeout(timer)
    }
  }, [isOpen])

  if (!isOpen) return null

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100vw',
        height: '100vh',
        background: 'rgba(5, 10, 20, 0.85)',
        backdropFilter: 'blur(16px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 10000,
      }}
    >
      <div
        style={{
          background: 'rgba(10, 15, 30, 0.95)',
          border: `1px solid ${success ? 'rgba(0, 255, 120, 0.6)' : 'rgba(0, 218, 248, 0.4)'}`,
          borderRadius: 16,
          padding: 32,
          maxWidth: 400,
          width: '90%',
          textAlign: 'center',
          boxShadow: success ? '0 0 40px rgba(0, 255, 120, 0.2)' : '0 0 40px rgba(251, 191, 36, 0.2)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 16,
        }}
      >
        <span style={{ fontSize: 11, color: '#fbbf24', fontWeight: 700, letterSpacing: 2 }}>
          ⚡ CONFIRMAÇÃO BIOMÉTRICA QUANTUM
        </span>

        {/* Scanner graphic */}
        <div
          style={{
            width: 100,
            height: 100,
            borderRadius: '50%',
            border: `2px dashed ${success ? '#00ff78' : '#fbbf24'}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            position: 'relative',
            animation: scanning ? 'spin 3s linear infinite' : 'none',
          }}
        >
          <span style={{ fontSize: 40 }}>{success ? '✓' : '👁️'}</span>
        </div>

        <div>
          <h3 style={{ margin: 0, color: '#fff', fontSize: 16 }}>{actionTitle}</h3>
          <p style={{ margin: '6px 0 0', color: '#aaa', fontSize: 12 }}>
            {scanning ? 'Verificando identidade e biometria...' : 'Acesso concedido com sucesso!'}
          </p>
        </div>

        <button
          type="button"
          onClick={onCancel}
          style={{
            marginTop: 8,
            background: 'transparent',
            border: '1px solid rgba(255, 255, 255, 0.15)',
            borderRadius: 8,
            color: '#888',
            padding: '6px 16px',
            fontSize: 12,
            cursor: 'pointer',
          }}
        >
          Cancelar
        </button>
      </div>
    </div>
  )
}
