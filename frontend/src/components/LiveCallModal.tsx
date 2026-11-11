import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import type { LiveAudioDiagnostics } from '../hooks/useMediaAssistant'
import type { ToolActivityEntry } from '../types'
import { ToolActivity } from './chat/ToolActivity'

type LiveCallModalProps = {
  open: boolean
  onClose: () => void
  recording: boolean
  status: string
  userTranscript?: string
  jarvisTranscript?: string
  turns?: { id: string; user: string; jarvis: string; pending?: boolean; activity?: ToolActivityEntry[] }[]
  orbState?: 'idle' | 'listening' | 'thinking' | 'speaking'
  emotionLabel?: string
  audioDiagnostics?: LiveAudioDiagnostics | null
  onToggleCapture: () => void
  onBargeIn?: () => void
  pushToTalkMode?: boolean
  onTogglePushToTalk?: () => void
  onPttStart?: () => void
  onPttEnd?: () => void
  isPttActive?: boolean
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
  turns = [],
  orbState = 'idle',
  emotionLabel,
  onToggleCapture,
  onBargeIn,
  audioDiagnostics,
  pushToTalkMode = false,
  onTogglePushToTalk,
  onPttStart,
  onPttEnd,
  isPttActive = false,
}: LiveCallModalProps) {
  const [isMinimized, setIsMinimized] = useState(false)
  const [durationSec, setDurationSec] = useState(0)
  const spaceHeld = useRef(false)

  useEffect(() => {
    if (!open) {
      setDurationSec(0)
      setIsMinimized(false)
      return
    }
    const iv = setInterval(() => setDurationSec(p => p + 1), 1000)
    return () => clearInterval(iv)
  }, [open])

  useEffect(() => {
    if (!open || !pushToTalkMode) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === 'Space') {
        const target = e.target as HTMLElement | null
        const isInput = target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)
        if (isInput) return
        e.preventDefault()
        if (!e.repeat) {
          spaceHeld.current = true
          onPttStart?.()
        }
      }
    }

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.code === 'Space' && spaceHeld.current) {
        spaceHeld.current = false
        e.preventDefault()
        onPttEnd?.()
      }
    }

    const handleWindowBlur = () => { spaceHeld.current = false; onPttEnd?.() }

    window.addEventListener('keydown', handleKeyDown)
    window.addEventListener('keyup', handleKeyUp)
    window.addEventListener('blur', handleWindowBlur)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('keyup', handleKeyUp)
      window.removeEventListener('blur', handleWindowBlur)
    }
  }, [open, pushToTalkMode, onPttStart, onPttEnd])

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
              <span>DIAGNÓSTICO · {audioDiagnostics.mode === 'backend-sr' ? 'MICROFONE DO PC (SPEECHRECOGNITION)' : audioDiagnostics.mode === 'fallback-vad' ? 'VAD DO NAVEGADOR' : 'RECONHECIMENTO DO NAVEGADOR'}</span>
              {audioDiagnostics.note && <div>{audioDiagnostics.note}</div>}
              {audioDiagnostics.mode === 'backend-sr' && (
                <div>
                  Entrada {Math.round(audioDiagnostics.rms || 0)} · Limiar {Math.round(audioDiagnostics.threshold || 0)}{audioDiagnostics.sttMs !== undefined ? ` · Transcrição ${audioDiagnostics.sttMs} ms` : ''}
                </div>
              )}
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

        {(turns.length > 0 || userTranscript) && (
          <div className="live-call-subtitles">
            {turns.map(turn => (
              <div key={turn.id}>
                <p style={{ color: '#e2e8f0' }}><strong style={{ color: '#00daf8' }}>Você: </strong>{turn.user}</p>
                <p style={{ color: '#f8fafc' }}><strong style={{ color: '#f59e0b' }}>Jarvis: </strong>{turn.jarvis || (turn.pending ? '…' : '')}</p>
                <ToolActivity entries={turn.activity} live={turn.pending} />
              </div>
            ))}
            {turns.at(-1)?.user !== userTranscript && userTranscript && (
              <p style={{ color: '#e2e8f0' }}>
                <strong style={{ color: '#00daf8' }}>Você: </strong>
                {userTranscript}
              </p>
            )}
          </div>
        )}

        {onTogglePushToTalk && (
          <div style={{ textAlign: 'center', marginBottom: 14 }}>
            <button
              type="button"
              onClick={onTogglePushToTalk}
              className="live-call-mode-pill"
              title="Alternar entre modo contínuo e segurar para falar"
            >
              <span>{pushToTalkMode ? '🎙️ Push-to-Talk (Segurar ou Espaço)' : '⚡ Contínuo (Hands-Free · 1.8s buffer)'}</span>
            </button>
          </div>
        )}

        <div className="live-call-actions">
          {isSpeaking && onBargeIn ? (
            <button type="button" onClick={onBargeIn} className="live-call-btn-bargein">
              ✋ Interromper
            </button>
          ) : pushToTalkMode ? (
            <button
              type="button"
              onPointerDown={event => { event.currentTarget.setPointerCapture(event.pointerId); onPttStart?.() }}
              onPointerUp={() => onPttEnd?.()}
              onPointerCancel={() => onPttEnd?.()}
              onLostPointerCapture={() => onPttEnd?.()}
              style={{ touchAction: 'none' }}
              className={`live-call-btn-ptt ${isPttActive ? 'active' : 'idle'}`}
            >
              <span>{isPttActive ? '🔴 Gravando… solte para enviar' : '🎙️ Segure para Falar (Espaço)'}</span>
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
          ⚡ <strong>Full-Duplex Barge-in:</strong> Fale ou toque a qualquer momento para interromper o Jarvis.
          {pushToTalkMode
            ? ' Segure a Barra de Espaço ou o botão acima enquanto fala.'
            : ' Buffer de silêncio de 1.8s para formular sua frase sem cortes.'}
        </p>
      </div>
    </div>,
    document.body
  )
}
