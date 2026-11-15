// The map's layout (P4; 02e §3, q5 a), pure so node --test can check it: "wide rooms, people before rooms".
// Name plates are 116×28 (D1), 4 px apart; a room's frame adds 18 to the width and 44 to the height (title 26).
// When it does not fit the height, try in order and keep the first that fits; never scroll sideways:
//   0 everything open → 1 second-level rooms fold into room plates → 2 quiet people in first-level rooms become
//   dots → 3 the same as 2, and the stage scrolls down. Someone with something going on (red / yellow light, a letter
//   for you, a board that waits on you) is never folded and never a dot.
import type { Tree } from "../api/types.ts";
import { isDept, machineIds, machineRollup, MACHINE, shortName } from "./tree.ts";

export const PLATE = { w: 116, h: 28 };
export const DOT = 14;
export const GAP = 4;
const FRAME_W = 18, FRAME_H = 44, PAD = 9, TITLE_TOP = 35;

export type MapItem =
  | { kind: "room"; id: string; x: number; y: number; w: number; h: number; title: string; count: number; depth: number }
  | { kind: "plate"; id: string; x: number; y: number; w: number; h: number; name: string; lead: boolean; busy: boolean }
  | { kind: "dot"; id: string; x: number; y: number; w: number; h: number; name: string }
  | { kind: "fold"; id: string; x: number; y: number; w: number; h: number; name: string; count: number; busy: boolean };

export interface MapLayout { items: MapItem[]; width: number; height: number; step: 0 | 1 | 2 | 3 }

// ---- the user's own folds (11-15: "地圖那邊我希望可以折疊") ----
// The unit is the room (a department, or the machine room): folded = one plate-sized cell with its name, head count and
// worst light; open = the frame with the people inside. `all` is what the 全部折疊 / 全部展開 buttons set (null = the
// automatic steps above decide); `ids` are single rooms the user flipped since, and win over `all`.
export type FoldMode = "fold" | "open";
export interface Folds { all: FoldMode | null; ids: Record<string, FoldMode> }
export const NO_FOLDS: Folds = { all: null, ids: {} };
/** true = the user wants it folded, false = open, null = leave it to the automatic steps */
export function userFolded(f: Folds, id: string): boolean | null {
  const m = f.ids[id] ?? f.all;
  return m == null ? null : m === "fold";
}
/** flip one room from what the map shows now (`shownFolded`) */
export function flipFold(f: Folds, id: string, shownFolded: boolean): Folds {
  return { all: f.all, ids: { ...f.ids, [id]: shownFolded ? "open" : "fold" } };
}
export const setAllFolds = (all: FoldMode | null): Folds => ({ all, ids: {} });
/** the stored JSON, checked field by field (anything odd = the default) */
export function parseFolds(raw: string | null): Folds {
  try {
    const j = raw ? JSON.parse(raw) : null;
    if (!j || typeof j !== "object") return { ...NO_FOLDS, ids: {} };
    const ok = (v: unknown): v is FoldMode => v === "fold" || v === "open";
    const ids: Record<string, FoldMode> = {};
    if (j.ids && typeof j.ids === "object") for (const [k, v] of Object.entries(j.ids)) if (ok(v)) ids[k] = v;
    return { all: ok(j.all) ? j.all : null, ids };
  } catch { return { ...NO_FOLDS, ids: {} }; }
}
export const STEP_WORD = ["全部展開", "小組已摺起", "只顯示有事的人", "可往下捲"] as const;

/** something going on: never folded, never a dot (03 §13.6 #8) */
export function busyOf(t: Tree, id: string): boolean {
  const n = t.nodes[id];
  if (!n) return false;
  return n.light === "red" || n.light === "yellow" || n.asks > 0 || !!n.board?.waiting_on?.some((w) => w.who === "user");
}
function busyBelow(t: Tree, id: string): boolean {
  if (busyOf(t, id)) return true;
  return (t.nodes[id]?.children || []).some((c) => busyBelow(t, c));
}

interface Box { w: number; h: number; items: MapItem[] }      // items relative to the box's top-left
type Piece = { w: number; h: number; place: (x: number, y: number) => MapItem[] };

/** left to right, wrap when the next one does not fit; a row is as tall as its tallest piece; tops aligned. */
function flow(pieces: Piece[], maxW: number): Box {
  const items: MapItem[] = [];
  let x = 0, y = 0, rowH = 0, w = 0;
  for (const p of pieces) {
    if (x > 0 && x + p.w > maxW) { x = 0; y += rowH + GAP; rowH = 0; }
    items.push(...p.place(x, y));
    x += p.w + GAP;
    rowH = Math.max(rowH, p.h);
    w = Math.max(w, x - GAP);
  }
  return { w, h: pieces.length ? y + rowH : 0, items };
}
const shift = (it: MapItem, dx: number, dy: number): MapItem => ({ ...it, x: it.x + dx, y: it.y + dy });

function plate(t: Tree, id: string, name: string, lead: boolean): Piece {
  const busy = busyOf(t, id);
  return { ...PLATE, place: (x, y) => [{ kind: "plate", id, x, y, ...PLATE, name, lead, busy }] };
}
function dot(id: string, name: string): Piece {
  return { w: DOT, h: DOT, place: (x, y) => [{ kind: "dot", id, x, y: y + (PLATE.h - DOT) / 2, w: DOT, h: DOT, name }] };
}
function fold(t: Tree, id: string, name: string): Piece {
  const count = id === MACHINE ? machineIds(t).length : t.nodes[id]?.rollup.nodes || 0;
  const busy = id === MACHINE ? machineIds(t).some((m) => busyBelow(t, m)) : busyBelow(t, id);
  return { ...PLATE, place: (x, y) => [{ kind: "fold", id, x, y, ...PLATE, name, count, busy }] };
}

/**
 * A room's contents: its lead plate (if it has one), its people, then its sub-rooms on new rows.
 * depth = 1 for rooms on the stage, 2 inside them; quiet rooms deeper than 2 are always folded (02d: two levels down).
 */
function contents(t: Tree, room: string, lead: string | null, people: string[], rooms: string[], maxW: number, depth: number,
                  step: number, parentOfLead: string | null, fs: Folds): Box {
  const ps: Piece[] = [];
  if (lead) ps.push(plate(t, lead, shortName(lead, parentOfLead), true));
  const ppl = step >= 2 && depth === 1 ? [...people.filter((p) => busyOf(t, p)), ...people.filter((p) => !busyOf(t, p))] : people;
  for (const p of ppl) {
    const name = shortName(p, room === MACHINE ? null : room);
    ps.push(step >= 2 && depth === 1 && !busyOf(t, p) ? dot(p, name) : plate(t, p, name, false));
  }
  const rs: Piece[] = [];
  for (const r of rooms) {
    const name = shortName(r, room === MACHINE || room === "" ? null : room);
    // deeper than two levels: folded unless something is going on inside (then it opens, so the busy one is a plate)
    // the user's own fold / open wins over that
    const folded = userFolded(fs, r) ?? (!busyBelow(t, r) && (depth + 1 > 2 || (step >= 1 && depth + 1 === 2)));
    if (folded) ps.push(fold(t, r, name));     // a folded room sits with the people
    else rs.push(roomPiece(t, r, room === "" ? null : room, maxW, depth + 1, step, fs));
  }
  const a = flow(ps, maxW);
  const b = flow(rs, maxW);
  const items = [...a.items, ...b.items.map((it) => shift(it, 0, a.h + (a.h && b.h ? GAP : 0)))];
  return { w: Math.max(a.w, b.w), h: a.h + b.h + (a.h && b.h ? GAP : 0), items };
}

function split(t: Tree, ids: string[]): { people: string[]; rooms: string[] } {
  return { people: ids.filter((k) => !isDept(t.nodes[k])), rooms: ids.filter((k) => isDept(t.nodes[k])) };
}

function roomPiece(t: Tree, id: string, parent: string | null, avail: number, depth: number, step: number, fs: Folds): Piece {
  const kids = id === MACHINE ? machineIds(t) : t.nodes[id]?.children || [];
  const { people, rooms } = split(t, kids);
  const inner = contents(t, id, id === MACHINE ? null : id, people, rooms, Math.max(PLATE.w, avail - FRAME_W), depth, step, parent, fs);
  const title = id === MACHINE ? "機房" : shortName(id, parent);
  const count = id === MACHINE ? machineIds(t).length : t.nodes[id]?.rollup.nodes || 0;
  const w = Math.max(inner.w, 120) + FRAME_W, h = inner.h + FRAME_H;
  return {
    w, h,
    place: (x, y) => [{ kind: "room", id, x, y, w, h, title, count, depth }, ...inner.items.map((it) => shift(it, x + PAD, y + TITLE_TOP))],
  };
}

/** the stage itself: an unframed room. focus null = the company (loners, then rooms, then the machine room). */
function stage(t: Tree, focus: string | null, W: number, step: number, fs: Folds): Box {
  if (focus === MACHINE) {
    const { people, rooms } = split(t, machineIds(t));
    return contents(t, MACHINE, null, people, rooms, W, 1, step, null, fs);
  }
  if (focus && t.nodes[focus]) {
    const { people, rooms } = split(t, t.nodes[focus].children);
    return contents(t, focus, focus, people, rooms, W, 1, step, t.nodes[focus].parent, fs);
  }
  const top = t.roots.filter((r) => t.nodes[r] && t.nodes[r].kind === "agent");
  const { people, rooms } = split(t, top);
  const m = machineIds(t).length ? [MACHINE] : [];
  // the top level: loners are plates on the stage; each top department and the machine room is a framed room
  const ps: Piece[] = people.map((p) => (step >= 2 && !busyOf(t, p) ? dot(p, p) : plate(t, p, p, false)));
  // a top room the user folded sits with the loners as one cell; the rest are framed rooms. When the whole company is
  // one room, 全部折疊 leaves that one open (else the map is a single cell); folding it by hand still works.
  const rs: Piece[] = [];
  const only = !people.length && rooms.length + m.length === 1;
  for (const r of [...rooms, ...m]) {
    if (only ? fs.ids[r] === "fold" : userFolded(fs, r)) ps.push(fold(t, r, r === MACHINE ? "機房" : r));
    else rs.push(roomPiece(t, r, null, W, 1, step, fs));
  }
  const a = flow(ps, W), b = flow(rs, W);
  const items = [...a.items, ...b.items.map((it) => shift(it, 0, a.h + (a.h && b.h ? GAP : 0)))];
  return { w: Math.max(a.w, b.w), h: a.h + b.h + (a.h && b.h ? GAP : 0), items };
}

export function layoutMap(t: Tree | null, focus: string | null, W: number, H: number, fs: Folds = NO_FOLDS): MapLayout {
  if (!t) return { items: [], width: 0, height: 0, step: 0 };
  const w = Math.max(PLATE.w + FRAME_W, Math.floor(W));
  let last: Box = { w: 0, h: 0, items: [] };
  for (const step of [0, 1, 2] as const) {
    last = stage(t, focus, w, step, fs);
    if (last.h <= H) return { items: last.items, width: last.w, height: last.h, step };
  }
  return { items: last.items, width: last.w, height: last.h, step: 3 };
}

/** the light a map item shows: a person its own, a room or folded room the worst inside */
export function itemLight(t: Tree, it: MapItem) {
  if (it.id === MACHINE) return machineRollup(t).worst;
  const n = t.nodes[it.id];
  if (!n) return "gray" as const;
  return it.kind === "room" || it.kind === "fold" ? n.rollup.worst : n.light;
}

// ---- keyboard on the map (02d §6 #2): arrows go to the nearest piece that way, by rectangles; pure and tested ----

export type Dir = "left" | "right" | "up" | "down";
/** one key per piece: a room and its lead plate share the id, so the kind is part of it */
export const itemKey = (it: MapItem) => `${it.kind}:${it.id}`;
/** what the arrows walk on: a room by its title bar, the rest whole */
function hitBox(it: MapItem) {
  return it.kind === "room" ? { x: it.x, y: it.y, w: it.w, h: 26 } : { x: it.x, y: it.y, w: it.w, h: it.h };
}

/** the piece reached from `from` (an itemKey) by one arrow; null = nothing that way. No current piece = the first. */
export function nearest(items: MapItem[], from: string | null, dir: Dir): string | null {
  if (!items.length) return null;
  const a = items.find((it) => itemKey(it) === from);
  if (!a) return itemKey(items[0]);
  const A = hitBox(a);
  const acx = A.x + A.w / 2, acy = A.y + A.h / 2;
  let best: { k: string; s: number } | null = null;
  for (const it of items) {
    if (it === a) continue;
    const B = hitBox(it);
    const bcx = B.x + B.w / 2, bcy = B.y + B.h / 2;
    // main = how far that way (must be ahead); side = how far off the line, 0 when the boxes overlap on the other axis
    let main: number, side: number;
    if (dir === "right" || dir === "left") {
      main = dir === "right" ? B.x - (A.x + A.w) : A.x - (B.x + B.w);
      if ((dir === "right" ? bcx <= acx : bcx >= acx)) continue;
      side = Math.max(A.y, B.y) - Math.min(A.y + A.h, B.y + B.h) > 0 ? Math.abs(bcy - acy) : 0;
    } else {
      main = dir === "down" ? B.y - (A.y + A.h) : A.y - (B.y + B.h);
      if ((dir === "down" ? bcy <= acy : bcy >= acy)) continue;
      side = Math.max(A.x, B.x) - Math.min(A.x + A.w, B.x + B.w) > 0 ? Math.abs(bcx - acx) : 0;
    }
    const s = Math.max(0, main) + side * 3;
    if (!best || s < best.s) best = { k: itemKey(it), s };
  }
  return best ? best.k : null;
}
