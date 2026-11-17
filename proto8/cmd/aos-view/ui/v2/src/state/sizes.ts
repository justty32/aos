// The user's own sizes (11-15: "字體大小希望可以調。各版面大小希望也可以拉調整"): the font step and the dragged widths /
// heights. Per browser (localStorage), every read and write in try/catch; nothing stored or unreadable = the defaults.
// The page reads them as CSS variables on <html> (--left-w, --right-w, --composer-h, the root font size), so a later
// phone breakpoint only has to override variables. The clamp rules are pure (node --test).
import { createStore } from "./store.ts";

/** font steps: the body text (Tailwind text-sm = 0.875 rem) in px; the root size follows, so the whole page scales */
export const FONT_STEPS = [13, 14, 15, 16, 17, 18] as const;
export const FONT_DEFAULT = 1;                        // 14 px body = the browser's 16 px root (what the page was built at)
export const rootPx = (step: number) => FONT_STEPS[clampStep(step)] / 0.875;

export const LEFT = { min: 200, max: 480, def: 280 };
export const RIGHT = { min: 320, max: 800, def: 400 };
export const CENTER_MIN = 400;
export const STRIP = 48;                              // the closed left column
export const COMPOSER = { min: 120, def: null as number | null };   // null = as tall as its content
export const THREAD_MIN = 120;                        // the list above the composer keeps at least this

export interface Sizes { font: number; left: number; right: number; composer: number | null }
export const DEFAULTS: Sizes = { font: FONT_DEFAULT, left: LEFT.def, right: RIGHT.def, composer: COMPOSER.def };

export function clampStep(s: number): number {
  return Number.isFinite(s) ? Math.min(FONT_STEPS.length - 1, Math.max(0, Math.round(s))) : FONT_DEFAULT;
}
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

/** the left width a drag asks for, kept inside 200–480 and leaving the center at least 400 */
export function clampLeft(w: number, page: number, right: number): number {
  return Math.round(clamp(w, LEFT.min, Math.max(LEFT.min, Math.min(LEFT.max, page - right - CENTER_MIN))));
}
/** the right width (it grows to the left: drag x → page - x), inside 320–800, the center at least 400 */
export function clampRight(w: number, page: number, left: number): number {
  return Math.round(clamp(w, RIGHT.min, Math.max(RIGHT.min, Math.min(RIGHT.max, page - left - CENTER_MIN))));
}
/** the composer height inside the right column: at least 120, the thread above keeps at least 120 */
export function clampComposer(h: number, column: number): number {
  return Math.round(clamp(h, COMPOSER.min, Math.max(COMPOSER.min, column - THREAD_MIN)));
}

/** what the stored JSON says, each field checked on its own (a bad one = its default) */
export function parseSizes(raw: string | null): Sizes {
  let o: Record<string, unknown> = {};
  try { const j = raw ? JSON.parse(raw) : null; if (j && typeof j === "object") o = j as Record<string, unknown>; } catch { /* default */ }
  const num = (v: unknown, lo: number, hi: number, def: number) => (typeof v === "number" && Number.isFinite(v) ? clamp(Math.round(v), lo, hi) : def);
  return {
    font: typeof o.font === "number" ? clampStep(o.font) : FONT_DEFAULT,
    left: num(o.left, LEFT.min, LEFT.max, LEFT.def),
    right: num(o.right, RIGHT.min, RIGHT.max, RIGHT.def),
    composer: typeof o.composer === "number" && Number.isFinite(o.composer) ? Math.max(COMPOSER.min, Math.round(o.composer)) : null,
  };
}

// ---- the browser side ----
const KEY = "page.sizes";                             // a neutral key: the page will be renamed (11-15)

function load(): Sizes {
  try { return parseSizes(localStorage.getItem(KEY)); } catch { return { ...DEFAULTS }; }
}
export const sizes = createStore<Sizes>(typeof window === "undefined" ? { ...DEFAULTS } : load());

/** write the CSS variables the layout uses */
export function applySizes(s: Sizes = sizes.get()): void {
  const r = document.documentElement.style;
  r.fontSize = `${rootPx(s.font)}px`;
  r.setProperty("--left-w", `${s.left}px`);
  r.setProperty("--right-w", `${s.right}px`);
  r.setProperty("--composer-h", s.composer == null ? "auto" : `${s.composer}px`);
}

export function setSizes(p: Partial<Sizes>, persist = true): void {
  sizes.set(p);
  applySizes();
  if (persist) { try { localStorage.setItem(KEY, JSON.stringify(sizes.get())); } catch { /* private window etc.: this session only */ } }
}
export const fontBigger = () => setSizes({ font: clampStep(sizes.get().font + 1) });
export const fontSmaller = () => setSizes({ font: clampStep(sizes.get().font - 1) });
