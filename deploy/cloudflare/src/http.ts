export const JSON_HEADERS = { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" };
export const MAX_TEXT = 12_000;

export function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), { status, headers: JSON_HEADERS });
}

export function error(message: string, status = 400): Response {
  return json({ ok: false, error: message }, status);
}

export function cookieValue(request: Request, name: string): string | null {
  const prefix = `${name}=`;
  for (const item of (request.headers.get("Cookie") || "").split(";")) {
    const part = item.trim();
    if (part.startsWith(prefix)) return part.slice(prefix.length);
  }
  return null;
}

export async function readJson(request: Request): Promise<Record<string, unknown> | null> {
  try {
    const body: unknown = await request.json();
    return body && typeof body === "object" && !Array.isArray(body) ? body as Record<string, unknown> : null;
  } catch {
    return null;
  }
}

export function cleanText(value: unknown, max = MAX_TEXT): string {
  return typeof value === "string" ? value.trim().slice(0, max) : "";
}

export function id(): string {
  return crypto.randomUUID();
}

export function now(): string {
  return new Date().toISOString();
}
