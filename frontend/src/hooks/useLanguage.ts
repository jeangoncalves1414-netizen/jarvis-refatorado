import { FormEvent, useEffect, useState } from 'react'
import type { ChatMessage, VocabCard, PronunciationAttempt, LanguageDashboard } from '../types'

type SetNotice = (message: string) => void

export type LanguageMode = 'home' | 'vocab' | 'pronunciation' | 'conversation' | 'shadowing' | 'progress' | null

export function useLanguage(setNotice: SetNotice) {
  const [dashboard, setDashboard] = useState<LanguageDashboard | null>(null)
  const [dueVocab, setDueVocab] = useState<VocabCard[]>([])
  const [vocabIndex, setVocabIndex] = useState(0)
  const [vocabBackVisible, setVocabBackVisible] = useState(false)
  const [pronunciationHistory, setPronunciationHistory] = useState<PronunciationAttempt[]>([])
  const [langMessages, setLangMessages] = useState<ChatMessage[]>([])
  const [langQuery, setLangQuery] = useState('')
  const [langSessionId, setLangSessionId] = useState('')

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

  const refreshLanguage = async () => {
    const [dashRes, dueRes, pronRes] = await Promise.all([
      fetch('/api/language/dashboard'),
      fetch('/api/language/vocabulary/due'),
      fetch('/api/language/pronunciation'),
    ])
    const [dashData, dueData, pronData] = await Promise.all([
      dashRes.json(), dueRes.json(), pronRes.json(),
    ])
    setDashboard(dashData)
    setDueVocab(dueData.cards || [])
    setPronunciationHistory(pronData.history || [])
  }

  const reviewVocab = async (grade: number) => {
    const card = dueVocab[vocabIndex]
    if (!card) return
    const res = await fetch('/api/language/vocabulary/review', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ card_id: card.id, grade }),
    })
    if (!res.ok) { setNotice('Erro ao revisar vocabulário.'); return }
    setVocabIndex(prev => prev + 1)
    setVocabBackVisible(false)
    refreshLanguage().catch(() => undefined)
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
    await fetch('/api/language/level', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ level }),
    })
    refreshLanguage().catch(() => undefined)
  }

  // ── Pronunciation via Web Speech API ───────────────────────

  const levenshteinSimilarity = (a: string, b: string): number => {
    const la = a.toLowerCase().replace(/[.,!?;:'"()\-]/g, '').trim()
    const lb = b.toLowerCase().replace(/[.,!?;:'"()\-]/g, '').trim()
    if (!la || !lb) return 0
    const longer = la.length > lb.length ? la : lb
    const shorter = la.length > lb.length ? lb : la
    if (longer.length === 0) return 1
    const matrix: number[][] = []
    for (let i = 0; i <= shorter.length; i++) {
      matrix[i] = [i]
      for (let j = 1; j <= longer.length; j++) {
        if (i === 0) { matrix[0][j] = j; continue }
        matrix[i][j] = shorter[i - 1] === longer[j - 1]
          ? matrix[i - 1][j - 1]
          : Math.min(matrix[i - 1][j - 1] + 1, matrix[i][j - 1] + 1, matrix[i - 1][j] + 1)
      }
    }
    const dist = matrix[shorter.length][longer.length]
    return (longer.length - dist) / longer.length
  }

  const findWrongWords = (target: string, transcript: string): string[] => {
    const targetWords = target.toLowerCase().replace(/[.,!?;:'"()\-]/g, '').split(/\s+/).filter(Boolean)
    const spokenWords = transcript.toLowerCase().replace(/[.,!?;:'"()\-]/g, '').split(/\s+/).filter(Boolean)
    const wrong: string[] = []
    for (const tw of targetWords) {
      if (!spokenWords.includes(tw)) wrong.push(tw)
    }
    return wrong
  }

  const startPronunciation = (target: string) => {
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
    recognition.lang = dashboard?.target_language === 'en' ? 'en-US' : dashboard?.target_language || 'en-US'
    recognition.interimResults = false
    recognition.maxAlternatives = 1

    recognition.onresult = async (event: any) => {
      const result = event.results[0][0]
      const transcript = (result.transcript || '').trim()
      const confidence = result.confidence || 0.8
      const similarity = levenshteinSimilarity(target, transcript)
      const score = Math.round((similarity * 0.7 + confidence * 0.3) * 100)
      const wrong = findWrongWords(target, transcript)

      setPronTranscript(transcript)
      setPronScore(score)
      setPronWrongWords(wrong)
      setPronListening(false)

      // Save to backend
      await fetch('/api/language/pronunciation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target, transcript, score, confidence, wrong_words: wrong }),
      })
      refreshLanguage().catch(() => undefined)
    }

    recognition.onerror = () => {
      setNotice('Erro no reconhecimento de voz. Tente novamente.')
      setPronListening(false)
    }

    recognition.onspeechend = () => recognition.stop()
    recognition.start()
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

  useEffect(() => {
    refreshLanguage().catch(() => undefined)
  }, [])

  return {
    dashboard, dueVocab, vocabIndex, vocabBackVisible, setVocabBackVisible,
    reviewVocab, addVocabulary, setCefrLevel,
    newWord, setNewWord, newTranslation, setNewTranslation,
    newExample, setNewExample, newCategory, setNewCategory,
    pronTarget, setPronTarget, pronTranscript, pronScore, pronListening,
    pronWrongWords, startPronunciation,
    pronunciationHistory,
    langMessages, langQuery, setLangQuery, sendLanguageMessage,
    langSessionId,
    refreshLanguage,
  }
}

