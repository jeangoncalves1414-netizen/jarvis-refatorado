import type { Env } from "./env";
import { cookieValue } from "./http";

const COOKIE = "__Host-jarvis_cloud";

export function authenticated(request: Request, env: Env): boolean {
  const received = cookieValue(request, COOKIE);
  if (!received || !env.MOBILE_CONTROL_TOKEN || received.length !== env.MOBILE_CONTROL_TOKEN.length) return false;
  let mismatch = 0;
  for (let index = 0; index < received.length; index++) mismatch |= received.charCodeAt(index) ^ env.MOBILE_CONTROL_TOKEN.charCodeAt(index);
  return mismatch === 0;
}

export async function tokenHash(token: string): Promise<string> {
  const bytes = new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(token)));
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}
