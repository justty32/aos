// Agent-only selection actions keep a primary target and an ordered multi-selection in memory.
import { MACHINE } from "../model/tree.ts";
import { data, ui } from "./app.ts";
import { select } from "./nav.ts";
import { setRight } from "./layout.ts";
import { norm, range, toggle } from "../model/multi.ts";

export function clearMulti(): void { ui.set({ multi: [] }); }
export function setMulti(ids: string[], add = false): void {
  const current = ui.get();
  const agents = [...new Set([...(add ? current.multi.length ? current.multi : current.route.sel ? [current.route.sel] : [] : []), ...ids])]
    .filter((id) => data.get().tree?.nodes[id]?.kind === "agent");
  ui.set({ multi: norm(agents) });
  if (agents.length === 1) select(agents[0]);
  else if (agents.length >= 2) {
    if (!current.route.sel || !agents.includes(current.route.sel)) select(agents[0]);
    setRight(true);
  }
}
export function pickWith(e: { shiftKey: boolean; ctrlKey: boolean; metaKey: boolean }, id: string, order: string[]): void {
  const s = ui.get();
  const modified = e.shiftKey || e.ctrlKey || e.metaKey;
  if (modified && data.get().tree?.nodes[id]?.kind !== "agent") {
    ui.set({ flash: "程序和外部服務不收話，沒有加進去" });
    return;
  }
  if (e.shiftKey) setMulti(range(order, s.anchor, id));
  else if (e.ctrlKey || e.metaKey) setMulti(toggle(s.multi.length ? s.multi : s.route.sel ? [s.route.sel] : [], id));
  else { clearMulti(); select(id === MACHINE ? null : id); }
  ui.set({ anchor: id });
}
export function dropFromMulti(id: string): void { setMulti(ui.get().multi.filter((x) => x !== id)); }
