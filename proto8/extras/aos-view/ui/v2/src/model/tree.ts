// Tree helpers (pure). A department = a node with members (children). The company = the roots that are agents,
// plus one "machine room" cell holding the procs and outside services (02c §11: drawn as one department cell).
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
