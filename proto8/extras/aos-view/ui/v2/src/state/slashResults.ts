// Per-agent slash results keep pending commands visible and poll only while their inspector is open.
import { getJson } from "../api/client.ts";
import type { SlashResult, SlashResults } from "../api/types.ts";
import { createStore } from "./store.ts";

export interface SlashEntry extends SlashResults { loadedAt: number }
export const slashResults = createStore<Record<string, SlashEntry>>({});
const open = new Map<string, number>();
const timers = new Map<string, ReturnType<typeof setTimeout>>();
const requests = new Map<string, Promise<void>>();

export function pendingOf(name: string, command: string): boolean {
  return !!slashResults.get()[name]?.items.some((item) => item.command === command && (item.state === "waiting" || item.state === "doing"));
}

function schedule(name: string): void {
  const timer = timers.get(name);
  if (timer !== undefined) clearTimeout(timer);
  timers.delete(name);
  if (!open.has(name) || !slashResults.get()[name]?.items.some((item) => item.state === "waiting" || item.state === "doing")) return;
  timers.set(name, setTimeout(() => {
    timers.delete(name);
    void refreshSlash(name);
  }, 3000));
}

export function refreshSlash(name: string): Promise<void> {
  const active = requests.get(name);
  if (active) return active;
  const request = (async () => {
    try {
      const { body } = await getJson<SlashResults>("/api/slash_results?name=" + encodeURIComponent(name));
      slashResults.set({ [name]: { ...body, loadedAt: Date.now() } });
    } catch { /* Keep the last known results and retry pending commands while the inspector stays open. */ }
    finally { requests.delete(name); schedule(name); }
  })();
  requests.set(name, request);
  return request;
}

export function watchSlash(name: string): () => void {
  open.set(name, (open.get(name) || 0) + 1);
  schedule(name);
  return () => {
    const count = (open.get(name) || 1) - 1;
    if (count) open.set(name, count); else open.delete(name);
    schedule(name);
  };
}

export function slashLabel(item: SlashResult, inTurn: boolean, name: string, now: number): string {
  const label = item.state === "waiting" ? (inTurn ? `排隊中：等 ${name} 這一輪講完` : "排隊中")
    : item.state === "doing" ? "做中…" : item.state === "answered" ? "完成" : "讀不到狀態";
  return label + (item.state !== "answered" && item.at !== null && now - item.at > 30 * 60 ? "（還沒回，可能還在長回合）" : "");
}
