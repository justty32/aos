// Pure selection helpers toggle agents, select ordered ranges, and hit-test map rectangles.
import type { MapItem } from "./layoutMap.ts";
export interface Rect { x: number; y: number; w: number; h: number }
export function bandRect(x1: number, y1: number, x2: number, y2: number, left: number, top: number): Rect {
  return { x: Math.min(x1, x2) - left, y: Math.min(y1, y2) - top, w: Math.abs(x2 - x1), h: Math.abs(y2 - y1) };
}
export function toggle(list: string[], id: string): string[] { return list.includes(id) ? list.filter((x) => x !== id) : [...list, id]; }
export function range(order: string[], anchor: string | null, id: string): string[] {
  const a = anchor ? order.indexOf(anchor) : -1, b = order.indexOf(id);
  return a < 0 || b < 0 ? [id] : order.slice(Math.min(a, b), Math.max(a, b) + 1);
}
export function hits(items: MapItem[], rect: Rect): string[] {
  return [...new Set(items.filter((it) => (it.kind === "plate" || it.kind === "dot") && it.x <= rect.x + rect.w && it.x + it.w >= rect.x && it.y <= rect.y + rect.h && it.y + it.h >= rect.y).map((it) => it.id))];
}
export function norm(list: string[]): string[] {
  const unique = [...new Set(list)];
  return unique.length >= 2 ? unique : [];
}
