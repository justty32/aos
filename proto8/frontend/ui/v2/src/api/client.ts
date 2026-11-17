// HTTP to the aos-frontend backend: 8 s timeout per call, ETag / If-None-Match, the CSRF token (header + cookie).
import type { SendResult, UiKey, UiState } from "./types.ts";

const TIMEOUT_MS = 8000;
let token: string | null = null;
const etags = new Map<string, { etag: string; body: unknown }>();

export class ApiError extends Error {
  status: number; code: string;
  constructor(status: number, code: string, message: string) { super(message); this.status = status; this.code = code; }
}

async function call(path: string, init: RequestInit = {}): Promise<Response> {
  const ac = new AbortController();
  const t = setTimeout(() => ac.abort(), TIMEOUT_MS);
  try {
    return await fetch(path, { ...init, signal: ac.signal, credentials: "same-origin", cache: "no-store" });
  } catch (e) {
    throw new ApiError(0, ac.signal.aborted ? "Timeout" : "Network", ac.signal.aborted ? "後端 8 秒沒回應" : "連不上後端");
  } finally {
    clearTimeout(t);
  }
}

async function fail(r: Response): Promise<never> {
  let code = "Http" + r.status, msg = "HTTP " + r.status;
  try { const j = await r.json(); code = j.error || code; msg = j.message || msg; } catch { /* not json */ }
  throw new ApiError(r.status, code, msg);
}

/** GET JSON. With etag=true the last body is reused on 304 (returns {changed:false}). */
export async function getJson<T>(path: string, etag = false): Promise<{ body: T; changed: boolean }> {
  const old = etag ? etags.get(path) : undefined;
  const r = await call(path, { headers: old ? { "If-None-Match": old.etag } : {} });
  if (r.status === 304 && old) return { body: old.body as T, changed: false };
  if (!r.ok) return fail(r);
  const body = (await r.json()) as T;
  const e = r.headers.get("ETag");
  if (etag && e) etags.set(path, { etag: e, body });
  return { body, changed: true };
}

export async function session(): Promise<string> {
  const { body } = await getJson<{ token: string }>("/api/session");
  token = body.token;
  return token;
}

async function write(method: "POST" | "PUT", path: string, data: unknown, retry = true): Promise<Response> {
  if (!token) await session();
  const r = await call(path, {
    method, body: JSON.stringify(data),
    headers: { "Content-Type": "application/json", "X-View-Token": token || "" },
  });
  if (r.status === 403 && retry) {
    const j = await r.clone().json().catch(() => ({}));
    if (j.error === "TokenBad") { await session(); return write(method, path, data, false); }
  }
  return r;
}

/** POST a send-like action (say / mail / order / answer / board). Errors come back as ok:false, never thrown. */
export async function post(path: string, data: unknown): Promise<SendResult & Record<string, unknown>> {
  try {
    const r = await write("POST", path, data);
    const j = await r.json().catch(() => ({ ok: false, message: "HTTP " + r.status }));
    return { ok: !!j.ok && r.ok, message: j.message || "", ...j };
  } catch (e) {
    return { ok: false, message: e instanceof Error ? e.message : String(e) };
  }
}

export async function putUi<T>(key: UiKey, value: unknown): Promise<UiState<T>> {
  const r = await write("PUT", "/api/ui-state?key=" + key, value);
  if (!r.ok) return fail(r);
  return (await r.json()) as UiState<T>;
}
