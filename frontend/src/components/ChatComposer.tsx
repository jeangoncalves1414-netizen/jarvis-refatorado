import {
  useEffect,
  useRef,
  useState,
  useCallback,
  type ChangeEvent,
  type KeyboardEvent,
  type MouseEvent,
} from 'react'
import { Phone } from 'lucide-react'
import { PromptSuggestions } from './PromptSuggestions'
import { isMobileStandalone } from '../hooks/useDirectChat'

export type ChatMode = 'general' | 'planning' | 'research' | 'coder' | 'browser' | 'react'

export type PersonaMode = 'general' | 'dev' | 'analyst' | 'tutor' | 'creative'

const PERSONAS: { id: PersonaMode; emoji: string; label: string; description: string }[] = [
  { id: 'general',  emoji: '🤖', label: 'Jarvis',      description: 'Assistente geral inteligente' },
  { id: 'dev',      emoji: '💻', label: 'Dev Hacker',  description: 'Especialista em código, debug e arquitetura' },
  { id: 'analyst',  emoji: '📊', label: 'Analista',    description: 'Dados, relatórios e análises profundas' },
  { id: 'tutor',    emoji: '🎓', label: 'Tutor',       description: 'Explica com método Feynman e flashcards' },
  { id: 'creative', emoji: '🎨', label: 'Criativo',    description: 'Copywriting, storytelling e brainstorm' },
]

type ChatAttachment = {
  name: string
  dataUrl: string
}

type CommandSuggestion = {
  icon: string
  label: string
  description: string
  prefix: string
}

type ChatComposerProps = {
  value: string
  loading: boolean
  mode: ChatMode
  persona?: PersonaMode
  attachment: ChatAttachment | null
  onChange: (value: string) => void
  onModeChange: (mode: ChatMode) => void
  onPersonaChange?: (persona: PersonaMode) => void
  onAttachment: (file: File) => void
  onClearAttachment: () => void
  onSubmit: () => void
  onVoice: () => void
  onScreen: () => void
  onCinema: () => void
  onOpenLiveCall: () => void
  recording: boolean
  racingMode?: boolean
  onRacingModeChange?: (racing: boolean) => void
}

const PLACEHOLDERS = [
  'Pergunte algo ao Jarvis…',
  'Qual a temperatura em São Paulo agora?',
  'Coloca o filme Matrix no Jarvis Cinema…',
  'Planejar minha rotina de estudos para o ENEM…',
  'Como está a cotação do Dólar hoje?',
  'Analisar screenshot da tela com visão IA…',
]

const COMMAND_SUGGESTIONS: CommandSuggestion[] = [
  { icon: '🌤️', label: 'Clima', description: 'Temperatura e tempo de qualquer cidade', prefix: '/clima ' },
  { icon: '🎬', label: 'Cinema', description: 'Assistir filme ou série no Jarvis Cinema', prefix: '/cinema ' },
  { icon: '🔍', label: 'Pesquisa', description: 'Busca profunda na web com fontes atuais', prefix: '/pesquisa ' },
  { icon: '🧠', label: 'Planejar', description: 'Raciocínio e plano estruturado por etapas', prefix: '/planejar ' },
  { icon: '👁️', label: 'Visão', description: 'Análise visual de tela ou imagem capturada', prefix: '/visao ' },
  { icon: '🎓', label: 'Estudos', description: 'Dúvidas de matérias, flashcards, ENEM', prefix: '/estudos ' },
]

// Splits a string into individual characters for the animated placeholder
function PlaceholderLetters({ text, key: _key }: { text: string; key: string }) {
  return (
    <span className="cc-ph-word">
      {text.split('').map((char, i) => (
        <span
          key={i}
          className="cc-ph-letter"
          style={{ animationDelay: `${i * 22}ms` }}
        >
          {char === ' ' ? '\u00A0' : char}
        </span>
      ))}
    </span>
  )
}

export function ChatComposer({
  value,
  loading,
  mode,
  persona: currentPersona = 'general',
  attachment,
  onChange,
  onModeChange,
  onPersonaChange,
  onAttachment,
  onClearAttachment,
  onSubmit,
  onVoice,
  onScreen,
  onCinema,
  onOpenLiveCall,
  recording,
  racingMode = false,
  onRacingModeChange,
}: ChatComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const paletteRef = useRef<HTMLDivElement>(null)
  const wrapperRef = useRef<HTMLDivElement>(null)
  const glowRef = useRef<HTMLDivElement>(null)
  const personaPickerRef = useRef<HTMLDivElement>(null)

  const [placeholderIndex, setPlaceholderIndex] = useState(0)
  const [phKey, setPhKey] = useState('0')
  const [isFocused, setIsFocused] = useState(false)
  const [showCommandPalette, setShowCommandPalette] = useState(false)
  const [activeSuggestion, setActiveSuggestion] = useState(0)
  const [showPersonaPicker, setShowPersonaPicker] = useState(false)

  const activePersona = PERSONAS.find(p => p.id === currentPersona) || PERSONAS[0]

  const canSubmit = Boolean(value.trim() || attachment) && !loading
  const [isMobileScreen, setIsMobileScreen] = useState(() => (typeof window !== 'undefined' ? window.innerWidth <= 768 : false))
  useEffect(() => {
    const onResize = () => setIsMobileScreen(window.innerWidth <= 768)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])
  const compact = isMobileStandalone() || isMobileScreen

  // Cycle animated placeholder
  useEffect(() => {
    if (compact || isFocused || value || attachment) return
    const interval = setInterval(() => {
      setPlaceholderIndex((prev) => (prev + 1) % PLACEHOLDERS.length)
      setPhKey(String(Date.now()))
    }, 4000)
    return () => clearInterval(interval)
  }, [isFocused, value, attachment, compact])

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) return
    const newHeight = Math.min(Math.max(textarea.scrollHeight, 52), 180)
    textarea.style.height = `${newHeight}px`
  }, [value])

  // Command palette detection
  useEffect(() => {
    if (value.startsWith('/') && !value.includes(' ')) {
      setShowCommandPalette(true)
      const idx = COMMAND_SUGGESTIONS.findIndex((c) => c.prefix.startsWith(value))
      setActiveSuggestion(idx >= 0 ? idx : 0)
    } else {
      setShowCommandPalette(false)
    }
  }, [value])

  // Click outside palette
  useEffect(() => {
    const handler = (e: globalThis.MouseEvent) => {
      if (paletteRef.current && !paletteRef.current.contains(e.target as Node)) {
        setShowCommandPalette(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [paletteRef])

  // Mouse-tracking glow effect
  const handleMouseMove = useCallback((e: MouseEvent<HTMLDivElement>) => {
    const glow = glowRef.current
    const wrapper = wrapperRef.current
    if (!glow || !wrapper || !isFocused) return
    const rect = wrapper.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    glow.style.left = `${x - 200}px`
    glow.style.top = `${y - 200}px`
    glow.style.opacity = '1'
  }, [isFocused])

  const handleMouseLeave = useCallback(() => {
    if (glowRef.current) glowRef.current.style.opacity = '0'
  }, [])

  const selectSuggestion = (index: number) => {
    const cmd = COMMAND_SUGGESTIONS[index]
    if (cmd) {
      if (cmd.prefix === '/planejar ') onModeChange('planning')
      else if (cmd.prefix === '/pesquisa ') onModeChange('research')
      else if (cmd.prefix === '/cinema ') onCinema()
      else if (cmd.prefix === '/visao ') onScreen()
      onChange(cmd.prefix)
    }
    setShowCommandPalette(false)
  }

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (showCommandPalette) {
      if (event.key === 'ArrowDown') {
        event.preventDefault()
        setActiveSuggestion((prev) => (prev < COMMAND_SUGGESTIONS.length - 1 ? prev + 1 : 0))
        return
      }
      if (event.key === 'ArrowUp') {
        event.preventDefault()
        setActiveSuggestion((prev) => (prev > 0 ? prev - 1 : COMMAND_SUGGESTIONS.length - 1))
        return
      }
      if (event.key === 'Enter' || event.key === 'Tab') {
        event.preventDefault()
        selectSuggestion(activeSuggestion)
        return
      }
      if (event.key === 'Escape') {
        setShowCommandPalette(false)
        return
      }
    }
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      if (canSubmit) onSubmit()
    }
  }

  const onFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) onAttachment(file)
    event.target.value = ''
  }

  return (
    <div
      ref={wrapperRef}
      className={`cc-wrapper${isFocused ? ' cc-focused' : ''}`}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
    >
      {/* Ambient background orbs */}
      <div className="cc-orbs" aria-hidden="true">
        <div className="cc-orb cc-orb-violet" />
        <div className="cc-orb cc-orb-indigo" />
        <div className="cc-orb cc-orb-fuchsia" />
      </div>

      {/* Mouse-tracking glow */}
      <div ref={glowRef} className="cc-mouse-glow" aria-hidden="true" />

      {/* Command Palette */}
      {showCommandPalette && (
        <div ref={paletteRef} className="cc-palette">
          <div className="cc-palette-header">
            <span>⌘ Comandos do Jarvis</span>
            <small>↑ ↓ Enter</small>
          </div>
          <div className="cc-palette-list">
            {COMMAND_SUGGESTIONS.map((cmd, idx) => (
              <button
                key={cmd.prefix}
                type="button"
                className={`cc-palette-item${idx === activeSuggestion ? ' cc-palette-item-active' : ''}`}
                onClick={() => selectSuggestion(idx)}
                onMouseEnter={() => setActiveSuggestion(idx)}
              >
                <span className="cc-palette-icon">{cmd.icon}</span>
                <span className="cc-palette-info">
                  <strong className="cc-palette-label">{cmd.label}</strong>
                  <span className="cc-palette-desc">{cmd.description}</span>
                </span>
                <code className="cc-palette-prefix">{cmd.prefix.trim()}</code>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Prompt Suggestions */}
      {!compact && !value && !attachment && (
        <PromptSuggestions onSelect={(prompt) => onChange(prompt)} />
      )}

      {/* Attachment bar */}
      {attachment && (
        <div className="cc-attachment">
          <img src={attachment.dataUrl} alt="Prévia" className="cc-attachment-img" />
          <span className="cc-attachment-name">{attachment.name}</span>
          <button type="button" onClick={onClearAttachment} className="cc-attachment-rm" title="Remover">✕</button>
        </div>
      )}

      {/* Main card */}
      <div className="cc-card">
        {/* Focus glow ring */}
        <div className={`cc-ring${isFocused ? ' cc-ring-active' : ''}`} aria-hidden="true" />

        {/* Voice recording wave visualizer overlay */}
        {recording && (
          <div className="cc-voice-wave-overlay">
            <span className="cc-wave-bar bar-1" />
            <span className="cc-wave-bar bar-2" />
            <span className="cc-wave-bar bar-3" />
            <span className="cc-wave-bar bar-4" />
            <span className="cc-wave-bar bar-5" />
            <span className="cc-voice-status">Ouvindo voz… Fale com o Jarvis</span>
          </div>
        )}

        {/* Textarea + animated placeholder */}
        <div className={`cc-input-area${compact ? ' cc-input-area-compact' : ''}`}>
          {/* Animated placeholder (visible only when empty + unfocused) */}
          {!compact && !value && !isFocused && !recording && (
            <div className="cc-placeholder" aria-hidden="true">
              <PlaceholderLetters text={PLACEHOLDERS[placeholderIndex]} key={phKey} />
            </div>
          )}
          <textarea
            ref={textareaRef}
            className="cc-textarea"
            value={value}
            rows={1}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={onKeyDown}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder={compact ? 'Mensagem para o Jarvis…' : ''}
            aria-label="Mensagem para o Jarvis"
            enterKeyHint="send"
            autoCapitalize="sentences"
            autoCorrect="on"
          />
          {compact && (
            <button
              type="button"
              className={`cc-send cc-send-inline${canSubmit ? ' cc-send-active' : ''}${loading ? ' cc-send-loading' : ''}`}
              disabled={!canSubmit && !loading}
              title={loading ? 'Processando…' : 'Enviar'}
              onClick={() => { if (canSubmit) onSubmit() }}
            >
              {loading ? (
                <span className="cc-spinner" />
              ) : (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="12" y1="19" x2="12" y2="5"/>
                  <polyline points="5 12 12 5 19 12"/>
                </svg>
              )}
            </button>
          )}
        </div>


        {/* Toolbar */}
        <div className="cc-toolbar">
          {/* Left cluster */}
          <div className="cc-toolbar-left">
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              className="cc-file-input"
              onChange={onFileChange}
            />
            <button
              type="button"
              className="cc-icon-btn"
              title="Anexar Imagem"
              onClick={() => fileRef.current?.click()}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
              </svg>
            </button>

            {/* / Command trigger */}
            <button
              type="button"
              className={`cc-icon-btn${showCommandPalette ? ' cc-icon-btn-active' : ''}`}
              title="Comandos (ou digite /)"
              onClick={() => setShowCommandPalette((p) => !p)}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                <path d="M18 3a3 3 0 0 0-3 3v12a3 3 0 0 0 3 3 3 3 0 0 0 3-3 3 3 0 0 0-3-3H6a3 3 0 0 0-3 3 3 3 0 0 0 3 3 3 3 0 0 0 3-3V6a3 3 0 0 0-3-3 3 3 0 0 0-3 3 3 3 0 0 0 3 3h12a3 3 0 0 0 3-3 3 3 0 0 0-3-3z"/>
              </svg>
            </button>

            {/* Think toggle */}
            <button
              type="button"
              className={`cc-pill${mode === 'planning' ? ' cc-pill-think' : ''}`}
              onClick={() => onModeChange(mode === 'planning' ? 'general' : 'planning')}
              title="Modo Raciocínio (Think)"
            >
              <span>🧠</span>
              <span className="cc-pill-label">Think</span>
              {mode === 'planning' && <span className="cc-pill-dot" />}
            </button>

            {!compact && (
              <>
            {/* Deep Search toggle */}
            <button
              type="button"
              className={`cc-pill${mode === 'research' ? ' cc-pill-search' : ''}`}
              onClick={() => onModeChange(mode === 'research' ? 'general' : 'research')}
              title="Pesquisa Profunda na Web (Research Subagent)"
            >
              <span>🔬</span>
              <span className="cc-pill-label">Research</span>
              {mode === 'research' && <span className="cc-pill-dot cc-pill-dot-blue" />}
            </button>

            {/* Coder Agent Mode */}
            <button
              type="button"
              className={`cc-pill${mode === 'coder' ? ' cc-pill-think' : ''}`}
              onClick={() => onModeChange(mode === 'coder' ? 'general' : 'coder')}
              title="Coder Subagent (Validação Sintática AST e Debug)"
              style={mode === 'coder' ? { borderColor: 'rgba(34,197,94,0.6)', color: '#4ade80', background: 'rgba(34,197,94,0.12)' } : {}}
            >
              <span>💻</span>
              <span className="cc-pill-label">Coder</span>
              {mode === 'coder' && <span className="cc-pill-dot" style={{ background: '#22c55e' }} />}
            </button>

            {/* Racing Mode toggle (G0DM0D3 Multi-LLM Racing Engine) */}
            <button
              type="button"
              className={`cc-pill${racingMode ? ' cc-pill-think' : ''}`}
              onClick={() => onRacingModeChange?.(!racingMode)}
              title="Modo Racing (Multi-LLM Corrida em Paralelo)"
              style={racingMode ? { borderColor: 'rgba(234,179,8,0.6)', color: '#eab308', background: 'rgba(234,179,8,0.12)' } : {}}
            >
              <span>⚡</span>
              <span className="cc-pill-label">Racing</span>
              {racingMode && <span className="cc-pill-dot" style={{ background: '#eab308' }} />}
            </button>
              </>
            )}

            {/* Persona Selector (G0DM0D3-inspired) */}
            <div ref={personaPickerRef} style={{ position: 'relative' }}>
              <button
                type="button"
                className="cc-pill"
                onClick={() => setShowPersonaPicker(p => !p)}
                title="Selecionar Persona do Jarvis"
                style={currentPersona !== 'general' ? { borderColor: 'rgba(168,85,247,0.6)', color: '#c084fc' } : {}}
              >
                <span>{activePersona.emoji}</span>
                <span className="cc-pill-label">{activePersona.label}</span>
                {currentPersona !== 'general' && <span className="cc-pill-dot" style={{ background: '#a855f7' }} />}
              </button>
              {showPersonaPicker && (
                <div style={{
                  position: 'absolute',
                  bottom: 'calc(100% + 8px)',
                  left: 0,
                  background: 'rgba(10,12,24,0.97)',
                  border: '1px solid rgba(168,85,247,0.35)',
                  borderRadius: 10,
                  minWidth: 220,
                  backdropFilter: 'blur(16px)',
                  boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
                  zIndex: 100,
                  overflow: 'hidden',
                }}>
                  <div style={{ padding: '8px 12px 6px', fontSize: 10, color: '#a855f7', fontWeight: 700, letterSpacing: 1, borderBottom: '1px solid rgba(168,85,247,0.15)' }}>
                    ⚡ PERSONA DO JARVIS
                  </div>
                  {PERSONAS.map(p => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => { onPersonaChange?.(p.id); setShowPersonaPicker(false) }}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 10, width: '100%',
                        padding: '8px 14px', background: currentPersona === p.id ? 'rgba(168,85,247,0.12)' : 'transparent',
                        border: 'none', cursor: 'pointer', color: currentPersona === p.id ? '#c084fc' : '#ccc',
                        fontSize: 13, textAlign: 'left', transition: 'background 0.15s',
                      }}
                    >
                      <span style={{ fontSize: 16 }}>{p.emoji}</span>
                      <span style={{ display: 'flex', flexDirection: 'column' }}>
                        <strong style={{ fontSize: 12 }}>{p.label}</strong>
                        <span style={{ fontSize: 10, opacity: 0.6 }}>{p.description}</span>
                      </span>
                      {currentPersona === p.id && <span style={{ marginLeft: 'auto', color: '#a855f7', fontSize: 12 }}>✓</span>}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right cluster */}
          <div className="cc-toolbar-right">
            {!compact && (
              <button type="button" className="cc-icon-btn" title="Analisar Tela" onClick={onScreen}>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                  <circle cx="12" cy="12" r="3"/>
                </svg>
              </button>
            )}

            <button
              type="button"
              className={`cc-icon-btn${recording ? ' cc-recording' : ''}`}
              title={recording ? 'Parar gravação' : 'Falar com Jarvis'}
              onClick={onVoice}
            >
              {recording ? (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>
              ) : (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                  <line x1="12" y1="19" x2="12" y2="23"/>
                  <line x1="8" y1="23" x2="16" y2="23"/>
                </svg>
              )}
            </button>

            {!compact && (
              <button type="button" className="cc-icon-btn" title="Jarvis Cinema" onClick={onCinema}>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="23 7 16 12 23 17 23 7"/>
                  <rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>
                </svg>
              </button>
            )}

            <button type="button" className="cc-icon-btn" title="Abrir ligação" onClick={onOpenLiveCall}>
              <Phone size={15} strokeWidth={1.8} />
            </button>

            {!compact && (
              <button
                type="button"
                className={`cc-send${canSubmit ? ' cc-send-active' : ''}${loading ? ' cc-send-loading' : ''}`}
                disabled={!canSubmit && !loading}
                title={loading ? 'Processando…' : 'Enviar (Enter)'}
                onClick={() => { if (canSubmit) onSubmit() }}
              >
                {loading ? (
                  <span className="cc-spinner" />
                ) : (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="12" y1="19" x2="12" y2="5"/>
                    <polyline points="5 12 12 5 19 12"/>
                  </svg>
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
