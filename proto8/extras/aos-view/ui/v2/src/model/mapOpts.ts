// Map display options parse persisted values and determine plate dimensions.
export interface MapOpts { w: "std" | "wide" | "xwide" | "fit"; name: "short" | "full"; over: "cut" | "wrap"; font: "s" | "m" | "l" }
export const DEFAULT_OPTS: MapOpts = { w: "std", name: "short", over: "cut", font: "m" };
export const FONT_PX = { s: 12, m: 13, l: 15 };

export function parseOpts(raw: string | null): MapOpts {
  try {
    const j = raw ? JSON.parse(raw) : null;
    if (!j || typeof j !== "object") return { ...DEFAULT_OPTS };
    return {
      w: ["std", "wide", "xwide", "fit"].includes(j.w) ? j.w : DEFAULT_OPTS.w,
      name: ["short", "full"].includes(j.name) ? j.name : DEFAULT_OPTS.name,
      over: ["cut", "wrap"].includes(j.over) ? j.over : DEFAULT_OPTS.over,
      font: ["s", "m", "l"].includes(j.font) ? j.font : DEFAULT_OPTS.font,
    };
  } catch { return { ...DEFAULT_OPTS }; }
}

export function plateOf(opts: MapOpts, fitW: number): { w: number; h: number } {
  const w = opts.w === "fit" ? Math.max(116, Math.min(280, fitW)) : { std: 116, wide: 160, xwide: 220 }[opts.w];
  return { w, h: opts.over === "wrap" ? 44 : 28 };
}
