import type { Env } from "./env";
import { cleanText, error, id, json, now, readJson } from "./http";

type Habit = { id: string; name: string; days_of_week: string[]; completed_today: boolean; created_at: string; updated_at: string };
type LifeOSSnapshot = { data: Record<string, unknown>; updatedAt: number };

const LIFEOS_SNAPSHOT_KEY = "lifeos_snapshot";

export function saoPauloDay(): string {
  return new Date().toLocaleDateString("en-CA", { timeZone: "America/Sao_Paulo" });
}

function normalizeHabit(value: string): string {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/\s+/g, " ").trim();
}

export function requestedHabit(message: string): string | null {
  const match = message.match(/^\s*(?:crie|criar|adicione|adicionar|registre|registrar|quero criar)\s+(?:um\s+|o\s+)?h[áa]bito(?:\s+(?:de|para))?\s+(.+?)[.?!]*\s*$/i);
  if (!match) return null;
  const name = cleanText(match[1], 120).replace(/\s+(?:todos os dias|todo dia|diariamente)$/i, "").trim();
  return name.length >= 2 ? name : null;
}

export async function createHabit(db: D1Database, name: string): Promise<{ habit: Habit; created: boolean }> {
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

export async function lifeOSSnapshot(db: D1Database): Promise<LifeOSSnapshot> {
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

export async function saveLifeOSSnapshot(db: D1Database, snapshot: LifeOSSnapshot): Promise<void> {
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

export async function syncLifeOS(request: Request, env: Env): Promise<Response> {
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

export async function listHabits(env: Env): Promise<Response> {
  const rows = await env.JARVIS_DB.prepare("SELECT h.id, h.name, h.days_of_week, h.created_at, h.updated_at, c.completed_at FROM habits h LEFT JOIN habit_completions c ON c.habit_id = h.id AND c.date_key = ? ORDER BY h.created_at DESC")
    .bind(saoPauloDay()).all<{ id: string; name: string; days_of_week: string; created_at: string; updated_at: string; completed_at: string | null }>();
  const habits = (rows.results || []).map(({ completed_at, ...habit }) => ({ ...habit, days_of_week: JSON.parse(habit.days_of_week), completed_today: Boolean(completed_at), completed_at }));
  return json({ ok: true, habits });
}

export async function toggleHabit(request: Request, env: Env, habitId: string): Promise<Response> {
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

export async function createHabitFromApi(request: Request, env: Env): Promise<Response> {
  const body = await readJson(request);
  const name = cleanText(body?.name, 120);
  if (name.length < 2) return error("Informe o nome do hábito.");
  const result = await createHabit(env.JARVIS_DB, name);
  return json({ ok: true, ...result }, result.created ? 201 : 200);
}

export async function evoluteStatus(env: Env): Promise<Response> {
  const snapshot = await lifeOSSnapshot(env.JARVIS_DB), date = saoPauloDay();
  const water = Number(snapshot.data[`lifeos_water_${date}`]) || 0;
  const habits = Array.isArray(snapshot.data.lifeos_habits) ? snapshot.data.lifeos_habits : [];
  const logs = snapshot.data[`lifeos_hlog_${date}`] && typeof snapshot.data[`lifeos_hlog_${date}`] === "object" ? snapshot.data[`lifeos_hlog_${date}`] as Record<string, { completed?: boolean }> : {};
  const normalized = habits.filter((habit): habit is Record<string, unknown> => Boolean(habit) && typeof habit === "object").map((habit) => ({ id: String(habit.id || ""), title: String(habit.title || "Hábito"), streak: Number(habit.streak) || 0, bestStreak: Number(habit.bestStreak || habit.streak) || 0, connectedTo: typeof habit.connectedTo === "string" ? habit.connectedTo : undefined, isPriority: Boolean(habit.isPriority), completed_today: Boolean(logs[String(habit.id)]?.completed) }));
  const completed = normalized.filter((habit) => habit.completed_today).length;
  return json({ ok: true, date, water: { current_ml: water, target_ml: 3000, percentage: Math.min(100, Math.round(water / 30)) }, habits: { total: normalized.length, completed, rate_percentage: normalized.length ? Math.round(completed * 100 / normalized.length) : 0, items: normalized, priority_total: normalized.filter((habit) => habit.isPriority).length, priority_completed: normalized.filter((habit) => habit.isPriority && habit.completed_today).length }, workout: { split_name: "Treino Diário", is_rest_day: false, completed: false }, study: { minutes_today: 0, sessions_count: 0 }, motivational: { quote: "A consistência diária vence o talento.", author: "Jarvis", action: "Mantenha o foco no próximo passo.", speech: "Você está no comando do seu dia." }, waterMl: water, vices: [] });
}

export async function addEvoluteWater(request: Request, env: Env): Promise<Response> {
  const amount = Math.max(-3_000, Math.min(3_000, Number((await readJson(request))?.amount_ml || 0)));
  if (!amount) return error("Informe uma quantidade de água válida.");
  const snapshot = await lifeOSSnapshot(env.JARVIS_DB), key = `lifeos_water_${saoPauloDay()}`;
  const total = Math.max(0, (Number(snapshot.data[key]) || 0) + amount);
  snapshot.data[key] = total;
  snapshot.updatedAt = Date.now();
  await saveLifeOSSnapshot(env.JARVIS_DB, snapshot);
  return json({ ok: true, added_ml: amount, total_ml: total, percentage: Math.min(100, Math.round(total / 30)), habit_completed: total >= 3000 });
}
