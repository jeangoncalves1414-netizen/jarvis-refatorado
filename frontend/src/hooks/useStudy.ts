import { FormEvent, useEffect, useState, useRef } from 'react'
import type { Assessment, ChatMessage, ChatSession, EnemQuestion, FeynmanAttempt, Flashcard, StudyCategory, WhiteboardElement } from '../types'

type SetNotice = (message: string) => void

const ENEM_SUBJECTS = [
  ['linguagens', 'Linguagens'],
  ['matematica', 'Matemática'],
  ['ciencias_natureza', 'Ciências da Natureza'],
  ['ciencias_humanas', 'Ciências Humanas'],
  ['redacao', 'Redação'],
] as const

const TUTOR_STUDY_PROMPT =
  'Vamos resolver esta questão juntos. Me guie passo a passo, uma pergunta de cada vez, sem dar a resposta direto.'

function subjectLabel(code?: string) {
  return ENEM_SUBJECTS.find(([value]) => value === code)?.[1] || code || 'ENEM'
}

function estimateTextHeight(text: string, fontSize = 15, maxWidth = 480) {
  const avgCharWidth = fontSize * 0.55
  const charsPerLine = Math.max(1, Math.floor(maxWidth / avgCharWidth))
  const lines = String(text || '').split('\n')
  let totalLines = 0
  for (const line of lines) {
    totalLines += Math.max(1, Math.ceil((line.length || 1) / charsPerLine))
  }
  return Math.ceil(totalLines * fontSize * 1.5) + 8
}

function elementBottom(el: WhiteboardElement) {
  const y = el.y || 0
  if (el.type === 'image') return y + 300
  return y + estimateTextHeight(el.content || '', el.size || 16)
}

function splitQuestionText(text: string) {
  const lines = String(text || '').split('\n')
  const stem: string[] = []
  const options: string[] = []
  let inOptions = false
  const optionRe = /^(\(?[A-Ea-e]\)?[\).:\-]\s*|\(?[A-Ea-e]\)\s*)/
  for (const line of lines) {
    const trimmed = line.trim()
    if (optionRe.test(trimmed)) {
      inOptions = true
      options.push(line)
    } else if (inOptions && trimmed === '') {
      options.push(line)
    } else if (!inOptions) {
      stem.push(line)
    } else {
      options.push(line)
    }
  }
  return { stem: stem.join('\n').trim(), options: options.join('\n').trim() }
}

function buildWhiteboardElements(question: EnemQuestion, offsetY = 0): WhiteboardElement[] {
  const elements: WhiteboardElement[] = []
  const x = 40
  let y = 40 + offsetY
  const label = subjectLabel(question.subject)
  const year = question.year ? ` · ${question.year}` : ''

  elements.push({
    id: crypto.randomUUID(),
    type: 'text',
    content: `[Questão ENEM — ${label}${year}]`,
    x,
    y,
    size: 14,
    color: '#00daf8',
  })
  y += 36

  const { stem, options } = splitQuestionText(question.text || '')
  const bodyText = stem || question.text || ''

  if (bodyText) {
    elements.push({
      id: crypto.randomUUID(),
      type: 'text',
      content: bodyText,
      x,
      y,
      size: 15,
      color: '#ffffff',
    })
    y += estimateTextHeight(bodyText, 15) + 20
  }

  if (question.image_base64) {
    const src = String(question.image_base64).startsWith('data:')
      ? question.image_base64
      : `data:image/png;base64,${question.image_base64}`
    elements.push({
      id: crypto.randomUUID(),
      type: 'image',
      content: src,
      x,
      y,
    })
    y += 324
  }

  if (options) {
    elements.push({
      id: crypto.randomUUID(),
      type: 'text',
      content: options,
      x,
      y,
      size: 14,
      color: '#bac9cd',
    })
  }

  return elements
}

async function pushQuestionToWhiteboard(sessionId: string, question: EnemQuestion) {
  const prev = await fetch(`/api/sessions/${sessionId}/whiteboard`)
  const prevData = await prev.json().catch(() => ({}))
  const existing = (prevData.whiteboard || []) as WhiteboardElement[]
  const offsetY = existing.reduce((max, el) => Math.max(max, elementBottom(el)), 0)
  const gap = existing.length ? 48 : 0
  const elements = [...existing, ...buildWhiteboardElements(question, offsetY + gap)]
  await fetch(`/api/sessions/${sessionId}/whiteboard`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ whiteboard: elements }),
  })
  return elements
}

export function useStudy(setNotice: SetNotice) {
  // Confirmações de estudo são renderizadas pelo StudyDialog; nunca abrir o confirm nativo.
  const confirm = (..._args: unknown[]) => true
  const [studyProgress, setStudyProgress] = useState<{ current_stage?: string; stats?: Record<string, number>; weak_spots?: string[] }>({})
  const [dueCards, setDueCards] = useState<Flashcard[]>([])
  const [studyCardIndex, setStudyCardIndex] = useState(0)
  const [cardBackVisible, setCardBackVisible] = useState(false)
  const [feynmanAttempts, setFeynmanAttempts] = useState<FeynmanAttempt[]>([])
  const [feynmanTopic, setFeynmanTopic] = useState('')
  const [feynmanExplanation, setFeynmanExplanation] = useState('')
  const [assessments, setAssessments] = useState<Assessment[]>([])
  const [assessmentCorrect, setAssessmentCorrect] = useState('')
  const [assessmentTotal, setAssessmentTotal] = useState('')
  const [enemQuestions, setEnemQuestions] = useState<EnemQuestion[]>([])
  const [enemText, setEnemText] = useState('')
  const [enemSubject, setEnemSubject] = useState('')
  const [enemYear, setEnemYear] = useState('')
  const [enemImage, setEnemImage] = useState('')
  const [tutorSessions, setTutorSessions] = useState<ChatSession[]>([])
  const [trashedStudySessions, setTrashedStudySessions] = useState<ChatSession[]>([])
  const [studyCategories, setStudyCategories] = useState<StudyCategory[]>([])
  const [studySessionId, setStudySessionId] = useState('')
  const [studyMessages, setStudyMessages] = useState<ChatMessage[]>([])
  const [studyQuery, setStudyQuery] = useState('')
  const [whiteboard, setWhiteboard] = useState<WhiteboardElement[]>([])
  const [whiteboardNote, setWhiteboardNote] = useState('')
  const whiteboardRef = useRef<WhiteboardElement[]>([])
  const whiteboardSaveTimer = useRef<number | null>(null)
  
  // Prevent race conditions in addWhiteboardImage
  const isAddingImageRef = useRef(false)

  useEffect(() => {
    whiteboardRef.current = whiteboard
  }, [whiteboard])

  const refreshStudy = async () => {
    const [progressResponse, cardsResponse, feynmanResponse, assessmentResponse, enemResponse, sessionsResponse, categoriesResponse, trashResponse] = await Promise.all([
      fetch('/api/tutor/progress'), fetch('/api/tutor/flashcards/due'), fetch('/api/tutor/feynman'), fetch('/api/tutor/assessments'), fetch('/api/enem/questions'), fetch('/api/sessions'), fetch('/api/study/categories'), fetch('/api/study/trash'),
    ])
    const [progressData, cardsData, feynmanData, assessmentData, enemData, sessionsData, categoriesData, trashData] = await Promise.all([
      progressResponse.json(), cardsResponse.json(), feynmanResponse.json(), assessmentResponse.json(), enemResponse.json(), sessionsResponse.json(), categoriesResponse.json(), trashResponse.json(),
    ])
    setStudyProgress({ ...(progressData.progress || {}), weak_spots: progressData.weak_spots || progressData.progress?.weak_spots || [] })
    setDueCards(cardsData.cards || [])
    setFeynmanAttempts(feynmanData.attempts || [])
    setAssessments(assessmentData.assessments || [])
    setEnemQuestions(enemData.questions || [])
    setTutorSessions((sessionsData.sessions || []).filter((item: ChatSession) => item.type === 'tutor'))
    setStudyCategories(categoriesData.categories || [])
    setTrashedStudySessions(trashData.sessions || [])
  }

  const renameStudySession = async (id: string, title: string) => {
    const clean = title.trim().slice(0, 80)
    if (!id || !clean) return
    const response = await fetch(`/api/sessions/${id}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title: clean }) })
    if (!response.ok) { setNotice('Não foi possível renomear a sessão.'); return }
    setTutorSessions(previous => previous.map(session => session.id === id ? { ...session, title: clean } : session))
  }

  const deleteStudySession = async (id: string) => {
    if (!id || !confirm('Mover esta sessão para a lixeira?')) return
    const response = await fetch(`/api/sessions/${id}`, { method: 'DELETE' })
    if (!response.ok) { setNotice('Não foi possível excluir a sessão.'); return }
    setTutorSessions(previous => previous.filter(session => session.id !== id))
    const deleted = tutorSessions.find(session => session.id === id)
    if (deleted) setTrashedStudySessions(previous => [deleted, ...previous])
    if (studySessionId === id) {
      setStudySessionId(''); setStudyMessages([]); whiteboardRef.current = []; setWhiteboard([])
    }
  }

  const restoreStudySession = async (id: string) => {
    const response = await fetch(`/api/sessions/${id}/restore`, { method: 'POST' })
    if (!response.ok) { setNotice('NÃ£o foi possÃ­vel restaurar a sessÃ£o.'); return }
    await refreshStudy()
  }

  const purgeStudySession = async (id: string) => {
    if (!confirm('Apagar esta sessÃ£o permanentemente? Esta aÃ§Ã£o nÃ£o pode ser desfeita.')) return
    const response = await fetch(`/api/sessions/${id}?permanent=1`, { method: 'DELETE' })
    if (!response.ok) { setNotice('NÃ£o foi possÃ­vel apagar permanentemente.'); return }
    setTrashedStudySessions(previous => previous.filter(session => session.id !== id))
  }

  const createStudyCategory = async (name: string, color: string) => {
    const response = await fetch('/api/study/categories', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, color }) })
    const data = await response.json().catch(() => ({}))
    if (!response.ok || !data.category) { setNotice('Não foi possível criar a categoria.'); return null }
    setStudyCategories(previous => [...previous, data.category])
    return data.category as StudyCategory
  }

  const assignStudyCategory = async (id: string, categoryId?: string) => {
    const response = await fetch(`/api/sessions/${id}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ category_id: categoryId || null }) })
    if (!response.ok) { setNotice('Não foi possível organizar a sessão.'); return }
    setTutorSessions(previous => previous.map(session => session.id === id ? { ...session, category_id: categoryId } : session))
  }

  const selectStudySession = async (id: string) => {
    const [historyResponse, boardResponse] = await Promise.all([fetch(`/api/sessions/${id}/history`), fetch(`/api/sessions/${id}/whiteboard`)])
    const historyData = await historyResponse.json()
    const boardData = await boardResponse.json()
    setStudySessionId(id)
    setStudyMessages((historyData.history || []).map((item: { role?: string; content?: string; text?: string }) => ({
      role: item.role === 'user' ? 'user' as const : 'assistant' as const,
      content: item.content || item.text || '',
    })))
    whiteboardRef.current = boardData.whiteboard || []
    setWhiteboard(whiteboardRef.current)
  }

  const createStudySession = async () => {
    const response = await fetch('/api/sessions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title: 'Sessão ENEM', type: 'tutor' }) })
    const data = await response.json()
    if (!response.ok || !data.id) {
      setNotice(data.error || 'Não foi possível criar a sessão de estudos.')
      return
    }
    setTutorSessions(previous => [data.session, ...previous])
    setStudySessionId(data.id)
    setStudyMessages([])
    whiteboardRef.current = []
    setWhiteboard([])
  }

  const sendStudyMessage = async (event: FormEvent) => {
    event.preventDefault()
    const message = studyQuery.trim()
    if (!message) return

    const n = message.toLowerCase()
    const openMode = (mode: 'review' | 'feynman' | 'quiz' | 'progress' | 'questions') => {
      setStudyQuery('')
      setNotice(`Modo ${mode} aberto.`)
      return true
    }

    if (/^(review|revisar|revisar cards|flashcards|cards|meus cards)$/.test(n)) {
      openMode('review')
      return
    }
    if (/^(feynman|explicar de volta)$/.test(n)) {
      openMode('feynman')
      return
    }
    if (/^(quiz|teste|test me|testar)$/.test(n)) {
      openMode('quiz')
      return
    }
    if (/^(progress|progresso|onde estou|dashboard)$/.test(n)) {
      openMode('progress')
      return
    }
    if (/^(quest(ã|a)o|questões|questions|enem|banco)$/.test(n)) {
      openMode('questions')
      return
    }

    await sendTutorMessage(message)
  }

  const sendTutorMessage = async (
    message: string,
    extra: { enem_question_id?: string; enem_context?: Record<string, unknown> } = {},
  ) => {
    let id = studySessionId
    if (!id) {
      const response = await fetch('/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: message.slice(0, 40), type: 'tutor' }),
      })
      const data = await response.json()
      if (!data.id) {
        setNotice(data.error || 'Não foi possível iniciar o tutor.')
        return null
      }
      id = data.id
      setStudySessionId(id)
      setTutorSessions(previous => [data.session, ...previous])
    }
    const history = [...studyMessages, { role: 'user' as const, content: message }]
    setStudyMessages(history)
    setStudyQuery('')
    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, session_id: id, mode: 'tutor', ...extra }),
      })
      const data = await response.json()
      const reply = data.summary || data.reply || data.error || 'Sem resposta.'
      const next = [...history, { role: 'assistant' as const, content: reply }]
      setStudyMessages(next)
      await fetch(`/api/sessions/${id}/history`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ history: next }),
      })
      if (data.whiteboard_updated) await selectStudySession(id)
      return id
    } catch {
      setNotice('Não foi possível falar com o professor Jarvis.')
      return null
    }
  }

  const ensureStudySession = async (title: string) => {
    if (studySessionId) return studySessionId
    const response = await fetch('/api/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: title.slice(0, 40) || 'Questão ENEM', type: 'tutor' }),
    })
    const data = await response.json()
    if (!response.ok || !data.id) {
      setNotice(data.error || 'Não foi possível criar a sessão de estudos.')
      return null
    }
    setTutorSessions(previous => [data.session, ...previous])
    setStudySessionId(data.id)
    setStudyMessages([])
    setWhiteboard([])
    return data.id as string
  }

  const startEnemStudy = async (question: EnemQuestion) => {
    const text = (question.text || '').trim()
    const image = question.image_base64
    if (!text && !image) {
      setNotice('Cole o enunciado (texto ou imagem) antes de estudar.')
      return false
    }
    const payload: EnemQuestion = {
      ...question,
      text: text || '[Questão com imagem — veja o quadro]',
    }
    const title = `${subjectLabel(payload.subject)}${payload.year ? ` ${payload.year}` : ''}`.trim()
    const sessionId = await ensureStudySession(title || 'Questão ENEM')
    if (!sessionId) return false
    try {
      const board = await pushQuestionToWhiteboard(sessionId, payload)
      setWhiteboard(board)
      const extra = payload.id
        ? { enem_question_id: payload.id }
        : {
            enem_context: {
              text: payload.text,
              subject: payload.subject,
              year: payload.year,
              image_base64: payload.image_base64,
            },
          }
      await sendTutorMessage(TUTOR_STUDY_PROMPT, extra)
      return true
    } catch {
      setNotice('Erro ao iniciar estudo da questão.')
      return false
    }
  }

  const studyEnemFromForm = async () => {
    if (!enemText.trim() && !enemImage) {
      setNotice('Cole o enunciado antes de estudar.')
      return false
    }
    return startEnemStudy({
      text: enemText.trim(),
      subject: enemSubject.trim(),
      year: enemYear || undefined,
      image_base64: enemImage || undefined,
    })
  }

  const studyEnemFromBank = async (questionId: string) => {
    if (!questionId) {
      setNotice('Selecione uma questão do banco.')
      return false
    }
    const response = await fetch(`/api/enem/questions/${encodeURIComponent(questionId)}`)
    const data = await response.json().catch(() => ({}))
    if (!response.ok || !data.question) {
      setNotice('Não foi possível carregar a questão selecionada.')
      return false
    }
    return startEnemStudy(data.question as EnemQuestion)
  }

  const addWhiteboardNote = async (event: FormEvent) => {
    event.preventDefault()
    if (!studySessionId || !whiteboardNote.trim()) return
    const previousWhiteboard = [...whiteboard]
    const next: WhiteboardElement[] = [...whiteboard, { id: crypto.randomUUID(), type: 'text', content: whiteboardNote.trim(), x: 24 + (whiteboard.length % 3) * 180, y: 24 + Math.floor(whiteboard.length / 3) * 90, color: '#d9ff84', size: 16 }]
    setWhiteboard(next)
    setWhiteboardNote('')
    try {
      const response = await fetch(`/api/sessions/${studySessionId}/whiteboard`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ whiteboard: next }) })
      if (!response.ok) {
        setWhiteboard(previousWhiteboard)
        setWhiteboardNote(whiteboardNote)
        setNotice('Não foi possível adicionar ao quadro.')
      }
    } catch {
      setWhiteboard(previousWhiteboard)
      setWhiteboardNote(whiteboardNote)
      setNotice('Erro de conexão ao adicionar ao quadro.')
    }
  }

  const addWhiteboardText = async (x: number, y: number, listStyle: WhiteboardElement['listStyle'] = 'plain'): Promise<string | undefined> => {
    if (!studySessionId) return undefined
    const id = crypto.randomUUID()
    const previousWhiteboard = [...whiteboard]
    const next: WhiteboardElement[] = [...whiteboard, { id, type: 'text', content: '', x, y, width: 280, height: listStyle === 'tasks' ? 110 : 90, color: '#d9ff84', size: 16, listStyle, ...(listStyle === 'tasks' ? { checked: [false] } : {}) }]
    whiteboardRef.current = next
    setWhiteboard(next)
    try {
      const response = await fetch(`/api/sessions/${studySessionId}/whiteboard`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ whiteboard: next }) })
      if (!response.ok) {
        setWhiteboard(previousWhiteboard)
        setNotice('Não foi possível adicionar texto ao quadro.')
      }
    } catch {
      setWhiteboard(previousWhiteboard)
      setNotice('Erro de conexão ao adicionar texto ao quadro.')
    }
    return id
  }

  const addWhiteboardImageData = async (x: number, y: number, base64: string): Promise<string | undefined> => {
    if (!studySessionId || !base64) return undefined
    const id = crypto.randomUUID()
    const previousWhiteboard = [...whiteboardRef.current]
    const next: WhiteboardElement[] = [...whiteboardRef.current, { id, type: 'image', content: base64, x, y, width: 280, height: 210, color: '#d9ff84', size: 16 }]
    whiteboardRef.current = next
    setWhiteboard(next)
    try {
      const response = await fetch(`/api/sessions/${studySessionId}/whiteboard`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ whiteboard: next }) })
      if (!response.ok) { whiteboardRef.current = previousWhiteboard; setWhiteboard(previousWhiteboard); setNotice('NÃ£o foi possÃ­vel colar a imagem no quadro.'); return undefined }
      return id
    } catch { whiteboardRef.current = previousWhiteboard; setWhiteboard(previousWhiteboard); setNotice('Erro de conexÃ£o ao colar imagem.'); return undefined }
  }

  const addWhiteboardImage = async (x: number, y: number) => {
    if (!studySessionId || isAddingImageRef.current) return
    isAddingImageRef.current = true
    
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = 'image/*'
    input.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0]
      if (!file) {
        input.remove()
        isAddingImageRef.current = false
        return
      }
      const reader = new FileReader()
      reader.onload = async () => {
        const base64 = typeof reader.result === 'string' ? reader.result : ''
        if (!base64) {
          input.remove()
          isAddingImageRef.current = false
          return
        }
        const previousWhiteboard = [...whiteboard]
        const next: WhiteboardElement[] = [...whiteboard, { id: crypto.randomUUID(), type: 'image', content: base64, x, y, width: 280, height: 210, color: '#d9ff84', size: 16 }]
        setWhiteboard(next)
        try {
          const response = await fetch(`/api/sessions/${studySessionId}/whiteboard`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ whiteboard: next }) })
          if (!response.ok) {
            setWhiteboard(previousWhiteboard)
            setNotice('Não foi possível adicionar imagem ao quadro.')
          }
        } catch {
          setWhiteboard(previousWhiteboard)
          setNotice('Erro de conexão ao adicionar imagem ao quadro.')
        }
        input.remove()
        isAddingImageRef.current = false
      }
      reader.onerror = () => {
        input.remove()
        isAddingImageRef.current = false
      }
      reader.readAsDataURL(file)
    }
    input.click()
  }

  const updateWhiteboardElement = async (id: string, patch: Partial<WhiteboardElement>, persist = true) => {
    if (!id) return
    const next = whiteboardRef.current.map(element => element.id === id ? { ...element, ...patch } : element)
    whiteboardRef.current = next
    setWhiteboard(next)
    if (!studySessionId) return
    if (!persist) {
      if (whiteboardSaveTimer.current) window.clearTimeout(whiteboardSaveTimer.current)
      whiteboardSaveTimer.current = window.setTimeout(() => { updateWhiteboardElement(id, {}, true).catch(() => undefined) }, 550)
      return
    }
    const response = await fetch(`/api/sessions/${studySessionId}/whiteboard`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ whiteboard: whiteboardRef.current }) })
    if (!response.ok) setNotice('Não foi possível salvar a edição no quadro.')
  }

  const deleteWhiteboardElement = async (id: string) => {
    if (!id || !studySessionId) return
    const next = whiteboardRef.current.filter(element => element.id !== id)
    whiteboardRef.current = next
    setWhiteboard(next)
    const response = await fetch(`/api/sessions/${studySessionId}/whiteboard`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ whiteboard: next }) })
    if (!response.ok) setNotice('Não foi possível excluir o elemento.')
  }

  const duplicateWhiteboardElement = async (id: string) => {
    if (!id || !studySessionId) return
    const source = whiteboardRef.current.find(element => element.id === id)
    if (!source) return
    const copy: WhiteboardElement = { ...source, id: crypto.randomUUID(), x: (source.x || 0) + 32, y: (source.y || 0) + 32, zIndex: (source.zIndex || 0) + 1 }
    const next: WhiteboardElement[] = [...whiteboardRef.current, copy]
    whiteboardRef.current = next
    setWhiteboard(next)
    const response = await fetch(`/api/sessions/${studySessionId}/whiteboard`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ whiteboard: next }) })
    if (!response.ok) setNotice('NÃ£o foi possÃ­vel duplicar o elemento.')
  }

  const clearWhiteboard = async () => {
    if (!studySessionId) return
    if (!confirm('Tem certeza que deseja limpar o quadro?')) return
    const previousWhiteboard = [...whiteboard]
    setWhiteboard([])
    try {
      const response = await fetch(`/api/sessions/${studySessionId}/whiteboard`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ whiteboard: [] }) })
      if (!response.ok) {
        setWhiteboard(previousWhiteboard)
        setNotice('Não foi possível limpar o quadro.')
      }
    } catch {
      setWhiteboard(previousWhiteboard)
      setNotice('Erro de conexão ao limpar o quadro.')
    }
  }

  const reviewCard = async (grade: number) => {
    const card = dueCards[studyCardIndex]
    if (!card) return
    const response = await fetch('/api/tutor/flashcards/review', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ card_id: card.id, grade }) })
    if (!response.ok) {
      setNotice('Não foi possível registrar a revisão.')
      return
    }
    setStudyCardIndex(previous => previous + 1)
    setCardBackVisible(false)
    refreshStudy().catch(() => undefined)
  }

  const saveFeynman = async (event: FormEvent) => {
    event.preventDefault()
    if (!feynmanTopic.trim() || !feynmanExplanation.trim()) return
    const response = await fetch('/api/tutor/feynman', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ topic: feynmanTopic, explanation: feynmanExplanation }) })
    if (!response.ok) {
      setNotice('Não foi possível salvar a explicação.')
      return
    }
    setFeynmanTopic('')
    setFeynmanExplanation('')
    setNotice('Explicação Feynman salva.')
    refreshStudy().catch(() => undefined)
  }

  const saveAssessment = async (event: FormEvent) => {
    event.preventDefault()
    const correct = Number(assessmentCorrect)
    const total = Number(assessmentTotal)
    if (!total || correct < 0 || correct > total) return
    const response = await fetch('/api/tutor/assessments', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ correct, total }) })
    if (!response.ok) {
      setNotice('Não foi possível registrar a avaliação.')
      return
    }
    setAssessmentCorrect('')
    setAssessmentTotal('')
    setNotice('Avaliação salva.')
    refreshStudy().catch(() => undefined)
  }

  const saveEnemQuestion = async (event: FormEvent) => {
    event.preventDefault()
    if (!enemText.trim()) return
    const response = await fetch('/api/enem/questions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: enemText.trim(), subject: enemSubject.trim(), year: enemYear || undefined, image_base64: enemImage || undefined, source: 'react_panel' }) })
    if (!response.ok) {
      const data = await response.json()
      setNotice(data.error || 'Não foi possível salvar a questão.')
      return
    }
    setEnemText('')
    setEnemSubject('')
    setEnemYear('')
    setEnemImage('')
    setNotice('Questão ENEM salva.')
    refreshStudy().catch(() => undefined)
  }

  const readEnemImage = (file: File | undefined) => {
    if (!file) return
    if (!file.type.startsWith('image/')) {
      setNotice('Escolha um arquivo de imagem.')
      return
    }
    const reader = new FileReader()
    reader.onload = () => setEnemImage(typeof reader.result === 'string' ? reader.result : '')
    reader.readAsDataURL(file)
  }

  useEffect(() => {
    refreshStudy().catch(() => undefined)
  }, [])

  return {
    addWhiteboardNote, addWhiteboardText, addWhiteboardImage, addWhiteboardImageData, updateWhiteboardElement, deleteWhiteboardElement, duplicateWhiteboardElement, clearWhiteboard, assessmentCorrect, assessmentTotal, assessments, cardBackVisible, createStudySession, dueCards,
    studyCategories, trashedStudySessions, renameStudySession, deleteStudySession, restoreStudySession, purgeStudySession, createStudyCategory, assignStudyCategory,
    enemImage, enemQuestions, enemSubject, enemText, enemYear, feynmanAttempts, feynmanExplanation, feynmanTopic,
    readEnemImage, reviewCard, saveAssessment, saveEnemQuestion, saveFeynman, selectStudySession, sendStudyMessage,
    setAssessmentCorrect, setAssessmentTotal, setCardBackVisible, setEnemImage, setEnemSubject, setEnemText, setEnemYear,
    setFeynmanExplanation, setFeynmanTopic, setStudyQuery, setStudySessionId, setWhiteboardNote, studyCardIndex, studyMessages,
    studyEnemFromBank, studyEnemFromForm, studyProgress, studyQuery, studySessionId, tutorSessions, whiteboard, whiteboardNote,
  }
}
