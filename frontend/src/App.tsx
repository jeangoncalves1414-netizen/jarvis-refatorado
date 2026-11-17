import { pairedAndroid } from './utils/pairedAndroid'
import { LiveEnrollment, handleLiveIntroduction } from './components/LiveEnrollment'
import { autoAllows } from './components/AutoApprovals'
import { isEvoluteCloudConnected } from './utils/evoluteCloud'
import { pollVisible } from './utils/panelVisibility'
import { isCameraObservationRequest, isCameraPanelRequest } from './utils/cameraRequest'
import { captureRequestedCameras } from './utils/cameraCapture'
import { FormEvent, lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { SettingsPage } from './pages/SettingsPage'
import { AppShell } from './components/AppShell'
import { AgentControls } from './components/AgentControls'
import { useOperationalSnapshot } from './hooks/useOperationalSnapshot'
import { panelRequest } from './utils/panelApi'
import { extractScreenRequest, resolveScreen } from './navigation'
import { WorkspaceHome, IntegrationsPage } from './pages/WorkspaceOverview'
import { CameraWorkspace, type CameraWorkspaceHandle } from './components/CameraWorkspace'
import { type ChatMode } from './components/ChatComposer'
import { CalendarSection } from './components/Calendar'
import { DashboardHero } from './components/DashboardHero'
import { Toast } from './components/Toast'
import { MatrixScanlineEffect } from './components/MatrixScanlineEffect'
// MatrixScanlineEffect is disabled on mobile to save CPU
import { ErrorBoundary } from './components/ErrorBoundary'
import { SkeletonLoader } from './components/SkeletonLoader'
import { useChat } from './hooks/useChat'
import { useConversationRun } from './hooks/useConversationRun'
import { useDirectChat, isMobileStandalone } from './hooks/useDirectChat'
import { useCinema } from './hooks/useCinema'
import { useMediaAssistant } from './hooks/useMediaAssistant'
import { useStudy } from './hooks/useStudy'
import { useLanguage } from './hooks/useLanguage'
import { playToggle, playSuccess, toggleSfx } from './utils/sfx'
import { Repeat } from 'lucide-react'
import { runCommandById, setDynamicCommands, unescapeSlash, WINDOW_CAMERAS, WINDOW_CINEMA, WINDOW_LIFE_OS, WINDOW_LIVE_CALL, type CommandHandlers } from './commands/registry'
import { extractWindowRequest, isManagedWindow } from './windows/registry'
import { useWindows } from './windows/WindowManager'
import { usePopups } from './popups/PopupProvider'
import { NoteViewer } from './components/RecentNotes'
import { PopupHost } from './popups/PopupHost'
import { extractPopups } from './popups/registry'
import { broadcastSyncEvent } from './utils/syncChannel'
import { addWaterDraft, flushWaterDrafts, loadWaterDrafts, postWater } from './utils/waterDrafts'
import { requestNotificationPermission } from './utils/notifications'
import { CloudSessionStatus } from './components/CloudSessionStatus'
import { autoSyncOnOpen, pushJarvisVault } from './utils/jarvisCloud'
import type { AiSettings, BridgeStatus, Climate, Dashboard, Finance, IdentityProfile, LlmSettings, LogEntry, Memory, Metrics, OxyyCatalog, OxyySettings, ProfileMemory, Proactive, SttSettings, Tray, TtsSettings, WakeWord, Weather } from './types'

const AutomationsPage = lazy(() => import('./pages/AutomationsPage').then(module => ({ default: module.AutomationsPage })))
const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage').then(module => ({ default: module.AnalyticsPage })))
const ChatPage = lazy(() => import('./pages/ChatPage').then(module => ({ default: module.ChatPage })))
const DashboardPage = lazy(() => import('./pages/DashboardPage').then(module => ({ default: module.DashboardPage })))
const MemoriesPage = lazy(() => import('./pages/MemoriesPage').then(module => ({ default: module.MemoriesPage })))
const StudyPage = lazy(() => import('./pages/StudyPage').then(module => ({ default: module.StudyPage })))
const LanguagePage = lazy(() => import('./pages/LanguagePage').then(module => ({ default: module.LanguagePage })))
const IdentityPage = lazy(() => import('./pages/IdentityPage').then(module => ({ default: module.IdentityPage })))
const EvoluteHubPage = lazy(() => import('./pages/EvoluteHubPage').then(module => ({ default: module.EvoluteHubPage })))
const MissionControlPage = lazy(() => import('./pages/MissionControlPage').then(module => ({ default: module.MissionControlPage })))
const HealthPage = lazy(() => import('./pages/HealthPage').then(module => ({ default: module.HealthPage })))

// Heavy modals loaded on demand
const ToolForgeModal = lazy(() => import('./components/ToolForgeModal').then(module => ({ default: module.ToolForgeModal })))
const CinemaModal = lazy(() => import('./components/CinemaModal').then(module => ({ default: module.CinemaModal })))
const LiveCallModal = lazy(() => import('./components/LiveCallModal').then(module => ({ default: module.LiveCallModal })))
const IsolatedVideoPlayer = lazy(() => import('./components/VideoPlayer').then(module => ({ default: module.VideoPlayer })))
const CommandPalette = lazy(() => import('./components/CommandPalette').then(module => ({ default: module.CommandPalette })))

const ACTIVE_SCREEN_KEY = 'jarvis-active-screen'
const IS_MOBILE = isMobileStandalone()

function readActiveScreen() {
  if (IS_MOBILE) return 'Chat'
  try {
    const stored = localStorage.getItem(ACTIVE_SCREEN_KEY)
    if (stored) return resolveScreen(stored)
  } catch {
    /* ignore storage errors */
  }
  return 'Chat'
}

export default function App() {
  useEffect(() => {
    void panelRequest('/api/finance/banks', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'opened' }) }).catch(() => {})
  }, [])
  const operational = useOperationalSnapshot()
  const [isToolForgeOpen, setIsToolForgeOpen] = useState(false)
  const [active, setActive] = useState(readActiveScreen)
  const [linkedRun, setLinkedRun] = useState('')
  useEffect(() => { if (active !== 'Central') setLinkedRun('') }, [active])
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false)

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
  const [aiSettings, setAiSettings] = useState<AiSettings | null>(null)
  const [ttsSettings, setTtsSettings] = useState<TtsSettings | null>(null)
  const [sttSettings, setSttSettings] = useState<SttSettings | null>(null)
  const [oxyySettings, setOxyySettings] = useState<OxyySettings | null>(null)
  const [oxyyCatalog, setOxyyCatalog] = useState<OxyyCatalog | null>(null)
  const [wakeWord, setWakeWord] = useState<WakeWord | null>(null)
  const [wakeHeard, setWakeHeard] = useState(false)
  const wakeHeardTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [tray, setTray] = useState<Tray | null>(null)
  const [briefingTime, setBriefingTime] = useState('08:00')
  const [briefingTopics, setBriefingTopics] = useState<string[]>(['weather', 'tasks', 'news'])
  const [briefingInstructions, setBriefingInstructions] = useState('')
  const [reminderMessage, setReminderMessage] = useState('')
  const [reminderTime, setReminderTime] = useState('+10m')
  const [notice, setNotice] = useState('')
  const [logLevel, setLogLevel] = useState('')
  const [logQuery, setLogQuery] = useState('')
  const { addWhiteboardNote, addWhiteboardText, addWhiteboardImage, addWhiteboardImageData, updateWhiteboardElement, deleteWhiteboardElement, duplicateWhiteboardElement, clearWhiteboard, assessmentCorrect, assessmentTotal, assessments, cardBackVisible, createStudySession, dueCards, studyCategories, trashedStudySessions, renameStudySession, deleteStudySession, restoreStudySession, purgeStudySession, createStudyCategory, assignStudyCategory, enemImage, enemQuestions, enemSubject, enemText, enemYear, feynmanAttempts, feynmanExplanation, feynmanTopic, readEnemImage, reviewCard, undoReview, studyUndoCount, nextCardDueAt, refreshStudy, saveAssessment, saveEnemQuestion, saveFeynman, selectStudySession, sendStudyMessage, sendTutorMessage, setAssessmentCorrect, setAssessmentTotal, setCardBackVisible, setEnemImage, setEnemSubject, setEnemText, setEnemYear, setFeynmanExplanation, setFeynmanTopic, setStudyQuery, setStudySessionId, setWhiteboardNote, studyCardIndex, studyEnemFromBank, studyEnemFromForm, studyMessages, studyProgress, studyQuery, studySessionId, tutorSessions, whiteboard, whiteboardNote } = useStudy(setNotice)
  const language = useLanguage(setNotice)
  const [taskTitle, setTaskTitle] = useState('')
  const [memories, setMemories] = useState<Memory[]>([])
  const [memoryCollection, setMemoryCollection] = useState<'cited' | 'conversations' | 'user_memory' | 'profile_memory'>('conversations')
  const [identityProfiles, setIdentityProfiles] = useState<IdentityProfile[]>([])
  const [selectedProfileId, setSelectedProfileId] = useState('')
  const [profileMemories, setProfileMemories] = useState<ProfileMemory[]>([])
  const [playingUrl, setPlayingUrl] = useState('')
  const [cameraWorkspaceOpen, setCameraWorkspaceOpen] = useState(false)
  const [cameraQuestion, setCameraQuestion] = useState('')
  const [chatMode, setChatMode] = useState<ChatMode>('auto')
  const [chatAttachment, setChatAttachment] = useState<{ name: string; dataUrl: string } | null>(null)
  const [apiKeys, setApiKeysState] = useState<Record<string, string>>({})

  const openEvoluteWindow = () => {
    // Evolution is now a first-class integrated panel inside Jarvis on both PC and mobile
    setActive('Evolução')
  }

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') || (e.altKey && e.key.toLowerCase() === 'j')) {
        e.preventDefault()
        setIsCommandPaletteOpen(prev => !prev)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  // Fase contexto 2: "editar" numa memória citada no chat abre Memórias > Com fonte.
  useEffect(() => {
    const openOrganizer = () => setActive('Dashboard')
    window.addEventListener('jarvis:personal-open', openOrganizer)
    const openFromLifeOS = (event: MessageEvent) => {
      if (event.origin === window.location.origin && event.data?.type === 'jarvis:open-personal' && event.data.kind === 'workout') {
        void import('./utils/personalRecords').then(({ openOrganizer }) => openOrganizer({ kind: 'workout', query: typeof event.data.query === 'string' ? event.data.query.slice(0, 100) : '' }))
      }
    }
    window.addEventListener('message', openFromLifeOS)
    const personalLink = new URLSearchParams(window.location.search)
    if (personalLink.get('personal') === 'workout') {
      void import('./utils/personalRecords').then(({ openOrganizer }) => openOrganizer({ kind: 'workout', query: (personalLink.get('query') || '').slice(0, 100) }))
    }
    fetch('/api/personal').then(r => r.ok ? r.json() : null).then(data => {
      if (data?.preferences) document.documentElement.classList.toggle('personal-reduced-motion', data.preferences.reduced_motion === true)
    }).catch(() => undefined)
    return () => { window.removeEventListener('jarvis:personal-open', openOrganizer); window.removeEventListener('message', openFromLifeOS) }
  }, [])

  useEffect(() => {
    const openMemory = () => { setActive('Memórias'); setMemoryCollection('cited') }
    window.addEventListener('jarvis:open-memory', openMemory)
    return () => window.removeEventListener('jarvis:open-memory', openMemory)
  }, [])

  // Fase contexto 3: botão "Abrir Configurações" na janela Casa.
  useEffect(() => {
    const openSettings = () => setActive('Configurações')
    window.addEventListener('jarvis:open-settings', openSettings)
    return () => window.removeEventListener('jarvis:open-settings', openSettings)
  }, [])

  // Auto-sync on app open (for mobile and PC)
  useEffect(() => {
    void autoSyncOnOpen().catch(() => setNotice('Não foi possível sincronizar a conta ao abrir. Verifique a conexão nas Configurações.'))
  }, [])

  // Request native notification permission on first user interaction
  useEffect(() => {
    const requestOnFirstInteraction = () => {
      requestNotificationPermission().catch(() => undefined)
      document.removeEventListener('click', requestOnFirstInteraction)
    }
    document.addEventListener('click', requestOnFirstInteraction, { once: true })
    return () => document.removeEventListener('click', requestOnFirstInteraction)
  }, [])

  const popups = usePopups()
  const showPopup = popups.show
  const handleQuickAddWater = useCallback(async (ml = 250) => {
    const result = await postWater(ml)
    if (!result.ok) {
      // Sem confirmação do servidor nada é somado: o valor fica como rascunho para reenviar.
      addWaterDraft(ml)
      setNotice(`Não consegui registrar +${ml}ml de água (${result.error}). Guardei o registro neste aparelho e reenvio quando o Jarvis responder.`)
      return
    }
    playSuccess()
    setNotice(`+${ml}ml de água registrados!`)
    broadcastSyncEvent('WATER_UPDATED', { amount_ml: ml })
    // A rota devolve o popup de água montado com os totais do Life OS (lote 6).
    if (result.data?.popup) showPopup(result.data.popup as Parameters<typeof showPopup>[0])
    if (loadWaterDrafts().length) {
      const flushed = await flushWaterDrafts()
      if (flushed.sent) { setNotice(`Reenviei ${flushed.sentMl}ml de água que estavam guardados.`); broadcastSyncEvent('WATER_UPDATED', { amount_ml: flushed.sentMl }) }
    }
  }, [setNotice, showPopup])

  // Reenvia registros de água guardados quando o app abre ou a rede volta.
  useEffect(() => {
    const retry = () => {
      if (!loadWaterDrafts().length) return
      void flushWaterDrafts().then(flushed => {
        if (!flushed.sent) return
        setNotice(`Reenviei ${flushed.sentMl}ml de água que estavam guardados.`)
        broadcastSyncEvent('WATER_UPDATED', { amount_ml: flushed.sentMl })
      })
    }
    retry()
    window.addEventListener('online', retry)
    return () => window.removeEventListener('online', retry)
  }, [setNotice])

  useEffect(() => {
    if (IS_MOBILE) return
    fetch('/api/settings/keys')
      .then(res => res.json())
      .then(data => { if (data.ok && data.keys) setApiKeysState(data.keys) })
      .catch(() => undefined)
  }, [])

  const saveApiKeys = async (keys: Record<string, string>) => {
    try {
      const res = await fetch('/api/settings/keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keys }),
      })
      const data = await res.json()
      if (!res.ok || !data.ok || !data.keys) throw new Error('Falha ao salvar')
      setApiKeysState(data.keys)
      setNotice('Chaves salvas neste computador.')
      if (isEvoluteCloudConnected()) {
        try {
          await pushJarvisVault()
          setNotice('Chaves salvas e sincronizadas com sua conta.')
        } catch {
          setNotice('Chaves salvas neste computador, mas o envio à nuvem falhou. Tente Salvar Chaves novamente quando a conexão voltar.')
        }
      }
    } catch {
      setNotice('Erro ao salvar chaves de API.')
    }
  }
  const cameraWorkspaceRef = useRef<CameraWorkspaceHandle>(null)
  const taskInputRef = useRef<HTMLInputElement>(null)
  const windows = useWindows()
  // Interface pedida pelo agente no contexto da resposta: janela (open_window) e tela (open_screen).
  // Ids e parâmetros são validados de novo aqui; o agente nunca gera interface.
  const showAgentPopup = (raw: unknown) => {
    if (!popups.show(raw)) setNotice('O agente pediu um popup inválido.')
  }
  const applyAgentUi = (context: unknown) => {
    const windowRequest = extractWindowRequest(context)
    if (windowRequest && !windows.open(windowRequest.windowId, windowRequest.params)) setNotice('O agente pediu uma janela que não existe ou com parâmetros inválidos.')
    const screen = extractScreenRequest(context)
    if (screen) setActive(screen)
    // Popups (lote 6): o mesmo popup pode ter chegado pelo WebSocket; id repetido é descartado.
    extractPopups(context).forEach(showAgentPopup)
  }
  const pcChat = useChat({ onAgentContext: context => applyAgentUi(context), onWakeWord: phrase => handleWakeWord(phrase), onPopup: showAgentPopup })
  const mobileChat = useDirectChat()
  const { answer, chatError, copySession, createSession, deleteSession, exportSession, loading, liveReasoning, liveSearch, messages, pendingScript, query, runPendingScript, selectSession, sendText, sendVisionQuestion, sessionId, sessions, setAnswer, setChatError, setPendingScript, setQuery, streamingReply } = IS_MOBILE ? mobileChat : pcChat
  const conversationRun = useConversationRun(sessionId, !IS_MOBILE, loading)
  const { captureVision, closeLiveCall, liveCallOpen, liveCallRecording, liveCallStatus, liveAudioDiagnostics, liveUserTranscript, liveJarvisTranscript, liveTurns, liveOrbState, recording, setLiveCallOpen, setSpeakEnabled, setVisionResult, speakEnabled, speakText, toggleLiveCallCapture, toggleVoiceInput, triggerBargeIn, visionResult, pushToTalkMode, togglePushToTalk, startPtt, stopPtt, isPttActive } = useMediaAssistant({ query, sendText, setAnswer, setQuery, sessionId, appendExchange: IS_MOBILE ? undefined : pcChat.appendExchange, previewExchange: IS_MOBILE ? undefined : pcChat.previewExchange, onAgentContext: IS_MOBILE ? undefined : context => applyAgentUi(context) })
  const { cinemaSearch, availableEpisodes, availableSeasons, cinemaLauncherOpen, setCinemaLauncherOpen, videoUrl, setVideoUrl, cinemaQuery, setCinemaQuery, cinemaResults, cinemaMedia, cinemaStatus, setCinemaStatus, cinemaLibrary, refreshCinemaLibrary, searchCinema, probeCinema, saveCinemaUrl, openCinemaPayload, selectEpisode, selectLibraryItem, selectLibrarySource, selectNextEpisode, selectSeason, selectedEpisode, selectedLibraryItem, selectedLibraryId, selectedLibrarySources, selectedSeason, selectedSourceUrl } = useCinema()

  const setTtsProvider = async (tts_provider: 'fish' | 'gemini' | 'edge' | 'oxyy') => {
    const response = await fetch('/api/settings/tts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tts_provider }) })
    setTtsSettings(await response.json())
    await refreshAiRoutes()
  }

  const refreshOxyy = async () => {
    const [settingsResponse, catalogResponse] = await Promise.all([
      fetch('/api/settings/oxyy'),
      fetch('/api/settings/oxyy/models'),
    ])
    if (settingsResponse.ok) setOxyySettings(await settingsResponse.json())
    if (catalogResponse.ok) setOxyyCatalog(await catalogResponse.json())
  }

  const saveOxyy = async (models: OxyySettings['models']) => {
    const response = await fetch('/api/settings/oxyy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ models }),
    })
    if (!response.ok) throw new Error('Não foi possível salvar a configuração Oxyy.')
    setOxyySettings(await response.json())
    await refreshAiRoutes()
    setNotice('Configuração Oxyy salva.')
  }

  const setSttProvider = async (stt_provider: 'local' | 'groq' | 'oxyy' | 'google') => {
    const response = await fetch('/api/settings/stt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ stt_provider }),
    })
    const data = await response.json()
    if (!response.ok) throw new Error(data.error || 'Não foi possível alterar o provedor STT.')
    setSttSettings(data)
    refreshAiRoutes()
    setNotice('Provedor de transcrição atualizado.')
  }

  const refreshAiRoutes = async () => {
    const response = await fetch('/api/settings/ai')
    if (response.ok) {
      const data = await response.json()
      setAiSettings(data)
      const chat = data.routes?.chat
      if (chat) setLlmSettings(previous => ({ ...previous, llm_provider: chat.primary?.provider, effective_provider: chat.effective?.provider, effective_model: chat.effective?.model, fallback_used: chat.fallback_used, fallback_reason: chat.reason, route: chat }))
    }
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

  const handleCopySession = async () => {
    if (!sessionId) return
    const copied = await copySession(sessionId)
    if (copied) setNotice('Chat copiado para o clipboard!')
  }

  const openNewTask = () => {
    setActive('Dashboard')
    window.setTimeout(() => taskInputRef.current?.focus(), 120)
  }

  useEffect(() => {
    if (IS_MOBILE) return
    fetch('/api/realtime').then(response => response.json()).then(data => { setWeather(data.weather); setFinance(data.finance) }).catch(() => undefined)
    fetch('/api/dashboard').then(response => response.json()).then(setDashboard).catch(() => undefined)
    fetch('/api/climate').then(response => response.json()).then(setClimate).catch(() => undefined)
    fetch('/api/bridge').then(response => response.json()).then(setBridge).catch(() => undefined)
    fetch('/api/bridge', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'pairing_code' }) })
      .then(response => response.ok ? response.json() : null)
      .then(data => { if (data?.pairing_code) setBridge(previous => previous ? { ...previous, pairing_code: data.pairing_code } : previous) })
      .catch(() => undefined)
    fetch('/api/settings/llm').then(response => response.json()).then(setLlmSettings).catch(() => undefined)
    fetch('/api/settings/ai').then(response => response.json()).then(setAiSettings).catch(() => undefined)
    fetch('/api/settings/tts').then(response => response.json()).then(setTtsSettings).catch(() => undefined)
    fetch('/api/settings/stt').then(response => response.json()).then(setSttSettings).catch(() => undefined)
    fetch('/api/settings/oxyy').then(response => response.json()).then(setOxyySettings).catch(() => undefined)
    fetch('/api/settings/oxyy/models').then(response => response.json()).then(setOxyyCatalog).catch(() => undefined)
    fetch('/api/memories?collection=conversations&limit=20').then(response => response.json()).then(data => setMemories(data.memories || [])).catch(() => undefined)
    if (!pairedAndroid) fetch('/api/identity').then(response => response.json()).then(data => setIdentityProfiles(data.profiles || [])).catch(() => undefined)
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
    if (IS_MOBILE) return
    const refreshBridge = () => fetch('/api/bridge').then(response => response.json()).then(setBridge).catch(() => undefined)
    return pollVisible(refreshBridge, 5_000)
  }, [])

  // O estado "ativo" do detector pode mudar sem a interface saber (modelo ausente, frase nova): reconsulta.
  useEffect(() => {
    if (IS_MOBILE) return
    const refreshWakeWord = () => fetch('/api/wake-word').then(response => response.json()).then(setWakeWord).catch(() => undefined)
    const stopPolling = pollVisible(refreshWakeWord, 15_000)
    return () => { stopPolling(); if (wakeHeardTimer.current) clearTimeout(wakeHeardTimer.current) }
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
    if (IS_MOBILE) return
    if (active !== 'Análises') return
    return pollVisible(() => refreshAnalytics(), 15_000, true)
  }, [logLevel, active])

  const visibleLogs = logs.filter(log => `${log.component || ''} ${log.message || ''}`.toLocaleLowerCase('pt-BR').includes(logQuery.trim().toLocaleLowerCase('pt-BR')))

  const refreshMemories = async (collection: 'conversations' | 'user_memory' = memoryCollection === 'profile_memory' || memoryCollection === 'cited' ? 'conversations' : memoryCollection) => {
    const response = await fetch(`/api/memories?collection=${collection}&limit=25`)
    const data = await response.json()
    setMemories(data.memories || [])
  }

  const refreshProfileMemories = async (profileId = selectedProfileId) => {
    if (!profileId) { setProfileMemories([]); return }
    const response = await fetch(`/api/profile-memory?profile_id=${encodeURIComponent(profileId)}&limit=100`)
    const data = await response.json()
    setProfileMemories(data.memories || [])
  }

  const addProfileMemory = async (text: string, kind: string, password: string) => {
    const response = await fetch('/api/profile-memory', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'add', profile_id: selectedProfileId, text, kind, password }) })
    const data = await response.json().catch(() => ({}))
    if (!response.ok || !data.ok) { setNotice(data.error || 'Não foi possível salvar a memória.'); return false }
    setNotice('Memória privada salva.')
    await refreshProfileMemories()
    return true
  }

  const deleteProfileMemory = async (memoryId: string, password: string) => {
    const response = await fetch('/api/profile-memory', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'delete', profile_id: selectedProfileId, memory_id: memoryId, password }) })
    const data = await response.json().catch(() => ({}))
    if (!response.ok || !data.ok) { setNotice(data.error || 'Não foi possível excluir a memória.'); return false }
    await refreshProfileMemories()
    return true
  }

  const clearProfileMemories = async (password: string) => {
    const response = await fetch('/api/profile-memory', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'clear', profile_id: selectedProfileId, password }) })
    const data = await response.json().catch(() => ({}))
    if (!response.ok || !data.ok) { setNotice(data.error || 'Não foi possível apagar as memórias.'); return false }
    setNotice(`${data.removed || 0} memória(s) privada(s) apagada(s).`)
    await refreshProfileMemories()
    return true
  }

  const clearTechnicalMemories = async () => {
    if (!await autoAllows('bulk') && !window.confirm('Remover da memória semântica os erros técnicos antigos? Isso não remove conversas normais.')) return
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
    return pollVisible(refreshLive, 25_000)
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
    if (!await autoAllows('remove') && !window.confirm('Remover esta tarefa?')) return
    await fetch('/api/tasks', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'delete', task_id: taskId }) })
    await refreshDashboard()
  }

  const setTemperature = async (value: number) => {
    const response = await fetch('/api/automation', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'set_temperature', device: 'climate', value }) })
    setClimate(await response.json())
  }

  const registerBridgeDemo = async () => {
    const pairingResponse = await fetch('/api/bridge', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'pairing_code' }) })
    const pairing = await pairingResponse.json()
    if (!pairingResponse.ok || !pairing.pairing_code) { setNotice(pairing.error || 'Abra esta tela no Jarvis local para parear um dispositivo.'); return }
    const existingToken = localStorage.getItem('jarvis-bridge-desktop-token') || ''
    let desktopToken = existingToken
    if (!desktopToken) {
      const controllerResponse = await fetch('/api/bridge', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'register', device_id: 'jarvis-desktop', name: 'Jarvis Desktop', kind: 'controller', platform: 'desktop', transport: 'local', pairing_code: pairing.pairing_code }) })
      const controller = await controllerResponse.json()
      if (!controllerResponse.ok || !controller.ok || !controller.device_token) { setNotice(controller.error || 'Não foi possível preparar o controle local.'); return }
      desktopToken = controller.device_token
      localStorage.setItem('jarvis-bridge-desktop-token', desktopToken)
    }
    const response = await fetch('/api/bridge', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'register', device_id: 'sim-lamp', name: 'Lâmpada de teste', kind: 'light', platform: 'simulator', transport: 'local', pairing_code: pairing.pairing_code }) })
    const data = await response.json()
    if (!response.ok || !data.ok) { setNotice(data.error || 'Não foi possível adicionar o dispositivo de teste.'); return }
    setBridge(previous => ({ ...previous, ...data, devices: [...(previous?.devices || []).filter(device => device.id !== data.device?.id), data.device] }))
    setNotice('Lâmpada de teste adicionada. Ela será substituída pelo adaptador real depois.')
  }

  const sendBridgeCommand = async (targetId: string, command: 'turn_on' | 'turn_off') => {
    const deviceToken = localStorage.getItem('jarvis-bridge-desktop-token') || ''
    const response = await fetch('/api/bridge', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'command', target_id: targetId, command, source: 'jarvis-desktop', device_token: deviceToken }) })
    const data = await response.json()
    if (!response.ok || !data.ok) { setNotice(data.error || 'Não foi possível enviar o comando.'); return }
    setBridge(previous => ({ ...previous, devices: (previous?.devices || []).map(device => device.id === targetId ? data.device : device) }))
    setNotice(data.executed ? 'Comando recebido e executado pelo dispositivo.' : 'Comando recebido pela ponte.')
  }

  const removeBridgeDevice = async (deviceId: string) => {
    // Só o controle local guarda credencial própria; os demais são revogados pelo dono no PC.
    const isLocalController = deviceId === 'jarvis-desktop'
    const deviceToken = isLocalController ? localStorage.getItem('jarvis-bridge-desktop-token') || '' : ''
    try {
      await panelRequest('/api/bridge', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'remove', device_id: deviceId, ...(deviceToken ? { device_token: deviceToken } : {}) }) })
    } catch (error) {
      if (error instanceof TypeError) throw new Error('Sem conexão com a ponte. Verifique se o backend está ligado e tente de novo.')
      // A ponte já não conhece o controle local: a credencial guardada deixou de valer.
      if (isLocalController && error instanceof Error && error.message.startsWith('Dispositivo não encontrado')) localStorage.removeItem('jarvis-bridge-desktop-token')
      throw error
    }
    if (isLocalController) localStorage.removeItem('jarvis-bridge-desktop-token')
    setBridge(previous => previous ? { ...previous, devices: (previous.devices || []).filter(device => device.id !== deviceId) } : previous)
    setNotice('Dispositivo removido da ponte.')
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

  // Ponto único de execução dos comandos do registro (paleta e menu "/"). Nada aqui chama o modelo.
  const commandHandlers: CommandHandlers = {
    stopRequest: () => { void conversationRun.stop() },
    navigate: screen => { playToggle(); setActive(screen) },
    openWindow: (windowId, params) => {
      if (isManagedWindow(windowId)) { if (!windows.open(windowId, params)) setNotice('Não foi possível abrir a janela.') }
      else if (windowId === WINDOW_LIFE_OS) openEvoluteWindow()
      else if (windowId === WINDOW_CINEMA) setCinemaLauncherOpen(true)
      else if (windowId === WINDOW_CAMERAS) { setCameraQuestion(''); setCameraWorkspaceOpen(true) }
      else if (windowId === WINDOW_LIVE_CALL) setLiveCallOpen(true)
      else setNotice('Esta janela ainda não está disponível.')
    },
    setMode: mode => { setChatMode(mode); setActive('Chat') },
    prefill: text => { setQuery(text); setActive('Chat') },
    newChat: () => { void Promise.resolve(createSession()).catch(() => setNotice('Não foi possível criar a conversa.')) },
    toggleDictation: toggleVoiceInput,
    toggleSfx: () => { playToggle(); toggleSfx() },
    addWater: ml => { void handleQuickAddWater(ml) },
    triggerBriefing: () => { void triggerBriefing().catch(() => setNotice('Não foi possível gerar o briefing.')) },
    triggerBackup: () => {
      playSuccess()
      setNotice('Iniciando download do backup completo...')
      window.location.href = '/api/system/backup'
    },
    captureVision,
    // Popup montado pelo backend a partir dos serviços, sem IA e sem Run (origem "command").
    openPopup: (template, params) => {
      const search = new URLSearchParams(params).toString()
      fetch(`/api/popups/${encodeURIComponent(template)}${search ? `?${search}` : ''}`)
        .then(async response => {
          const data = await response.json().catch(() => ({}))
          if (!response.ok || !data.ok) throw new Error(typeof data.error === 'string' ? data.error : '')
          if (!popups.show(data.popup)) throw new Error('O popup recebido é inválido.')
        })
        .catch(error => setNotice(error instanceof Error && error.message && error.message !== 'Failed to fetch' ? error.message : 'Não foi possível abrir o popup. Verifique se o backend está ligado.'))
    },
    clearPopups: () => popups.clear(),
    runRoutine: (routineId: string) => {
      panelRequest(`/api/routines/${encodeURIComponent(routineId)}/run`, { method: 'POST' })
        .then((res: unknown) => {
          const runId = (res as { ok?: boolean; run_id?: string })?.run_id
          setNotice('Rotina iniciada.')
          if (!IS_MOBILE && runId) {
            setLinkedRun(runId)
            setActive('Central')
          }
        })
        .catch((error: unknown) => {
          setNotice(`Não foi possível iniciar a rotina: ${error instanceof Error ? error.message : 'erro desconhecido.'}`)
        })
    },
  }

  const setWakeWordEnabled = async (enabled: boolean) => {
    const response = await fetch('/api/wake-word', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled }) })
    const data = await response.json()
    if (!response.ok) { setNotice(data.error || 'Não foi possível alterar a palavra de ativação.'); return }
    setWakeWord(previous => ({ ...previous, enabled: data.enabled, active: Boolean(data.enabled && previous?.running) }))
  }

  // Evento "wake_word" do detector local (chega pelo WebSocket do chat). Mostra o aviso e abre a
  // conversa por voz pelo mesmo comando do registro, com origem "voz". Ignora se já há ligação ou ditado.
  const handleWakeWord = (phrase: string) => {
    if (wakeHeardTimer.current) clearTimeout(wakeHeardTimer.current)
    setWakeHeard(true)
    wakeHeardTimer.current = setTimeout(() => setWakeHeard(false), 6000)
    if (phrase) setWakeWord(previous => ({ ...previous, phrase }))
    if (liveCallOpen || recording) return
    runCommandById('action-live-call', commandHandlers, { origin: 'voz' })
  }

  // Sincroniza comandos de barra (/) das rotinas a partir de GET /api/routines
  useEffect(() => {
    let cancelled = false
    const syncRoutineCommands = () => {
      panelRequest('/api/routines')
        .then((data: unknown) => {
          if (cancelled) return
          const payload = data as { ok?: boolean; commands?: { routine_id: string; name: string; slash: string }[] }
          if (!payload?.ok || !Array.isArray(payload.commands)) return
          const dynamicList = payload.commands.map(cmd => ({
            id: `routine-${cmd.routine_id}-${cmd.slash}`,
            label: cmd.name,
            title: `Executar rotina ${cmd.name}`,
            description: `Rotina /${cmd.slash}`,
            aliases: [],
            slash: cmd.slash,
            group: 'Ações Rápidas' as const,
            action: { kind: 'routine' as const, routineId: cmd.routine_id },
            worksOffline: true,
            icon: Repeat,
          }))
          setDynamicCommands(dynamicList)
        })
        .catch(() => { /* backend indisponível ou inicializando */ })
    }

    syncRoutineCommands()
    const onRoutineEvent = () => syncRoutineCommands()
    window.addEventListener('jarvis:routine-event', onRoutineEvent)
    return () => {
      cancelled = true
      window.removeEventListener('jarvis:routine-event', onRoutineEvent)
    }
  }, [])

  const setBootEnabled = async (enabled: boolean) => {
    const response = await fetch('/api/tray', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: enabled ? 'enable_boot' : 'disable_boot' }) })
    const data = await response.json()
    if (!response.ok) { setNotice(data.error || 'Não foi possível alterar a inicialização automática.'); return }
    setTray({ boot_enabled: data.boot_enabled })
  }

  const setProvider = async (llm_provider: 'gemini' | 'groq' | 'oxyy') => {
    const response = await fetch('/api/settings/llm', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ llm_provider }) })
    const data = await response.json()
    setLlmSettings(data)
    await refreshAiRoutes()
  }

  const openVideo = (url: string) => {
    const trimmed = url.trim()
    if (!(/^https?:\/\//i.test(trimmed) && (/\.(?:m3u8|mp4|webm|ogv|mov|m4v)(?:$|[?#])/i.test(trimmed) || /\/api\/cinema\/session\/media\//.test(trimmed)))) {
      setNotice('O player do Jarvis aceita somente mídia MP4/HLS confirmada. Use a sessão isolada para páginas externas.')
      return false
    }
    setPlayingUrl(trimmed)
    return true
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

  const cameraFromVoice = useRef(false)
  const cameraBusy = useRef(false)
  const cameraContext = useRef({ session: sessionId, previous: '' })
  if (cameraContext.current.session !== sessionId) cameraContext.current = { session: sessionId, previous: '' }
  const cameraRequest = (message: string) => {
    const previous = cameraContext.current.previous || [...messages].reverse().find(m => m.role === 'user')?.content || ''
    const requested = isCameraObservationRequest(message, previous) || isCameraPanelRequest(message)
    cameraContext.current.previous = requested ? (isCameraObservationRequest(message) ? message : 'Quem aparece nas câmeras?') : message
    return requested
  }
  const observeCameras = async (message: string): Promise<string> => {
    if (isCameraPanelRequest(message)) { setCameraQuestion(''); setCameraWorkspaceOpen(true); return '' }
    if (cameraBusy.current) return 'Já estou analisando as câmeras. Aguarde um instante.'
    cameraBusy.current = true
    setNotice('Observando as câmeras conectadas…')
    try {
      const frames = await captureRequestedCameras(message)
      const reply = await sendVisionQuestion(message, frames[0].image, frames[0].cameraName, frames)
      setNotice('')
      return reply || ''
    } catch (failure) {
      const error = failure instanceof Error && failure.message.startsWith('A câmera solicitada') ? failure.message : 'Não consegui acessar as câmeras. Confira a conexão e a permissão de câmera.'
      setNotice(error)
      return error
    } finally { cameraBusy.current = false }
  }
  const observeCamerasRef = useRef(observeCameras)
  observeCamerasRef.current = observeCameras
  const cameraRequestRef = useRef(cameraRequest)
  cameraRequestRef.current = cameraRequest
  useEffect(() => {
    const requested = (event: Event) => {
      const { message, resolve } = (event as CustomEvent<{ message: string; resolve: (text: string) => void }>).detail
      if (!cameraRequestRef.current(message)) return
      event.preventDefault()
      void observeCamerasRef.current(message).then(resolve)
    }
    window.addEventListener('jarvis-request-camera', requested)
    return () => window.removeEventListener('jarvis-request-camera', requested)
  }, [])

  const sendChatText = async (message: string, mode: ChatMode = chatMode): Promise<string> => {
    if (handleLiveIntroduction(message)) return ''
    if (cameraRequest(message)) return observeCameras(message)
    return sendText(message, mode)
  }

  const sendChatMessage = async () => {
    // "//texto" é mensagem comum que começa com "/": envia sem a primeira barra (A6).
    const message = unescapeSlash(query.trim())
    const attachment = chatAttachment
    if (attachment) {
      setQuery('')
      setChatAttachment(null)
      await sendVisionQuestion(message || `Descreva a imagem enviada: ${attachment.name}`, attachment.dataUrl, attachment.name)
      return
    }
    if (!message) return
    setQuery('')
    await sendChatText(message)
  }

  const renderSection = () => {
    const page = (() => {
      if (active === 'Dashboard') return <WorkspaceHome operational={operational} onNavigate={setActive} />
      if (active === 'Integrações') return <IntegrationsPage operational={operational} onNavigate={setActive} />
      if (active === 'Saúde') return <HealthPage operational={operational} audio={liveAudioDiagnostics} />
      if (active === 'Painel pessoal') {
        return (
          <DashboardPage
            dashboard={dashboard}
            finance={finance}
            ttsSettings={ttsSettings}
            proactive={proactive}
            tray={tray}
            onOpenEvolute={openEvoluteWindow}
          />
        )
      }
      if (active === 'Central') return <MissionControlPage initialRunId={linkedRun} operational={operational} sessionId={sessionId} onOpenSession={id => { void selectSession(id); setActive('Chat') }} />
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
            onRemoveDevice={removeBridgeDevice}
          />
        )
      }
      if (active === 'Chat') {
        return (
          <ChatPage
            onEditMessage={IS_MOBILE ? undefined : pcChat.editMessage}
            liveActivity={IS_MOBILE ? undefined : pcChat.liveActivity}
            canStopRequest={conversationRun.canStop}
            hasActiveRequest={conversationRun.hasActive}
            liveMode={IS_MOBILE ? undefined : pcChat.liveMode}
            runStatus={conversationRun.message}
            commandHandlers={commandHandlers}
            wakeWord={wakeWord}
            wakeHeard={wakeHeard}
            onOpenRun={IS_MOBILE ? undefined : id => { setLinkedRun(id); setActive('Central') }}
            sessions={sessions}
            sessionId={sessionId}
            messages={messages}
            answer={answer}
            loading={loading}
            streamingReply={streamingReply}
            liveSearch={liveSearch}
            liveReasoning={liveReasoning}
            agentProgress={IS_MOBILE ? null : pcChat.agentProgress}
            chatError={chatError}
            query={query}
            chatMode={chatMode}
            chatAttachment={chatAttachment}
            recording={recording}
            pendingScript={pendingScript}
            onDeleteSession={id => void Promise.resolve(deleteSession(id, true)).catch(() => setNotice('Não foi possível excluir a conversa.'))}
            onExportSession={() => handleExportSession().catch(() => undefined)}
            onCopySession={() => handleCopySession().catch(() => undefined)}
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
            onSendText={sendChatText}
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
            undoReview={undoReview}
            studyUndoCount={studyUndoCount}
            nextCardDueAt={nextCardDueAt}
            refreshStudy={refreshStudy}
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
            sendTutorMessage={sendTutorMessage}
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
      if (active === 'Inglês') return <LanguagePage {...language} setNotice={setNotice} />
      if (active === 'Calendário') return <CalendarSection onNotice={setNotice} />
      if (active === 'Configurações') {
        return (
          <SettingsPage
            ttsSettings={ttsSettings}
            sttSettings={sttSettings}
            oxyySettings={oxyySettings}
            oxyyCatalog={oxyyCatalog}
            llmSettings={llmSettings}
            aiSettings={aiSettings}
            wakeWord={wakeWord}
            tray={tray}
            proactive={proactive}
            briefingTime={briefingTime}
            briefingTopics={briefingTopics}
            briefingInstructions={briefingInstructions}
            notice={notice}
            apiKeys={apiKeys}
            onSaveApiKeys={saveApiKeys}
            onSetTtsProvider={setTtsProvider}
            onSetProvider={setProvider}
            onRoutesSaved={() => void refreshAiRoutes()}
            onSetSttProvider={setSttProvider}
            onSaveOxyy={saveOxyy}
            onRefreshOxyy={refreshOxyy}
            onSetWakeWordEnabled={setWakeWordEnabled}
            onSetBootEnabled={setBootEnabled}
            speakEnabled={speakEnabled}
            onSetSpeakEnabled={setSpeakEnabled}
            onSaveBriefing={saveBriefing}
            onBriefingTimeChange={setBriefingTime}
            onToggleBriefingTopic={toggleBriefingTopic}
            onBriefingInstructionsChange={setBriefingInstructions}
            onNavigate={setActive}
          />
        )
      }
      if (active === 'Memórias') {
        return (
          <MemoriesPage
            memories={memories}
            memoryCollection={memoryCollection}
            notice={notice}
            identityProfiles={identityProfiles}
            selectedProfileId={selectedProfileId}
            profileMemories={profileMemories}
            onRefresh={() => refreshMemories()}
            onClearTechnical={clearTechnicalMemories}
            onSelectCollection={collection => {
              setMemoryCollection(collection)
              if (collection === 'profile_memory') refreshProfileMemories()
              else if (collection !== 'cited') refreshMemories(collection)
            }}
            onSelectProfile={profileId => { setSelectedProfileId(profileId); refreshProfileMemories(profileId).catch(() => undefined) }}
            onRefreshProfile={() => refreshProfileMemories()}
            onAddProfileMemory={addProfileMemory}
            onDeleteProfileMemory={deleteProfileMemory}
            onClearProfileMemory={clearProfileMemories}
          />
        )
      }
      if (!pairedAndroid && active === 'Identidade') return <IdentityPage />
      if (active === 'Evolução') return <EvoluteHubPage />
      return (
        <section className="migration-card">
          <p className="eyebrow">MIGRAÇÃO GRADUAL</p>
          <h2>{active}</h2>
          <p>Esta área continua disponível no painel legado em /legacy.</p>
        </section>
      )
    })()

    return (
      <Suspense fallback={<SkeletonLoader variant={active === 'Dashboard' ? 'dashboard' : 'card'} />}>
        {page}
      </Suspense>
    )
  }

  const quickActions = (
    <>
      <button type="button" className="sidebar-action-btn" onClick={openEvoluteWindow} title="Abrir Painel de Evolução (Life OS)"><span>⚡</span> <span>Life OS</span></button>
      <button type="button" className="sidebar-action-btn" onClick={() => setCinemaLauncherOpen(true)} title="Abrir cinema"><span>◉</span> <span>Cinema</span></button>
      <button type="button" className="sidebar-action-btn" onClick={captureVision} title="Analisar tela"><span>👁</span> <span>Visão</span></button>
      <button type="button" className={`sidebar-action-btn${recording ? ' sidebar-action-active' : ''}`} onClick={toggleVoiceInput} title={recording ? 'Parar gravação' : 'Falar com Jarvis'}><span>{recording ? '⏹' : '🎙'}</span> <span>{recording ? 'Parar' : 'Voz'}</span></button>
      <button type="button" className="sidebar-action-btn" onClick={() => { setCameraQuestion(''); setCameraWorkspaceOpen(true) }} title="Câmeras"><span>📷</span> <span>Câmeras</span></button>
      <button type="button" className="sidebar-action-btn" onClick={() => setLiveCallOpen(true)} title="Ligação"><span>📞</span> <span>Ligação</span></button>
    </>
  )

  const hero = active === 'Painel pessoal' ? (
    <DashboardHero
      weather={weather}
      onOpenCinema={() => setCinemaLauncherOpen(true)}
      onCaptureVision={captureVision}
      onToggleVoice={toggleVoiceInput}
      onOpenLiveCall={() => setLiveCallOpen(true)}
      recording={recording}
    />
  ) : null

  return (
    <>
      <AppShell
        active={active}
        sessions={sessions}
        sessionId={sessionId}
        changeChatTrash={IS_MOBILE ? undefined : pcChat.changeChatTrash}
        chatBusy={loading}
        onSelectSession={selectSession}
        onNewChat={() => {
          setActive('Chat')
          setChatAttachment(null)
          void Promise.resolve(createSession()).catch(() => setNotice('Não foi possível criar a conversa.'))
        }}
        onOpenCommands={() => setIsCommandPaletteOpen(true)}
        operational={operational}
        controls={<AgentControls operational={operational} llm={llmSettings} speakEnabled={speakEnabled} onToggleSpeech={() => setSpeakEnabled(!speakEnabled)} onNavigate={setActive} />}
        sidebarCollapsed={sidebarCollapsed}
        onToggleSidebar={() => setSidebarCollapsed(!sidebarCollapsed)}
        onNavigate={(screen) => {
          playToggle()
          setActive(screen)
          try {
            localStorage.setItem(ACTIVE_SCREEN_KEY, screen)
          } catch {
            /* ignore storage error */
          }
        }}
        hero={hero}
        quickActions={quickActions}
        openRun={IS_MOBILE ? undefined : id => { setLinkedRun(id); setActive('Central') }}
      >
        <ErrorBoundary fallbackTitle="Erro ao carregar esta seção.">
          {renderSection()}
        </ErrorBoundary>
      </AppShell>
      <CameraWorkspace ref={cameraWorkspaceRef} open={cameraWorkspaceOpen} initialQuestion={cameraQuestion} onClose={() => { setCameraQuestion(''); setCameraWorkspaceOpen(false) }} onQuestion={async (frames, prompt) => { setCameraQuestion(''); setCameraWorkspaceOpen(false); setActive('Chat'); const reply = await sendVisionQuestion(prompt || `O que você vê na ${frames[0].cameraName}?`, frames[0].image, frames[0].cameraName, frames); if (cameraFromVoice.current && reply) await speakText(reply); cameraFromVoice.current = false }} />
      {cinemaLauncherOpen && (
        <Suspense fallback={null}>
          <CinemaModal
            open={cinemaLauncherOpen}
            onClose={() => setCinemaLauncherOpen(false)}
            onPlay={openVideo}
            cinemaSearch={cinemaSearch}
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
        </Suspense>
      )}
      {visionResult && <div className="tool-modal" role="dialog" aria-modal="true" aria-label="Análise visual"><section className="vision-modal"><button className="modal-close" onClick={() => setVisionResult(null)} aria-label="Fechar">×</button><p className="eyebrow">FERRAMENTA · VISÃO</p><h2>Análise de tela</h2>{visionResult.imageUrl && <img src={visionResult.imageUrl} alt="Captura de tela analisada" />}<p>{visionResult.reply}</p></section></div>}
      {!pairedAndroid && <LiveEnrollment />}
      {liveCallOpen && (
        <Suspense fallback={null}>
          <LiveCallModal open={liveCallOpen} onClose={closeLiveCall} recording={liveCallRecording} status={liveCallStatus} audioDiagnostics={liveAudioDiagnostics} userTranscript={liveUserTranscript} jarvisTranscript={liveJarvisTranscript} turns={liveTurns} orbState={liveOrbState} onToggleCapture={toggleLiveCallCapture} onBargeIn={triggerBargeIn} pushToTalkMode={pushToTalkMode} onTogglePushToTalk={togglePushToTalk} onPttStart={startPtt} onPttEnd={stopPtt} isPttActive={isPttActive} />
        </Suspense>
      )}
      {pendingScript && <div className="tool-modal" role="dialog" aria-modal="true" aria-label="Confirmar script"><section className="vision-modal"><button className="modal-close" onClick={() => setPendingScript(null)} aria-label="Cancelar">×</button><p className="eyebrow">CONFIRMAÇÃO NECESSÁRIA</p><h2>Executar script?</h2><p>{pendingScript.description}</p><pre>{pendingScript.code}</pre><div className="library-actions"><button type="button" onClick={() => setPendingScript(null)}>Cancelar</button><button type="button" onClick={() => runPendingScript()}>Executar {pendingScript.language}</button></div></section></div>}
      {playingUrl && (
        <div className="player-modal">
          <Suspense fallback={null}>
            <IsolatedVideoPlayer
              src={playingUrl}
              directMedia={cinemaMedia.find(item => item.url === playingUrl)?.direct}
              sourceKind={cinemaMedia.find(item => item.url === playingUrl)?.kind}
              onClose={() => setPlayingUrl('')}
              title={selectedLibraryItem?.title || cinemaSearch.selection?.title || cinemaQuery || 'Jarvis Cinema'}
              mediaType={selectedLibraryItem?.type || (cinemaSearch.detectedEpisodes.length ? 'tv' : 'movie')}
              currentSeason={selectedLibraryItem ? selectedSeason : cinemaSearch.detectedEpisode?.season}
              currentEpisode={selectedLibraryItem ? selectedEpisode : cinemaSearch.detectedEpisode?.episode}
              episodes={selectedLibraryItem?.episodes || cinemaSearch.detectedEpisodes}
              onSelectEpisode={async (season, episode) => {
                if (selectedLibraryItem) {
                  const entry = selectedLibraryItem.episodes?.find(item => (item.season || 1) === season && (item.episode || 1) === episode)
                  const url = entry?.sources?.[0]?.url
                  if (!url) return false
                  selectEpisode(episode, season)
                  return openVideo(url)
                }
                const entry = cinemaSearch.detectedEpisodes.find(item => item.season === season && item.episode === episode)
                if (!entry) return false
                const url = await cinemaSearch.playDetectedEpisode(entry.url)
                return Boolean(url && openVideo(url))
              }}
              onNextEpisode={() => {
                if (!selectedLibraryItem && cinemaSearch.detectedEpisode) {
                  const index = cinemaSearch.detectedEpisodes.findIndex(item => item.url === cinemaSearch.detectedEpisode?.url)
                  const entry = cinemaSearch.detectedEpisodes[index + 1]
                  if (entry) void cinemaSearch.playDetectedEpisode(entry.url).then(url => { if (url) openVideo(url) })
                  return
                }
                const next = selectNextEpisode()
                if (next) openVideo(next)
              }}
            />
          </Suspense>
        </div>
      )}
      {isToolForgeOpen && (
        <Suspense fallback={null}>
          <ToolForgeModal
            isOpen={isToolForgeOpen}
            onClose={() => setIsToolForgeOpen(false)}
          />
        </Suspense>
      )}
      {isCommandPaletteOpen && (
        <Suspense fallback={null}>
          <CommandPalette
            isOpen={isCommandPaletteOpen}
            onClose={() => setIsCommandPaletteOpen(false)}
            handlers={commandHandlers}
            recording={recording}
          />
        </Suspense>
      )}
      <NoteViewer />
      {!IS_MOBILE && <PopupHost />}
      <CloudSessionStatus />
      <Toast message={notice} onDismiss={dismissNotice} />
    </>
  )
}
