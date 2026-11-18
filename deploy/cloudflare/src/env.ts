export interface Env {
  ASSETS: Fetcher;
  JARVIS_DB: D1Database;
  MOBILE_CONTROL_TOKEN: string;
  FISH_API_KEY?: string;
  FISH_REFERENCE_ID?: string;
  FISH_TTS_MODEL?: string;
  GROQ_API_KEY?: string;
  GROQ_MODEL?: string;
  GEMINI_API_KEY?: string;
  GEMINI_MODEL?: string;
}
