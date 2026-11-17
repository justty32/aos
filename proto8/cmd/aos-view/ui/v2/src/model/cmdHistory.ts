// Command history and pins use injected key-value storage and bounded, deduplicated lists.
import type { Kv } from "./drafts.ts";
export interface CmdEntry { line: string; at: number; target: string | null }
export const DEFAULT_PINS = ["/compact", "/status", "/mail", "/map"];
export function readHistory(kv: Kv): CmdEntry[] {
  try { const rows = JSON.parse(kv.getItem("page.cmd.history") || "[]"); return Array.isArray(rows) ? rows.filter((x) => typeof x?.line === "string" && x.line.startsWith("/") && typeof x.at === "number").slice(0, 50) : []; } catch { return []; }
}
export function recordCommand(kv: Kv, line: string, target: string | null, at: number): void {
  if (!line.startsWith("/")) return;
  try { kv.setItem("page.cmd.history", JSON.stringify([{ line, target, at }, ...readHistory(kv).filter((x) => x.line !== line)].slice(0, 50))); } catch { /* private window etc. */ }
}
export function readPins(kv: Kv): string[] {
  try { const raw = kv.getItem("page.cmd.pins"); if (!raw) return [...DEFAULT_PINS]; const rows = JSON.parse(raw); return Array.isArray(rows) ? [...new Set(rows.filter((s): s is string => typeof s === "string" && s.startsWith("/")))].slice(0, 12) : [...DEFAULT_PINS]; } catch { return [...DEFAULT_PINS]; }
}
export function togglePin(kv: Kv, line: string): string[] {
  const pins = readPins(kv);
  const next = pins.includes(line) ? pins.filter((s) => s !== line) : [...pins, line].slice(0, 12);
  try { kv.setItem("page.cmd.pins", JSON.stringify(next)); } catch { /* private window etc. */ }
  return next;
}
