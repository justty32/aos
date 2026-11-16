// Persist wall-card detail settings per browser while tolerating unavailable localStorage.
import { createStore } from "./store.ts";
import { data } from "./app.ts";
import { DEFAULT, parseDetail, prune, setAll, setOne, type Level, type WallDetail } from "../model/wallDetail.ts";

const KEY = "page.wallDetail";
function load(): WallDetail {
  try { return parseDetail(localStorage.getItem(KEY)); } catch { return { ...DEFAULT, ids: {} }; }
}
export const wallDetail = createStore<{ d: WallDetail }>({ d: typeof window === "undefined" ? { ...DEFAULT, ids: {} } : load() });

function save(d: WallDetail): void {
  const tree = data.get().tree;
  const next = tree ? prune(d, (id) => id === "_machine" || !!tree.nodes[id]) : d;
  wallDetail.set({ d: next });
  try { localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* private window etc. */ }
}
export const setWallAll = (level: Level) => save(setAll(wallDetail.get().d, level));
export const setWallOne = (id: string, level: Level) => save(setOne(wallDetail.get().d, id, level));
