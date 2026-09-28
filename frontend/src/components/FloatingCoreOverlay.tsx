import { useEffect, useState } from 'react'
import { JarvisOrb, type AgentState } from './JarvisOrb'
import { Maximize2, Mic, X } from 'lucide-react'

export function FloatingCoreOverlay() {
  const [state, setState] = useState<AgentState>('idle')
  const [recording, setRecording] = useState(false)
  const [hovered, setHovered] = useState(false)

  // Sincroniza estado com o backend local caso disponível
  useEffect(() => {
    document.body.classList.add('floating-overlay-active')
    document.title = 'Jarvis · Floating Core'

    const checkStatus = async () => {
      try {
        const res = await fetch('/api/evolute/status')
        if (res.ok) {
          // O backend está vivo
        }
      } catch {
        // Ignora oscilações
      }
    }

    const interval = setInterval(checkStatus, 5000)
    return () => {
      document.body.classList.remove('floating-overlay-active')
      clearInterval(interval)
    }
  }, [])

  const handleRestore = () => {
    const pywebview = (window as any).pywebview
    if (pywebview?.api?.restoreMainWindow) {
      pywebview.api.restoreMainWindow()
    } else {
      if (window.opener) {
        window.opener.focus()
        window.close()
      } else {
        window.location.href = '/app/'
      }
    }
  }

  const handleToggleVoice = (e: React.MouseEvent) => {
    e.stopPropagation()
    setRecording(prev => !prev)
    setState(prev => (prev === 'idle' ? 'thinking' : 'idle'))
  }

  return (
    <div
      className="floating-core-overlay-container"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      data-pywebview-drag-region
    >
      <div className="floating-core-wrapper">
        {/* Halo de iluminação ambiente */}
        <div className="floating-core-halo" aria-hidden="true" />

        {/* Reator Quântico com clique para restaurar a janela */}
        <div
          className="floating-core-orb-box"
          onClick={handleRestore}
          title="Clique para abrir o painel principal do Jarvis"
        >
          <JarvisOrb
            size={160}
            listening={recording}
            state={state}
            interactive
          />
        </div>

        {/* Controles de hover (Restaurar, Mic, Fechar) */}
        {hovered && (
          <div className="floating-core-controls">
            <button
              type="button"
              className="floating-core-btn primary"
              onClick={handleRestore}
              title="Restaurar painel principal"
            >
              <Maximize2 size={12} />
              <span>Painel</span>
            </button>

            <button
              type="button"
              className={`floating-core-btn voice ${recording ? 'active' : ''}`}
              onClick={handleToggleVoice}
              title={recording ? 'Parar microfone' : 'Ativar microfone'}
            >
              <Mic size={12} />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
