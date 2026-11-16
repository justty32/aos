// Separate a node's own light from the warning counts below it or inside a room.
import type { Light, Node, Rollup } from "../api/types.ts";

export type Warning = "red" | "blue" | "yellow";
export interface Below { red: number; blue: number; yellow: number; worst: Warning | null }
const ORDER: Record<Light, number> = { red: 0, blue: 1, yellow: 2, green: 3, gray: 4 };

export function belowOf(n: Pick<Node, "light" | "rollup">): Below {
  const c = n.rollup.counts;
  const red = c ? Math.max(0, c.red - Number(n.light === "red")) : 0;
  const blue = c ? Math.max(0, c.blue - Number(n.light === "blue")) : 0;
  const yellow = c ? Math.max(0, c.yellow - Number(n.light === "yellow")) : 0;
  const worst = red ? "red" : blue ? "blue" : yellow ? "yellow" : null;
  const fallback = !c && ORDER[n.rollup.worst] < ORDER[n.light] && ORDER[n.rollup.worst] <= 2 ? n.rollup.worst as Warning : null;
  return { red, blue, yellow, worst: worst ?? fallback };
}

export function roomOf(n: { rollup: Pick<Rollup, "worst" | "counts"> }): Below {
  const c = n.rollup.counts;
  const red = c?.red ?? 0, blue = c?.blue ?? 0, yellow = c?.yellow ?? 0;
  const worst = red ? "red" : blue ? "blue" : yellow ? "yellow" : !c && ORDER[n.rollup.worst] <= 2 ? n.rollup.worst as Warning : null;
  return { red, blue, yellow, worst };
}
