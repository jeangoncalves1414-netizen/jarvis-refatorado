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

const COOKIE = "__Host-jarvis_cloud";
const JSON_HEADERS = { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" };
const MAX_TEXT = 12_000;
const MAX_AUDIO = 25 * 1024 * 1024;

type ChatMessage = { role: "user" | "assistant"; content: string };
type Habit = { id: string; name: string; days_of_week: string[]; completed_today: boolean; created_at: string; updated_at: string };

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), { status, headers: JSON_HEADERS });
}

function error(message: string, status = 400): Response {
  return json({ ok: false, error: message }, status);
}

function cookieValue(request: Request, name: string): string | null {
  const prefix = `${name}=`;
  for (const item of (request.headers.get("Cookie") || "").split(";")) {
    const part = item.trim();
    if (part.startsWith(prefix)) return part.slice(prefix.length);
  }
  return null;
}

function authenticated(request: Request, env: Env): boolean {
  const received = cookieValue(request, COOKIE);
  if (!received || !env.MOBILE_CONTROL_TOKEN || received.length !== env.MOBILE_CONTROL_TOKEN.length) return false;
  let mismatch = 0;
  for (let i = 0; i < received.length; i++) mismatch |= received.charCodeAt(i) ^ env.MOBILE_CONTROL_TOKEN.charCodeAt(i);
  return mismatch === 0;
}

function id(): string {
  return crypto.randomUUID();
}

function now(): string {
  return new Date().toISOString();
}

function cleanText(value: unknown, max = MAX_TEXT): string {
  return typeof value === "string" ? value.trim().slice(0, max) : "";
}

function normalizeHabit(value: string): string {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/\s+/g, " ").trim();
}

function requestedHabit(message: string): string | null {
  const match = message.match(/^\s*(?:crie|criar|adicione|adicionar|registre|registrar|quero criar)\s+(?:um\s+|o\s+)?h[áa]bito(?:\s+(?:de|para))?\s+(.+?)[.?!]*\s*$/i);
  if (!match) return null;
  const name = cleanText(match[1], 120).replace(/\s+(?:todos os dias|todo dia|diariamente)$/i, "").trim();
  return name.length >= 2 ? name : null;
}

async function createHabit(db: D1Database, name: string): Promise<{ habit: Habit; created: boolean }> {
  const normalized = normalizeHabit(name);
  const existing = await db.prepare("SELECT id, name, days_of_week, created_at, updated_at FROM habits WHERE normalized_name = ?")
    .bind(normalized).first<{ id: string; name: string; days_of_week: string; created_at: string; updated_at: string }>();
  if (existing) return { habit: { ...existing, days_of_week: JSON.parse(existing.days_of_week), completed_today: false }, created: false };
  const timestamp = now();
  const habit: Habit = { id: id(), name, days_of_week: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"], completed_today: false, created_at: timestamp, updated_at: timestamp };
  await db.prepare("INSERT INTO habits (id, name, normalized_name, days_of_week, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)")
    .bind(habit.id, habit.name, normalized, JSON.stringify(habit.days_of_week), timestamp, timestamp).run();
  return { habit, created: true };
}

async function listHabits(env: Env): Promise<Response> {
  const rows = await env.JARVIS_DB.prepare("SELECT id, name, days_of_week, created_at, updated_at FROM habits ORDER BY created_at DESC")
    .all<{ id: string; name: string; days_of_week: string; created_at: string; updated_at: string }>();
  const habits = (rows.results || []).map((habit) => ({ ...habit, days_of_week: JSON.parse(habit.days_of_week), completed_today: false }));
  return json({ ok: true, habits });
}

async function createHabitFromApi(request: Request, env: Env): Promise<Response> {
  const body = await readJson(request);
  const name = cleanText(body?.name, 120);
  if (name.length < 2) return error("Informe o nome do hábito.");
  const result = await createHabit(env.JARVIS_DB, name);
  return json({ ok: true, ...result }, result.created ? 201 : 200);
}

async function readJson(request: Request): Promise<Record<string, unknown> | null> {
  try {
    const body: unknown = await request.json();
    return body && typeof body === "object" && !Array.isArray(body) ? body as Record<string, unknown> : null;
  } catch {
    return null;
  }
}

async function sessionHistory(db: D1Database, sessionId: string): Promise<ChatMessage[]> {
  const rows = await db.prepare(
    "SELECT role, content FROM messages WHERE session_id = ? ORDER BY created_at DESC LIMIT 20",
  ).bind(sessionId).all<{ role: "user" | "assistant"; content: string }>();
  return (rows.results || []).reverse().map(({ role, content }) => ({ role, content }));
}

async function saveMessage(db: D1Database, sessionId: string, role: ChatMessage["role"], content: string): Promise<void> {
  const timestamp = now();
  await db.batch([
    db.prepare("INSERT OR IGNORE INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)")
      .bind(sessionId, role === "user" ? content.slice(0, 72) || "Nova conversa" : "Nova conversa", timestamp, timestamp),
    db.prepare("INSERT INTO messages (id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)")
      .bind(id(), sessionId, role, content, timestamp),
    db.prepare("UPDATE sessions SET updated_at = ?, title = CASE WHEN title = 'Nova conversa' AND ? = 'user' THEN ? ELSE title END WHERE id = ?")
      .bind(timestamp, role, content.slice(0, 72) || "Nova conversa", sessionId),
  ]);
}

function systemPrompt(): string {
  return [
    "Você é Jarvis, assistente pessoal da usuária, falando em português brasileiro.",
    "Responda de forma natural, objetiva e útil.",
    "Você está no painel mobile, independente do PC. Não alegue controlar o computador, arquivos locais, câmera, microfone ou aplicativos do Windows.",
    "Não peça verificação facial nem de voz. Para alarmes, oriente a usuária a abrir a aba Rotina do aplicativo.",
    "Você pode criar hábitos no painel mobile quando a usuária pedir explicitamente, por exemplo: 'crie o hábito de ler'. Confirme a criação de forma breve.",
  ].join(" ");
}

async function askGroq(env: Env, messages: ChatMessage[]): Promise<string> {
  const key = env.GROQ_API_KEY?.trim();
  if (!key) throw new Error("GROQ_API_KEY não configurada.");
  const response = await fetch("https://api.groq.com/openai/v1/chat/completions", {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "content-type": "application/json" },
    body: JSON.stringify({
      model: env.GROQ_MODEL || "openai/gpt-oss-120b",
      temperature: 0.7,
      messages: [{ role: "system", content: systemPrompt() }, ...messages],
    }),
  });
  if (!response.ok) throw new Error(`Groq respondeu HTTP ${response.status}.`);
  const payload = await response.json<{ choices?: Array<{ message?: { content?: string } }> }>();
  const answer = cleanText(payload.choices?.[0]?.message?.content);
  if (!answer) throw new Error("Groq não retornou uma resposta.");
  return answer;
}

async function askGemini(env: Env, messages: ChatMessage[]): Promise<string> {
  const key = env.GEMINI_API_KEY?.trim();
  if (!key) throw new Error("GEMINI_API_KEY não configurada.");
  const model = env.GEMINI_MODEL || "gemini-2.5-flash";
  const contents = messages.map((message) => ({
    role: message.role === "assistant" ? "model" : "user",
    parts: [{ text: message.content }],
  }));
  const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent?key=${encodeURIComponent(key)}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ systemInstruction: { parts: [{ text: systemPrompt() }] }, contents }),
  });
  if (!response.ok) throw new Error(`Gemini respondeu HTTP ${response.status}.`);
  const payload = await response.json<{ candidates?: Array<{ content?: { parts?: Array<{ text?: string }> } }> }>();
  const answer = cleanText(payload.candidates?.[0]?.content?.parts?.map((part) => part.text || "").join(""));
  if (!answer) throw new Error("Gemini não retornou uma resposta.");
  return answer;
}

async function respond(env: Env, messages: ChatMessage[]): Promise<string> {
  if (env.GROQ_API_KEY?.trim()) {
    try {
      return await askGroq(env, messages);
    } catch (cause) {
      // A key/model quota can change independently of the mobile app. Keep
      // the phone usable by falling back to Gemini when it is configured.
      console.warn("Groq unavailable; trying Gemini", cause);
      if (!env.GEMINI_API_KEY?.trim()) throw cause;
    }
  }
  if (env.GEMINI_API_KEY?.trim()) return askGemini(env, messages);
  throw new Error("Configure GROQ_API_KEY ou GEMINI_API_KEY nos Secrets do Worker.");
}

async function handleChat(request: Request, env: Env): Promise<Response> {
  const body = await readJson(request);
  const message = cleanText(body?.message);
  if (!message) return error("Mensagem não pode ser vazia.");
  const sessionId = cleanText(body?.session_id, 100) || id();
  const history = await sessionHistory(env.JARVIS_DB, sessionId);
  await saveMessage(env.JARVIS_DB, sessionId, "user", message);
  try {
    const habitName = requestedHabit(message);
    if (habitName) {
      const result = await createHabit(env.JARVIS_DB, habitName);
      const reply = result.created ? `Pronto, criei o hábito “${result.habit.name}” para todos os dias.` : `O hábito “${result.habit.name}” já está na sua rotina.`;
      await saveMessage(env.JARVIS_DB, sessionId, "assistant", reply);
      return json({ ok: true, status: "complete", session_id: sessionId, reply, summary: reply, intent: "habit_create", actions: [{ type: "habit_created", habit: result.habit }], context: { mobile: true } });
    }
    const reply = await respond(env, [...history, { role: "user", content: message }]);
    await saveMessage(env.JARVIS_DB, sessionId, "assistant", reply);
    return json({ ok: true, status: "complete", session_id: sessionId, reply, summary: reply, intent: "chat", actions: [], context: { mobile: true } });
  } catch (cause) {
    console.error("chat failed", cause);
    return error("Não consegui responder agora. Confira a configuração da IA no Worker.", 503);
  }
}

async function handleTts(request: Request, env: Env): Promise<Response> {
  const body = await readJson(request);
  const text = cleanText(body?.text, 4_000);
  if (!text) return error("Texto não pode ser vazio.");
  const key = env.FISH_API_KEY?.trim();
  if (!key) return error("A voz FishAudio ainda não foi configurada.", 503);
  const response = await fetch("https://api.fish.audio/v1/tts", {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "content-type": "application/json", Accept: "audio/mpeg", model: env.FISH_TTS_MODEL || "s2.1-pro-free" },
    body: JSON.stringify({
      text,
      reference_id: env.FISH_REFERENCE_ID || "78d40157e19a43ebb725f09fc6125585",
      temperature: 0.7,
      top_p: 0.7,
      prosody: { speed: 1.4, volume: 0, normalize_loudness: true },
      latency: "balanced",
      chunk_length: 100,
      min_chunk_length: 30,
      condition_on_previous_chunks: true,
      format: "mp3",
    }),
  });
  if (!response.ok || !response.body) {
    console.error("fish failed", response.status);
    return error("A voz FishAudio não respondeu agora.", 503);
  }
  return new Response(response.body, { headers: { "content-type": response.headers.get("content-type") || "audio/mpeg", "cache-control": "no-store" } });
}

async function handleStt(request: Request, env: Env): Promise<Response> {
  const key = env.GROQ_API_KEY?.trim();
  if (!key) return error("A transcrição requer GROQ_API_KEY configurada.", 503);
  const audio = await request.arrayBuffer();
  if (!audio.byteLength || audio.byteLength > MAX_AUDIO) return error("Áudio inválido ou grande demais.");
  const type = request.headers.get("content-type") || "audio/webm";
  const extension = type.includes("ogg") ? "ogg" : type.includes("wav") ? "wav" : "webm";
  const form = new FormData();
  form.set("file", new Blob([audio], { type }), `voice.${extension}`);
  form.set("model", "whisper-large-v3-turbo");
  form.set("language", "pt");
  form.set("response_format", "json");
  const response = await fetch("https://api.groq.com/openai/v1/audio/transcriptions", { method: "POST", headers: { Authorization: `Bearer ${key}` }, body: form });
  if (!response.ok) return error("Não consegui transcrever este áudio.", 503);
  const payload = await response.json<{ text?: string }>();
  return json({ ok: true, text: cleanText(payload.text, MAX_TEXT) });
}

async function listSessions(env: Env): Promise<Response> {
  const rows = await env.JARVIS_DB.prepare("SELECT id, title, created_at, updated_at FROM sessions ORDER BY updated_at DESC LIMIT 50").all<{ id: string; title: string; created_at: string; updated_at: string }>();
  return json({ sessions: (rows.results || []).map((row) => ({ ...row, type: "chat" })) });
}

async function getSession(url: URL, env: Env): Promise<Response> {
  const sessionId = url.searchParams.get("id") || "";
  if (!sessionId) return error("Sessão ausente.");
  const messages = await sessionHistory(env.JARVIS_DB, sessionId);
  return json({ session_id: sessionId, messages });
}

async function getSessionHistory(sessionId: string, env: Env): Promise<Response> {
  const history = await sessionHistory(env.JARVIS_DB, sessionId);
  return json({ history: history.map((message) => ({ ...message, timestamp: Date.now() })) });
}

async function createSession(request: Request, env: Env): Promise<Response> {
  const body = await readJson(request);
  const sessionId = id();
  const title = cleanText(body?.title, 100) || "Nova conversa";
  const timestamp = now();
  await env.JARVIS_DB.prepare("INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)")
    .bind(sessionId, title, timestamp, timestamp).run();
  return json({ ok: true, id: sessionId, session: { id: sessionId, title, type: "chat", created_at: timestamp, updated_at: timestamp } }, 201);
}

async function replaceHistory(request: Request, sessionId: string, env: Env): Promise<Response> {
  const body = await readJson(request);
  const source = Array.isArray(body?.history) ? body.history : [];
  const history = source.slice(-80).flatMap((value): ChatMessage[] => {
    if (!value || typeof value !== "object") return [];
    const item = value as Record<string, unknown>;
    const role = item.role === "user" ? "user" : item.role === "assistant" ? "assistant" : null;
    const content = cleanText(item.content);
    return role && content ? [{ role, content }] : [];
  });
  if (!history.length) return json({ ok: true });
  const timestamp = now();
  const statements = [
    env.JARVIS_DB.prepare("DELETE FROM messages WHERE session_id = ?").bind(sessionId),
    ...history.map((item, index) => env.JARVIS_DB.prepare("INSERT INTO messages (id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)")
      .bind(id(), sessionId, item.role, item.content, new Date(Date.parse(timestamp) + index).toISOString())),
    env.JARVIS_DB.prepare("UPDATE sessions SET updated_at = ? WHERE id = ?").bind(timestamp, sessionId),
  ];
  await env.JARVIS_DB.batch(statements);
  return json({ ok: true });
}

async function deleteSession(sessionId: string, env: Env): Promise<Response> {
  await env.JARVIS_DB.batch([
    env.JARVIS_DB.prepare("DELETE FROM messages WHERE session_id = ?").bind(sessionId),
    env.JARVIS_DB.prepare("DELETE FROM sessions WHERE id = ?").bind(sessionId),
  ]);
  return json({ ok: true });
}

function cloudSettings(env: Env): Record<string, unknown> {
  return {
    llm_provider: env.GROQ_API_KEY?.trim() ? "groq" : "gemini",
    gemini_configured: Boolean(env.GEMINI_API_KEY?.trim()),
    groq_configured: Boolean(env.GROQ_API_KEY?.trim()),
    effective_provider: env.GEMINI_API_KEY?.trim() ? "gemini" : "groq",
    effective_model: env.GEMINI_API_KEY?.trim() ? (env.GEMINI_MODEL || "gemini-2.5-flash") : (env.GROQ_MODEL || "openai/gpt-oss-120b"),
  };
}

function mobileCompatibility(path: string, env: Env): Response | null {
  if (path === "/api/app-lock") return json({ configured: true, enabled: false, unlocked: true, face: false, voice: false });
  if (path === "/api/identity") return json({ ok: true, profiles: [], mobile: true, face: false, voice: false });
  if (path === "/api/settings/llm") return json(cloudSettings(env));
  if (path === "/api/settings/tts") return json({ tts_provider: "fish", fish_configured: Boolean(env.FISH_API_KEY?.trim()), fish_reference_id: env.FISH_REFERENCE_ID || "", fish_model: env.FISH_TTS_MODEL || "s2.1-pro-free" });
  if (path === "/api/settings/stt") return json({ stt_provider: "groq", groq_configured: Boolean(env.GROQ_API_KEY?.trim()), local_available: false, local_reason: "A transcrição é processada na nuvem." });
  if (path === "/api/settings/ai") return json({ ok: true, routes: { chat: { configured: Boolean(env.GEMINI_API_KEY?.trim() || env.GROQ_API_KEY?.trim()) }, tts: { configured: Boolean(env.FISH_API_KEY?.trim()) }, stt: { configured: Boolean(env.GROQ_API_KEY?.trim()) } } });
  if (path === "/api/settings/oxyy") return json({ models: {}, oxyy_configured: false, key_count: 0 });
  if (path === "/api/settings/oxyy/models") return json({ models: {}, all: [], remote: false });
  if (path === "/api/dashboard") return json({ system: { cpu: 0, ram: 0 }, tasks: { pending: 0, completed: 0, items: [] }, sessions: { total: 0 }, activity: [] });
  if (path === "/api/realtime") return json({ weather: { ok: false }, finance: { ok: false } });
  if (path === "/api/metrics") return json({ cpu: 0, ram_used: 0, ram_total: 0, ram_percent: 0, provider: "cloud" });
  if (path === "/api/logs") return json({ logs: [] });
  if (path === "/api/memories") return json({ memories: [] });
  if (path === "/api/proactive") return json({ config: { briefing_enabled: false, briefing_time: "08:00", topics: [] }, reminders: [] });
  if (path === "/api/wake-word") return json({ enabled: false, available: false, running: false, active: false, phrase: "Jarvis" });
  if (path === "/api/tray") return json({ boot_enabled: false });
  if (path === "/api/bridge") return json({ ok: true, protocol: "cloud", devices: [], events: [] });
  if (path === "/api/climate") return json({ ok: false });
  if (path === "/api/personal") return json({ preferences: {} });
  return null;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === "/api/health") return json({ ok: true, service: "jarvis-mobile-cloud", version: "1" });
    if (!authenticated(request, env)) return error("Sessão do aparelho não autorizada.", 401);
    if (url.pathname === "/api/chat" && request.method === "POST") return handleChat(request, env);
    if (url.pathname === "/api/voice/tts" && request.method === "POST") return handleTts(request, env);
    if (url.pathname === "/api/voice/tts/stream" && request.method === "POST") return handleTts(request, env);
    if (url.pathname === "/api/voice/stt" && request.method === "POST") return handleStt(request, env);
    if (url.pathname === "/api/lifeos/habits" && request.method === "GET") return listHabits(env);
    if (url.pathname === "/api/lifeos/habits" && request.method === "POST") return createHabitFromApi(request, env);
    if (url.pathname === "/api/sessions" && request.method === "GET") return listSessions(env);
    if (url.pathname === "/api/sessions" && request.method === "POST") return createSession(request, env);
    if (url.pathname === "/api/session" && request.method === "GET") return getSession(url, env);
    const historyMatch = url.pathname.match(/^\/api\/sessions\/([^/]+)\/history$/);
    if (historyMatch && request.method === "GET") return getSessionHistory(decodeURIComponent(historyMatch[1]), env);
    if (historyMatch && request.method === "POST") return replaceHistory(request, decodeURIComponent(historyMatch[1]), env);
    const sessionMatch = url.pathname.match(/^\/api\/sessions\/([^/]+)$/);
    if (sessionMatch && request.method === "DELETE") return deleteSession(decodeURIComponent(sessionMatch[1]), env);
    const compatible = mobileCompatibility(url.pathname, env);
    if (compatible) return compatible;
    if (url.pathname.startsWith("/api/")) return error("Endpoint mobile não encontrado.", 404);
    // The Android app opens /app/. The PC bundle uses absolute /assets URLs,
    // so map that entry point to the same root document rather than keeping a
    // visually different mobile-only page.
    if (url.pathname === "/" || url.pathname === "/app" || url.pathname === "/app/") {
      return env.ASSETS.fetch(new Request(new URL("/index.html", url), request));
    }
    return env.ASSETS.fetch(request);
  },
} satisfies ExportedHandler<Env>;
