// Ctrl+K: find someone, or say what to do first (02d §4.2 "找人框兼做下命令"). Pure, so node --test checks it.
//   "board"        → select ok-board, caret in the box (say)
//   "信 board"     → the same, the box set to mail
//   "加人 view" / "擴充 view" / "電力 view" → the same, the box set to that order
//   "決定"         → open the next 要你決定
//   "地圖" / "牆" / "待辦" → that center tab
import type { Node, Tree } from "../api/types.ts";

export type Verb =
  | { kind: "say" } | { kind: "mail" } | { kind: "order"; order: "hire" | "expand" | "power" }
  | { kind: "decide" } | { kind: "view"; view: "wall" | "map" | "todo" };

const WORDS: [string[], Verb][] = [
  [["說", "say"], { kind: "say" }],
  [["信", "寄信", "mail"], { kind: "mail" }],
  [["加人", "hire"], { kind: "order", order: "hire" }],
  [["擴充", "expand"], { kind: "order", order: "expand" }],
  [["電力", "power"], { kind: "order", order: "power" }],
  [["決定", "decide"], { kind: "decide" }],
  [["地圖", "map"], { kind: "view", view: "map" }],
  [["牆", "部門牆", "wall"], { kind: "view", view: "wall" }],
  [["待辦", "todo"], { kind: "view", view: "todo" }],
];

/** the leading verb and the rest. A verb counts when it is the whole query or followed by a space (or, for a CJK verb,
 * directly by the name: "信board"). "決定" and the tabs take no name. Nothing recognised = a plain name search. */
export function parseQuery(q: string): { verb: Verb | null; rest: string } {
  const s = q.trim();
  for (const [ws, v] of WORDS) {
    for (const w of ws) {
      const cjk = /[^\x00-\x7f]/.test(w);
      if (s === w || s.toLowerCase().startsWith(w + " ") || (cjk && s.startsWith(w) && s.length > w.length && v.kind !== "view" && v.kind !== "decide")) {
        return { verb: v, rest: s.slice(w.length).trim() };
      }
    }
  }
  return { verb: null, rest: s };
}

/** who matches: name or tag contains the text; names that start with it first, then agents, then by name. 30 at most.
 * A verb that talks to someone (say / mail / order) keeps only agents. */
export function findNodes(t: Tree | null, text: string, agentsOnly = false): Node[] {
  if (!t) return [];
  const s = text.trim().toLowerCase();
  // the short name counts too: "sol-1" finds "ok-board-sol-1"; "board" finds "ok-board" before "ok-board-sol-1"
  const score = (id: string) => {
    const l = id.toLowerCase();
    if (!s) return 0;
    if (l === s || l.endsWith("-" + s)) return 0;
    if (l.startsWith(s) || l.includes("-" + s)) return 1;
    return 2;
  };
  return Object.values(t.nodes)
    .filter((n) => (!agentsOnly || n.kind === "agent") && (!s || n.id.toLowerCase().includes(s) || (n.tags || []).some((x) => x.toLowerCase().includes(s))))
    .sort((a, b) => score(a.id) - score(b.id) || (a.kind === "agent" ? 0 : 1) - (b.kind === "agent" ? 0 : 1) || a.id.length - b.id.length || a.id.localeCompare(b.id))
    .slice(0, 30);
}

/** the line on top of the list that says what Enter will do */
export function verbHint(v: Verb | null): string {
  if (!v) return "Enter：跳過去，游標進打字區（說話）";
  switch (v.kind) {
    case "say": return "Enter：跳過去，打字區是「說話」";
    case "mail": return "Enter：跳過去，打字區是「寄信」";
    case "order": return `Enter：跳過去，打字區是「指令：${{ hire: "加人", expand: "擴充", power: "電力" }[v.order]}」`;
    case "decide": return "Enter：打開下一張要你決定";
    case "view": return `Enter：中間切到「${{ wall: "部門牆", map: "地圖", todo: "待辦" }[v.view]}」`;
  }
}
