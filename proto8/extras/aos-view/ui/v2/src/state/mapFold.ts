// The map's folds the user chose (11-15: "地圖那邊我希望可以折疊"), per browser like the sizes: localStorage under a
// neutral key, every read and write in try/catch (a private window = this session only). The rules are pure in
// model/layoutMap.ts (userFolded / flipFold / setAllFolds / parseFolds).
import { createStore } from "./store.ts";
import { flipFold, NO_FOLDS, parseFolds, setAllFolds, type FoldMode, type Folds } from "../model/layoutMap.ts";

const KEY = "page.mapFold";                           // neutral: the page will be renamed (11-15)

function load(): Folds {
  try { return parseFolds(localStorage.getItem(KEY)); } catch { return { ...NO_FOLDS, ids: {} }; }
}
export const mapFolds = createStore<{ f: Folds }>({ f: typeof window === "undefined" ? { ...NO_FOLDS, ids: {} } : load() });

function save(f: Folds): void {
  mapFolds.set({ f });
  try { localStorage.setItem(KEY, JSON.stringify(f)); } catch { /* private window etc. */ }
}
/** flip one room from what the map shows now */
export const toggleFold = (id: string, shownFolded: boolean) => save(flipFold(mapFolds.get().f, id, shownFolded));
/** 全部折疊 / 全部展開 / back to the automatic steps (null) */
export const foldAll = (m: FoldMode | null) => save(setAllFolds(m));
