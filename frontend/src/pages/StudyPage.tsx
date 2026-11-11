import { FormEvent, useEffect, useState, type Dispatch, type SetStateAction } from 'react'
import type { EnemQuestion, StudyCategory, WhiteboardElement } from '../types'
import type { StudyMode } from '../components/study/StudyToolbar'
import { StudyCanvas } from '../components/study/StudyCanvas'
import { StudySidebar } from '../components/study/StudySidebar'
import { StudyToolbar } from '../components/study/StudyToolbar'
import { MessageContent } from '../components/MessageContent'
import { LanguagePage } from './LanguagePage'

type StudyPageProps = {
  tutorSessions: { id: string; title?: string }[]
  studyCategories: StudyCategory[]
  trashedStudySessions: { id: string; title?: string }[]
  renameStudySession: (id: string, title: string) => Promise<void>
  deleteStudySession: (id: string) => Promise<void>
  restoreStudySession: (id: string) => Promise<void>
  purgeStudySession: (id: string) => Promise<void>
  createStudyCategory: (name: string, color: string) => Promise<StudyCategory | null>
  assignStudyCategory: (id: string, categoryId?: string) => Promise<void>
  studySessionId: string
  selectStudySession: (id: string) => Promise<void>
  createStudySession: () => Promise<void>
  studyProgress: { current_stage?: string; weak_spots?: string[]; stats?: Record<string, number> }
  dueCards: { id: string; front?: string; back?: string }[]
  studyCardIndex: number
  cardBackVisible: boolean
  setCardBackVisible: Dispatch<SetStateAction<boolean>>
  reviewCard: (grade: number) => Promise<void>
  enemQuestions: EnemQuestion[]
  feynmanTopic: string
  feynmanExplanation: string
  setFeynmanTopic: (v: string) => void
  setFeynmanExplanation: (v: string) => void
  saveFeynman: (e: FormEvent) => Promise<void>
  feynmanAttempts: { id?: string; topic?: string; date?: string }[]
  assessmentCorrect: string
  assessmentTotal: string
  setAssessmentCorrect: (v: string) => void
  setAssessmentTotal: (v: string) => void
  saveAssessment: (e: FormEvent) => Promise<void>
  assessments: { id?: string; correct?: number; total?: number; score?: number }[]
  enemSubject: string
  enemYear: string
  enemText: string
  enemImage: string
  setEnemSubject: (v: string) => void
  setEnemYear: (v: string) => void
  setEnemText: (v: string) => void
  setEnemImage: (v: string) => void
  readEnemImage: (file: File | undefined) => void
  saveEnemQuestion: (e: FormEvent) => Promise<void>
  setStudyQuery: (v: string) => void
  setStudySessionId: (v: string) => void
  studyMessages: { role: string; content: string }[]
  studyQuery: string
  sendStudyMessage: (e: FormEvent) => Promise<void>
  sendTutorMessage: (message: string) => Promise<string | null>
  studyEnemFromForm: () => Promise<boolean>
  studyEnemFromBank: (questionId: string) => Promise<boolean>
  whiteboard: WhiteboardElement[]
  whiteboardNote: string
  setWhiteboardNote: (v: string) => void
  saveWhiteboard: (e: FormEvent) => Promise<void>
  addWhiteboardText: (x: number, y: number, listStyle?: WhiteboardElement['listStyle']) => Promise<string | undefined>
  addWhiteboardImageData: (x: number, y: number, base64: string) => Promise<string | undefined>
  addWhiteboardImage: (x: number, y: number) => void
  updateWhiteboardElement: (id: string, patch: Partial<WhiteboardElement>, persist?: boolean) => void
  deleteWhiteboardElement: (id: string) => void
  duplicateWhiteboardElement: (id: string) => void
  clearWhiteboard: () => void
  setNotice: (message: string) => void
  languageProps?: Record<string, any>
}

export function StudyPage(props: StudyPageProps) {
  const [activeMode, setActiveMode] = useState<StudyMode>('plan')
  const [selectedEnemId, setSelectedEnemId] = useState('')
  const [pasteText, setPasteText] = useState('')
  const [pasteImage, setPasteImage] = useState('')
  const currentCard = props.dueCards[props.studyCardIndex]
  const selectedEnem = props.enemQuestions.find(item => item.id === selectedEnemId)

  const handlePaste = async () => {
    const text = pasteText.trim()
    if (!text && !props.enemImage) {
      props.setNotice('Cole o enunciado (texto ou imagem) antes de estudar.')
      return
    }
    if (text) {
      props.setEnemText(text)
    }
    const started = await props.studyEnemFromForm()
    if (started) {
      setPasteText('')
      setPasteImage('')
      setActiveMode('learn')
    }
  }

  const handlePasteEvent = (e: ClipboardEvent) => {
    if (activeMode !== 'questions') return
    const items = e.clipboardData?.items
    if (!items) return
    for (const item of Array.from(items)) {
      if (item.type.startsWith('image/')) {
        e.preventDefault()
        const file = item.getAsFile()
        if (file) {
          props.readEnemImage(file)
          props.setNotice('Imagem colada. Clique em "Estudar agora" para começar.')
        }
        return
      }
    }
    const text = e.clipboardData?.getData('text')
    if (text && activeMode === 'questions') {
      e.preventDefault()
      setPasteText(text)
    }
  }

  const handleDrop = (e: DragEvent) => {
    if (activeMode !== 'questions') return
    e.preventDefault()
    const file = e.dataTransfer?.files?.[0]
    if (file?.type.startsWith('image/')) {
      props.readEnemImage(file)
      props.setNotice('Imagem arrastada. Clique em "Estudar agora" para começar.')
    }
  }

  useEffect(() => {
    window.addEventListener('paste', handlePasteEvent)
    window.addEventListener('drop', handleDrop)
    window.addEventListener('dragover', e => e.preventDefault())
    return () => {
      window.removeEventListener('paste', handlePasteEvent)
      window.removeEventListener('drop', handleDrop)
      window.removeEventListener('dragover', e => e.preventDefault())
    }
  }, [activeMode, handlePasteEvent, handleDrop])

  const openLearnAfterStudy = async (started: boolean) => {
    if (!started) return
    setActiveMode('learn')
  }

  const refreshCanvas = () => {
    if (props.studySessionId) props.selectStudySession(props.studySessionId).catch(() => undefined)
  }

  const beginGuidedStudy = (message: string, mode: StudyMode = 'learn') => {
    setActiveMode(mode)
    props.sendTutorMessage(message).catch(() => undefined)
  }

  return (
    <section className="study-layout">
      <StudySidebar
        sessions={props.tutorSessions}
        categories={props.studyCategories}
        trashedSessions={props.trashedStudySessions}
        activeSessionId={props.studySessionId}
        onSelectSession={id => { props.selectStudySession(id).catch(() => undefined) }}
        onNewSession={() => props.createStudySession().catch(() => undefined)}
        onRenameSession={(id, title) => props.renameStudySession(id, title).catch(() => undefined)}
        onDeleteSession={id => props.deleteStudySession(id).catch(() => undefined)}
        onRestoreSession={id => props.restoreStudySession(id).catch(() => undefined)}
        onPurgeSession={id => props.purgeStudySession(id).catch(() => undefined)}
        onCreateCategory={props.createStudyCategory}
        onAssignCategory={(id, categoryId) => props.assignStudyCategory(id, categoryId).catch(() => undefined)}
        progressLabel={props.studyProgress.current_stage || 'Sua jornada de estudo'}
        weakSpots={props.studyProgress.weak_spots}
        dueCards={props.dueCards.length}
        enemCount={props.enemQuestions.length}
      />
      <div className="study-main">
        <StudyToolbar activeMode={activeMode} onModeChange={setActiveMode} />
        <StudyCanvas
          elements={props.whiteboard}
          sessionId={props.studySessionId}
          onRefresh={refreshCanvas}
          onAddText={props.addWhiteboardText}
          onAddImage={props.addWhiteboardImage}
          onAddPastedImage={props.addWhiteboardImageData}
          onUpdateElement={props.updateWhiteboardElement}
          onDeleteElement={props.deleteWhiteboardElement}
          onDuplicateElement={props.duplicateWhiteboardElement}
          onClearCanvas={props.clearWhiteboard}
        />
        {activeMode === 'plan' && (
          <div className="study-overlay-panel study-today">
            <p className="eyebrow">PLANO DE HOJE</p>
            <h2>{props.studyProgress.current_stage || 'Preparação para provas'}</h2>
            <p className="study-today-copy">Comece pelo diagnóstico ou escolha uma prática. O Jarvis registra lacunas, questões e revisões para o próximo estudo.</p>
            <div className="study-today-stats">
              <span><b>{props.dueCards.length}</b> revisões</span>
              <span><b>{props.enemQuestions.length}</b> questões salvas</span>
              <span><b>{props.assessments.length}</b> simulados</span>
            </div>
            <div className="study-today-actions">
              <button type="button" className="primary" onClick={() => beginGuidedStudy('diagnostico: quero iniciar meu diagnóstico para provas. Faça uma pergunta curta por vez, comece perguntando minha matéria mais difícil e espere minha resposta antes de corrigir.')}>Fazer diagnóstico</button>
              <button type="button" onClick={() => beginGuidedStudy('Quero montar uma sessão de estudo para hoje. Pergunte primeiro qual prova, matéria e tempo disponível; depois proponha a primeira atividade.')}>Estudar um tema</button>
              <button type="button" onClick={() => beginGuidedStudy('simulado: quero um mini simulado de 5 questões. Envie uma questão por vez, espere minha resposta e, no final, dê desempenho, erros e uma revisão indicada.')}>Mini simulado</button>
              <button type="button" onClick={() => setActiveMode('review')}>Revisar agora</button>
              <button type="button" onClick={() => setActiveMode('questions')}>Adicionar questão</button>
              <button type="button" onClick={() => setActiveMode('feynman')}>Explicar de volta</button>
            </div>
          </div>
        )}
        {activeMode === 'learn' && (
          <div className="study-overlay-panel">
            <p className="eyebrow">PROFESSOR JARVIS</p>
            <div className="study-chat-history">
              {props.studyMessages.length ? props.studyMessages.map((m, i) => (
                <div className={`study-chat-message ${m.role}`} key={`${m.role}-${i}`}>
                  <b>{m.role === 'user' ? 'VOCÊ' : 'PROFESSOR'}</b>
                  <MessageContent text={m.content} />
                </div>
              )) : <span>Pergunte ao professor sobre qualquer tópico.</span>}
            </div>
            <form className="study-tutor-form" onSubmit={props.sendStudyMessage}>
              <input value={props.studyQuery} onChange={e => props.setStudyQuery(e.target.value)} placeholder="Ex.: explique função quadrática" />
              <button type="submit">Enviar</button>
            </form>
            <form className="whiteboard-form" onSubmit={props.saveWhiteboard}>
              <input disabled={!props.studySessionId} value={props.whiteboardNote} onChange={e => props.setWhiteboardNote(e.target.value)} placeholder="Adicionar anotação ao quadro" />
              <button disabled={!props.studySessionId} type="submit">Adicionar</button>
            </form>
          </div>
        )}
        {activeMode === 'review' && (
          <div className="study-overlay-panel">
            <p className="eyebrow">REVISÃO ESPAÇADA</p>
            {currentCard ? (
              <>
                <button type="button" className="flashcard" onClick={() => props.setCardBackVisible(v => !v)}>
                  <small>{props.cardBackVisible ? 'RESPOSTA' : 'PERGUNTA'} · clique para virar</small>
                  <strong>{props.cardBackVisible ? currentCard.back : currentCard.front}</strong>
                </button>
                <div className="grade-actions">
                  <button type="button" onClick={() => props.reviewCard(0)}>Errei</button>
                  <button type="button" onClick={() => props.reviewCard(1)}>Difícil</button>
                  <button type="button" onClick={() => props.reviewCard(2)}>Bom</button>
                  <button type="button" onClick={() => props.reviewCard(3)}>Fácil</button>
                </div>
              </>
            ) : <p className="empty-state">Nenhum flashcard pendente hoje.</p>}
          </div>
        )}
        {activeMode === 'feynman' && (
          <div className="study-overlay-panel">
            <p className="eyebrow">MODO FEYNMAN</p>
            <form className="study-form" onSubmit={props.saveFeynman}>
              <input value={props.feynmanTopic} onChange={e => props.setFeynmanTopic(e.target.value)} placeholder="Tópico" />
              <textarea value={props.feynmanExplanation} onChange={e => props.setFeynmanExplanation(e.target.value)} placeholder="Explique com suas palavras…" />
              <button type="submit">Salvar explicação</button>
            </form>
          </div>
        )}
        {activeMode === 'questions' && (
          <div className="study-overlay-panel study-enem">
            <p className="eyebrow">BANCO ENEM</p>
            <div className="study-enem-tabs">
              <button type="button" className={pasteText ? 'study-tab-active' : ''} onClick={() => { setPasteText(''); props.setEnemText('') }}>Colar questão</button>
              <button type="button" className={!pasteText ? 'study-tab-active' : ''} onClick={() => { setPasteText(''); props.setEnemText('') }}>Banco de questões</button>
            </div>
            {pasteText ? (
              <div className="study-enem-paste">
                <textarea value={pasteText} onChange={e => setPasteText(e.target.value)} placeholder="Cole o enunciado da questão aqui…" />
                {props.enemImage && <img src={props.enemImage} alt="Imagem colada" className="study-enem-preview-img" />}
                <div className="study-enem-actions">
                  <button type="button" onClick={() => { setPasteText(''); props.setEnemImage('') }}>Cancelar</button>
                  <button type="button" className="primary" onClick={handlePaste}>Estudar agora</button>
                </div>
              </div>
            ) : (
              <>
                <form className="study-form" onSubmit={props.saveEnemQuestion}>
                  <div className="enem-meta">
                    <select value={props.enemSubject} onChange={e => props.setEnemSubject(e.target.value)}>
                      <option value="">Disciplina</option>
                      <option value="linguagens">Linguagens</option>
                      <option value="matematica">Matemática</option>
                      <option value="ciencias_natureza">Ciências da Natureza</option>
                      <option value="ciencias_humanas">Ciências Humanas</option>
                      <option value="redacao">Redação</option>
                    </select>
                    <input type="number" min="1998" max="2030" value={props.enemYear} onChange={e => props.setEnemYear(e.target.value)} placeholder="Ano" />
                  </div>
                  <textarea value={props.enemText} onChange={e => props.setEnemText(e.target.value)} placeholder="Cole o enunciado…" />
                  <label className="image-upload">
                    {props.enemImage ? 'Trocar imagem' : 'Adicionar imagem'}
                    <input type="file" accept="image/*" onChange={e => props.readEnemImage(e.target.files?.[0])} />
                  </label>
                  {props.enemImage && <img src={props.enemImage} alt="Prévia da questão" className="study-enem-preview-img" />}
                  <div className="study-enem-actions">
                    <button type="submit">Salvar no banco</button>
                    <button
                      type="button"
                      className="primary"
                      onClick={() => props.studyEnemFromForm().then(openLearnAfterStudy).catch(() => undefined)}
                    >
                      Estudar agora
                    </button>
                  </div>
                </form>
                <div className="study-enem-bank">
                  <select value={selectedEnemId} onChange={e => setSelectedEnemId(e.target.value)}>
                    <option value="">— Selecione uma questão —</option>
                    {props.enemQuestions.map(item => (
                      <option key={item.id} value={item.id}>
                        {(item.subject || 'ENEM') + (item.year ? ` (${item.year})` : '')} — {item.preview || item.text?.slice(0, 40) || item.id}
                      </option>
                    ))}
                  </select>
                  <div className="study-enem-preview">
                    {selectedEnem ? (
                      <>
                        <small>{selectedEnem.subject || 'ENEM'}{selectedEnem.year ? ` · ${selectedEnem.year}` : ''}</small>
                        <pre>{selectedEnem.text}</pre>
                      </>
                    ) : (
                      <p className="empty-state">Selecione uma questão para ver o enunciado.</p>
                    )}
                  </div>
                  <button
                    type="button"
                    className="primary"
                    disabled={!selectedEnemId}
                    onClick={() => props.studyEnemFromBank(selectedEnemId).then(openLearnAfterStudy).catch(() => undefined)}
                  >
                    Estudar questão selecionada
                  </button>
                </div>
              </>
            )}
          </div>
        )}
        {activeMode === 'quiz' && (
          <div className="study-overlay-panel">
            <p className="eyebrow">AVALIAÇÕES</p>
            <form className="assessment-form" onSubmit={props.saveAssessment}>
              <input type="number" min="0" value={props.assessmentCorrect} onChange={e => props.setAssessmentCorrect(e.target.value)} placeholder="Acertos" />
              <input type="number" min="1" value={props.assessmentTotal} onChange={e => props.setAssessmentTotal(e.target.value)} placeholder="Total" />
              <button type="submit">Registrar</button>
            </form>
          </div>
        )}
        {activeMode === 'progress' && (
          <div className="study-overlay-panel">
            <p className="eyebrow">PROGRESSO</p>
            <div className="study-stats">
              <span><b>{props.dueCards.length}</b> cards</span>
              <span><b>{props.enemQuestions.length}</b> questões ENEM</span>
              <span><b>{props.studyProgress.stats?.feynman_attempts ?? props.feynmanAttempts.length}</b> explicações</span>
            </div>
          </div>
        )}
        {activeMode === 'language' && props.languageProps && (
          <LanguagePage {...props.languageProps as any} />
        )}
      </div>
    </section>
  )
}
