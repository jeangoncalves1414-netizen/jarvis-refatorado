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
export type SttSettings = { stt_provider?: 'groq' | 'oxyy' | 'google'; groq_configured?: boolean; oxyy_configured?: boolean; oxyy_model?: string }
export type OxyyModel = { id: string; name?: string; provider?: string; type?: string; context_length?: number | null }
export type OxyyCatalog = { models?: Record<string, OxyyModel[]>; all?: OxyyModel[]; remote?: boolean; error?: string }
export type OxyySettings = { models: { chat?: string; tts?: string; tts_voice?: string; stt?: string; image?: string; video?: string; embedding?: string }; oxyy_configured?: boolean; key_count?: number; base_url?: string }
export type ChatMessage = { role: 'user' | 'assistant'; content: string; run_id?: string }
export type ScriptRequest = { language: 'python' | 'powershell'; code: string; description: string }
export type StudyCategory = { id: string; name: string; color: string; created_at?: number }
export type ChatSession = { id: string; title?: string; type?: string; updated_at?: number; category_id?: string; category_color?: string; deleted_at?: number }
export type Memory = { id?: string; text?: string; metadata?: Record<string, string> }
export type IdentityProfile = { id: string; name: string; role?: string; voice_samples?: number; face_samples?: number; created_at?: number }
export type ProfileMemory = { id: string; profile_id: string; text: string; kind?: 'note' | 'fact' | 'preference' | 'conversation'; importance?: number; source?: string; created_at?: number; updated_at?: number }
export type Finance = { ok?: boolean; currencies?: Record<string, { bid?: number; pctChange?: number }> }
export type Proactive = { config?: { briefing_enabled?: boolean; briefing_time?: string; topics?: string[]; custom_instructions?: string }; reminders?: { id?: string; message?: string; target_time?: string }[] }
export type WakeWord = { enabled?: boolean; available?: boolean }
export type Tray = { boot_enabled?: boolean }
export type Metrics = { cpu?: number; ram_used?: number; ram_total?: number; ram_percent?: number; provider?: string; total_requests?: number; total_errors?: number; uptime_seconds?: number; tools_executed?: Record<string, number> }
export type LogEntry = { level?: string; component?: string; message?: string; timestamp?: string }
export type Flashcard = { id: string; front?: string; back?: string }
export type FeynmanAttempt = { id?: string; topic?: string; explanation?: string; grade?: number; date?: string }
export type Assessment = { id?: string; stage_id?: string; correct?: number; total?: number; score?: number; date?: string }
export type EnemQuestion = { id?: string; text?: string; subject?: string; year?: string | number; created?: string; image_base64?: string; preview?: string }
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
export type CinemaResult = { title?: string; url: string; source?: string; snippet?: string; media_hint?: string }
export type CinemaMedia = { url: string; label?: string; kind?: string; source_url?: string; direct?: boolean; embed_url?: string }
export type CinemaSource = { label?: string; url: string; kind?: string; quality?: string; episode?: number; season?: number }
export type CinemaEpisode = { season?: number; episode?: number; title?: string; sources?: CinemaSource[] }
export type CinemaItem = { id?: string; title?: string; type?: 'movie' | 'tv'; sources?: CinemaSource[]; episodes?: CinemaEpisode[] }

