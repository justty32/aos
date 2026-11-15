// The two sides open / closed and the tree's open departments (02f §4, q6b a): only the user changes them, by button
// or [ ]; kept in prefs (backend ui-state, this machine) so a reload or the next day looks the same.
import { data, type Prefs } from "./app.ts";
import { savePrefs } from "../api/poll.ts";
import { defaultOpen } from "../model/tree.ts";

export const leftOpen = (p: Prefs): boolean => p.left_open !== false;
export const rightOpen = (p: Prefs): boolean => p.right_open !== false;

export function toggleLeft(): void {
  const p = data.get().prefs;
  savePrefs({ ...p, left_open: !leftOpen(p) });
}
export function setRight(open: boolean): void {
  const p = data.get().prefs;
  if (rightOpen(p) !== open) savePrefs({ ...p, right_open: open });
}
export function toggleRight(): void { setRight(!rightOpen(data.get().prefs)); }

export function treeOpenSet(p: Prefs): Set<string> {
  return new Set(p.tree_open ?? defaultOpen(data.get().tree));
}
export function setTreeOpen(ids: Iterable<string>): void {
  const p = data.get().prefs;
  savePrefs({ ...p, tree_open: [...new Set(ids)].sort() });
}
export function toggleDept(id: string): void {
  const s = treeOpenSet(data.get().prefs);
  if (s.has(id)) s.delete(id); else s.add(id);
  setTreeOpen(s);
}
