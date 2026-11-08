import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import type { LiveAudioDiagnostics } from '../hooks/useMediaAssistant'

type LiveCallModalProps = {
  open: boolean
  onClose: () => void
  recording: boolean
  status: string
  userTranscript?: string
  jarvisTranscript?: string
  turns?: { id: string; user: string; jarvis: string }[]
  orbState?: 'idle' | 'listening' | 'thinking' | 'speaking'
  emotionLabel?: string
  audioDiagnostics?: LiveAudioDiagnostics | null
  onToggleCapture: () => void
  onBargeIn?: () => void
}

function deriveEmotion(orbState: string, rec: boolean): { emoji: string; label: string; color: string } {
  if (orbState === 'speaking') return { emoji: '🗣️', label: 'Respondendo', color: '#f59e0b' }
  if (orbState === 'thinking') return { emoji: '🤔', label: 'Processando', color: '#c084fc' }
  if (rec || orbState === 'listening') return { emoji: '👂', label: 'Ouvindo você', color: '#00daf8' }
  return { emoji: '😊', label: 'Aguardando', color: '#94a3b8' }
}

export function LiveCallModal({
  open,
  onClose,
  recording,
  status,
  userTranscript = '',
  jarvisTranscript = '',
  turns = [],
  orbState = 'idle',
  emotionLabel,
  onToggleCapture,
  onBargeIn,
  audioDiagnostics,
}: LiveCallModalProps) {
  const [isMinimized, setIsMinimized] = useState(false)
  const [durationSec, setDurationSec] = useState(0)

  useEffect(() => {
    if (!open) {
      setDurationSec(0)
      setIsMinimized(false)
      return
    }
    const iv = setInterval(() => setDurationSec(p => p + 1), 1000)
    return () => clearInterval(iv)
  }, [open])

  if (!open || typeof document === 'undefined') return null

  const fmt = `${Math.floor(durationSec / 60).toString().padStart(2, '0')}:${(durationSec % 60).toString().padStart(2, '0')}`
  const isListening = recording || orbState === 'listening'
  const isSpeaking = orbState === 'speaking'
  const isThinking = orbState === 'thinking'
  const voiceTag = isSpeaking
    ? '« JARVIS: TRANSMITINDO »'
    : isThinking
      ? '« JARVIS: PROCESSANDO »'
      : isListening
        ? '« ENTRADA DE VOZ DETECTADA »'
        : '« JARVIS ONLINE »'

  if (isMinimized) {
    return createPortal(
      <aside className="live-call-floating-bar" role="region" aria-label="Jarvis em chamada">
        <div className="live-call-floating-left">
          <span className="live-call-ping" />
          <span className="live-call-floating-timer">{fmt}</span>
          <span className="live-call-floating-status">
            {isSpeaking ? 'Jarvis falando...' : isThinking ? 'Processando...' : isListening ? 'Ouvindo você...' : 'Ligação ativa'}
          </span>
        </div>
        <div className="live-call-floating-actions">
          {isSpeaking && onBargeIn && (
            <button type="button" onClick={onBargeIn} className="live-call-floating-btn bargein">
              ✋ Interromper
            </button>
          )}
          <button type="button" onClick={() => setIsMinimized(false)} className="live-call-floating-btn expand">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 3 21 3 21 9" />
              <polyline points="9 21 3 21 3 15" />
              <line x1="21" y1="3" x2="14" y2="10" />
              <line x1="3" y1="21" x2="10" y2="14" />
            </svg>
            <span>Expandir</span>
          </button>
          <button type="button" onClick={onClose} className="live-call-floating-btn hangup">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 9c-1.6 0-3.15.25-4.6.72v3.1c0 .39-.23.74-.56.9-.98.49-1.87 1.12-2.66 1.85-.18.18-.43.28-.7.28-.28 0-.53-.11-.71-.29L.29 13.08a.996.996 0 0 1 0-1.41C3.42 8.47 7.48 6.5 12 6.5s8.58 1.97 11.71 5.17c.39.39.39 1.02 0 1.41l-2.48 2.48c-.18.18-.43.29-.71.29-.27 0-.52-.11-.7-.28-.79-.74-1.69-1.36-2.67-1.85-.33-.16-.56-.5-.56-.9v-3.1C15.15 9.25 13.6 9 12 9z" />
            </svg>
            <span>Desligar</span>
          </button>
        </div>
      </aside>,
      document.body
    )
  }

  return createPortal(
    <div
      className="live-call-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="Conversa por voz"
      onClick={() => setIsMinimized(true)}
    >
      <div
        className="live-call-card"
        onClick={e => e.stopPropagation()}
      >
        <div className="live-call-header">
          <span className="live-call-badge">
            <span className="live-call-ping" />
            CONVERSA · {fmt}
          </span>
          <div className="live-call-header-controls">
            <button
              type="button"
              onClick={() => setIsMinimized(true)}
              className="live-call-btn-icon minimize"
              title="Minimizar"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
            </button>
            <button
              type="button"
              onClick={onClose}
              className="live-call-btn-icon close"
              title="Fechar"
            >
              ✕
            </button>
          </div>
        </div>

        <div style={{ textAlign: 'center', marginBottom: 4 }}>
          <span style={{ fontSize: 10, letterSpacing: 4, color: 'var(--jarvis-cyan)', textTransform: 'uppercase', fontWeight: 700, textShadow: '0 0 10px rgba(0, 218, 248, 0.6)' }}>
            {voiceTag}
          </span>
        </div>

        {isSpeaking && <button type="button" className="ws-button" onClick={onBargeIn}>Interromper resposta</button>}

        <div>
          <h2 className="live-call-title">
            {isSpeaking
              ? 'Assistente respondendo'
              : isThinking
                ? 'Processando...'
                : isListening
                  ? 'Ouvindo você...'
                  : 'Conversa por voz'}
          </h2>
          <p className="live-call-status">{status}</p>

          {audioDiagnostics && (
            <div
              className="live-call-diagnostics"
              style={{
                margin: '10px auto 0',
                maxWidth: 390,
                color: '#94a3b8',
                fontFamily: 'DM Mono, monospace',
                fontSize: 10,
                lineHeight: 1.65,
              }}
            >
              <span>DIAGNÓSTICO · {audioDiagnostics.mode === 'fallback-vad' ? 'VAD LOCAL' : 'RECONHECIMENTO DO NAVEGADOR'}</span>
              {audioDiagnostics.mode === 'fallback-vad' && (
                <div>
                  Entrada {(audioDiagnostics.rms || 0).toFixed(3)} · Ruído {(audioDiagnostics.noiseFloor || 0).toFixed(3)} · Limiar {(audioDiagnostics.threshold || 0).toFixed(3)}
                </div>
              )}
              {audioDiagnostics.turnId && <div>Turno {audioDiagnostics.turnId.slice(0, 8)}</div>}
            </div>
          )}
        </div>

        {(() => {
          const em = emotionLabel
            ? { emoji: emotionLabel.split(' ')[0], label: emotionLabel.split(' ').slice(1).join(' '), color: 'var(--jarvis-cyan)' }
            : deriveEmotion(orbState, isListening)
          return (
            <div>
              <div className="live-call-emotion-pill">
                <span style={{ fontSize: 16 }}>{em.emoji}</span>
                <span style={{ color: em.color }}>{em.label}</span>
              </div>
            </div>
          )
        })()}

        {(turns.length > 0 || userTranscript || jarvisTranscript) && (
          <div className="live-call-subtitles">
            {turns.map(turn => (
              <div key={turn.id}>
                <p style={{ color: '#e2e8f0' }}><strong style={{ color: '#00daf8' }}>Você: </strong>{turn.user}</p>
                <p style={{ color: '#f8fafc' }}><strong style={{ color: '#f59e0b' }}>Jarvis: </strong>{turn.jarvis}</p>
              </div>
            ))}
            {turns.at(-1)?.user !== userTranscript && userTranscript && (
              <p style={{ color: '#e2e8f0' }}>
                <strong style={{ color: '#00daf8' }}>Você: </strong>
                {userTranscript}
              </p>
            )}
            {turns.at(-1)?.user !== userTranscript && jarvisTranscript && (
              <p style={{ color: '#f8fafc' }}>
                <strong style={{ color: '#f59e0b' }}>Jarvis: </strong>
                {jarvisTranscript}
              </p>
            )}
          </div>
        )}

        <div className="live-call-actions">
          {isSpeaking && onBargeIn ? (
            <button type="button" onClick={onBargeIn} className="live-call-btn-bargein">
              ✋ Interromper
            </button>
          ) : (
            <button
              type="button"
              onClick={onToggleCapture}
              className={`live-call-btn-toggle ${isListening ? 'recording' : 'idle'}`}
            >
              <span>{isListening ? '⏸ Pausar Ligação' : '🎙 Iniciar Ligação'}</span>
            </button>
          )}
          <button type="button" onClick={() => setIsMinimized(true)} className="live-call-btn-minimize">
            🗕 Minimizar
          </button>
          <button type="button" onClick={onClose} className="live-call-btn-hangup">
            Encerrar
          </button>
        </div>

        <p className="live-call-footer-hint">
          ⚡ <strong>Full-Duplex Barge-in:</strong> Fale ou toque a qualquer momento para interromper o Jarvis. Ele saberá exatamente onde parou.
        </p>
      </div>
    </div>,
    document.body
  )
}