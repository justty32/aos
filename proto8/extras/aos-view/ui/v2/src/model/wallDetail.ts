// Pure wall-card detail settings support per-node overrides and whole-wall defaults.
export type Level = "fold" | "simple" | "detail";
export interface WallDetail { all: Level; ids: Record<string, Level> }
export const DEFAULT: WallDetail = { all: "simple", ids: {} };
const LEVELS: Level[] = ["fold", "simple", "detail"];

export function parseDetail(raw: string | null): WallDetail {
  try {
    const value = raw ? JSON.parse(raw) : null;
    if (!value || typeof value !== "object") return { ...DEFAULT, ids: {} };
    const ids: Record<string, Level> = {};
    if (value.ids && typeof value.ids === "object" && !Array.isArray(value.ids)) {
      for (const [id, level] of Object.entries(value.ids)) if (LEVELS.includes(level as Level)) ids[id] = level as Level;
    }
    return { all: LEVELS.includes(value.all) ? value.all : DEFAULT.all, ids };
  } catch { return { ...DEFAULT, ids: {} }; }
}

export function levelOf(d: WallDetail, id: string, max: Level = "detail"): Level {
  return LEVELS[Math.min(LEVELS.indexOf(d.ids[id] ?? d.all), LEVELS.indexOf(max))];
}

export function step(level: Level, max: Level = "detail"): Level {
  return LEVELS[Math.min(LEVELS.indexOf(level) + 1, LEVELS.indexOf(max))];
}

export function cycle(level: Level, max: Level = "detail"): Level {
  return LEVELS[(LEVELS.indexOf(level) + 1) % (LEVELS.indexOf(max) + 1)];
}

export function setAll(_d: WallDetail, all: Level): WallDetail { return { all, ids: {} }; }
export function setOne(d: WallDetail, id: string, level: Level): WallDetail { return { ...d, ids: { ...d.ids, [id]: level } }; }
export function prune(d: WallDetail, alive: (id: string) => boolean): WallDetail {
  if (Object.keys(d.ids).length <= 200) return d;
  return { ...d, ids: Object.fromEntries(Object.entries(d.ids).filter(([id]) => alive(id))) };
}
