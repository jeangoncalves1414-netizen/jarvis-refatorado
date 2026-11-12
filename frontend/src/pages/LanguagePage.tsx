import { FormEvent, useEffect, useRef, useState } from 'react'
import type { VocabCard, PronunciationAttempt, LanguageDashboard, ChatMessage } from '../types'
import type { PronunciationKind } from '../hooks/useLanguage'
import { useReviewShortcuts } from '../hooks/useReviewShortcuts'
import { useNextDueRefresh } from '../hooks/useNextDueRefresh'
import { MessageContent } from '../components/MessageContent'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { languageName, speechLang } from '../utils/speechLang'
import { Curriculum } from '../components/study/Curriculum'
import { PronunciationFeedback } from '../components/study/PronunciationFeedback'

const CEFR_LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
const CATEGORIES = ['general', 'travel', 'work', 'food', 'health', 'technology', 'social', 'academic']

const PRONUNCIATION_PHRASES: Record<string, string[]> = {
  A1: [
    'Hello, how are you today?',
    'My name is Jean. Nice to meet you.',
    'I like coffee and tea.',
    'Where is the train station?',
    'Thank you very much.',
  ],
  A2: [
    'I think this restaurant is really good.',
    'She walks to work every morning.',
    'The weather is beautiful today.',
    'I would like a glass of water, please.',
    'Can you help me find the bathroom?',
  ],
  B1: [
    'I have been studying English for three months.',
    'Although the weather was bad, we decided to go out.',
    'The thirty-three thieves thought they thrilled the throne.',
    'She sells seashells by the seashore.',
    'Peter Piper picked a peck of pickled peppers.',
  ],
  B2: [
    'The phenomenon of artificial intelligence has transformed modern society.',
    'Despite the overwhelming evidence, the theory remains controversial.',
    'She thoroughly thought through the methodology before proceeding.',
    'The entrepreneurial ecosystem has grown substantially in recent years.',
    'Psychological research suggests that multilingualism enhances cognitive flexibility.',
  ],
  C1: [
    'Notwithstanding the compelling evidence, the committee remained reluctant to endorse the proposal.',
    'The implications of this unprecedented development warrant a thorough reassessment of our assumptions.',
    'Had the negotiations proceeded differently, a mutually beneficial compromise might have been reached.',
  ],
  C2: [
    'The ostensibly innocuous remark belied a profound ambivalence towards institutional accountability.',
    'Seldom has the interplay between linguistic nuance and cultural identity been so eloquently articulated.',
    'Her perspicacious critique exposed the inherent contradictions underpinning the prevailing orthodoxy.',
  ],
}

type LanguagePageProps = {
  dashboard: LanguageDashboard | null
  dueVocab: VocabCard[]
  vocabIndex: number
  vocabBackVisible: boolean
  setVocabBackVisible: (v: boolean | ((p: boolean) => boolean)) => void
  reviewVocab: (grade: number) => Promise<void>
  undoVocabReview: () => Promise<void>
  vocabUndoCount: number
  nextVocabDueAt: string | null
  refreshLanguage: () => Promise<unknown>
  vocabulary: VocabCard[]
  deleteVocabulary: (id: string) => Promise<void>
  addVocabulary: (e: FormEvent) => Promise<void>
  setCefrLevel: (level: string) => Promise<void>
  newWord: string; setNewWord: (v: string) => void
  newTranslation: string; setNewTranslation: (v: string) => void
  newExample: string; setNewExample: (v: string) => void
  newCategory: string; setNewCategory: (v: string) => void
  pronTarget: string; setPronTarget: (v: string) => void
  pronTranscript: string; pronScore: number | null; pronListening: boolean
  pronWrongWords: string[]
  startPronunciation: (target: string, kind?: PronunciationKind) => void
  pronunciationHistory: PronunciationAttempt[]
  langMessages: ChatMessage[]
  langQuery: string; setLangQuery: (v: string) => void
  sendLanguageMessage: (e: FormEvent) => Promise<void>
  endConversation: () => Promise<void>
  setNotice: (message: string) => void
  initialTab?: LangTab
  // Chamado depois que uma atividade de idiomas foi salva (o painel recarrega), para atualizar XP e estatísticas.
  onStudyActivity?: () => void
}

export type LangTab = 'home' | 'vocab' | 'pronunciation' | 'conversation' | 'shadowing' | 'progress'

const LANG_MODES: { id: LangTab; label: string; icon: string }[] = [
  { id: 'home', label: 'Início', icon: '🏠' },
  { id: 'vocab', label: 'Vocabulário', icon: '📚' },
  { id: 'pronunciation', label: 'Pronúncia', icon: '🎤' },
  { id: 'conversation', label: 'Conversa', icon: '💬' },
  { id: 'shadowing', label: 'Shadowing', icon: '🔊' },
  { id: 'progress', label: 'Progresso', icon: '📊' },
]

function scoreClass(score: number) {
  if (score >= 80) return 'lang-score-good'
  if (score >= 50) return 'lang-score-ok'
  return 'lang-score-bad'
}

function highlightTranscript(transcript: string, wrongWords: string[]) {
  if (!wrongWords.length) return transcript
  const words = transcript.split(/\s+/)
  return words.map((w, i) => {
    const clean = w.toLowerCase().replace(/[.,!?;:'"()\-]/g, '')
    const isWrong = wrongWords.some(ww => ww.toLowerCase() === clean)
    return isWrong
      ? <span key={i} className="lang-wrong-word">{w} </span>
      : <span key={i}>{w} </span>
  })
}

export function LanguagePage(props: LanguagePageProps) {
  const { dashboard } = props
  const level = dashboard?.cefr_level || 'A1'
  const phrases = PRONUNCIATION_PHRASES[level] || PRONUNCIATION_PHRASES.A1
  const currentCard = props.dueVocab[props.vocabIndex]

  const [activeTab, setActiveTab] = useState<LangTab>(props.initialTab || 'home')
  const [shadowIdx, setShadowIdx] = useState(0)
  const [pendingDelete, setPendingDelete] = useState<VocabCard | null>(null)
  const [deleting, setDeleting] = useState(false)
  const speechSequence = useRef(0)
  const [speaking, setSpeaking] = useState(false)
  useEffect(() => {
    speechSequence.current++
    window.speechSynthesis?.cancel()
    setSpeaking(false)
    return () => { speechSequence.current++; window.speechSynthesis?.cancel() }
  }, [activeTab])
  const targetName = languageName(dashboard?.target_language)
  const hasUserMessage = props.langMessages.some(m => m.role === 'user')

  // Toda atividade salva (revisão, desfazer, exclusão, conversa, pronúncia, shadowing) termina em
  // refreshLanguage, que entrega um novo dashboard: é o sinal para atualizar XP e estatísticas.
  const lastDashboard = useRef(dashboard)
  const onStudyActivityRef = useRef(props.onStudyActivity)
  onStudyActivityRef.current = props.onStudyActivity
  useEffect(() => {
    if (lastDashboard.current === dashboard) return
    lastDashboard.current = dashboard
    onStudyActivityRef.current?.()
  }, [dashboard])

  useReviewShortcuts({
    enabled: activeTab === 'vocab' && !!currentCard && !pendingDelete,
    revealed: props.vocabBackVisible,
    onFlip: () => props.setVocabBackVisible(v => !v),
    onGrade: grade => { props.reviewVocab(grade).catch(() => undefined) },
    onUndo: () => { props.undoVocabReview().catch(() => undefined) },
  })
  const nextDueMinutes = useNextDueRefresh(props.nextVocabDueAt, activeTab === 'vocab' && !currentCard, props.refreshLanguage)

  const confirmDelete = async () => {
    if (!pendingDelete) return
    setDeleting(true)
    try {
      await props.deleteVocabulary(pendingDelete.id)
    } finally {
      setDeleting(false)
      setPendingDelete(null)
    }
  }

  const speakPhrase = (text: string, thenRecord = false) => {
    if (!window.speechSynthesis) {
      props.setNotice('Seu navegador não suporta síntese de voz.')
      return
    }
    const sequence = ++speechSequence.current
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = speechLang(dashboard?.target_language)
    utterance.rate = 0.85
    setSpeaking(true)
    utterance.onend = () => {
      if (sequence !== speechSequence.current) return
      setSpeaking(false)
      if (thenRecord) props.startPronunciation(text, activeTab === 'shadowing' ? 'shadowing' : 'pronunciation')
    }
    utterance.onerror = () => { if (sequence === speechSequence.current) { setSpeaking(false); props.setNotice('Não foi possível reproduzir a referência. Tente novamente.') } }
    window.speechSynthesis.speak(utterance)
  }

  return (
    <div className="study-overlay-panel" style={{ maxHeight: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      {/* Toolbar */}
      <nav className="lang-toolbar" aria-label="Modos de idioma">
        {LANG_MODES.map(mode => (
          <button
            key={mode.id}
            type="button"
            className={activeTab === mode.id ? 'lang-mode-active' : ''}
            onClick={() => setActiveTab(mode.id)}
          >
            <span>{mode.icon}</span>
            {mode.label}
          </button>
        ))}
      </nav>

      <div className="lang-panel">
        {/* ── HOME ────────────────────────────────────────── */}
        {activeTab === 'home' && (
          <>
            <p className="eyebrow">APRENDIZADO DE IDIOMAS</p>
            <div className="lang-cefr-select">
              <label>
                Nível CEFR:{' '}
                <select value={level} onChange={e => props.setCefrLevel(e.target.value)}>
                  {CEFR_LEVELS.map(l => <option key={l} value={l}>{l}</option>)}
                </select>
              </label>
            </div>

            <Curriculum level={level} english={(dashboard?.target_language || "en").startsWith("en")} apply={props.setCefrLevel} />
            {dashboard && (
              <>
                <div className="lang-streak">
                  <span>🔥</span>
                  <b>{dashboard.streak}</b>
                  <span style={{ color: '#9696a2', fontSize: 11 }}>dias seguidos</span>
                  <span style={{ marginLeft: 'auto', color: '#abbc7a', fontSize: 11 }}>{dashboard.daily_xp}/{dashboard.daily_goal} XP</span>
                </div>
                <div className="lang-xp-bar">
                  <div className="lang-xp-fill" style={{ width: `${Math.min(100, (dashboard.daily_xp / Math.max(1, dashboard.daily_goal)) * 100)}%` }} />
                </div>

                <div className="lang-dashboard-grid">
                  <div className="lang-stat">
                    <b>{dashboard.due_vocabulary}</b>
                    <small>revisões pendentes</small>
                  </div>
                  <div className="lang-stat">
                    <b>{dashboard.total_xp}</b>
                    <small>XP total</small>
                  </div>
                  <div className="lang-stat">
                    <b>{dashboard.stats?.total_vocab ?? 0}</b>
                    <small>palavras salvas</small>
                  </div>
                </div>
              </>
            )}

            <div className="lang-quick-actions">
              <button type="button" className="primary" onClick={() => setActiveTab('vocab')}>📚 Revisar vocabulário</button>
              <button type="button" onClick={() => setActiveTab('pronunciation')}>🎤 Praticar pronúncia</button>
              <button type="button" onClick={() => setActiveTab('conversation')}>💬 Conversar com tutor</button>
              <button type="button" onClick={() => setActiveTab('shadowing')}>🔊 Shadowing</button>
            </div>
          </>
        )}

        {/* ── VOCABULARY ─────────────────────────────────── */}
        {activeTab === 'vocab' && (
          <>
            <p className="eyebrow">VOCABULÁRIO · REVISÃO ESPAÇADA (FSRS)</p>
            {currentCard ? (
              <>
                <button type="button" className="lang-card" onClick={() => props.setVocabBackVisible((v: boolean) => !v)}>
                  <small>{props.vocabBackVisible ? 'TRADUÇÃO' : 'PALAVRA'} · clique para virar</small>
                  <strong>{props.vocabBackVisible ? currentCard.translation : currentCard.word}</strong>
                  {props.vocabBackVisible && currentCard.example && (
                    <span style={{ color: '#9696a2', fontSize: 12, fontStyle: 'italic' }}>{currentCard.example}</span>
                  )}
                  {currentCard.phonetic && props.vocabBackVisible && (
                    <span style={{ color: '#abbc7a', fontSize: 11 }}>/{currentCard.phonetic}/</span>
                  )}
                </button>
                <div className="grade-actions">
                  <button type="button" onClick={() => props.reviewVocab(0)}><kbd className="review-key">1</kbd> Errei</button>
                  <button type="button" onClick={() => props.reviewVocab(1)}><kbd className="review-key">2</kbd> Difícil</button>
                  <button type="button" onClick={() => props.reviewVocab(2)}><kbd className="review-key">3</kbd> Bom</button>
                  <button type="button" onClick={() => props.reviewVocab(3)}><kbd className="review-key">4</kbd> Fácil</button>
                </div>
              </>
            ) : (
              <>
                <p className="empty-state">Nenhum vocabulário pendente para revisão agora. 🎉</p>
                {nextDueMinutes !== null && <p className="review-next-due">Próximo cartão em {nextDueMinutes} min</p>}
              </>
            )}
            <div className="review-footer">
              <span>{currentCard ? `${props.dueVocab.length} pendentes · Espaço vira · 1-4 avaliam` : ''}</span>
              <button
                type="button"
                className="review-undo"
                onClick={() => { props.undoVocabReview().catch(() => undefined) }}
                disabled={props.vocabUndoCount === 0}
                title="Desfazer última revisão (Z)"
              >
                ↩ Desfazer
              </button>
            </div>

            <hr style={{ border: 'none', borderTop: '1px solid #292933', margin: '20px 0' }} />
            <p className="eyebrow">ADICIONAR VOCABULÁRIO</p>
            <form className="lang-add-form" onSubmit={props.addVocabulary}>
              <input value={props.newWord} onChange={e => props.setNewWord(e.target.value)} placeholder={`Palavra em ${targetName}`} />
              <input value={props.newTranslation} onChange={e => props.setNewTranslation(e.target.value)} placeholder="Tradução" />
              <input value={props.newExample} onChange={e => props.setNewExample(e.target.value)} placeholder="Frase de exemplo (opcional)" />
              <select value={props.newCategory} onChange={e => props.setNewCategory(e.target.value)}>
                {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
              <button type="submit">Adicionar</button>
            </form>

            <p className="eyebrow" style={{ marginTop: 20 }}>MINHAS PALAVRAS</p>
            {props.vocabulary.length ? (
              <div className="lang-vocab-list">
                {props.vocabulary.map(card => (
                  <div key={card.id} className="lang-vocab-row">
                    <span><b>{card.word}</b> — {card.translation}</span>
                    <button type="button" onClick={() => setPendingDelete(card)} aria-label={`Excluir ${card.word}`}>Excluir</button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="empty-state">Nenhuma palavra salva ainda.</p>
            )}
          </>
        )}

        {/* ── PRONUNCIATION ──────────────────────────────── */}
        {activeTab === 'pronunciation' && (
          <>
            <p className="eyebrow">PRONÚNCIA · NÍVEL {level}</p>
            <div className="lang-phrase-list">
              {phrases.map((phrase, i) => (
                <button
                  key={i}
                  type="button"
                  className={`lang-phrase-btn${props.pronTarget === phrase ? ' lang-mode-active' : ''}`}
                  onClick={() => { props.setPronTarget(phrase); speakPhrase(phrase) }}
                >
                  {phrase}
                </button>
              ))}
            </div>

            <input
              style={{ marginTop: 10 }}
              value={props.pronTarget}
              onChange={e => props.setPronTarget(e.target.value)}
              placeholder="Ou digite uma frase personalizada…"
            />

            <div className="lang-record-area">
              <button
                type="button"
                className={`lang-record-btn${props.pronListening ? ' listening' : ''}`}
                onClick={() => props.startPronunciation(props.pronTarget)}
                disabled={!props.pronTarget || props.pronListening}
                title={props.pronListening ? 'Ouvindo…' : 'Gravar pronúncia'}
              >
                {props.pronListening ? '⏺' : '🎙'}
              </button>
              <span style={{ color: '#9696a2', fontSize: 12 }}>
                {props.pronListening ? 'Fale agora…' : 'Clique para gravar'}
              </span>
              {props.pronTarget && (
                <button
                  type="button"
                  className="lang-play-btn"
                  onClick={() => speakPhrase(props.pronTarget)}
                >
                  ▶ Ouvir
                </button>
              )}
            </div>

            {props.pronScore !== null && (
              <div className="lang-score">
                <PronunciationFeedback target={props.pronTarget} transcript={props.pronTranscript} onRepeat={text => speakPhrase(text, true)} />
                <span className={`lang-score-value ${scoreClass(props.pronScore)}`}>
                  {props.pronScore}%
                </span>
                <span style={{ color: '#9696a2', fontSize: 12, marginLeft: 8 }}>
                  {props.pronScore >= 80 ? 'Excelente!' : props.pronScore >= 50 ? 'Bom, continue praticando.' : 'Tente novamente.'}
                </span>
                <div className="lang-transcript">
                  <small style={{ color: '#6e6e7a' }}>Você disse:</small>
                  <p style={{ margin: '4px 0 0' }}>
                    {highlightTranscript(props.pronTranscript, props.pronWrongWords)}
                  </p>
                </div>
                {props.pronWrongWords.length > 0 && (
                  <p style={{ color: '#f44336', fontSize: 11, marginTop: 6 }}>
                    Palavras para melhorar: {props.pronWrongWords.join(', ')}
                  </p>
                )}
              </div>
            )}

            {props.pronunciationHistory.length > 0 && (
              <>
                <p className="eyebrow" style={{ marginTop: 18 }}>HISTÓRICO RECENTE</p>
                <div className="lang-history">
                  {props.pronunciationHistory.slice(0, 8).map(a => (
                    <div key={a.id} className="lang-history-item">
                      <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.target}</span>
                      <span className={scoreClass(a.score)}>{a.score}%</span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </>
        )}

        {/* ── CONVERSATION ───────────────────────────────── */}
        {activeTab === 'conversation' && (
          <>
            <p className="eyebrow">CONVERSA COM TUTOR · {level}</p>
            <div className="study-chat-history">
              {props.langMessages.length ? props.langMessages.map((m, i) => (
                <div className={`study-chat-message ${m.role}`} key={`${m.role}-${i}`}>
                  <b>{m.role === 'user' ? 'VOCÊ' : 'TUTOR'}</b>
                  <MessageContent text={m.content} />
                </div>
              )) : <span>Converse em {targetName} com o tutor de idiomas. Ele adapta ao seu nível {level}.</span>}
            </div>
            <form className="study-tutor-form" onSubmit={props.sendLanguageMessage}>
              <input
                value={props.langQuery}
                onChange={e => props.setLangQuery(e.target.value)}
                placeholder={`Escreva em ${targetName} ou português…`}
              />
              <button type="submit">Enviar</button>
            </form>
            <button
              type="button"
              className="lang-end-conversation"
              disabled={!hasUserMessage}
              onClick={() => { props.endConversation().catch(() => undefined) }}
            >
              Encerrar conversa
            </button>
          </>
        )}

        {/* ── SHADOWING ──────────────────────────────────── */}
        {activeTab === 'shadowing' && (
          <>
            <p className="eyebrow">SHADOWING · NÍVEL {level}</p>
            <p style={{ color: '#9696a2', fontSize: 12 }}>
              Ouça a frase, depois repita imitando a pronúncia e o ritmo.
            </p>

            <div className="lang-shadowing-phrase">
              {phrases[shadowIdx % phrases.length]}
            </div>

            <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginTop: 14 }}>
              <button
                type="button"
                className="lang-play-btn"
                onClick={() => speakPhrase(phrases[shadowIdx % phrases.length])}
              >
                ▶ Ouvir
              </button>
              <button
                type="button"
                className={`lang-record-btn${props.pronListening ? ' listening' : ''}`}
                style={{ width: 40, height: 40, fontSize: 16 }}
                onClick={() => {
                  const phrase = phrases[shadowIdx % phrases.length]
                  props.setPronTarget(phrase)
                  speakPhrase(phrase, true)
                }}
                disabled={props.pronListening || speaking}
                title="Ouvir referência e depois gravar shadowing"
              >
                {props.pronListening ? '⏺' : '🎙'}
              </button>
              <button
                type="button"
                className="lang-play-btn"
                onClick={() => setShadowIdx(i => i + 1)}
              >
                Próxima ▶
              </button>
            </div>

            {props.pronScore !== null && (
              <div className="lang-score" style={{ textAlign: 'center' }}>
                <PronunciationFeedback target={props.pronTarget} transcript={props.pronTranscript} onRepeat={text => speakPhrase(text, true)} />
                <span className={`lang-score-value ${scoreClass(props.pronScore)}`}>{props.pronScore}%</span>
                <div className="lang-transcript">
                  <p style={{ margin: '4px 0 0' }}>
                    {highlightTranscript(props.pronTranscript, props.pronWrongWords)}
                  </p>
                </div>
              </div>
            )}
          </>
        )}

        {/* ── PROGRESS ───────────────────────────────────── */}
        {activeTab === 'progress' && (
          <>
            <p className="eyebrow">PROGRESSO</p>
            {dashboard && (
              <>
                <div className="lang-dashboard-grid">
                  <div className="lang-stat">
                    <b>{level}</b>
                    <small>nível CEFR</small>
                  </div>
                  <div className="lang-stat">
                    <b>{dashboard.streak}</b>
                    <small>dias seguidos</small>
                  </div>
                  <div className="lang-stat">
                    <b>{dashboard.total_xp}</b>
                    <small>XP total</small>
                  </div>
                  <div className="lang-stat">
                    <b>{dashboard.stats?.total_vocab ?? 0}</b>
                    <small>palavras</small>
                  </div>
                  <div className="lang-stat">
                    <b>{dashboard.stats?.pronunciation_sessions ?? 0}</b>
                    <small>pronúncias</small>
                  </div>
                  <div className="lang-stat">
                    <b>{dashboard.stats?.conversation_sessions ?? 0}</b>
                    <small>conversas</small>
                  </div>
                  <div className="lang-stat">
                    <b>{dashboard.stats?.shadowing_sessions ?? 0}</b>
                    <small>shadowings</small>
                  </div>
                </div>

                {dashboard.weak_phonemes.length > 0 && (
                  <div style={{ marginTop: 16 }}>
                    <p className="eyebrow">FONEMAS PARA MELHORAR</p>
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
                      {dashboard.weak_phonemes.map(p => (
                        <span key={p} style={{ padding: '4px 8px', borderRadius: 6, background: '#2a1a1a', color: '#f44336', fontSize: 11 }}>/{p}/</span>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}

            {props.pronunciationHistory.length > 0 && (
              <>
                <p className="eyebrow" style={{ marginTop: 20 }}>HISTÓRICO DE PRONÚNCIA</p>
                <div className="lang-history">
                  {props.pronunciationHistory.map(a => (
                    <div key={a.id} className="lang-history-item">
                      <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.target}</span>
                      <span className={scoreClass(a.score)}>{a.score}%</span>
                      {a.date && <span>{new Date(a.date).toLocaleDateString('pt-BR')}</span>}
                    </div>
                  ))}
                </div>
              </>
            )}
          </>
        )}
      </div>
      {pendingDelete && (
        <ConfirmDialog
          title="Excluir palavra?"
          message={`“${pendingDelete.word}” e o agendamento de revisão serão removidos. O histórico de revisões continua nas estatísticas.`}
          confirmLabel="Excluir"
          danger
          busy={deleting}
          onConfirm={() => { confirmDelete().catch(() => undefined) }}
          onCancel={() => setPendingDelete(null)}
        />
      )}
    </div>
  )
}
