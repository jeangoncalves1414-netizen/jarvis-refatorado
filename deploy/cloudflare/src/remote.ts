import type { Env } from "./env";
import { tokenHash } from "./auth";
import { cleanText, cookieValue, error, id, JSON_HEADERS, json, readJson } from "./http";

const REMOTE_COOKIE = "__Host-jarvis_remote";
const REMOTE_COMMANDS = new Set(["open_youtube", "open_chrome", "open_whatsapp", "open_settings", "home", "back", "recents", "notifications"]);

type RemoteDevice = { id: string; name: string; platform: string; last_seen_at: number };
type RemoteController = { id: string; device_id: string; token_hash: string; name: string; created_at: number; last_seen_at: number };

export async function remoteController(request: Request, env: Env): Promise<RemoteController | null> {
  const token = cookieValue(request, REMOTE_COOKIE);
  if (!token || token.length < 32) return null;
  const controller = await env.JARVIS_DB.prepare("SELECT id, device_id, token_hash, name, created_at, last_seen_at FROM remote_controllers WHERE token_hash = ?")
    .bind(await tokenHash(token)).first<RemoteController>();
  if (controller) await env.JARVIS_DB.prepare("UPDATE remote_controllers SET last_seen_at = ? WHERE id = ?").bind(Date.now(), controller.id).run();
  return controller || null;
}

export async function remoteClaim(request: Request, env: Env): Promise<Response> {
  const body = await readJson(request);
  const code = cleanText(body?.code, 6).replace(/\D/g, "");
  if (code.length !== 6) return error("Informe o código de seis dígitos exibido no celular.");
  const device = await env.JARVIS_DB.prepare("SELECT id FROM remote_devices WHERE paired_code = ? AND paired_code_expires_at > ?")
    .bind(code, Date.now()).first<{ id: string }>();
  if (!device) return error("Código inválido ou expirado.", 403);
  const token = crypto.randomUUID().replaceAll("-", "") + crypto.randomUUID().replaceAll("-", "");
  const timestamp = Date.now();
  await env.JARVIS_DB.batch([
    env.JARVIS_DB.prepare("UPDATE remote_devices SET paired_code = NULL, paired_code_expires_at = NULL WHERE id = ?").bind(device.id),
    env.JARVIS_DB.prepare("INSERT INTO remote_controllers (id, device_id, token_hash, name, created_at, last_seen_at) VALUES (?, ?, ?, ?, ?, ?)")
      .bind(id(), device.id, await tokenHash(token), "PC", timestamp, timestamp),
  ]);
  return new Response(JSON.stringify({ ok: true }), { headers: { ...JSON_HEADERS, "set-cookie": `${REMOTE_COOKIE}=${token}; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=2592000` } });
}

export async function remoteDevice(request: Request, env: Env, action: string): Promise<Response> {
  const body = await readJson(request);
  const deviceId = cleanText(body?.device_id, 100);
  if (!deviceId) return error("Identificação do celular ausente.");
  const timestamp = Date.now();
  if (action === "register") {
    const name = cleanText(body?.name, 100) || "Celular Android";
    await env.JARVIS_DB.prepare("INSERT INTO remote_devices (id, name, platform, last_seen_at, created_at) VALUES (?, ?, 'android', ?, ?) ON CONFLICT(id) DO UPDATE SET name = excluded.name, last_seen_at = excluded.last_seen_at")
      .bind(deviceId, name, timestamp, timestamp).run();
    return json({ ok: true, device_id: deviceId });
  }
  const exists = await env.JARVIS_DB.prepare("SELECT id FROM remote_devices WHERE id = ?").bind(deviceId).first<{ id: string }>();
  if (!exists) return error("Celular não registrado. Reative o controle remoto.", 404);
  await env.JARVIS_DB.prepare("UPDATE remote_devices SET last_seen_at = ? WHERE id = ?").bind(timestamp, deviceId).run();
  if (action === "pair-code") {
    const code = String(Math.floor(100000 + Math.random() * 900000));
    await env.JARVIS_DB.prepare("UPDATE remote_devices SET paired_code = ?, paired_code_expires_at = ? WHERE id = ?").bind(code, timestamp + 10 * 60_000, deviceId).run();
    return json({ ok: true, code, expires_at: timestamp + 10 * 60_000 });
  }
  if (action === "poll") {
    const commands = await env.JARVIS_DB.prepare("SELECT id, command, payload FROM remote_commands WHERE target_id = ? AND status = 'pending' ORDER BY created_at ASC LIMIT 10")
      .bind(deviceId).all<{ id: string; command: string; payload: string | null }>();
    const rows = commands.results || [];
    if (rows.length) await env.JARVIS_DB.batch(rows.map((command) => env.JARVIS_DB.prepare("UPDATE remote_commands SET status = 'delivered', updated_at = ? WHERE id = ? AND status = 'pending'").bind(timestamp, command.id)));
    return json({ ok: true, commands: rows.map((command) => ({ ...command, payload: command.payload ? JSON.parse(command.payload) : {} })) });
  }
  if (action === "result") {
    const commandId = cleanText(body?.command_id, 100);
    if (!commandId) return error("Comando ausente.");
    const ok = body?.ok === true;
    await env.JARVIS_DB.prepare("UPDATE remote_commands SET status = ?, result = ?, updated_at = ? WHERE id = ? AND target_id = ?")
      .bind(ok ? "executed" : "failed", cleanText(body?.result, 300), timestamp, commandId, deviceId).run();
    return json({ ok: true });
  }
  return error("Ação remota inválida.");
}

export async function remoteControl(request: Request, env: Env, controller: RemoteController): Promise<Response> {
  if (request.method === "GET") {
    const devices = await env.JARVIS_DB.prepare("SELECT id, name, platform, last_seen_at FROM remote_devices ORDER BY last_seen_at DESC").all<RemoteDevice>();
    return json({ ok: true, devices: (devices.results || []).map((device) => ({ ...device, online: Date.now() - device.last_seen_at < 20_000 })) });
  }
  const body = await readJson(request);
  const targetId = cleanText(body?.target_id, 100);
  const command = cleanText(body?.command, 50);
  if (!targetId || !REMOTE_COMMANDS.has(command)) return error("Comando remoto não permitido.");
  const target = await env.JARVIS_DB.prepare("SELECT id FROM remote_devices WHERE id = ?").bind(targetId).first<{ id: string }>();
  if (!target) return error("Celular não encontrado.", 404);
  const timestamp = Date.now();
  const commandId = id();
  await env.JARVIS_DB.prepare("INSERT INTO remote_commands (id, target_id, command, payload, status, created_at, updated_at) VALUES (?, ?, ?, ?, 'pending', ?, ?)")
    .bind(commandId, targetId, command, "{}", timestamp, timestamp).run();
  return json({ ok: true, command_id: commandId, accepted: true });
}
