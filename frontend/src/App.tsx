import { FormEvent, lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { AppShell } from './components/AppShell'
import { CameraWorkspace, type CameraWorkspaceHandle } from './components/CameraWorkspace'
import { type ChatMode } from './components/ChatComposer'
import { CinemaModal } from './components/CinemaModal'
import { LiveCallModal } from './components/LiveCallModal'
import { CalendarSection } from './components/Calendar'
import { VideoPlayer as IsolatedVideoPlayer } from './components/VideoPlayer'
import { DashboardHero } from './components/DashboardHero'
import { Toast } from './components/Toast'
import { useChat } from './hooks/useChat'
import { useCinema } from './hooks/useCinema'
import { useMediaAssistant } from './hooks/useMediaAssistant'
import { useStudy } from './hooks/useStudy'
import type { BridgeStatus, Climate, Dashboard, Finance, LlmSettings, LogEntry, Memory, Metrics, Proactive, Tray, TtsSettings, WakeWord, Weather } from './types'

const AutomationsPage = lazy(() => import('./pages/AutomationsPage').then(module => ({ default: module.AutomationsPage })))
const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage').then(module => ({ default: module.AnalyticsPage })))
const ChatPage = lazy(() => import('./pages/ChatPage').then(module => ({ default: module.ChatPage })))
const DashboardPage = lazy(() => import('./pages/DashboardPage').then(module => ({ default: module.DashboardPage })))
const MemoriesPage = lazy(() => import('./pages/MemoriesPage').then(module => ({ default: module.MemoriesPage })))
const SettingsPage = lazy(() => import('./pages/SettingsPage').then(module => ({ default: module.SettingsPage })))
const StudyPage = lazy(() => import('./pages/StudyPage').then(module => ({ default: module.StudyPage })))

const navItems = [
  { id: 'Dashboard', icon: '◈' },
  { id: 'Automações', icon: '⟳' },
  { id: 'Chat', icon: '✦' },
  { id: 'Calendário', icon: '◷' },
  { id: 'Análises', icon: '◉' },
  { id: 'Estudos', icon: '◎' },
  { id: 'Memórias', icon: '◇' },
  { id: 'Configurações', icon: '⚙' },
]

const ACTIVE_SCREEN_KEY = 'jarvis-active-screen'

function readActiveScreen() {
  try {
    const stored = localStorage.getItem(ACTIVE_SCREEN_KEY)
    if (stored) return stored
  } catch {
    /* ignore storage errors */
  }
  return 'Dashboard'
}

export default function App() {
  const [active, setActive] = useState(readActiveScreen)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [weather, setWeather] = useState<Weather | null>(null)
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [finance, setFinance] = useState<Finance | null>(null)
  const [proactive, setProactive] = useState<Proactive | null>(null)
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [climate, setClimate] = useState<Climate | null>(null)
  const [bridge, setBridge] = useState<BridgeStatus | null>(null)
  const [llmSettings, setLlmSettings] = useState<LlmSettings | null>(null)
  const [ttsSettings, setTtsSettings] = useState<TtsSettings | null>(null)
  const [wakeWord, setWakeWord] = useState<WakeWord | null>(null)
  const [tray, setTray] = useState<Tray | null>(null)
  const [briefingTime, setBriefingTime] = useState('08:00')
  const [briefingTopics, setBriefingTopics] = useState<string[]>(['weather', 'tasks', 'news'])
  const [briefingInstructions, setBriefingInstructions] = useState('')
  const [reminderMessage, setReminderMessage] = useState('')
  const [reminderTime, setReminderTime] = useState('+10m')
  const [notice, setNotice] = useState('')
  const [logLevel, setLogLevel] = useState('')
  const [logQuery, setLogQuery] = useState('')
  const { addWhiteboardNote, addWhiteboardText, addWhiteboardImage, addWhiteboardImageData, updateWhiteboardElement, deleteWhiteboardElement, duplicateWhiteboardElement, clearWhiteboard, assessmentCorrect, assessmentTotal, assessments, cardBackVisible, createStudySession, dueCards, studyCategories, trashedStudySessions, renameStudySession, deleteStudySession, restoreStudySession, purgeStudySession, createStudyCategory, assignStudyCategory, enemImage, enemQuestions, enemSubject, enemText, enemYear, feynmanAttempts, feynmanExplanation, feynmanTopic, readEnemImage, reviewCard, saveAssessment, saveEnemQuestion, saveFeynman, selectStudySession, sendStudyMessage, setAssessmentCorrect, setAssessmentTotal, setCardBackVisible, setEnemImage, setEnemSubject, setEnemText, setEnemYear, setFeynmanExplanation, setFeynmanTopic, setStudyQuery, setStudySessionId, setWhiteboardNote, studyCardIndex, studyEnemFromBank, studyEnemFromForm, studyMessages, studyProgress, studyQuery, studySessionId, tutorSessions, whiteboard, whiteboardNote } = useStudy(setNotice)
  const [taskTitle, setTaskTitle] = useState('')
  const [memories, setMemories] = useState<Memory[]>([])
  const [memoryCollection, setMemoryCollection] = useState<'conversations' | 'user_memory'>('conversations')
  const [playingUrl, setPlayingUrl] = useState('')
  const [cameraWorkspaceOpen, setCameraWorkspaceOpen] = useState(false)
  const [cameraQuestion, setCameraQuestion] = useState('')
  const [chatMode, setChatMode] = useState<ChatMode>('general')
  const [chatAttachment, setChatAttachment] = useState<{ name: string; dataUrl: string } | null>(null)
  const cameraWorkspaceRef = useRef<CameraWorkspaceHandle>(null)
  const taskInputRef = useRef<HTMLInputElement>(null)
  const { answer, chatError, createSession, deleteSession, exportSession, loading, liveReasoning, liveSearch, messages, pendingScript, query, runPendingScript, selectSession, sendText, sendVisionQuestion, sessionId, sessions, setAnswer, setChatError, setPendingScript, setQuery, streamingReply } = useChat()
  const { captureVision, closeLiveCall, liveCallOpen, liveCallRecording, liveCallStatus, recording, setLiveCallOpen, setSpeakEnabled, setVisionResult, speakEnabled, speakText, toggleLiveCallCapture, toggleVoiceInput, visionResult } = useMediaAssistant({ query, sendText, setAnswer, setQuery })
  const { availableEpisodes, availableSeasons, cinemaLauncherOpen, setCinemaLauncherOpen, videoUrl, setVideoUrl, cinemaQuery, setCinemaQuery, cinemaResults, cinemaMedia, cinemaStatus, setCinemaStatus, cinemaLibrary, refreshCinemaLibrary, searchCinema, probeCinema, saveCinemaUrl, openCinemaPayload, selectEpisode, selectLibraryItem, selectLibrarySource, selectNextEpisode, selectSeason, selectedEpisode, selectedLibraryItem, selectedLibraryId, selectedLibrarySources, selectedSeason, selectedSourceUrl } = useCinema()

  const setTtsProvider = async (tts_provider: 'gemini' | 'edge') => {
    const response = await fetch('/api/settings/tts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tts_provider }) })
    setTtsSettings(await response.json())
  }

  useEffect(() => {
    try {
      localStorage.setItem(ACTIVE_SCREEN_KEY, active)
    } catch {
      /* ignore storage errors */
    }
  }, [active])

  useEffect(() => {
    if (active !== 'Dashboard') return
    taskInputRef.current?.focus()
  }, [active])

  const dismissNotice = useCallback(() => setNotice(''), [])

  const handleExportSession = async () => {
    if (!sessionId) return
    const exported = await exportSession(sessionId)
    if (exported) setNotice('Conversa exportada em Markdown.')
  }

  const openNewTask = () => {
    setActive('Dashboard')
    window.setTimeout(() => taskInputRef.current?.focus(), 120)
  }

  useEffect(() => {
    fetch('/api/realtime').then(response => response.json()).then(data => { setWeather(data.weather); setFinance(data.finance) }).catch(() => undefined)
    fetch('/api/dashboard').then(response => response.json()).then(setDashboard).catch(() => undefined)
    fetch('/api/climate').then(response => response.json()).then(setClimate).catch(() => undefined)
    fetch('/api/bridge').then(response => response.json()).then(setBridge).catch(() => undefined)
    fetch('/api/settings/llm').then(response => response.json()).then(setLlmSettings).catch(() => undefined)
    fetch('/api/settings/tts').then(response => response.json()).then(setTtsSettings).catch(() => undefined)
    fetch('/api/memories?collection=conversations&limit=20').then(response => response.json()).then(data => setMemories(data.memories || [])).catch(() => undefined)
    fetch('/api/proactive').then(response => response.json()).then(data => {
      setProactive(data)
      setBriefingTime(data.config?.briefing_time || '08:00')
      setBriefingTopics(data.config?.topics || ['weather', 'tasks', 'news'])
      setBriefingInstructions(data.config?.custom_instructions || '')
    }).catch(() => undefined)
    fetch('/api/wake-word').then(response => response.json()).then(setWakeWord).catch(() => undefined)
    fetch('/api/tray').then(response => response.json()).then(setTray).catch(() => undefined)
  }, [])

  useEffect(() => {
    const refreshBridge = () => fetch('/api/bridge').then(response => response.json()).then(setBridge).catch(() => undefined)
    const interval = window.setInterval(refreshBridge, 5_000)
    return () => window.clearInterval(interval)
  }, [])

  const refreshAnalytics = async (level = logLevel) => {
    const suffix = level ? `?level=${encodeURIComponent(level)}` : ''
    const [metricsResponse, logsResponse] = await Promise.all([fetch('/api/metrics'), fetch(`/api/logs${suffix}`)])
    if (metricsResponse.ok) setMetrics(await metricsResponse.json())
    if (logsResponse.ok) {
      const data = await logsResponse.json()
      setLogs(data.logs || [])
    }
  }

  useEffect(() => {
    refreshAnalytics().catch(() => undefined)
    const refreshId = window.setInterval(() => refreshAnalytics().catch(() => undefined), 15_000)
    return () => window.clearInterval(refreshId)
  }, [logLevel])

  const visibleLogs = logs.filter(log => `${log.component || ''} ${log.message || ''}`.toLocaleLowerCase('pt-BR').includes(logQuery.trim().toLocaleLowerCase('pt-BR')))

  const refreshMemories = async (collection = memoryCollection) => {
    const response = await fetch(`/api/memories?collection=${collection}&limit=25`)
    const data = await response.json()
    setMemories(data.memories || [])
  }

  const clearTechnicalMemories = async () => {
    if (!window.confirm('Remover da memória semântica os erros técnicos antigos? Isso não remove conversas normais.')) return
    const response = await fetch('/api/memories/cleanup', { method: 'POST' })
    const data = await response.json()
    if (!response.ok || !data.ok) {
      setNotice(data.error || 'Não foi possível limpar as memórias técnicas.')
      return
    }
    setNotice(data.removed ? `${data.removed} memória(s) técnica(s) removida(s).` : 'Nenhuma memória técnica foi encontrada.')
    await refreshMemories()
  }

  const refreshDashboard = async () => {
    const response = await fetch('/api/dashboard')
    setDashboard(await response.json())
  }

  useEffect(() => {
    if (active !== 'Dashboard') return
    const refreshLive = () => {
      fetch('/api/realtime').then(response => response.json()).then(data => { setWeather(data.weather); setFinance(data.finance) }).catch(() => undefined)
      refreshDashboard().catch(() => undefined)
      fetch('/api/proactive').then(response => response.json()).then(setProactive).catch(() => undefined)
      fetch('/api/tray').then(response => response.json()).then(setTray).catch(() => undefined)
    }
    const refreshId = window.setInterval(refreshLive, 25_000)
    return () => window.clearInterval(refreshId)
  }, [active])

  const addTask = async (event: FormEvent) => {
    event.preventDefault()
    if (!taskTitle.trim()) return
    await fetch('/api/tasks', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'create', title: taskTitle }) })
    setTaskTitle('')
    await refreshDashboard()
  }

  const toggleTask = async (taskId: string) => {
    await fetch('/api/tasks', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'toggle', task_id: taskId }) })
    await refreshDashboard()
  }

  const deleteTask = async (taskId: string) => {
    if (!window.confirm('Remover esta tarefa?')) return
    await fetch('/api/tasks', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'delete', task_id: taskId }) })
    await refreshDashboard()
  }

  const setTemperature = async (value: number) => {
    const response = await fetch('/api/automation', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'set_temperature', device: 'climate', value }) })
    setClimate(await response.json())
  }

  const registerBridgeDemo = async () => {
    const response = await fetch('/api/bridge', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'register', device_id: 'sim-lamp', name: 'Lâmpada de teste', kind: 'light', platform: 'simulator', transport: 'local' }) })
    const data = await response.json()
    if (!response.ok || !data.ok) { setNotice(data.error || 'Não foi possível adicionar o dispositivo de teste.'); return }
    setBridge(previous => ({ ...previous, ...data, devices: [...(previous?.devices || []).filter(device => device.id !== data.device?.id), data.device] }))
    setNotice('Lâmpada de teste adicionada. Ela será substituída pelo adaptador real depois.')
  }

  const sendBridgeCommand = async (targetId: string, command: 'turn_on' | 'turn_off') => {
    const response = await fetch('/api/bridge', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'command', target_id: targetId, command, source: 'desktop' }) })
    const data = await response.json()
    if (!response.ok || !data.ok) { setNotice(data.error || 'Não foi possível enviar o comando.'); return }
    setBridge(previous => ({ ...previous, devices: (previous?.devices || []).map(device => device.id === targetId ? data.device : device) }))
    setNotice(data.executed ? 'Comando recebido e executado pelo dispositivo.' : 'Comando recebido pela ponte.')
  }

  const refreshProactive = async () => {
    const response = await fetch('/api/proactive')
    const data = await response.json()
    setProactive(data)
    setBriefingTime(data.config?.briefing_time || '08:00')
    setBriefingTopics(data.config?.topics || [])
    setBriefingInstructions(data.config?.custom_instructions || '')
  }

  const saveBriefing = async (enabled = proactive?.config?.briefing_enabled ?? false) => {
    const response = await fetch('/api/proactive', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'configure_briefing', enabled, briefing_time: briefingTime, topics: briefingTopics, custom_instructions: briefingInstructions }) })
    const data = await response.json()
    if (!response.ok) throw new Error(data.error || 'Não foi possível salvar o briefing.')
    setProactive(previous => ({ ...previous, config: data.config }))
    setNotice('Configuração do briefing salva.')
  }

  const toggleBriefingTopic = (topic: string) => setBriefingTopics(previous => previous.includes(topic) ? previous.filter(item => item !== topic) : [...previous, topic])

  const addReminder = async (event: FormEvent) => {
    event.preventDefault()
    if (!reminderMessage.trim()) return
    const response = await fetch('/api/proactive', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'add_reminder', reminder_message: reminderMessage.trim(), reminder_time: reminderTime.trim() || '+10m' }) })
    const data = await response.json()
    if (!response.ok) { setNotice(data.error || 'Não foi possível criar o lembrete.'); return }
    setReminderMessage('')
    setNotice('Lembrete criado.')
    await refreshProactive()
  }

  const triggerBriefing = async () => {
    const response = await fetch('/api/proactive', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'trigger_briefing' }) })
    const data = await response.json()
    if (!response.ok) { setNotice(data.error || 'Não foi possível gerar o briefing.'); return }
    setAnswer(data.briefing_text || 'Briefing gerado.')
    setActive('Chat')
  }

  const setWakeWordEnabled = async (enabled: boolean) => {
    const response = await fetch('/api/wake-word', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled }) })
    const data = await response.json()
    if (!response.ok) { setNotice(data.error || 'Não foi possível alterar a palavra de ativação.'); return }
    setWakeWord(previous => ({ ...previous, enabled: data.enabled }))
  }

  const setBootEnabled = async (enabled: boolean) => {
    const response = await fetch('/api/tray', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: enabled ? 'enable_boot' : 'disable_boot' }) })
    const data = await response.json()
    if (!response.ok) { setNotice(data.error || 'Não foi possível alterar a inicialização automática.'); return }
    setTray({ boot_enabled: data.boot_enabled })
  }

  const setProvider = async (llm_provider: 'gemini' | 'groq') => {
    const response = await fetch('/api/settings/llm', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ llm_provider }) })
    setLlmSettings(await response.json())
  }

  const openVideo = (url: string) => {
    const trimmed = url.trim()
    if (!/^https?:\/\//i.test(trimmed)) return
    setPlayingUrl(trimmed)
  }

  const askCameraQuestion = async (prompt?: string) => {
    const capture = await cameraWorkspaceRef.current?.captureSelectedFrame()
    if (!capture) {
      setNotice('Abra o espaço de câmeras e selecione uma transmissão antes de perguntar.')
      return
    }
    await sendVisionQuestion(
      prompt?.trim() || `O que você vê na ${capture.cameraName}?`,
      capture.image,
      capture.cameraName,
    )
  }

  const handleChatAttachment = (file: File) => {
    if (!file.type.startsWith('image/')) {
      setNotice('Por enquanto, o chat aceita imagens para análise. Use Tela para capturar o monitor.')
      return
    }
    if (file.size > 8_000_000) {
      setNotice('A imagem é grande demais. Escolha uma imagem de até 8 MB.')
      return
    }
    const reader = new FileReader()
    reader.onload = () => setChatAttachment({ name: file.name, dataUrl: String(reader.result) })
    reader.onerror = () => setNotice('Não foi possível ler a imagem selecionada.')
    reader.readAsDataURL(file)
  }

  const sendChatMessage = async () => {
    const message = query.trim()
    const attachment = chatAttachment
    if (attachment) {
      setQuery('')
      setChatAttachment(null)
      await sendVisionQuestion(message || `Descreva a imagem enviada: ${attachment.name}`, attachment.dataUrl, attachment.name)
      return
    }
    if (!message) return
    const asksAboutCamera = /\b(c[aâ]mera|webcam)\b/i.test(message)
    if (asksAboutCamera && !cameraWorkspaceOpen) {
      setCameraQuestion(message)
      setQuery('')
      setCameraWorkspaceOpen(true)
      setNotice('Selecione uma câmera no plano e envie sua pergunta por lá.')
      return
    }
    if (asksAboutCamera && cameraWorkspaceOpen) {
      setQuery('')
      await askCameraQuestion(message)
      return
    }
    setQuery('')
    await sendText(message, chatMode)
  }

  const renderSection = () => {
    const page = (() => {
    if (active === 'Dashboard') {
      return (
        <DashboardPage
          dashboard={dashboard}
          finance={finance}
          ttsSettings={ttsSettings}
          proactive={proactive}
          tray={tray}
          taskTitle={taskTitle}
          taskInputRef={taskInputRef}
          onTaskTitleChange={setTaskTitle}
          onAddTask={addTask}
          onToggleTask={toggleTask}
          onDeleteTask={deleteTask}
        />
      )
    }
    if (active === 'Automações') {
      return (
        <AutomationsPage
          climate={climate}
          bridge={bridge}
          proactive={proactive}
          reminderMessage={reminderMessage}
          reminderTime={reminderTime}
          onReminderMessageChange={setReminderMessage}
          onReminderTimeChange={setReminderTime}
          onAddReminder={addReminder}
          onSetTemperature={setTemperature}
          onTriggerBriefing={triggerBriefing}
          onRegisterBridgeDemo={() => registerBridgeDemo().catch(() => setNotice('Falha ao registrar o dispositivo de teste.'))}
          onBridgeCommand={(targetId, command) => sendBridgeCommand(targetId, command).catch(() => setNotice('Falha ao enviar o comando para a ponte.'))}
        />
      )
    }
    if (active === 'Chat') {
      return (
        <ChatPage
          sessions={sessions}
          sessionId={sessionId}
          messages={messages}
          answer={answer}
          loading={loading}
          streamingReply={streamingReply}
          liveSearch={liveSearch}
          liveReasoning={liveReasoning}
          chatError={chatError}
          query={query}
          chatMode={chatMode}
          chatAttachment={chatAttachment}
          recording={recording}
          pendingScript={pendingScript}
          onSelectSession={selectSession}
          onCreateSession={() => createSession().catch(error => {
            const message = error instanceof Error ? error.message : 'Não foi possível criar uma nova conversa.'
            setNotice(message)
            setAnswer(message)
          })}
          onExportSession={() => handleExportSession().catch(() => undefined)}
          onOpenLiveCall={() => setLiveCallOpen(true)}
          onSpeakText={speakText}
          onClearChatError={() => setChatError('')}
          onQueryChange={setQuery}
          onModeChange={setChatMode}
          onAttachment={handleChatAttachment}
          onClearAttachment={() => setChatAttachment(null)}
          onSubmit={() => sendChatMessage()}
          onVoice={toggleVoiceInput}
          onScreen={captureVision}
          onCinema={() => setCinemaLauncherOpen(true)}
          onCinemaRequest={openCinemaPayload}
          onSendText={sendText}
          onRunPendingScript={runPendingScript}
        />
      )
    }
    if (active === 'Análises') {
      return (
        <AnalyticsPage
          metrics={metrics}
          visibleLogs={visibleLogs}
          logLevel={logLevel}
          logQuery={logQuery}
          onLogLevelChange={setLogLevel}
          onLogQueryChange={setLogQuery}
          onRefresh={() => refreshAnalytics().catch(() => undefined)}
        />
      )
    }
    if (active === 'Estudos') {
      return (
        <StudyPage
          tutorSessions={tutorSessions}
          studyCategories={studyCategories}
          trashedStudySessions={trashedStudySessions}
          renameStudySession={renameStudySession}
          deleteStudySession={deleteStudySession}
          restoreStudySession={restoreStudySession}
          purgeStudySession={purgeStudySession}
          createStudyCategory={createStudyCategory}
          assignStudyCategory={assignStudyCategory}
          studySessionId={studySessionId}
          selectStudySession={selectStudySession}
          createStudySession={createStudySession}
          studyProgress={studyProgress}
          dueCards={dueCards}
          studyCardIndex={studyCardIndex}
          cardBackVisible={cardBackVisible}
          setCardBackVisible={setCardBackVisible}
          reviewCard={reviewCard}
          enemQuestions={enemQuestions}
          feynmanTopic={feynmanTopic}
          feynmanExplanation={feynmanExplanation}
          setFeynmanTopic={setFeynmanTopic}
          setFeynmanExplanation={setFeynmanExplanation}
          saveFeynman={saveFeynman}
          feynmanAttempts={feynmanAttempts}
          assessmentCorrect={assessmentCorrect}
          assessmentTotal={assessmentTotal}
          setAssessmentCorrect={setAssessmentCorrect}
          setAssessmentTotal={setAssessmentTotal}
          saveAssessment={saveAssessment}
          assessments={assessments}
          enemSubject={enemSubject}
          enemYear={enemYear}
          enemText={enemText}
          enemImage={enemImage}
          setEnemSubject={setEnemSubject}
          setEnemYear={setEnemYear}
          setEnemText={setEnemText}
          setEnemImage={setEnemImage}
          readEnemImage={readEnemImage}
          saveEnemQuestion={saveEnemQuestion}
          setStudyQuery={setStudyQuery}
          setStudySessionId={setStudySessionId}
          studyMessages={studyMessages}
          studyQuery={studyQuery}
          sendStudyMessage={sendStudyMessage}
          studyEnemFromForm={studyEnemFromForm}
          studyEnemFromBank={studyEnemFromBank}
          whiteboard={whiteboard}
          whiteboardNote={whiteboardNote}
          setWhiteboardNote={setWhiteboardNote}
          saveWhiteboard={addWhiteboardNote}
          addWhiteboardText={addWhiteboardText}
          addWhiteboardImage={addWhiteboardImage}
          addWhiteboardImageData={addWhiteboardImageData}
          updateWhiteboardElement={updateWhiteboardElement}
          deleteWhiteboardElement={deleteWhiteboardElement}
          duplicateWhiteboardElement={duplicateWhiteboardElement}
          clearWhiteboard={clearWhiteboard}
          setNotice={setNotice}
        />
      )
    }
    if (active === 'Calendário') return <CalendarSection onNotice={setNotice} />
    if (active === 'Configurações') {
      return (
        <SettingsPage
          ttsSettings={ttsSettings}
          llmSettings={llmSettings}
          wakeWord={wakeWord}
          tray={tray}
          proactive={proactive}
          briefingTime={briefingTime}
          briefingTopics={briefingTopics}
          briefingInstructions={briefingInstructions}
          notice={notice}
          onSetTtsProvider={setTtsProvider}
          onSetProvider={setProvider}
          onSetWakeWordEnabled={setWakeWordEnabled}
          onSetBootEnabled={setBootEnabled}
          speakEnabled={speakEnabled}
          onSetSpeakEnabled={setSpeakEnabled}
          onSaveBriefing={saveBriefing}
          onBriefingTimeChange={setBriefingTime}
          onToggleBriefingTopic={toggleBriefingTopic}
          onBriefingInstructionsChange={setBriefingInstructions}
        />
      )
    }
    if (active === 'Memórias') {
      return (
        <MemoriesPage
          memories={memories}
          memoryCollection={memoryCollection}
          notice={notice}
          onRefresh={() => refreshMemories()}
          onClearTechnical={clearTechnicalMemories}
          onSelectCollection={collection => {
            setMemoryCollection(collection)
            refreshMemories(collection)
          }}
        />
      )
    }
    return (
      <section className="migration-card">
        <p className="eyebrow">MIGRAÇÃO GRADUAL</p>
        <h2>{active}</h2>
        <p>Esta área continua disponível no painel legado em /legacy.</p>
      </section>
    )
    })()

    return (
      <Suspense fallback={<section className="page-loading"><p className="eyebrow">CARREGANDO</p><strong>{active}</strong></section>}>
        {page}
      </Suspense>
    )
  }

  const quickActions = (
    <>
      <button type="button" className="sidebar-action-btn" onClick={openNewTask} title="Nova tarefa"><span>✚</span> <span>Nova tarefa</span></button>
      <button type="button" className="sidebar-action-btn" onClick={() => setCinemaLauncherOpen(true)} title="Abrir cinema"><span>◉</span> <span>Cinema</span></button>
      <button type="button" className="sidebar-action-btn" onClick={captureVision} title="Analisar tela"><span>👁</span> <span>Visão</span></button>
      <button type="button" className={`sidebar-action-btn${recording ? ' sidebar-action-active' : ''}`} onClick={toggleVoiceInput} title={recording ? 'Parar gravação' : 'Falar com Jarvis'}><span>{recording ? '⏹' : '🎙'}</span> <span>{recording ? 'Parar' : 'Voz'}</span></button>
      <button type="button" className="sidebar-action-btn" onClick={() => { setCameraQuestion(''); setCameraWorkspaceOpen(true) }} title="Câmeras"><span>📷</span> <span>Câmeras</span></button>
      <button type="button" className="sidebar-action-btn" onClick={() => setLiveCallOpen(true)} title="Ligação"><span>📞</span> <span>Ligação</span></button>
    </>
  )

  const hero = active === 'Dashboard' ? (
    <DashboardHero weather={weather} onOpenCinema={() => setCinemaLauncherOpen(true)} />
  ) : null

  return (
    <>
      <AppShell
        active={active}
        navItems={navItems}
        sidebarCollapsed={sidebarCollapsed}
        onToggleSidebar={() => setSidebarCollapsed(!sidebarCollapsed)}
        onNavigate={setActive}
        headerExtra={active === 'Chat' && sessionId ? <button type="button" className="header-delete" onClick={() => deleteSession(sessionId)}>Excluir conversa</button> : null}
        hero={hero}
        quickActions={quickActions}
      >
        {renderSection()}
      </AppShell>
      <CameraWorkspace ref={cameraWorkspaceRef} open={cameraWorkspaceOpen} initialQuestion={cameraQuestion} onClose={() => { setCameraQuestion(''); setCameraWorkspaceOpen(false) }} onQuestion={async (image, cameraName, prompt) => { setCameraQuestion(''); setCameraWorkspaceOpen(false); setActive('Chat'); await sendVisionQuestion(prompt || `O que você vê na ${cameraName}?`, image, cameraName) }} />
      <CinemaModal
        open={cinemaLauncherOpen}
        onClose={() => setCinemaLauncherOpen(false)}
        onPlay={openVideo}
        cinemaQuery={cinemaQuery}
        setCinemaQuery={setCinemaQuery}
        videoUrl={videoUrl}
        setVideoUrl={setVideoUrl}
        cinemaResults={cinemaResults}
        cinemaMedia={cinemaMedia}
        cinemaStatus={cinemaStatus}
        setCinemaStatus={setCinemaStatus}
        cinemaLibrary={cinemaLibrary}
        refreshCinemaLibrary={refreshCinemaLibrary}
        searchCinema={searchCinema}
        probeCinema={probeCinema}
        saveCinemaUrl={saveCinemaUrl}
        selectedLibraryItem={selectedLibraryItem}
        selectedLibraryId={selectedLibraryId}
        selectLibraryItem={selectLibraryItem}
        availableSeasons={availableSeasons}
        availableEpisodes={availableEpisodes}
        selectedSeason={selectedSeason}
        selectedEpisode={selectedEpisode}
        selectedSourceUrl={selectedSourceUrl}
        selectSeason={selectSeason}
        selectEpisode={selectEpisode}
        selectLibrarySource={selectLibrarySource}
        selectNextEpisode={selectNextEpisode}
        selectedLibrarySources={selectedLibrarySources}
      />
      {visionResult && <div className="tool-modal" role="dialog" aria-modal="true" aria-label="Análise visual"><section className="vision-modal"><button className="modal-close" onClick={() => setVisionResult(null)} aria-label="Fechar">×</button><p className="eyebrow">FERRAMENTA · VISÃO</p><h2>Análise de tela</h2>{visionResult.imageUrl && <img src={visionResult.imageUrl} alt="Captura de tela analisada" />}<p>{visionResult.reply}</p></section></div>}
      <LiveCallModal open={liveCallOpen} onClose={closeLiveCall} recording={liveCallRecording} status={liveCallStatus} onToggleCapture={toggleLiveCallCapture} />
      {pendingScript && <div className="tool-modal" role="dialog" aria-modal="true" aria-label="Confirmar script"><section className="vision-modal"><button className="modal-close" onClick={() => setPendingScript(null)} aria-label="Cancelar">×</button><p className="eyebrow">CONFIRMAÇÃO NECESSÁRIA</p><h2>Executar script?</h2><p>{pendingScript.description}</p><pre>{pendingScript.code}</pre><div className="library-actions"><button type="button" onClick={() => setPendingScript(null)}>Cancelar</button><button type="button" onClick={() => runPendingScript()}>Executar {pendingScript.language}</button></div></section></div>}
      {playingUrl && <div className="player-modal"><IsolatedVideoPlayer
        src={playingUrl}
        onClose={() => setPlayingUrl('')}
        title={selectedLibraryItem?.title || cinemaQuery || 'Jarvis Cinema'}
        mediaType={selectedLibraryItem?.type || 'movie'}
        currentSeason={selectedSeason}
        currentEpisode={selectedEpisode}
        episodes={selectedLibraryItem?.episodes || []}
        onNextEpisode={() => {
          const next = selectNextEpisode()
          if (next) setPlayingUrl(next)
        }}
      /></div>}
      <Toast message={notice} onDismiss={dismissNotice} />
    </>
  )

}
