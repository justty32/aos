// Map options persist per browser and remain usable when storage is unavailable.
import { createStore } from "./store.ts";
import { DEFAULT_OPTS, parseOpts, type MapOpts } from "../model/mapOpts.ts";
const KEY = "page.mapOpts";
function load(): MapOpts {
  try { return parseOpts(localStorage.getItem(KEY)); } catch { return { ...DEFAULT_OPTS }; }
}
export const mapOpts = createStore<{ opts: MapOpts }>({ opts: typeof window === "undefined" ? { ...DEFAULT_OPTS } : load() });
export function setMapOpts(p: Partial<MapOpts>): void {
  const opts = { ...mapOpts.get().opts, ...p };
  mapOpts.set({ opts });
  try { localStorage.setItem(KEY, JSON.stringify(opts)); } catch { /* private window etc. */ }
}
