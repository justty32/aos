// Moving around (02c §3.2 with 12.8 #2): click anywhere on a card = select; title / ▸ / double click / Enter = go in
// (then the department itself is selected); Backspace / breadcrumb = up. The route is mirrored in the address bar:
// a new department is a history entry (Back works), a new selection or tab only replaces the entry.
import { data, ui } from "./app.ts";
import { parseHash, toHash, type Route, type Tab } from "./route.ts";
import { chainOf, isDept, MACHINE, soleRoot, standFor } from "../model/tree.ts";

function setRoute(p: Partial<Route>, push: boolean) {
  const r = { ...ui.get().route, ...p };
  if (r.focus && r.focus === soleRoot(data.get().tree)) r.focus = null;   // the company view already opens it
  ui.set({ route: r });
  const chain = chainOf(data.get().tree, r.focus);
  const h = toHash(r, chain.length ? chain : r.focus ? [r.focus] : []);
  if (h !== location.hash) history[push ? "pushState" : "replaceState"](null, "", h);
}

export function select(id: string | null, tab?: Tab) {
  const r = ui.get().route;
  setRoute({ sel: id, tab: tab ?? (id === r.sel ? r.tab : "now") }, false);
}

export function enter(id: string) {
  const t = data.get().tree;
  if (id !== MACHINE && !isDept(t?.nodes[id])) { select(id); return; }
  setRoute({ focus: id, sel: id === MACHINE ? null : id, tab: "now" }, true);
}

export function up() {
  const r = ui.get().route;
  if (!r.focus) return;
  const t = data.get().tree;
  const parent = r.focus === MACHINE ? null : standFor(t, r.focus);
  // (standFor gives null for a child of the sole top department: up goes to the company view)
  setRoute({ focus: parent, sel: r.focus === MACHINE ? null : r.focus, tab: "now" }, true);
}

export function goTo(focus: string | null) {
  setRoute({ focus, sel: focus && focus !== MACHINE ? focus : null, tab: "now" }, true);
}

/** Ctrl+K: stand where id can be seen, select it, caret into the composer. */
export function jump(id: string, caret = true) {
  const t = data.get().tree;
  const n = t?.nodes[id];
  const focus = n && isDept(n) ? id : standFor(t, id);
  setRoute({ focus, sel: id, tab: "now" }, true);
  if (caret) ui.set({ focusComposer: ui.get().focusComposer + 1 });
}

export function setTab(tab: Tab) { setRoute({ tab }, false); }
export function setView(view: "wall" | "map") { setRoute({ view }, false); }
export function openAsk(letter: string | null) { setRoute({ ask: letter }, false); }

export function installHash(): () => void {
  const h = () => ui.set({ route: parseHash(location.hash) });
  window.addEventListener("hashchange", h);
  window.addEventListener("popstate", h);
  return () => { window.removeEventListener("hashchange", h); window.removeEventListener("popstate", h); };
}

export function caretToComposer() {
  ui.set({ focusComposer: ui.get().focusComposer + 1 });
}
