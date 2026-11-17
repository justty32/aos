// Tree helpers (pure). A department = a node with members (children). The company = the roots that are agents,
// plus one "machine room" cell holding the procs and outside services (02c §11: drawn as one department cell).
import { belowOf, roomOf, type Below } from "./lights.ts";
import type { Light, Node, Tree } from "../api/types.ts";

export const MACHINE = "_machine";
export const LIGHT_ORDER: Record<Light, number> = { red: 0, blue: 1, yellow: 2, green: 3, gray: 4 };

export function isDept(n: Node | undefined): boolean {
  return !!n && n.children.length > 0;
}

/** ids from the top down to id (id included). */
export function chainOf(t: Tree | null, id: string | null): string[] {
  if (!t || !id) return [];
  if (id === MACHINE) return [MACHINE];
  const out: string[] = [];
  let cur: string | null = id;
  const seen = new Set<string>();
  while (cur && t.nodes[cur] && !seen.has(cur)) {
    seen.add(cur);
    out.unshift(cur);
    cur = t.nodes[cur].parent_by === "aide" ? null : t.nodes[cur].parent;
  }
  if (out.length && t.nodes[out[0]] && t.nodes[out[0]].kind !== "agent") out.unshift(MACHINE);
  return out;
}

export function machineIds(t: Tree): string[] {
  return t.roots.filter((r) => t.nodes[r] && t.nodes[r].kind !== "agent");
}

/** the one top department when the company has exactly one (then the company view opens it: one card is a wasted level). */
export function soleRoot(t: Tree | null): string | null {
  if (!t) return null;
  const top = t.roots.filter((r) => t.nodes[r] && t.nodes[r].kind === "agent");
  return top.length === 1 && isDept(t.nodes[top[0]]) ? top[0] : null;
}

/** what the wall shows when standing in focus: the lead desk first (02c §3.3), then members. */
export function membersOf(t: Tree | null, focus: string | null): string[] {
  if (!t) return [];
  if (focus === MACHINE) return machineIds(t);
  const m = machineIds(t).length ? [MACHINE] : [];
  if (!focus || !t.nodes[focus]) {
    const one = soleRoot(t);
    if (one) return [one, ...t.nodes[one].children, ...m];
    const top = t.roots.filter((r) => t.nodes[r] && t.nodes[r].kind === "agent");
    return [...top, ...m];
  }
  return [focus, ...t.nodes[focus].children];
}

/** the department whose lead desk is first on the wall when standing in focus (null = none). */
export function leadOf(t: Tree | null, focus: string | null): string | null {
  if (focus === MACHINE) return null;
  return focus || soleRoot(t);
}

/** where to stand to see id on the wall: its department (parent), or the company. */
export function standFor(t: Tree | null, id: string): string | null {
  if (!t) return null;
  if (id === MACHINE) return null;
  const n = t.nodes[id];
  if (!n) return null;
  if (n.kind !== "agent" && !n.parent) return MACHINE;
  return n.parent && n.parent === soleRoot(t) ? null : n.parent;
}

export function machineRollup(t: Tree): { worst: Light; counts: { red: number; yellow: number; blue: number }; nodes: number } {
  const ids = machineIds(t);
  let worst: Light = "gray";
  const counts = { red: 0, yellow: 0, blue: 0 };
  for (const i of ids) {
    const r = t.nodes[i].rollup;
    if (LIGHT_ORDER[r.worst] < LIGHT_ORDER[worst]) worst = r.worst;
    if (r.counts) { counts.red += r.counts.red; counts.yellow += r.counts.yellow; counts.blue += r.counts.blue; }
  }
  return { worst, counts, nodes: ids.length };
}

/** every node id under id (not id itself), aides excluded. */
export function descendants(t: Tree, id: string): string[] {
  const out: string[] = [];
  const walk = (k: string) => { for (const c of t.nodes[k]?.children || []) { out.push(c); walk(c); } };
  walk(id);
  return out;
}

export function displayName(id: string): string {
  return id === MACHINE ? "機房" : id;
}

// ---- the left tree (02f §2; P2): rows of what is visible, pure so node --test can check it ----

export interface Badges { ask: number; red: number; reply: number }
export interface TreeRow {
  id: string;            // a node id, or MACHINE
  depth: number;
  dept: boolean;         // has members (an arrow)
  open: boolean;
  name: string;          // shown name: the parent's prefix cut to "·" (02e §3.1)
  light: Light;          // always the node itself; the machine room has no own dot
  below: Below;
  badges: Badges;        // closed department = summed below; otherwise its own
  members: number;       // a department's head count (rollup.nodes); 0 for a person
}

/** "repo-aos-sol-7" under "repo-aos" shows as "·sol-7"; the top level keeps the full name. */
export function shortName(id: string, parent: string | null): string {
  if (id === MACHINE) return "機房";
  return parent && id.startsWith(parent + "-") && id.length > parent.length + 1 ? "·" + id.slice(parent.length + 1) : id;
}

/** the departments open by default: the sole top department (else one closed row is all you see). */
export function defaultOpen(t: Tree | null): string[] {
  const one = soleRoot(t);
  return one ? [one] : [];
}

/** order inside a department: sub-departments first, then people (02f §2.2), each in the tree's own order. */
function kidsOf(t: Tree, id: string): string[] {
  if (id === MACHINE) return machineIds(t);
  const c = t.nodes[id]?.children || [];
  return [...c.filter((k) => isDept(t.nodes[k])), ...c.filter((k) => !isDept(t.nodes[k]))];
}

/** top level: departments, then the loners, then one "machine room" row. */
export function topRows(t: Tree): string[] {
  const top = t.roots.filter((r) => t.nodes[r] && t.nodes[r].kind === "agent");
  const m = machineIds(t).length ? [MACHINE] : [];
  return [...top.filter((r) => isDept(t.nodes[r])), ...top.filter((r) => !isDept(t.nodes[r])), ...m];
}

export function treeRows(t: Tree | null, open: Set<string>, replies: Record<string, number> = {}): TreeRow[] {
  if (!t) return [];
  const own = (id: string): Badges => {
    const n = t.nodes[id];
    return { ask: n?.asks || 0, red: n?.light === "red" ? 1 : 0, reply: replies[id] || 0 };
  };
  const sum = (id: string): Badges => {
    const ids = id === MACHINE ? [...machineIds(t), ...machineIds(t).flatMap((m) => descendants(t, m))] : [id, ...descendants(t, id)];
    const b = { ask: 0, red: 0, reply: 0 };
    for (const k of ids) { const o = own(k); b.ask += o.ask; b.red += o.red; b.reply += o.reply; }
    return b;
  };
  const out: TreeRow[] = [];
  const walk = (id: string, depth: number, parent: string | null) => {
    const n = t.nodes[id];
    if (id !== MACHINE && !n) return;
    const dept = id === MACHINE || isDept(n);
    const isOpen = dept && open.has(id);
    out.push({
      id, depth, dept, open: isOpen, name: shortName(id, parent),
      light: id === MACHINE ? "gray" : n.light,
      below: id === MACHINE ? roomOf({ rollup: machineRollup(t) }) : belowOf(n),
      badges: dept && !isOpen ? sum(id) : id === MACHINE ? { ask: 0, red: 0, reply: 0 } : own(id),
      members: id === MACHINE ? machineIds(t).length : dept ? n.rollup.nodes : 0,
    });
    if (isOpen) for (const k of kidsOf(t, id)) walk(k, depth + 1, id === MACHINE ? null : id);
  };
  for (const r of topRows(t)) walk(r, 0, null);
  return out;
}

/** the departments to open so id's row is visible (its chain above it; the machine room for procs). */
export function openFor(t: Tree | null, id: string): string[] {
  const chain = chainOf(t, id);
  return chain.slice(0, -1);
}

/** Department ids under a node, including that node when it is itself a department. */
export function deptsUnder(t: Tree, id: string): string[] {
  return [id, ...descendants(t, id)].filter((k) => isDept(t.nodes[k]));
}
