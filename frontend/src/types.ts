export type Weather = { temp_c?: number; description?: string; city?: string; ok?: boolean }
export type Task = { id: string; title: string; completed?: boolean; priority?: string }
export type Dashboard = { system?: { cpu?: number; ram?: number; ram_used?: number; ram_total?: number; ram_percent?: number }; tasks?: { pending?: number; completed?: number; items?: Task[] }; sessions?: { total?: number }; tutor?: { due_flashcards?: number; stage?: string; weak_spots?: string[] }; activity?: { type?: string; message?: string; timestamp?: string }[]; timers?: { label?: string; fire_at?: string }[]; enem?: { questions?: number } }
export type Climate = { target_c?: number; current_c?: number; ok?: boolean }
export type BridgeDevice = { id: string; name?: string; kind?: string; platform?: string; transport?: string; connected?: boolean; power?: boolean; brightness?: number; color?: unknown; last_seen?: number }
export type BridgeStatus = { ok?: boolean; protocol?: string; pairing_code?: string; devices?: BridgeDevice[]; events?: { id?: string; type?: string; device_id?: string; at?: number }[]; error?: string }
export type RouteRef = { provider?: string; model?: string; configured?: boolean }
export type CapabilityRoute = { capability?: string; primary?: RouteRef; primary_configured?: boolean; effective?: RouteRef | null; fallback?: RouteRef[]; fallback_used?: boolean; reason?: string; configured?: boolean }
export type AiSettings = { ok?: boolean; routes?: Record<string, CapabilityRoute>; effective?: Record<string, RouteRef | null> }
export type LlmSettings = { llm_provider?: 'gemini' | 'groq' | 'oxyy'; gemini_configured?: boolean; groq_configured?: boolean; oxyy_configured?: boolean; effective_provider?: string; effective_model?: string; fallback_used?: boolean; fallback_reason?: string; route?: CapabilityRoute }
export type TtsSettings = { tts_provider?: 'fish' | 'gemini' | 'edge' | 'oxyy'; tts_voice?: string; tts_gemini_voice?: string; fish_reference_id?: string; fish_model?: string; fish_configured?: boolean; gemini_configured?: boolean; oxyy_configured?: boolean; oxyy_model?: string; oxyy_voice?: string }
export type SttSettings = { stt_provider?: 'local' | 'groq' | 'oxyy' | 'google'; local_available?: boolean; local_reason?: string; local_model?: string; local_models?: string[]; local_device?: string; local_model_downloaded?: boolean; local_download_hint?: string; groq_configured?: boolean; oxyy_configured?: boolean; oxyy_model?: string }
export type OxyyModel = { id: string; name?: string; provider?: string; type?: string; context_length?: number | null }
export type OxyyCatalog = { models?: Record<string, OxyyModel[]>; all?: OxyyModel[]; remote?: boolean; error?: string }
export type OxyySettings = { models: { chat?: string; tts?: string; tts_voice?: string; stt?: string; image?: string; video?: string; embedding?: string }; oxyy_configured?: boolean; key_count?: number; base_url?: string }
/** Memória citada no turno (fase contexto 2). */
export type MemoryCitation = { id: string; text: string; date: string; label: string; origin: string; session_id?: string; applied_to?: { tool: string; param: string; value: string }; how: 'preenchido' | 'citado' }
/** Metadados do turno, só ao vivo (não vão para o histórico salvo). */
export type ToolActivityEntry = { id: string; tool: string; status: string; label?: string; speech?: string; result?: string; detail?: string; sources?: { url: string; title: string; read?: boolean }[] }
export type ContextUsage = { provider: string; model: string; estimated_tokens: number; before_tokens: number; budget: number | null; reduced: boolean }
export type TurnMeta = { access_mode?: 'public'; context_usage?: ContextUsage[]; tool_activity?: ToolActivityEntry[]; memory_lookup?: { tool: string; summary: string; items: { title: string; text: string }[] }; situational_context?: { text: string; sources: { key: string; label: string }[]; chars: number }; memory_used?: MemoryCitation[] }
export type ChatMessage = { timestamp?: number; activity?: ToolActivityEntry[]; role: 'user' | 'assistant'; content: string; run_id?: string; meta?: TurnMeta }
export type ScriptRequest = { language: 'python' | 'powershell'; code: string; description: string }
export type StudyCategory = { id: string; name: string; color: string; created_at?: number }
export type ChatSession = { id: string; title?: string; type?: string; updated_at?: number; category_id?: string; category_color?: string; deleted_at?: number }
export type Memory = { id?: string; text?: string; metadata?: Record<string, string> }
export type IdentityProfile = { id: string; name: string; role?: string; voice_samples?: number; face_samples?: number; created_at?: number }
export type ProfileMemory = { id: string; profile_id: string; text: string; kind?: 'note' | 'fact' | 'preference' | 'conversation'; importance?: number; source?: string; created_at?: number; updated_at?: number }
export type Finance = { ok?: boolean; currencies?: Record<string, { bid?: number; pctChange?: number }> }
export type Proactive = { config?: { briefing_enabled?: boolean; briefing_time?: string; topics?: string[]; custom_instructions?: string }; reminders?: { id?: string; message?: string; target_time?: string }[] }
export type WakeWord = { enabled?: boolean; available?: boolean; running?: boolean; active?: boolean; phrase?: string }
export type Tray = { boot_enabled?: boolean }
export type Metrics = { cpu?: number; ram_used?: number; ram_total?: number; ram_percent?: number; provider?: string; total_requests?: number; total_errors?: number; uptime_seconds?: number; tools_executed?: Record<string, number> }
export type LogEntry = { level?: string; component?: string; message?: string; timestamp?: string }
export type ReviewState = 'new' | 'learning' | 'review' | 'relearning'
export type Flashcard = { id: string; front?: string; back?: string; due?: string; reps?: number; state?: ReviewState; step?: number | null; last_review?: string | null; retrievability?: number | null }
export type FeynmanAttempt = { id?: string; topic?: string; explanation?: string; grade?: number; date?: string }
export type Assessment = { id?: string; stage_id?: string; correct?: number; total?: number; score?: number; date?: string }
export type EnemQuestion = { id?: string; text?: string; subject?: string; year?: string | number; created?: string; image_base64?: string; preview?: string }
/** Language learning types */
export type VocabCard = { id: string; word: string; translation: string; example?: string; phonetic?: string; category?: string; cefr?: string; due?: string; reps?: number; difficulty?: number | null; stability?: number | null; state?: ReviewState; step?: number | null; last_review?: string | null; retrievability?: number | null }
export type PronunciationAttempt = { id: string; target: string; transcript: string; score: number; confidence?: number; wrong_words?: string[]; date?: string }
export type LanguageDashboard = { cefr_level: string; target_language: string; placement_done: boolean; pronunciation_threshold?: number; stats: Record<string, number>; due_vocabulary: number; weak_phonemes: string[]; streak: number; daily_xp: number; daily_goal: number; total_xp: number }
export type StreakInfo = { streak_count: number; last_study_date?: string; total_xp: number; daily_xp: number; daily_goal: number }
/** Painel de estudos unificado (app/storage/study_stats.py) */
export type StudyXpSummary = { total_xp: number; daily_xp: number; daily_goal: number; goal_met: boolean; studied_today: boolean; streak: number; best_streak: number; pomodoros: number; last_study_date?: string | null }
export type StudyLevel = { level: number; name: string; xp_into_level: number; xp_for_next: number; next_threshold: number }
export type StudyBadge = { id: string; label: string; description: string; earned: boolean }
export type StudyDashboardData = { today: string; due: { flashcards: number; vocabulary: number; next_due_at?: string | null }; xp: StudyXpSummary; level: StudyLevel; badges: StudyBadge[] }
export type StudyStateCounts = { new: number; learning: number; review: number; relearning: number }
export type StudyStatsData = {
  heatmap: { date: string; reviews: number; xp: number }[]
  daily_reviews: { date: string; tutor: number; language: number }[]
  retention: { rate: number | null; correct: number; total: number; window_days: number }
  states: Record<'tutor' | 'language' | 'total', StudyStateCounts>
  totals: { reviews: number; pomodoros: number; vocabulary: number; flashcards: number }
}
export type WhiteboardElement = {
  id?: string
  type?: 'text' | 'image'
  content?: string
  x?: number
  y?: number
  width?: number
  height?: number
  color?: string
  size?: number
  backgroundColor?: string
  fontWeight?: 'normal' | 'bold'
  fontStyle?: 'normal' | 'italic'
  textAlign?: 'left' | 'center' | 'right'
  listStyle?: 'plain' | 'bullets' | 'ordered' | 'tasks'
  checked?: boolean[]
  fontFamily?: string
  textDecoration?: 'none' | 'underline' | 'line-through'
  variant?: 'paragraph' | 'heading' | 'quote' | 'code' | 'callout'
  objectFit?: 'contain' | 'cover' | 'fill'
  caption?: string
  opacity?: number
  rotation?: number
  zIndex?: number
  locked?: boolean
}
export type CinemaResult = { title?: string; url: string; source?: string; snippet?: string; media_hint?: string; source_priority?: number }
export type CinemaCatalogItem = { id: string; title: string; original_title?: string; title_language?: string; type: 'movie' | 'tv'; year?: string | number; poster?: string; description?: string; genres?: string[] }
export type CinemaSearchMode = 'movie' | 'series' | 'anime' | 'sites'
export type CinemaSearchSource = { id: string; name: string; enabled?: boolean }
export type CinemaMedia = { url: string; playback_url?: string; label?: string; kind?: string; source_url?: string; session_id?: string; evidence?: 'network' | 'dom'; direct?: boolean; embed_url?: string; quality?: string; audio?: string; suspected_ad?: boolean; compatible?: boolean; verification?: 'confirmed' | 'timeout' | 'cancelled' | 'failed' | 'embedded'; qualities?: string[]; audio_tracks?: string[] }
export type CinemaDetectedEpisode = { url: string; title: string; season: number; episode: number }
export type CinemaSource = { label?: string; url: string; kind?: string; quality?: string; episode?: number; season?: number }
export type CinemaEpisode = { season?: number; episode?: number; title?: string; sources?: CinemaSource[] }
export type CinemaItem = { id?: string; title?: string; type?: 'movie' | 'tv'; sources?: CinemaSource[]; episodes?: CinemaEpisode[] }

