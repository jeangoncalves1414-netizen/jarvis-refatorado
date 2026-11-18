import { authenticated } from "./auth";
import type { Env } from "./env";
import { cleanText, error, id, json, MAX_TEXT, now, readJson } from "./http";
import { remoteClaim, remoteControl, remoteController, remoteDevice } from "./remote";

const MAX_AUDIO = 25 * 1024 * 1024;

type ToolActivity = { id: string; tool: string; status: string; label?: string; result?: string };
type ChatMessage = { role: "user" | "assistant"; content: string; activity?: ToolActivity[] };
type Habit = { id: string; name: string; days_of_week: string[]; completed_today: boolean; created_at: string; updated_at: string };
type CloudTask = { id: string; title: string; completed: boolean; created_at: string; updated_at: string };
type CalendarEntry = { id: string; title: string; start: string; reminder_minutes: number; reminder_policy: string; reminder_at: string | null; reminder_status: string };
type LifeOSSnapshot = { data: Record<string, unknown>; updatedAt: number };
type MemoryFact = { id: string; text: string; created_at: number; updated_at: number; session_id: string; origin: string; kind: string };

const LIFEOS_SNAPSHOT_KEY = "lifeos_snapshot";

function saoPauloDay(): string {
  return new Date().toLocaleDateString("en-CA", { timeZone: "America/Sao_Paulo" });
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
  await addHabitToLifeOS(db, habit);
  return { habit, created: true };
}

async function lifeOSSnapshot(db: D1Database): Promise<LifeOSSnapshot> {
  const row = await db.prepare("SELECT value FROM preferences WHERE key = ?").bind(LIFEOS_SNAPSHOT_KEY).first<{ value: string }>();
  if (!row?.value) return { data: {}, updatedAt: 0 };
  try {
    const parsed: unknown = JSON.parse(row.value);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      const value = parsed as Partial<LifeOSSnapshot>;
      return { data: value.data && typeof value.data === "object" && !Array.isArray(value.data) ? value.data : {}, updatedAt: Number(value.updatedAt) || 0 };
    }
  } catch { /* Corrupt local state must not block the panel. */ }
  return { data: {}, updatedAt: 0 };
}

async function saveLifeOSSnapshot(db: D1Database, snapshot: LifeOSSnapshot): Promise<void> {
  await db.prepare("INSERT INTO preferences (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at")
    .bind(LIFEOS_SNAPSHOT_KEY, JSON.stringify(snapshot), now()).run();
}

async function addHabitToLifeOS(db: D1Database, habit: Habit): Promise<void> {
  const snapshot = await lifeOSSnapshot(db);
  const current = Array.isArray(snapshot.data.lifeos_habits) ? snapshot.data.lifeos_habits : [];
  const exists = current.some((item) => item && typeof item === "object" && (item as { id?: unknown }).id === habit.id);
  if (exists) return;
  snapshot.data.lifeos_habits = [...current, {
    id: habit.id, title: habit.name, type: "boolean", createdAt: habit.created_at.slice(0, 10), streak: 0, bestStreak: 0,
  }];
  snapshot.updatedAt = Date.now();
  await saveLifeOSSnapshot(db, snapshot);
}

async function syncLifeOS(request: Request, env: Env): Promise<Response> {
  const current = await lifeOSSnapshot(env.JARVIS_DB);
  if (request.method === "GET") return json({ data: current.data, updatedAt: current.updatedAt });
  const body = await readJson(request);
  const data = body?.data;
  if (!data || typeof data !== "object" || Array.isArray(data)) return error("Dados do Life OS inválidos.");
  const baseUpdatedAt = Number(body?.baseUpdatedAt || 0);
  if (current.updatedAt && baseUpdatedAt && baseUpdatedAt < current.updatedAt) return json({ ok: false, error: "O Life OS foi atualizado em outro aparelho.", data: current.data, updatedAt: current.updatedAt }, 409);
  const updatedAt = Math.max(Date.now(), Number(body?.updatedAt || 0));
  await saveLifeOSSnapshot(env.JARVIS_DB, { data: data as Record<string, unknown>, updatedAt });
  return json({ ok: true, data, updatedAt });
}

async function listHabits(env: Env): Promise<Response> {
  const rows = await env.JARVIS_DB.prepare("SELECT h.id, h.name, h.days_of_week, h.created_at, h.updated_at, c.completed_at FROM habits h LEFT JOIN habit_completions c ON c.habit_id = h.id AND c.date_key = ? ORDER BY h.created_at DESC")
    .bind(saoPauloDay()).all<{ id: string; name: string; days_of_week: string; created_at: string; updated_at: string; completed_at: string | null }>();
  const habits = (rows.results || []).map(({ completed_at, ...habit }) => ({ ...habit, days_of_week: JSON.parse(habit.days_of_week), completed_today: Boolean(completed_at), completed_at }));
  return json({ ok: true, habits });
}

async function toggleHabit(request: Request, env: Env, habitId: string): Promise<Response> {
  const habit = await env.JARVIS_DB.prepare("SELECT id, name, days_of_week, created_at, updated_at FROM habits WHERE id = ?").bind(habitId).first<{ id: string; name: string; days_of_week: string; created_at: string; updated_at: string }>();
  if (!habit) return error("Hábito não encontrado.", 404);
  const body = await readJson(request);
  const completed = body?.completed !== false;
  const dateKey = saoPauloDay();
  if (completed) await env.JARVIS_DB.prepare("INSERT OR IGNORE INTO habit_completions (habit_id, date_key, completed_at) VALUES (?, ?, ?)").bind(habitId, dateKey, now()).run();
  else await env.JARVIS_DB.prepare("DELETE FROM habit_completions WHERE habit_id = ? AND date_key = ?").bind(habitId, dateKey).run();
  const completion = completed ? await env.JARVIS_DB.prepare("SELECT completed_at FROM habit_completions WHERE habit_id = ? AND date_key = ?").bind(habitId, dateKey).first<{ completed_at: string }>() : null;
  return json({ ok: true, habit: { ...habit, days_of_week: JSON.parse(habit.days_of_week), completed_today: Boolean(completion), completed_at: completion?.completed_at || null, changed: true } });
}

async function createHabitFromApi(request: Request, env: Env): Promise<Response> {
  const body = await readJson(request);
  const name = cleanText(body?.name, 120);
  if (name.length < 2) return error("Informe o nome do hábito.");
  const result = await createHabit(env.JARVIS_DB, name);
  return json({ ok: true, ...result }, result.created ? 201 : 200);
}

async function sessionHistory(db: D1Database, sessionId: string): Promise<ChatMessage[]> {
  const rows = await db.prepare(
    "SELECT role, content, activity FROM messages WHERE session_id = ? ORDER BY created_at DESC LIMIT 20",
  ).bind(sessionId).all<{ role: "user" | "assistant"; content: string; activity: string | null }>();
  return (rows.results || []).reverse().map(({ role, content, activity }) => ({ role, content, ...(activity ? { activity: parseActivity(activity) } : {}) }));
}

function parseActivity(value: string): ToolActivity[] {
  try {
    const parsed: unknown = JSON.parse(value);
    return Array.isArray(parsed) ? parsed.filter((item): item is ToolActivity => Boolean(item) && typeof item === "object" && typeof (item as ToolActivity).id === "string" && typeof (item as ToolActivity).tool === "string") : [];
  } catch { return []; }
}

async function saveMessage(db: D1Database, sessionId: string, role: ChatMessage["role"], content: string, activity?: ToolActivity[]): Promise<void> {
  const timestamp = now();
  await db.batch([
    db.prepare("INSERT OR IGNORE INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)")
      .bind(sessionId, role === "user" ? content.slice(0, 72) || "Nova conversa" : "Nova conversa", timestamp, timestamp),
    db.prepare("INSERT INTO messages (id, session_id, role, content, activity, created_at) VALUES (?, ?, ?, ?, ?, ?)")
      .bind(id(), sessionId, role, content, activity?.length ? JSON.stringify(activity) : null, timestamp),
    db.prepare("UPDATE sessions SET updated_at = ?, title = CASE WHEN title = 'Nova conversa' AND ? = 'user' THEN ? ELSE title END WHERE id = ?")
      .bind(timestamp, role, content.slice(0, 72) || "Nova conversa", sessionId),
  ]);
}

async function recentFacts(db: D1Database): Promise<MemoryFact[]> {
  const rows = await db.prepare("SELECT id, text, created_at, updated_at, session_id, origin, kind FROM memory_facts ORDER BY updated_at DESC LIMIT 16").all<MemoryFact>();
  return rows.results || [];
}

function requestedMemory(message: string): string | null {
  const explicit = message.match(/(?:lembre(?:-se)?|lembra|guarde|anote)\s*(?:que|isto|isso)?\s*[:,—-]?\s*(.+)/i)
    || message.match(/(?:eu\s+)?(?:prefiro|gosto de|n[aã]o gosto de)\s+(.+)/i);
  const text = cleanText(explicit?.[1], 300).replace(/[.?!]+$/, "");
  return text.length >= 3 ? text : null;
}

type ExecutionTarget = "mobile" | "pc" | "ambiguous";

function requestedExecutionTarget(message: string): ExecutionTarget {
  const text = message.toLocaleLowerCase("pt-BR");
  const asksForPc = /\b(?:no|do|para o|pelo)\s+(?:pc|computador|desktop|windows)\b|\b(?:pc|computador|desktop|windows)\b/.test(text);
  const asksForPhone = /\b(?:no|do|para o|pelo)\s+(?:celular|telefone|android)\b|\b(?:celular|telefone|android)\b/.test(text);
  if (asksForPc && asksForPhone) return "ambiguous";
  return asksForPc ? "pc" : "mobile";
}

function requestedPhoneAction(message: string): { command: string; label: string } | null {
  const text = message.toLocaleLowerCase("pt-BR");
  if (!/(?:abra|abrir|acesse|acessar|vá para|ir para|mostre|mostrar|volte|voltar)/.test(text)) return null;
  if (/youtube/.test(text)) return { command: "open_youtube", label: "YouTube" };
  if (/chrome|navegador/.test(text)) return { command: "open_chrome", label: "Chrome" };
  if (/whatsapp/.test(text)) return { command: "open_whatsapp", label: "WhatsApp" };
  if (/configura[çc][õo]es|ajustes/.test(text)) return { command: "open_settings", label: "Configurações" };
  if (/in[ií]cio|tela inicial/.test(text)) return { command: "home", label: "Início" };
  if (/recentes/.test(text)) return { command: "recents", label: "Recentes" };
  if (/notifica[çc][õo]es/.test(text)) return { command: "notifications", label: "Notificações" };
  if (/voltar/.test(text)) return { command: "back", label: "Voltar" };
  return null;
}

async function saveMemory(db: D1Database, text: string, sessionId: string, kind = "manual"): Promise<MemoryFact> {
  const existing = await db.prepare("SELECT id, text, created_at, updated_at, session_id, origin, kind FROM memory_facts WHERE lower(text) = lower(?) LIMIT 1")
    .bind(text).first<MemoryFact>();
  const timestamp = Date.now();
  if (existing) {
    await db.prepare("UPDATE memory_facts SET updated_at = ?, session_id = ?, kind = ? WHERE id = ?").bind(timestamp, sessionId, kind, existing.id).run();
    return { ...existing, updated_at: timestamp, session_id: sessionId, kind };
  }
  const fact: MemoryFact = { id: id(), text, created_at: timestamp, updated_at: timestamp, session_id: sessionId, origin: "mobile", kind };
  await db.prepare("INSERT INTO memory_facts (id, text, created_at, updated_at, session_id, origin, kind) VALUES (?, ?, ?, ?, ?, ?, ?)")
    .bind(fact.id, fact.text, fact.created_at, fact.updated_at, fact.session_id, fact.origin, fact.kind).run();
  return fact;
}

function systemPrompt(facts: MemoryFact[] = []): string {
  return [
    "Você é Jarvis, assistente pessoal da usuária, falando em português brasileiro.",
    "Responda de forma natural, objetiva e útil.",
    "CONTEXTO DE EXECUÇÃO: esta conversa acontece no celular Android. Se a usuária não indicar dispositivo, ações disponíveis devem atingir este celular. Se ela disser PC, computador, desktop ou Windows, nunca execute a ação no celular como substituto: diga com clareza que o PC foi escolhido e que este painel não possui uma ponte ativa para controlá-lo. Se mencionar PC e celular na mesma ação sem dizer qual é o alvo, peça uma escolha curta. Nunca alegue controlar o computador, arquivos locais, câmera, microfone ou aplicativos do Windows.",
    "Não peça verificação facial nem de voz. Para alarmes, oriente a usuária a abrir a aba Rotina do aplicativo.",
    "Você pode criar hábitos no painel mobile quando a usuária pedir explicitamente, por exemplo: 'crie o hábito de ler'. Confirme a criação de forma breve.",
    facts.length ? `Memórias persistentes confirmadas pela usuária:\n${facts.map((fact) => `- ${fact.text}`).join("\n")}` : "",
  ].join(" ");
}

async function askGroq(env: Env, messages: ChatMessage[], facts: MemoryFact[]): Promise<string> {
  const key = env.GROQ_API_KEY?.trim();
  if (!key) throw new Error("GROQ_API_KEY não configurada.");
  const response = await fetch("https://api.groq.com/openai/v1/chat/completions", {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "content-type": "application/json" },
    body: JSON.stringify({
      model: env.GROQ_MODEL || "openai/gpt-oss-120b",
      temperature: 0.7,
      messages: [{ role: "system", content: systemPrompt(facts) }, ...messages.map(({ role, content }) => ({ role, content }))],
    }),
  });
  if (!response.ok) throw new Error(`Groq respondeu HTTP ${response.status}.`);
  const payload = await response.json<{ choices?: Array<{ message?: { content?: string } }> }>();
  const answer = cleanText(payload.choices?.[0]?.message?.content);
  if (!answer) throw new Error("Groq não retornou uma resposta.");
  return answer;
}

async function askGemini(env: Env, messages: ChatMessage[], facts: MemoryFact[]): Promise<string> {
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
    body: JSON.stringify({ systemInstruction: { parts: [{ text: systemPrompt(facts) }] }, contents }),
  });
  if (!response.ok) throw new Error(`Gemini respondeu HTTP ${response.status}.`);
  const payload = await response.json<{ candidates?: Array<{ content?: { parts?: Array<{ text?: string }> } }> }>();
  const answer = cleanText(payload.candidates?.[0]?.content?.parts?.map((part) => part.text || "").join(""));
  if (!answer) throw new Error("Gemini não retornou uma resposta.");
  return answer;
}

async function respond(env: Env, messages: ChatMessage[], facts: MemoryFact[]): Promise<string> {
  if (env.GROQ_API_KEY?.trim()) {
    try {
      return await askGroq(env, messages, facts);
    } catch (cause) {
      // A key/model quota can change independently of the mobile app. Keep
      // the phone usable by falling back to Gemini when it is configured.
      console.warn("Groq unavailable; trying Gemini", cause);
      if (!env.GEMINI_API_KEY?.trim()) throw cause;
    }
  }
  if (env.GEMINI_API_KEY?.trim()) return askGemini(env, messages, facts);
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
    const memory = requestedMemory(message);
    if (memory) await saveMemory(env.JARVIS_DB, memory, sessionId, "gatilho");
    const habitName = requestedHabit(message);
    if (habitName) {
      const result = await createHabit(env.JARVIS_DB, habitName);
      const reply = result.created ? `Pronto, criei o hábito “${result.habit.name}” para todos os dias.` : `O hábito “${result.habit.name}” já está na sua rotina.`;
      const activity: ToolActivity[] = [{ id: id(), tool: "habit_tool", status: "succeeded", label: result.created ? "Hábito criado" : "Hábito já existente", result: result.habit.name }];
      await saveMessage(env.JARVIS_DB, sessionId, "assistant", reply, activity);
      return json({ ok: true, status: "complete", session_id: sessionId, reply, summary: reply, intent: "habit_create", actions: [{ type: "habit_created", habit: result.habit }], context: { mobile: true, tool_activity: activity } });
    }
    const target = requestedExecutionTarget(message);
    const phoneAction = requestedPhoneAction(message);
    if (phoneAction && target === "ambiguous") {
      const reply = "Você quer executar isso no celular ou no PC? Não vou escolher por conta própria.";
      await saveMessage(env.JARVIS_DB, sessionId, "assistant", reply);
      return json({ ok: true, status: "complete", session_id: sessionId, reply, summary: reply, intent: "target_clarification", actions: [], context: { mobile: true } });
    }
    if (phoneAction && target === "pc") {
      const reply = `Você indicou o PC para “${phoneAction.label}”. Não vou abrir no celular. O controle remoto do PC ainda não está conectado a este painel.`;
      await saveMessage(env.JARVIS_DB, sessionId, "assistant", reply);
      return json({ ok: true, status: "complete", session_id: sessionId, reply, summary: reply, intent: "pc_target_unavailable", actions: [], context: { mobile: true } });
    }
    if (phoneAction) {
      const reply = `Vou executar “${phoneAction.label}” neste celular.`;
      const activity: ToolActivity[] = [{ id: id(), tool: "android_control", status: "queued", label: "Controle do celular", result: phoneAction.label }];
      await saveMessage(env.JARVIS_DB, sessionId, "assistant", reply, activity);
      return json({ ok: true, status: "complete", session_id: sessionId, reply, summary: reply, intent: "android_control", actions: [{ type: "android_action", command: phoneAction.command }], context: { mobile: true, tool_activity: activity } });
    }
    const facts = await recentFacts(env.JARVIS_DB);
    const reply = await respond(env, [...history, { role: "user", content: message }], facts);
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
    const activity = typeof item.activity === "string" ? parseActivity(item.activity) : Array.isArray(item.activity) ? parseActivity(JSON.stringify(item.activity)) : [];
    return role && content ? [{ role, content, ...(activity.length ? { activity } : {}) }] : [];
  });
  if (!history.length) return json({ ok: true });
  const timestamp = now();
  const statements = [
    env.JARVIS_DB.prepare("DELETE FROM messages WHERE session_id = ?").bind(sessionId),
    ...history.map((item, index) => env.JARVIS_DB.prepare("INSERT INTO messages (id, session_id, role, content, activity, created_at) VALUES (?, ?, ?, ?, ?, ?)")
      .bind(id(), sessionId, item.role, item.content, item.activity?.length ? JSON.stringify(item.activity) : null, new Date(Date.parse(timestamp) + index).toISOString())),
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

function asCitedFact(fact: MemoryFact): Record<string, unknown> {
  return { ...fact, slot: null, value: null, when: null, source: { created_at: fact.created_at, session_id: fact.session_id, run_id: "", origin: fact.origin, kind: fact.kind } };
}

async function listMemories(url: URL, env: Env): Promise<Response> {
  const collection = url.searchParams.get("collection") || "conversations";
  const limit = Math.min(Math.max(Number(url.searchParams.get("limit")) || 25, 1), 100);
  if (collection === "user_memory") {
    const facts = await recentFacts(env.JARVIS_DB);
    return json({ memories: facts.slice(0, limit).map((fact) => ({ id: fact.id, text: fact.text, metadata: { timestamp: String(Math.floor(fact.updated_at / 1000)), origin: fact.origin } })) });
  }
  const rows = await env.JARVIS_DB.prepare("SELECT id, title, updated_at FROM sessions ORDER BY updated_at DESC LIMIT ?").bind(limit).all<{ id: string; title: string; updated_at: string }>();
  return json({ memories: (rows.results || []).map((row) => ({ id: row.id, text: row.title, metadata: { timestamp: String(Math.floor(Date.parse(row.updated_at) / 1000)) } })) });
}

async function memoryFacts(request: Request, env: Env): Promise<Response> {
  if (request.method === "GET") return json({ ok: true, facts: (await recentFacts(env.JARVIS_DB)).map(asCitedFact) });
  const body = await readJson(request);
  const operation = cleanText(body?.operation, 30);
  if (operation === "save") {
    const text = cleanText(body?.text, 300);
    if (!text) return error("Informe a memória.");
    return json({ ok: true, fact: asCitedFact(await saveMemory(env.JARVIS_DB, text, "", "manual")) });
  }
  if (operation === "update") {
    const factId = cleanText(body?.id, 100), text = cleanText(body?.text, 300);
    if (!factId || !text) return error("Memória inválida.");
    const changed = await env.JARVIS_DB.prepare("UPDATE memory_facts SET text = ?, updated_at = ? WHERE id = ?").bind(text, Date.now(), factId).run();
    if (!changed.meta.changes) return error("Memória não encontrada.", 404);
    return json({ ok: true });
  }
  if (operation === "delete_many") {
    const ids = Array.isArray(body?.ids) ? body.ids.filter((value): value is string => typeof value === "string").slice(0, 100) : [];
    if (!ids.length) return error("Selecione ao menos uma memória.");
    await env.JARVIS_DB.batch(ids.map((factId) => env.JARVIS_DB.prepare("DELETE FROM memory_facts WHERE id = ?").bind(factId)));
    return json({ ok: true });
  }
  return error("Operação de memória inválida.");
}

async function cleanupMemories(env: Env): Promise<Response> {
  const result = await env.JARVIS_DB.prepare("DELETE FROM memory_facts WHERE lower(text) LIKE '%erro técnico%' OR lower(text) LIKE '%http %'").run();
  return json({ ok: true, removed: result.meta.changes || 0 });
}

type Reminder = { id: string; message: string; target_time: string; created_at: string };
type ProactiveConfig = { briefing_enabled: boolean; briefing_time: string; topics: string[]; custom_instructions?: string };

async function proactiveConfig(db: D1Database): Promise<ProactiveConfig> {
  const row = await db.prepare("SELECT value FROM preferences WHERE key = 'proactive_config'").first<{ value: string }>();
  try {
    const parsed = JSON.parse(row?.value || "{}") as Partial<ProactiveConfig>;
    return { briefing_enabled: Boolean(parsed.briefing_enabled), briefing_time: cleanText(parsed.briefing_time, 5) || "08:00", topics: Array.isArray(parsed.topics) ? parsed.topics.filter((topic): topic is string => typeof topic === "string").slice(0, 10) : [], custom_instructions: cleanText(parsed.custom_instructions, 500) };
  } catch { return { briefing_enabled: false, briefing_time: "08:00", topics: [] }; }
}

function reminderTime(input: string): string | null {
  const value = cleanText(input, 40);
  const relative = value.match(/^\+(\d{1,4})\s*([mh])$/i);
  if (relative) return new Date(Date.now() + Number(relative[1]) * (relative[2].toLowerCase() === "h" ? 3_600_000 : 60_000)).toISOString();
  if (/^\d{2}:\d{2}$/.test(value)) {
    const [hours, minutes] = value.split(":").map(Number);
    if (hours > 23 || minutes > 59) return null;
    const localToday = new Date().toLocaleDateString("en-CA", { timeZone: "America/Sao_Paulo" });
    let target = new Date(`${localToday}T${value}:00-03:00`);
    if (target.getTime() <= Date.now()) target = new Date(target.getTime() + 86_400_000);
    return target.toISOString();
  }
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) && parsed > Date.now() ? new Date(parsed).toISOString() : null;
}

async function getProactive(env: Env): Promise<Response> {
  const rows = await env.JARVIS_DB.prepare("SELECT id, message, target_time, created_at FROM reminders WHERE completed_at IS NULL ORDER BY target_time ASC LIMIT 50").all<Reminder>();
  return json({ config: await proactiveConfig(env.JARVIS_DB), reminders: rows.results || [] });
}

async function updateProactive(request: Request, env: Env): Promise<Response> {
  const body = await readJson(request);
  const action = cleanText(body?.action, 40);
  if (action === "configure_briefing") {
    const config: ProactiveConfig = { briefing_enabled: Boolean(body?.enabled), briefing_time: cleanText(body?.briefing_time, 5) || "08:00", topics: Array.isArray(body?.topics) ? body.topics.filter((topic): topic is string => typeof topic === "string").slice(0, 10) : [], custom_instructions: cleanText(body?.custom_instructions, 500) };
    await env.JARVIS_DB.prepare("INSERT INTO preferences (key, value, updated_at) VALUES ('proactive_config', ?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at").bind(JSON.stringify(config), now()).run();
    return json({ ok: true, config });
  }
  if (action === "add_reminder") {
    const message = cleanText(body?.reminder_message, 300), targetTime = reminderTime(cleanText(body?.reminder_time, 40));
    if (!message || !targetTime) return error("Informe o texto e um horário válido, como +10m ou 14:30.");
    const reminder: Reminder = { id: id(), message, target_time: targetTime, created_at: now() };
    await env.JARVIS_DB.prepare("INSERT INTO reminders (id, message, target_time, created_at) VALUES (?, ?, ?, ?)").bind(reminder.id, reminder.message, reminder.target_time, reminder.created_at).run();
    return json({ ok: true, reminder });
  }
  if (action === "trigger_briefing") {
    const config = await proactiveConfig(env.JARVIS_DB);
    const pending = await env.JARVIS_DB.prepare("SELECT count(*) AS count FROM reminders WHERE completed_at IS NULL").first<{ count: number }>();
    const topics = config.topics.length ? ` Foco: ${config.topics.join(", ")}.` : "";
    return json({ ok: true, briefing_text: `Briefing do Jarvis: você tem ${pending?.count || 0} lembrete(s) pendente(s).${topics}` });
  }
  return error("Ação proativa inválida.");
}

async function tasks(request: Request, env: Env): Promise<Response> {
  if (request.method === "GET") {
    const rows = await env.JARVIS_DB.prepare("SELECT id, title, completed, created_at, updated_at FROM tasks ORDER BY completed ASC, updated_at DESC LIMIT 100").all<Omit<CloudTask, "completed"> & { completed: number }>();
    return json({ ok: true, tasks: (rows.results || []).map((task) => ({ ...task, completed: Boolean(task.completed) })) });
  }
  const body = await readJson(request), action = cleanText(body?.action, 20), taskId = cleanText(body?.task_id, 100);
  if (action === "create") {
    const title = cleanText(body?.title, 300);
    if (!title) return error("Informe a tarefa.");
    const task: CloudTask = { id: id(), title, completed: false, created_at: now(), updated_at: now() };
    await env.JARVIS_DB.prepare("INSERT INTO tasks (id, title, completed, created_at, updated_at) VALUES (?, ?, 0, ?, ?)").bind(task.id, task.title, task.created_at, task.updated_at).run();
    return json({ ok: true, task }, 201);
  }
  if (!taskId) return error("Tarefa inválida.");
  if (action === "toggle") await env.JARVIS_DB.prepare("UPDATE tasks SET completed = CASE completed WHEN 1 THEN 0 ELSE 1 END, updated_at = ? WHERE id = ?").bind(now(), taskId).run();
  else if (action === "delete") await env.JARVIS_DB.prepare("DELETE FROM tasks WHERE id = ?").bind(taskId).run();
  else return error("Ação de tarefa inválida.");
  return json({ ok: true });
}

async function calendar(request: Request, env: Env): Promise<Response> {
  if (request.method === "GET") {
    const rows = await env.JARVIS_DB.prepare("SELECT id, title, start, reminder_minutes, reminder_policy, reminder_at, reminder_status FROM calendar_events ORDER BY start ASC LIMIT 200").all<CalendarEntry>();
    return json({ ok: true, events: rows.results || [] });
  }
  const body = await readJson(request), action = cleanText(body?.action, 40);
  if (action === "cancel_reminder") {
    const eventId = cleanText(body?.id, 100);
    if (!eventId) return error("Evento inválido.");
    await env.JARVIS_DB.prepare("UPDATE calendar_events SET reminder_status = 'cancelled' WHERE id = ?").bind(eventId).run();
    return json({ ok: true });
  }
  const toCalendarTimestamp = (value: string): number => {
    // Browser date/time inputs do not carry an offset. The owner's cloud uses
    // Brazil time, so preserve the wall-clock time rather than treating it as UTC.
    const zoned = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value : `${value}-03:00`;
    return Date.parse(zoned);
  };
  const title = cleanText(body?.title, 300), start = cleanText(body?.start, 40), startAt = toCalendarTimestamp(start);
  if (!title || !Number.isFinite(startAt)) return error("Informe um evento e uma data válidos.");
  const minutes = Math.max(0, Math.min(10_080, Number(body?.reminder_minutes) || 0));
  const requestedReminder = cleanText(body?.reminder_at, 40);
  const requestedAt = toCalendarTimestamp(requestedReminder);
  const reminderAt = requestedReminder && Number.isFinite(requestedAt) ? new Date(requestedAt).toISOString() : new Date(startAt - minutes * 60_000).toISOString();
  const policy = cleanText(body?.reminder_policy, 40);
  const entry: CalendarEntry = { id: id(), title, start: new Date(startAt).toISOString(), reminder_minutes: minutes, reminder_policy: ["once", "until_confirmed", "next_conversation"].includes(policy) ? policy : "once", reminder_at: reminderAt, reminder_status: "scheduled" };
  await env.JARVIS_DB.prepare("INSERT INTO calendar_events (id, title, start, reminder_minutes, reminder_policy, reminder_at, reminder_status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)").bind(entry.id, entry.title, entry.start, entry.reminder_minutes, entry.reminder_policy, entry.reminder_at, entry.reminder_status, now()).run();
  return json({ ok: true, event: entry }, 201);
}

async function evoluteStatus(env: Env): Promise<Response> {
  const snapshot = await lifeOSSnapshot(env.JARVIS_DB), date = saoPauloDay();
  const water = Number(snapshot.data[`lifeos_water_${date}`]) || 0;
  const habits = Array.isArray(snapshot.data.lifeos_habits) ? snapshot.data.lifeos_habits : [];
  const logs = snapshot.data[`lifeos_hlog_${date}`] && typeof snapshot.data[`lifeos_hlog_${date}`] === "object" ? snapshot.data[`lifeos_hlog_${date}`] as Record<string, { completed?: boolean }> : {};
  const normalized = habits.filter((habit): habit is Record<string, unknown> => Boolean(habit) && typeof habit === "object").map((habit) => ({ id: String(habit.id || ""), title: String(habit.title || "Hábito"), streak: Number(habit.streak) || 0, bestStreak: Number(habit.bestStreak || habit.streak) || 0, connectedTo: typeof habit.connectedTo === "string" ? habit.connectedTo : undefined, isPriority: Boolean(habit.isPriority), completed_today: Boolean(logs[String(habit.id)]?.completed) }));
  const completed = normalized.filter((habit) => habit.completed_today).length;
  return json({ ok: true, date, water: { current_ml: water, target_ml: 3000, percentage: Math.min(100, Math.round(water / 30)) }, habits: { total: normalized.length, completed, rate_percentage: normalized.length ? Math.round(completed * 100 / normalized.length) : 0, items: normalized, priority_total: normalized.filter((habit) => habit.isPriority).length, priority_completed: normalized.filter((habit) => habit.isPriority && habit.completed_today).length }, workout: { split_name: "Treino Diário", is_rest_day: false, completed: false }, study: { minutes_today: 0, sessions_count: 0 }, motivational: { quote: "A consistência diária vence o talento.", author: "Jarvis", action: "Mantenha o foco no próximo passo.", speech: "Você está no comando do seu dia." }, waterMl: water, vices: [] });
}

async function addEvoluteWater(request: Request, env: Env): Promise<Response> {
  const amount = Math.max(-3_000, Math.min(3_000, Number((await readJson(request))?.amount_ml || 0)));
  if (!amount) return error("Informe uma quantidade de água válida.");
  const snapshot = await lifeOSSnapshot(env.JARVIS_DB), key = `lifeos_water_${saoPauloDay()}`;
  const total = Math.max(0, (Number(snapshot.data[key]) || 0) + amount);
  snapshot.data[key] = total;
  snapshot.updatedAt = Date.now();
  await saveLifeOSSnapshot(env.JARVIS_DB, snapshot);
  return json({ ok: true, added_ml: amount, total_ml: total, percentage: Math.min(100, Math.round(total / 30)), habit_completed: total >= 3000 });
}

async function cloudDashboard(env: Env): Promise<Response> {
  const [sessions, tasksResult, habits, latestMessages] = await Promise.all([
    env.JARVIS_DB.prepare("SELECT count(*) AS count FROM sessions").first<{ count: number }>(),
    env.JARVIS_DB.prepare("SELECT id, title, completed FROM tasks ORDER BY completed ASC, updated_at DESC LIMIT 20").all<{ id: string; title: string; completed: number }>(),
    env.JARVIS_DB.prepare("SELECT id, name, created_at FROM habits ORDER BY created_at DESC LIMIT 5").all<{ id: string; name: string; created_at: string }>(),
    env.JARVIS_DB.prepare("SELECT role, content, created_at FROM messages ORDER BY created_at DESC LIMIT 5").all<{ role: string; content: string; created_at: string }>(),
  ]);
  const activity = [
    ...(habits.results || []).map((habit) => ({ type: "habit", message: `Hábito criado: ${habit.name}`, timestamp: habit.created_at })),
    ...(latestMessages.results || []).map((message) => ({
      type: message.role === "user" ? "message" : "assistant",
      message: message.content.slice(0, 160), timestamp: message.created_at,
    })),
  ].sort((a, b) => b.timestamp.localeCompare(a.timestamp)).slice(0, 8);
  return json({
    system: { cpu: 0, ram: 0 },
    tasks: { pending: (tasksResult.results || []).filter((task) => !task.completed).length, completed: (tasksResult.results || []).filter((task) => Boolean(task.completed)).length, items: (tasksResult.results || []).map((task) => ({ ...task, completed: Boolean(task.completed) })) },
    sessions: { total: sessions?.count || 0 },
    activity,
  });
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
  if (path === "/api/realtime") return json({ weather: { ok: false }, finance: { ok: false } });
  if (path === "/api/metrics") return json({ cpu: 0, ram_used: 0, ram_total: 0, ram_percent: 0, provider: "cloud" });
  if (path === "/api/logs") return json({ logs: [] });
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
    if (url.pathname === "/control" || url.pathname === "/control/") return env.ASSETS.fetch(new Request(new URL("/control.html", url), request));
    if (url.pathname === "/api/remote/claim" && request.method === "POST") return remoteClaim(request, env);
    const controller = await remoteController(request, env);
    if (controller && url.pathname === "/api/remote/status" && request.method === "GET") return remoteControl(request, env, controller);
    if (controller && url.pathname === "/api/remote/command" && request.method === "POST") return remoteControl(request, env, controller);
    // The Android WebView enters through /app/. This is only the public
    // document shell; every data/action API below still requires the device
    // token. Serve it before the API authentication guard.
    if (url.pathname === "/app" || url.pathname === "/app/") {
      return env.ASSETS.fetch(new Request(new URL("/index.html", url), request));
    }
    if (!authenticated(request, env)) return error("Sessão do aparelho não autorizada.", 401);
    if (url.pathname === "/api/remote/register" && request.method === "POST") return remoteDevice(request, env, "register");
    if (url.pathname === "/api/remote/pair-code" && request.method === "POST") return remoteDevice(request, env, "pair-code");
    if (url.pathname === "/api/remote/poll" && request.method === "POST") return remoteDevice(request, env, "poll");
    if (url.pathname === "/api/remote/result" && request.method === "POST") return remoteDevice(request, env, "result");
    if (url.pathname === "/api/chat" && request.method === "POST") return handleChat(request, env);
    if (url.pathname === "/api/voice/tts" && request.method === "POST") return handleTts(request, env);
    if (url.pathname === "/api/voice/tts/stream" && request.method === "POST") return handleTts(request, env);
    if (url.pathname === "/api/voice/stt" && request.method === "POST") return handleStt(request, env);
    if (url.pathname === "/api/sync" && (request.method === "GET" || request.method === "POST")) return syncLifeOS(request, env);
    if (url.pathname === "/api/lifeos/habits" && request.method === "GET") return listHabits(env);
    if (url.pathname === "/api/lifeos/habits" && request.method === "POST") return createHabitFromApi(request, env);
    const habitMatch = url.pathname.match(/^\/api\/lifeos\/habits\/([^/]+)\/toggle$/);
    if (habitMatch && request.method === "POST") return toggleHabit(request, env, decodeURIComponent(habitMatch[1]));
    if (url.pathname === "/api/tasks" && (request.method === "GET" || request.method === "POST")) return tasks(request, env);
    if (url.pathname === "/api/calendar" && (request.method === "GET" || request.method === "POST")) return calendar(request, env);
    if (url.pathname === "/api/evolute/status" || url.pathname === "/api/evolute/summary") return evoluteStatus(env);
    if (url.pathname === "/api/evolute/water/add" && request.method === "POST") return addEvoluteWater(request, env);
    if (url.pathname === "/api/memories" && request.method === "GET") return listMemories(url, env);
    if (url.pathname === "/api/memories/facts" && (request.method === "GET" || request.method === "POST")) return memoryFacts(request, env);
    if (url.pathname === "/api/memories/cleanup" && request.method === "POST") return cleanupMemories(env);
    if (url.pathname === "/api/proactive" && request.method === "GET") return getProactive(env);
    if (url.pathname === "/api/proactive" && request.method === "POST") return updateProactive(request, env);
    if (url.pathname === "/api/dashboard" && request.method === "GET") return cloudDashboard(env);
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
    if (url.pathname === "/") {
      return env.ASSETS.fetch(new Request(new URL("/index.html", url), request));
    }
    return env.ASSETS.fetch(request);
  },
} satisfies ExportedHandler<Env>;
