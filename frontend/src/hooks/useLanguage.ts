import { FormEvent, useEffect, useRef, useState } from 'react'
import type { ChatMessage, VocabCard, PronunciationAttempt, LanguageDashboard } from '../types'
import { speechLang } from '../utils/speechLang'
import { alignWords } from '../utils/pronunciation'

type SetNotice = (message: string) => void

export type LanguageMode = 'home' | 'vocab' | 'pronunciation' | 'conversation' | 'shadowing' | 'progress' | null

export type PronunciationKind = 'pronunciation' | 'shadowing'

async function readOkJson(result: PromiseSettledResult<Response>) {
  if (result.status !== 'fulfilled' || !result.value.ok) return null
  try {
    return await result.value.json()
  } catch {
    return null
  }
}

export function useLanguage(setNotice: SetNotice) {
  const [dashboard, setDashboard] = useState<LanguageDashboard | null>(null)
  const [dueVocab, setDueVocab] = useState<VocabCard[]>([])
  const [vocabulary, setVocabulary] = useState<VocabCard[]>([])
  const [vocabIndex, setVocabIndex] = useState(0)
  const [vocabBackVisible, setVocabBackVisible] = useState(false)
  const [vocabUndoCount, setVocabUndoCount] = useState(0)
  const [nextVocabDueAt, setNextVocabDueAt] = useState<string | null>(null)
  const [pronunciationHistory, setPronunciationHistory] = useState<PronunciationAttempt[]>([])
  const [langMessages, setLangMessages] = useState<ChatMessage[]>([])
  const [langQuery, setLangQuery] = useState('')
  const [langSessionId, setLangSessionId] = useState('')
  const [langStartedAt, setLangStartedAt] = useState<number | null>(null)

  // Pronunciation state
  const [pronTarget, setPronTarget] = useState('')
  const [pronTranscript, setPronTranscript] = useState('')
  const [pronScore, setPronScore] = useState<number | null>(null)
  const [pronListening, setPronListening] = useState(false)
  const [pronWrongWords, setPronWrongWords] = useState<string[]>([])

  // Vocab add form
  const [newWord, setNewWord] = useState('')
  const [newTranslation, setNewTranslation] = useState('')
  const [newExample, setNewExample] = useState('')
  const [newCategory, setNewCategory] = useState('general')

  // Retorna a nova fila de revisão (ou null se ela não pôde ser carregada).
  const refreshLanguage = async (): Promise<VocabCard[] | null> => {
    const results = await Promise.allSettled([
      fetch('/api/language/dashboard'),
      fetch('/api/language/vocabulary/due'),
      fetch('/api/language/pronunciation'),
      fetch('/api/language/vocabulary'),
    ])
    const [dashData, dueData, pronData, vocabData] = await Promise.all(results.map(readOkJson))
    if (dashData) setDashboard(dashData)
    let dueCards: VocabCard[] | null = null
    if (dueData) {
      dueCards = (dueData.cards || []) as VocabCard[]
      // O cartão revisado sai da fila, então o próximo é sempre o índice 0.
      setDueVocab(dueCards)
      setVocabIndex(0)
      setVocabBackVisible(false)
      setNextVocabDueAt(dueData.next_due_at || null)
    }
    if (pronData) setPronunciationHistory(pronData.history || [])
    if (vocabData) setVocabulary(vocabData.cards || [])
    return dueCards
  }

  const reviewVocab = async (grade: number) => {
    const card = dueVocab[vocabIndex]
    if (!card) return
    const res = await fetch('/api/language/vocabulary/review', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ card_id: card.id, grade }),
    })
    if (res.status === 400) { setNotice('Nota inválida.'); return }
    if (!res.ok) { setNotice('Erro ao revisar vocabulário.'); return }
    setVocabUndoCount(count => count + 1)
    setVocabBackVisible(false)
    refreshLanguage().catch(() => undefined)
  }

  const undoVocabReview = async () => {
    const res = await fetch('/api/language/vocabulary/undo', { method: 'POST' })
    if (res.status === 404) { setVocabUndoCount(0); setNotice('Nada para desfazer.'); return }
    if (res.status === 409) { setNotice('Não foi possível desfazer: o cartão mudou ou foi excluído.'); return }
    if (!res.ok) { setNotice('Erro ao desfazer a revisão.'); return }
    const data = await res.json().catch(() => ({}))
    const cards = await refreshLanguage().catch(() => null)
    const restoredId = data?.card?.id
    const index = cards && restoredId ? cards.findIndex(item => item.id === restoredId) : -1
    setVocabIndex(index >= 0 ? index : 0)
    setVocabBackVisible(false)
    setVocabUndoCount(count => Math.max(0, count - 1))
    setNotice('Revisão desfeita.')
  }

  const deleteVocabulary = async (id: string) => {
    if (!id) return
    const res = await fetch(`/api/language/vocabulary/${encodeURIComponent(id)}/delete`, { method: 'POST' })
    if (!res.ok) { setNotice('Não foi possível excluir a palavra.'); return }
    await refreshLanguage().catch(() => undefined)
    setNotice('Palavra excluída.')
  }

  const addVocabulary = async (e: FormEvent) => {
    e.preventDefault()
    if (!newWord.trim() || !newTranslation.trim()) return
    const res = await fetch('/api/language/vocabulary', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        word: newWord.trim(),
        translation: newTranslation.trim(),
        example: newExample.trim(),
        category: newCategory,
      }),
    })
    if (!res.ok) { setNotice('Erro ao adicionar vocabulário.'); return }
    setNewWord(''); setNewTranslation(''); setNewExample('')
    setNotice('Vocabulário adicionado!')
    refreshLanguage().catch(() => undefined)
  }

  const setCefrLevel = async (level: string) => {
    const response = await fetch('/api/language/level', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ level }),
    })
    if (!response.ok) { setNotice('Falha ao salvar o nível.'); throw new Error('level_update_failed') }
    refreshLanguage().catch(() => undefined)
  }

  // ── Pronunciation via Web Speech API ───────────────────────

  const recognitionRef = useRef<any>(null)
  useEffect(() => () => {
    const recognition = recognitionRef.current
    if (recognition) {
      recognition.onresult = recognition.onerror = recognition.onend = null
      recognition.abort()
    }
  }, [])

  const startPronunciation = (target: string, kind: PronunciationKind = 'pronunciation') => {
    if (!target.trim() || recognitionRef.current) return
    window.speechSynthesis?.cancel()
    setPronTarget(target)
    setPronTranscript('')
    setPronScore(null)
    setPronWrongWords([])
    setPronListening(true)

    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SpeechRecognition) {
      setNotice('Seu navegador não suporta reconhecimento de voz. Use o Chrome.')
      setPronListening(false)
      return
    }

    const recognition = new SpeechRecognition()
    recognitionRef.current = recognition
    recognition.lang = speechLang(dashboard?.target_language)
    recognition.interimResults = false
    recognition.maxAlternatives = 1

    recognition.onresult = async (event: any) => {
      const result = event.results[0][0]
      const transcript = (result.transcript || '').trim()
      const confidence = result.confidence ?? 0
      const words = alignWords(target, transcript)
      const score = words.length ? Math.round(words.reduce((total, word) => total + word.score, 0) / words.length) : 0
      const wrong = words.filter(word => word.score < 80).map(word => word.word)

      setPronTranscript(transcript)
      setPronScore(score)
      setPronWrongWords(wrong)
      setPronListening(false)

      // Save to backend
      try {
        if (kind === 'shadowing') {
          const response = await fetch('/api/language/shadowing', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: target, score, speed: 0.85 }),
          })
          if (!response.ok) throw new Error('save_failed')
        } else {
          const response = await fetch('/api/language/pronunciation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target, transcript, score, confidence, wrong_words: wrong }),
          })
          if (!response.ok) throw new Error('save_failed')
        }
      } catch {
        setNotice('Não foi possível salvar a prática.')
      }
      refreshLanguage().catch(() => undefined)
    }

    recognition.onerror = () => {
      setNotice('Erro no reconhecimento de voz. Tente novamente.')
      setPronListening(false)
    }

    recognition.onspeechend = () => recognition.stop()
    recognition.onend = () => { recognitionRef.current = null; setPronListening(false) }
    try { recognition.start() } catch {
      recognitionRef.current = null
      setPronListening(false)
      setNotice('Não foi possível acessar o microfone.')
    }
  }

  // ── Conversation with AI ───────────────────────────────────

  const sendLanguageMessage = async (e: FormEvent) => {
    e.preventDefault()
    const message = langQuery.trim()
    if (!message) return

    let id = langSessionId
    if (!id) {
      const res = await fetch('/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'Language Practice', type: 'language' }),
      })
      const data = await res.json()
      if (!data.id) { setNotice('Erro ao iniciar sessão de idiomas.'); return }
      id = data.id
      setLangSessionId(id)
    }

    const history = [...langMessages, { role: 'user' as const, content: message }]
    setLangMessages(history)
    setLangQuery('')
    if (langStartedAt === null) setLangStartedAt(Date.now())

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, session_id: id, mode: 'language' }),
      })
      const data = await res.json()
      const reply = data.summary || data.reply || data.error || 'No response.'
      const next = [...history, { role: 'assistant' as const, content: reply }]
      setLangMessages(next)
      await fetch(`/api/sessions/${id}/history`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ history: next }),
      })
    } catch {
      setNotice('Erro ao comunicar com o tutor de idiomas.')
    }
  }

  const endConversation = async () => {
    const firstUserMessage = langMessages.find(message => message.role === 'user')
    if (!firstUserMessage) return
    const startedAt = langStartedAt ?? Date.now()
    const res = await fetch('/api/language/conversation', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        topic: firstUserMessage.content.slice(0, 80),
        corrections: 0,
        new_vocab: [],
        duration_minutes: Math.max(0, Math.floor((Date.now() - startedAt) / 60000)),
      }),
    })
    if (!res.ok) { setNotice('Não foi possível registrar a conversa.'); return }
    setLangMessages([])
    setLangSessionId('')
    setLangStartedAt(null)
    setNotice('Conversa registrada! +25 XP')
    refreshLanguage().catch(() => undefined)
  }

  useEffect(() => {
    refreshLanguage().catch(() => undefined)
  }, [])

  return {
    dashboard, dueVocab, vocabIndex, vocabBackVisible, setVocabBackVisible,
    reviewVocab, undoVocabReview, vocabUndoCount, nextVocabDueAt,
    vocabulary, deleteVocabulary,
    addVocabulary, setCefrLevel,
    newWord, setNewWord, newTranslation, setNewTranslation,
    newExample, setNewExample, newCategory, setNewCategory,
    pronTarget, setPronTarget, pronTranscript, pronScore, pronListening,
    pronWrongWords, startPronunciation,
    pronunciationHistory,
    langMessages, langQuery, setLangQuery, sendLanguageMessage, endConversation,
    langSessionId,
    refreshLanguage,
  }
}

