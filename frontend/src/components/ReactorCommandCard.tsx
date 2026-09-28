import { useEffect, useState } from 'react'
import { JarvisOrb, type AgentState } from './JarvisOrb'
import { isMobileStandalone } from '../hooks/useDirectChat'
import { Mic, Eye, Film, PhoneCall, ExternalLink, Cpu, Activity, Zap, Sparkles } from 'lucide-react'
import type { Weather } from '../types'

export type ReactorCommandCardProps = {
  weather?: Weather | null
  onOpenCinema: () => void
  onCaptureVision?: () => void
  onToggleVoice?: () => void
  onOpenLiveCall?: () => void
  onDetachOverlay?: () => void
  recording?: boolean
  state?: AgentState
}

export function ReactorCommandCard({
  weather,
  onOpenCinema,
  onCaptureVision,
  onToggleVoice,
  onOpenLiveCall,
  onDetachOverlay,
  recording = false,
  state: agentState = 'idle',
}: ReactorCommandCardProps) {
  // Live hardware simulation telemetry
  const [cpuUsage, setCpuUsage] = useState(16)
  const [ramUsage, setRamUsage] = useState(41)
  const [latency, setLatency] = useState(14)
  const [activeThreads, setActiveThreads] = useState(8)

  const mobile = isMobileStandalone()

  useEffect(() => {
    if (mobile) return
    const interval = setInterval(() => {
      setCpuUsage(Math.floor(12 + Math.random() * 20))
      setRamUsage(Math.floor(40 + Math.random() * 5))
      setLatency(Math.floor(11 + Math.random() * 8))
      setActiveThreads(Math.floor(6 + Math.random() * 4))
    }, 2800)
    return () => clearInterval(interval)
  }, [])

  // Proportional fluid UI scaling for the Quantum Core Orb
  const [orbSize, setOrbSize] = useState(210)

  useEffect(() => {
    const handleResize = () => {
      const w = window.innerWidth
      if (w < 640) setOrbSize(145)
      else if (w < 860) setOrbSize(170)
      else if (w < 1200) setOrbSize(195)
      else if (w < 1500) setOrbSize(215)
      else setOrbSize(235)
    }
    handleResize()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  // 'listening' is handled via the boolean prop on JarvisOrb, not via AgentState
  const currentState: AgentState = agentState

  const getStateLabel = () => {
    if (recording) return { text: '« ESCUTA ATIVA » PROCESSANDO...', color: '#ffd54f', dotClass: 'listening' }
    if (agentState === 'thinking' || agentState === 'tool_executing') return { text: '« JARVIS: PROCESSANDO » ANALISANDO...', color: 'var(--jarvis-cyan)', dotClass: 'thinking' }
    if (agentState === 'streaming') return { text: '« JARVIS » TRANSMITINDO RESPOSTA', color: 'var(--jarvis-cyan)', dotClass: 'speaking' }
    if (agentState === 'celebrating') return { text: 'OPERAÇÃO CONCLUÍDA', color: '#ffd700', dotClass: 'celebrating' }
    return { text: 'SISTEMA COGNITIVO OPERACIONAL', color: '#ffb300', dotClass: 'idle' }
  }

  const stateInfo = getStateLabel()

  return (
    <div className="reactor-card-outer">
      <section className="reactor-command-card">
        {/* Ambient Halo behind Reactor */}
        <div className="reactor-ambient-glow" aria-hidden="true" />
        <div className="reactor-grid-pattern" aria-hidden="true" />

        {/* ─── Top: Header & System Status ──────────────────────────── */}
        <div className="reactor-hud-top">
          <div className="reactor-title-group">
            <span className="reactor-badge-tag" style={{ borderColor: 'rgba(255, 180, 0, 0.45)', color: '#ffe599' }}>
              <Zap size={11} className="reactor-sparkle-icon" /> JARVIS CORE // SISTEMA COGNITIVO
            </span>
            <span className="reactor-subtitle-label">ASSISTENTE PESSOAL · JARVIS</span>
          </div>

          <div className="reactor-top-right">
            <div className="reactor-status-pill" style={{ borderColor: 'rgba(255, 180, 0, 0.3)' }}>
              <span className={`reactor-status-dot ${stateInfo.dotClass}`} />
              <span className="reactor-status-text" style={{ color: stateInfo.color }}>
                {stateInfo.text}
              </span>
            </div>

            {!mobile && onDetachOverlay && (
              <button
                type="button"
                className="reactor-detach-btn"
                onClick={onDetachOverlay}
                title="Desencaixar reator para overlay flutuante na tela"
              >
                <ExternalLink size={12} />
                <span>Flutuante</span>
              </button>
            )}
          </div>
        </div>

        {/* ─── Center Body: Left Telemetry | Center Reactor | Right AI ─ */}
        <div className="reactor-hud-body">
          {/* Left Flank: Real-Time Hardware Telemetry */}
          <div className="reactor-hud-flank reactor-flank-left">
            <div className="reactor-flank-header">
              <Cpu size={12} />
              <span>HARDWARE HUD</span>
            </div>

            <div className="reactor-telemetry-item">
              <div className="reactor-item-header">
                <span className="reactor-item-label">CPU LOAD</span>
                <span className="reactor-item-val" style={{ color: cpuUsage > 30 ? '#f59e0b' : '#fbbf24' }}>
                  {cpuUsage}%
                </span>
              </div>
              <div className="reactor-bar-track">
                <div
                  className="reactor-bar-fill"
                  style={{
                    width: `${cpuUsage}%`,
                    background: cpuUsage > 30 ? 'linear-gradient(90deg, #f59e0b, #ef4444)' : 'linear-gradient(90deg, #fbbf24, #10b981)',
                  }}
                />
              </div>
            </div>

            <div className="reactor-telemetry-item">
              <div className="reactor-item-header">
                <span className="reactor-item-label">RAM USAGE</span>
                <span className="reactor-item-val">{ramUsage}%</span>
              </div>
              <div className="reactor-bar-track">
                <div
                  className="reactor-bar-fill"
                  style={{ width: `${ramUsage}%`, background: 'linear-gradient(90deg, #10b981, #fbbf24)' }}
                />
              </div>
            </div>

            <div className="reactor-telemetry-row">
              <div className="reactor-mini-stat">
                <span className="reactor-item-label">LATÊNCIA</span>
                <strong className="reactor-mono-val">{latency}ms</strong>
              </div>
              <div className="reactor-mini-stat">
                <span className="reactor-item-label">THREADS</span>
                <strong className="reactor-mono-val">{activeThreads} Cores</strong>
              </div>
            </div>
          </div>

          {/* Center: Holographic Reactor Core */}
          <div className="reactor-hud-center">
            <div className="reactor-orb-stage">
              <JarvisOrb
                size={orbSize}
                use3D={true}
                listening={recording}
                speaking={agentState === 'streaming'}
                state={currentState}
                interactive
                onClick={onToggleVoice}
              />
            </div>
          </div>

          {/* Right Flank: Neural & Audio Spectrum */}
          <div className="reactor-hud-flank reactor-flank-right">
            <div className="reactor-flank-header">
              <Activity size={12} />
              <span>NEURAL & ÁUDIO</span>
            </div>

            <div className="reactor-telemetry-item">
              <span className="reactor-item-label">ROTA NEURAL</span>
              <div className="reactor-chip-row">
                <span className="reactor-ai-badge">Groq Llama 3.3 70B</span>
              </div>
            </div>

            <div className="reactor-telemetry-item">
              <span className="reactor-item-label">MOTOR TTS / VOZ</span>
              <div className="reactor-chip-row">
                <span className="reactor-voice-badge">Fish Audio S2.1</span>
              </div>
            </div>

            <div className="reactor-telemetry-item">
              <div className="reactor-item-header">
                <span className="reactor-item-label">ESPECTRO DE VOZ</span>
                <span className="reactor-item-val" style={{ color: recording ? '#f59e0b' : '#10b981' }}>
                  {recording ? 'MIC ON' : 'ATIVO'}
                </span>
              </div>
              <div className="reactor-equalizer-bars">
                <span className={`reactor-eq-bar bar-1 ${recording ? 'live' : ''}`} />
                <span className={`reactor-eq-bar bar-2 ${recording ? 'live' : ''}`} />
                <span className={`reactor-eq-bar bar-3 ${recording ? 'live' : ''}`} />
                <span className={`reactor-eq-bar bar-4 ${recording ? 'live' : ''}`} />
                <span className={`reactor-eq-bar bar-5 ${recording ? 'live' : ''}`} />
              </div>
            </div>
          </div>
        </div>

        {/* ─── Bottom: Action Console Dock ──────────────────────────── */}
        <div className="reactor-hud-bottom">
          <div className="reactor-actions-dock">
            {onToggleVoice && (
              <button
                type="button"
                className={`reactor-action-btn primary-voice ${recording ? 'is-recording' : ''}`}
                onClick={onToggleVoice}
                title={recording ? 'Parar gravação de voz' : 'Falar com Jarvis agora'}
              >
                <Mic size={15} />
                <span>{recording ? 'Parar Microfone' : 'Conversar por Voz'}</span>
              </button>
            )}

            {!mobile && onCaptureVision && (
              <button
                type="button"
                className="reactor-action-btn"
                onClick={onCaptureVision}
                title="Capturar e analisar a tela atual com visão IA"
              >
                <Eye size={15} />
                <span>Analisar Tela</span>
              </button>
            )}

            {!mobile && (
            <button
              type="button"
              className="reactor-action-btn"
              onClick={onOpenCinema}
              title="Abrir Central de Mídia & Cinema"
            >
              <Film size={15} />
              <span>Cinema & Mídia</span>
            </button>
            )}

            {onOpenLiveCall && (
              <button
                type="button"
                className="reactor-action-btn highlight-call"
                onClick={onOpenLiveCall}
                title="Iniciar ligação contínua de voz full-duplex"
              >
                <PhoneCall size={15} />
                <span>Ligação Ao Vivo</span>
              </button>
            )}
          </div>
        </div>
      </section>
    </div>
  )
}
