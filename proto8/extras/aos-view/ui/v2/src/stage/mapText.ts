// Canvas measurements and middle-ellipsis names used by map pieces.
import { PLATE } from "../model/layoutMap.ts";

export const TEXT_W = PLATE.w - 26;           // plate minus the dot and padding

// measured once per name after the fonts are in (02e §3.1: measure, do not guess); cut in the middle with "…"
export const widths = new Map<string, number>();
let ctx: CanvasRenderingContext2D | null = null;
export function textW(s: string, font = 13): number {
  const key = `${font}:${s}`;
  let w = widths.get(key);
  if (w == null) {
    if (!ctx) ctx = document.createElement("canvas").getContext("2d");
    if (ctx) ctx.font = `${font}px ui-sans-serif, system-ui, sans-serif`;
    w = ctx ? ctx.measureText(s).width : s.length * font * 7 / 13;
    widths.set(key, w);
  }
  return w;
}
export function fitName(s: string, max = TEXT_W, font = 13): string {
  if (textW(s, font) <= max) return s;
  let a = Math.ceil(s.length / 2), b = Math.floor(s.length / 2);
  while (a > 1) {
    const t = s.slice(0, a) + "…" + s.slice(s.length - b);
    if (textW(t, font) <= max) return t;
    if (a >= b) a--; else b--;
  }
  return s.slice(0, 1) + "…";
}

