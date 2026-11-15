// The address bar holds where you are (02c §3.1): #/<dept chain>?sel=<id>&tab=<now|thread|history>&view=<wall|map>&ask=<letter>
// focus = the department you stand in (last of the chain; empty = the company). Pure functions: tested by node --test.

export type Tab = "now" | "thread" | "history";
export interface Route { focus: string | null; sel: string | null; tab: Tab; view: "wall" | "map"; ask: string | null }

const TABS: Tab[] = ["now", "thread", "history"];
const ID = /^(?:[A-Za-z0-9][A-Za-z0-9_.-]{0,79}|_machine)$/;  // _machine = the machine room cell

export function parseHash(h: string): Route {
  const s = h.replace(/^#/, "");
  const [path, query = ""] = s.split("?", 2);
  const chain = path.split("/").filter((x) => ID.test(x));
  const q = new URLSearchParams(query);
  const sel = q.get("sel");
  const tab = q.get("tab") as Tab;
  const ask = q.get("ask");
  return {
    focus: chain.length ? chain[chain.length - 1] : null,
    sel: sel && ID.test(sel) ? sel : null,
    tab: TABS.includes(tab) ? tab : "now",
    view: q.get("view") === "map" ? "map" : "wall",
    ask: ask && /^[A-Za-z0-9._:-]{1,120}$/.test(ask) ? ask : null,
  };
}

/** chain = the ids from the top department down to focus (from the tree's parents). */
export function toHash(r: Route, chain: string[]): string {
  const q = new URLSearchParams();
  if (r.sel) q.set("sel", r.sel);
  if (r.tab !== "now") q.set("tab", r.tab);
  if (r.view !== "wall") q.set("view", r.view);
  if (r.ask) q.set("ask", r.ask);
  const qs = q.toString();
  return "#/" + chain.join("/") + (qs ? "?" + qs : "");
}
