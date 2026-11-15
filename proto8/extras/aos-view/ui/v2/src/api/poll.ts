// Pulse-driven fetching (12.8 #7): only /api/pulse runs on a timer (5 s; 30 s while the tab is hidden). A kind is
// fetched again only when its rev changed (with If-None-Match as a second guard). A 10 s local tick moves the clock
// so "N min ago" and "waiting long" change on time without new data.
import { getJson, putUi, session } from "./client.ts";
import type { Answered, Ask, LetterIn, OrderKind, OutItem, Pulse, RevKey, Tree, UiState, UserBoard } from "./types.ts";
import { data, type Prefs } from "../state/app.ts";

const last: Partial<Record<RevKey, string>> = {};
const listeners = new Set<(changed: RevKey[]) => void>();

const FETCH: Record<RevKey, () => Promise<void>> = {
  async tree() {
    const { body, changed } = await getJson<{ tree: Tree | null; error: string | null }>("/api/tree", true);
    if (changed) data.set({ tree: body.tree, treeError: body.error });
  },
  async asks() {
    const { body, changed } = await getJson<{ asks: Ask[] }>("/api/asks", true);
    if (changed) data.set({ asks: body.asks });
  },
  async relay() {
    const { body, changed } = await getJson<{ letters: LetterIn[] }>("/api/relay", true);
    if (changed) data.set({ relay: body.letters });
  },
  async outbox() {
    const { body, changed } = await getJson<{ items: OutItem[]; checked_at: number | null }>("/api/outbox", true);
    if (changed) data.set({ outbox: body.items, outboxChecked: body.checked_at });
  },
  async board() {
    const { body, changed } = await getJson<{ user: UserBoard | null }>("/api/board", true);
    if (changed) data.set({ board: body.user });
  },
  async answered() {
    const { body, changed } = await getJson<{ answered: Answered[] }>("/api/answered", true);
    if (changed) data.set({ answered: body.answered });
  },
  async ui_state() {
    const [s, d, p] = await Promise.all([
      getJson<UiState<Record<string, number>>>("/api/ui-state?key=seen"),
      getJson<UiState<Record<string, number>>>("/api/ui-state?key=dismissed"),
      getJson<UiState<Prefs>>("/api/ui-state?key=prefs"),
    ]);
    data.set({ seen: s.body.value || {}, dismissed: d.body.value || {}, prefs: p.body.value || {} });
  },
};

async function fetchKind(k: RevKey, rev: string): Promise<boolean> {
  try {
    await FETCH[k]();
    last[k] = rev;
    const e = { ...data.get().errors };
    delete e[k];
    data.set({ errors: e });
    return true;
  } catch (err) {
    data.set({ errors: { ...data.get().errors, [k]: err instanceof Error ? err.message : String(err) } });
    return false;
  }
}

let timer: ReturnType<typeof setTimeout> | null = null;
let running = false;

export async function pulse(): Promise<void> {
  if (running) return;
  running = true;
  try {
    const { body } = await getJson<Pulse>("/api/pulse");
    const c = Date.now() / 1000;
    data.set({ pulse: body, pulseOkAt: c, pulseError: null, skew: body.now - c, clock: c });
    const changed = (Object.keys(body.rev) as RevKey[]).filter((k) => body.rev[k] !== last[k]);
    const ok = await Promise.all(changed.map((k) => fetchKind(k, body.rev[k])));
    if (!data.get().loaded) data.set({ loaded: true });
    const done = changed.filter((_, i) => ok[i]);
    if (done.length) listeners.forEach((f) => f(done));
  } catch (err) {
    data.set({ pulseError: err instanceof Error ? err.message : String(err) });
  } finally {
    running = false;
    schedule();
  }
}

function schedule() {
  if (timer) clearTimeout(timer);
  timer = setTimeout(pulse, document.visibilityState === "visible" ? 5000 : 30000);
}

/** something on the page sent / changed: ask again now instead of waiting up to 5 s. */
export function pulseSoon(ms = 300): void {
  if (timer) clearTimeout(timer);
  timer = setTimeout(pulse, ms);
}

/** panels that keep their own data (thread, bot card) refetch when one of these kinds changed. */
export function onChange(f: (changed: RevKey[]) => void): () => void {
  listeners.add(f);
  return () => { listeners.delete(f); };
}

export async function start(): Promise<void> {
  try { await session(); } catch { /* pulse shows the error */ }
  getJson<{ kinds: OrderKind[] }>("/api/orders").then(({ body }) => data.set({ orders: body.kinds })).catch(() => {});
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") pulseSoon(50); });
  setInterval(() => data.set({ clock: Date.now() / 1000 }), 10000);
  await pulse();
}

// ---- writes to the ui-state drawer (B4): optimistic, then the merged value from the backend ----
async function mergeUi(key: "seen" | "dismissed", diff: Record<string, number | null>) {
  const cur = { ...(data.get()[key] || {}) };
  for (const [k, v] of Object.entries(diff)) { if (v === null) delete cur[k]; else cur[k] = v; }
  data.set({ [key]: cur } as Partial<ReturnType<typeof data.get>>);
  try {
    const r = await putUi<Record<string, number>>(key, diff);
    data.set({ [key]: r.value || {} } as Partial<ReturnType<typeof data.get>>);
  } catch { /* kept locally; the next ui_state rev brings the truth */ }
}

export function markSeen(keys: string[]): void {
  const t = Date.now() / 1000;
  const todo = keys.filter((k) => !data.get().seen[k]);
  if (todo.length) mergeUi("seen", Object.fromEntries(todo.map((k) => [k, t])));
}
export function markUnseen(key: string): void { mergeUi("seen", { [key]: null }); }
export function dismiss(key: string): void { mergeUi("dismissed", { [key]: Date.now() / 1000 }); }
export function undismiss(key: string): void { mergeUi("dismissed", { [key]: null }); }

export async function savePrefs(p: Prefs): Promise<void> {
  data.set({ prefs: p });
  try { await putUi("prefs", p); } catch { /* local only */ }
}
