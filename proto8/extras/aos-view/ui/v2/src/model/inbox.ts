// The to-do queue (02c §2): four kinds in a fixed order, all derived from data the page already has (no model).
// Pure: the 10 s local tick re-runs it, so "waiting long" appears on time without new data (12.8 #7).
import type { Ask, LetterIn, OutItem, Tree } from "../api/types.ts";
import { boardCounts } from "./board.ts";

export type TodoKind = "ask" | "red" | "reply" | "wait";
export interface Todo {
  key: string;            // also the dismissed / seen key
  kind: TodoKind;
  title: string;
  sub: string;
  at: number | null;
  node: string | null;    // the node to select
  letter?: string;        // ask letter / relay letter / outbox letter
  urgent?: boolean;
  canDismiss: boolean;
}

// thresholds (Q3, as recommended): stopped = at once; idle and unread = 10 min; queued in a turn = 30 min; read, no reply = 60 min
export const WAIT = { idle: 10 * 60, turn: 30 * 60, read: 60 * 60 };

export function askOrder(a: Ask, b: Ask): number {
  if (a.urgent !== b.urgent) return a.urgent ? -1 : 1;
  const da = a.deadline || "9999", db = b.deadline || "9999";
  if (da !== db) return da < db ? -1 : 1;
  return (a.sent_at || 0) - (b.sent_at || 0);
}

export function waitReason(o: OutItem, tree: Tree | null, now: number): string | null {
  if (o.reply || !o.followed || !o.sent_at) return null;
  const age = now - o.sent_at;
  if (o.gone) return "對方已經收隊，信沒人讀";
  const n = tree?.nodes[o.to];
  const st = (n?.state || "").toLowerCase();
  if (o.delivery === "queued") {
    if (n && st !== "running" && st !== "paused") return "對方停了，信沒人讀";
    if (o.turn) return age >= WAIT.turn ? `對方這一輪還沒結束，前面還有 ${o.queue_ahead ?? "?"} 則` : null;
    return age >= WAIT.idle ? "對方閒著但沒讀" : null;
  }
  if (o.delivery === "read") return age >= WAIT.read ? "讀了但沒回" : null;
  return null;
}

export interface InboxInput {
  tree: Tree | null; asks: Ask[]; relay: LetterIn[]; outbox: OutItem[];
  seen: Record<string, number>; dismissed: Record<string, number>; answeredHere: Set<string>; now: number;
}

export function redKey(id: string, why: string): string {
  return `red:${id}:${why.slice(0, 40)}`;
}

export function buildInbox(x: InboxInput): Todo[] {
  const out: Todo[] = [];
  for (const a of [...x.asks].sort(askOrder)) {
    if (x.answeredHere.has(a.letter) || a.error) continue;
    const nq = a.questions?.length || 0;
    out.push({ key: "ask:" + a.letter, kind: "ask", title: `${a.from || "?"}：${a.title}`, letter: a.letter,
      sub: [a.urgent ? "急" : "", a.risk === "irreversible" ? "不可逆" : "", nq ? `${nq} 題` : a.kind, a.deadline ? `期限 ${a.deadline}` : ""].filter(Boolean).join("｜"),
      at: a.sent_at, node: a.from && x.tree?.nodes[a.from] ? a.from : null, urgent: a.urgent, canDismiss: false });
  }
  if (x.tree) {
    for (const n of Object.values(x.tree.nodes)) {
      const reds: string[] = [];
      if (n.light === "red") reds.push(n.why);
      if (n.team_light?.light === "red") reds.push(n.team_light.why);
      for (const why of reds) {
        const key = redKey(n.id, why);
        if (x.dismissed[key]) continue;
        out.push({ key, kind: "red", title: n.id, sub: why, at: n.active_at, node: n.id, canDismiss: true });
      }
    }
  }
  const replies = x.relay.filter((l) => l.sent_at && x.now - l.sent_at < 3 * 86400 && !x.seen["in:" + l.letter] && !x.dismissed["in:" + l.letter]);
  for (const l of replies) {
    out.push({ key: "in:" + l.letter, kind: "reply", title: `${l.from} 回：${l.title}`, sub: l.status || "", at: l.sent_at,
      node: x.tree?.nodes[l.from] ? l.from : null, letter: l.letter, canDismiss: true });
  }
  // the board/1 "waiting on the user" lines (03 §12.4)
  if (x.tree) {
    for (const w of boardCounts(Object.values(x.tree.nodes), x.now).waitingUser) {
      const key = `bw:${w.id}:${w.what.slice(0, 40)}`;
      if (x.dismissed[key]) continue;
      out.push({ key, kind: "wait", title: `${w.id} 在等你：${w.what}`, sub: "它的布告欄寫的", at: w.since, node: w.id, canDismiss: true });
    }
  }
  const waits = x.outbox.map((o) => ({ o, why: waitReason(o, x.tree, x.now) })).filter((w) => w.why && !x.dismissed["wait:" + w.o.letter]);
  waits.sort((a, b) => (a.o.sent_at || 0) - (b.o.sent_at || 0));
  for (const { o, why } of waits) {
    out.push({ key: "wait:" + o.letter, kind: "wait", title: `給 ${o.to} 的${o.kind === "say" ? "話" : o.kind === "order" ? "指令" : "信"}：${o.title}`,
      sub: why!, at: o.sent_at, node: x.tree?.nodes[o.to] ? o.to : null, letter: o.letter, canDismiss: true });
  }
  return out;
}

export interface Counts { ask: number; red: number; yellow: number; reply: number }

export function headCounts(todo: Todo[], tree: Tree | null): Counts {
  const yellow = tree ? Object.values(tree.nodes).filter((n) => n.light === "yellow" || n.team_light?.light === "yellow").length : 0;
  return {
    ask: todo.filter((t) => t.kind === "ask").length,
    red: todo.filter((t) => t.kind === "red").length,
    yellow,
    reply: todo.filter((t) => t.kind === "reply" || t.kind === "wait").length,
  };
}

/** the track tab (02c §4.4): everything not closed, "most needing attention" first. */
export function trackOrder(items: OutItem[], tree: Tree | null, now: number): OutItem[] {
  const rank = (o: OutItem) => (waitReason(o, tree, now) ? 0 : o.reply ? 3 : o.delivery === "queued" ? 1 : 2);
  return [...items].sort((a, b) => rank(a) - rank(b) || (b.sent_at || 0) - (a.sent_at || 0));
}

/** "等你處理" under the tree (02f §1.3): one of each non-empty group first (ask, red, waiting on you), then fill up
 *  in the order ask → red → waiting on you → reply → long wait. Pure. */
export interface WaitRow { key: string; group: "ask" | "red" | "you" | "reply" | "wait"; title: string; node: string | null; todo: Todo }
export function pickWaiting(todo: Todo[], limit: number): WaitRow[] {
  const groups: Record<WaitRow["group"], WaitRow[]> = { ask: [], red: [], you: [], reply: [], wait: [] };
  for (const t of todo) {
    const g = t.kind === "wait" && t.key.startsWith("bw:") ? "you" : t.kind;   // bw: = an agent's board says it waits on you
    groups[g].push({ key: t.key, group: g, title: t.title, node: t.node, todo: t });
  }
  const out: WaitRow[] = [];
  for (const g of ["ask", "red", "you"] as const) if (groups[g].length && out.length < limit) out.push(groups[g].shift()!);
  for (const g of ["ask", "red", "you", "reply", "wait"] as const) while (groups[g].length && out.length < limit) out.push(groups[g].shift()!);
  return out;
}
