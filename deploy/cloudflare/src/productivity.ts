import type { Env } from "./env";
import { cleanText, error, id, json, now, readJson } from "./http";

type CloudTask = { id: string; title: string; completed: boolean; created_at: string; updated_at: string };
type CalendarEntry = { id: string; title: string; start: string; reminder_minutes: number; reminder_policy: string; reminder_at: string | null; reminder_status: string };

export async function tasks(request: Request, env: Env): Promise<Response> {
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

export async function calendar(request: Request, env: Env): Promise<Response> {
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
