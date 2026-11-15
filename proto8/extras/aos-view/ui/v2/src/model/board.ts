// Reading an agent's board/1 (ok-board, board-1114/06 §7.3–§7.4). Pure; the page only reads, never writes for an agent.
import type { Board1, BoardMode, Node, WaitingOn } from "../api/types.ts";
import { parseIso } from "./time.ts";

export interface BoardView {
  raw: Board1;
  mode: BoardMode;          // after the four steps
  stale: boolean;           // expired: shown grey, mode counts as here, waiting_on not counted
  clockOdd: boolean;        // updated_at more than 5 min in the future
  overdue: boolean;         // back_at passed while the post is still fresh
  waiting: WaitingOn[];     // the ones that count
  updated: number;
}

export function readBoard(b: Board1 | null | undefined, state: string | null, now: number): BoardView | null {
  // step 1: not readable or not board/1 = not posted (the backend already drops other formats)
  if (!b || (b.format && b.format !== "board/1") || !b.mode) return null;
  let updated = parseIso(b.updated_at);
  if (updated === null) return null;
  // step 2: clock check
  let clockOdd = false;
  if (updated > now + 300) { updated = now; clockOdd = true; }
  // step 3: expiry (no expires_at = updated_at + 24 h, whatever the mode)
  const exp = parseIso(b.expires_at) ?? updated + 86400;
  const stale = now > exp;
  let mode: BoardMode = stale ? "here" : b.mode;
  const waiting = stale ? [] : (b.waiting_on || []).filter((w) => w && w.who && w.what);
  // step 4: a sleeping / stopped proc is away whatever it wrote
  const st = (state || "").toLowerCase();
  if (st && st !== "running" && st !== "paused") mode = "away";
  const back = parseIso(b.back_at);
  return { raw: b, mode, stale, clockOdd, overdue: !stale && back !== null && now > back, waiting, updated };
}

export const MODE_WORD: Record<BoardMode, string> = { here: "在", busy: "在忙", dnd: "請勿打擾", away: "不在" };

export interface BoardCounts { dnd: number; waiting: number; waitingUser: { id: string; what: string; since: number | null }[] }

/** §7.4: over the given nodes (a department's members, or everyone below it). */
export function boardCounts(nodes: Node[], now: number): BoardCounts {
  const out: BoardCounts = { dnd: 0, waiting: 0, waitingUser: [] };
  for (const n of nodes) {
    const v = readBoard(n.board, n.state, now);
    if (!v || v.stale) continue;
    if (v.mode === "dnd") out.dnd++;
    if (v.waiting.length) out.waiting++;
    for (const w of v.waiting) if (w.who === "user") out.waitingUser.push({ id: n.id, what: w.what, since: parseIso(w.since_at) });
  }
  return out;
}
