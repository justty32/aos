// Drafts (12.8 #5): one per target, every field kept, so switching say / mail / order never loses text.
// Kept in localStorage (injected, so node --test can use a memory one). Cleared only on a successful send or "丟掉",
// and pruned after 14 days.

export type Mode = "say" | "mail" | "order";
export interface Draft {
  text: string; mailTitle: string; mailStatus: string; mode: Mode; orderKind: string;
  fields: Record<string, string>; updatedAt: number;
}
export interface Kv { getItem(k: string): string | null; setItem(k: string, v: string): void; removeItem(k: string): void; readonly length: number; key(i: number): string | null }

export const NONE = "_none";       // a draft typed before a target was chosen (A4)
const PREFIX = "aosview.draft:";
const ASK_PREFIX = "aosview.ask:";
const KEEP_S = 14 * 86400;

export function emptyDraft(): Draft {
  return { text: "", mailTitle: "", mailStatus: "REQUEST", mode: "say", orderKind: "expand", fields: {}, updatedAt: 0 };
}

export function isEmpty(d: Draft): boolean {
  return !d.text.trim() && !d.mailTitle.trim() && !Object.values(d.fields).some((v) => v && v.trim());
}

export function loadDraft(kv: Kv, target: string | null): Draft {
  try {
    const s = kv.getItem(PREFIX + (target || NONE));
    if (s) return { ...emptyDraft(), ...JSON.parse(s) };
  } catch { /* broken entry: start empty */ }
  return emptyDraft();
}

export function saveDraft(kv: Kv, target: string | null, d: Draft, now: number): void {
  const key = PREFIX + (target || NONE);
  if (isEmpty(d)) { kv.removeItem(key); return; }
  kv.setItem(key, JSON.stringify({ ...d, updatedAt: now }));
}

export function dropDraft(kv: Kv, target: string | null): void {
  kv.removeItem(PREFIX + (target || NONE));
}

function keys(kv: Kv, prefix: string): string[] {
  const out: string[] = [];
  for (let i = 0; i < kv.length; i++) { const k = kv.key(i); if (k && k.startsWith(prefix)) out.push(k); }
  return out;
}

export function listDrafts(kv: Kv): { target: string; draft: Draft }[] {
  const out: { target: string; draft: Draft }[] = [];
  for (const k of keys(kv, PREFIX)) {
    const d = loadDraft(kv, k.slice(PREFIX.length));
    if (!isEmpty(d)) out.push({ target: k.slice(PREFIX.length), draft: d });
  }
  return out.sort((a, b) => b.draft.updatedAt - a.draft.updatedAt);
}

/** drop drafts older than 14 days, and those whose target left (gone = not on the tree and not NONE). */
export function pruneDrafts(kv: Kv, now: number, alive: (id: string) => boolean): number {
  let n = 0;
  for (const k of [...keys(kv, PREFIX), ...keys(kv, ASK_PREFIX)]) {
    let at = 0;
    try { at = JSON.parse(kv.getItem(k) || "{}").updatedAt || 0; } catch { /* broken */ }
    const target = k.startsWith(PREFIX) ? k.slice(PREFIX.length) : null;
    if (now - at > KEEP_S || (target && target !== NONE && !alive(target))) { kv.removeItem(k); n++; }
  }
  return n;
}

// half-answered decision cards (02c §4.3), by letter
export interface AskDraft { answers: Record<string, string>; note: string; text: string; updatedAt: number }

export function loadAsk(kv: Kv, letter: string): AskDraft {
  try { const s = kv.getItem(ASK_PREFIX + letter); if (s) return JSON.parse(s); } catch { /* broken */ }
  return { answers: {}, note: "", text: "", updatedAt: 0 };
}
export function saveAsk(kv: Kv, letter: string, a: AskDraft, now: number): void {
  kv.setItem(ASK_PREFIX + letter, JSON.stringify({ ...a, updatedAt: now }));
}
export function dropAsk(kv: Kv, letter: string): void {
  kv.removeItem(ASK_PREFIX + letter);
}

export class MemoryKv implements Kv {
  m = new Map<string, string>();
  getItem(k: string) { return this.m.has(k) ? this.m.get(k)! : null; }
  setItem(k: string, v: string) { this.m.set(k, v); }
  removeItem(k: string) { this.m.delete(k); }
  get length() { return this.m.size; }
  key(i: number) { return [...this.m.keys()][i] ?? null; }
}
