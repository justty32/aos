// The middle column (02f §1.2, the user's note "地圖也要可以折疊，或是tab"): tabs 部門牆 | 地圖 | 待辦.
// The wall shows one level at a time, the lead desk first (02c §3.3). The tree moved to the left column (02f §2).
import { useEffect, useMemo, useRef } from "react";
import { useData, useInbox, useNow, useUi } from "../state/hooks.ts";
import { enter, openAsk, select, setView, up } from "../state/nav.ts";
import { bind } from "../input/keys.ts";
import { useStore } from "../state/store.ts";
import { wallDetail, setWallAll, setWallOne } from "../state/wallDetail.ts";
import { cycle, levelOf, step } from "../model/wallDetail.ts";
import { clearMulti } from "../state/multi.ts";
import { ui } from "../state/app.ts";
import { Card } from "./Card.tsx";
import { MACHINE, membersOf, displayName, machineIds, descendants, leadOf } from "../model/tree.ts";
import { rightOpen, setRight } from "../state/layout.ts";
import { Inbox } from "../inbox/Inbox.tsx";
import { MapView } from "./MapView.tsx";
import { Decision } from "../inbox/Decision.tsx";

export function Stage() {
  const tree = useData((s) => s.tree);
  const treeErr = useData((s) => s.treeError);
  const loaded = useData((s) => s.loaded);
  const route = useUi((s) => s.route);
  const filter = useUi((s) => s.filter);
  const { todo } = useInbox();
  const now = useNow();
  const prefs = useData((s) => s.prefs);
  const multi = useUi((s) => s.multi);
  const detail = useStore(wallDetail, (s) => s.d);
  const wallRef = useRef<HTMLDivElement>(null);
  const ids = useMemo(() => membersOf(tree, route.focus), [tree, route.focus]);
  const lead = leadOf(tree, route.focus);

  // which cards light up for a header filter (the rest dims)
  const hot = useMemo(() => {
    if (!filter || !tree) return null;
    const want = new Set<string>();
    const mark = (id: string) => { want.add(id); };
    if (filter === "reply") todo.filter((t) => t.kind === "reply" || t.kind === "wait").forEach((t) => t.node && mark(t.node));
    if (filter === "ask") todo.filter((t) => t.kind === "ask").forEach((t) => t.node && mark(t.node));
    for (const n of Object.values(tree.nodes)) {
      if (filter === "red" && (n.light === "red" || n.team_light?.light === "red")) mark(n.id);
      if (filter === "yellow" && (n.light === "yellow" || n.team_light?.light === "yellow")) mark(n.id);
    }
    const lit = (id: string): boolean => id === MACHINE ? machineIds(tree).some((m) => want.has(m) || descendants(tree, m).some((d) => want.has(d)))
      : want.has(id) || (id !== lead && descendants(tree, id).some((d) => want.has(d)));
    return lit;
  }, [filter, tree, todo, route.focus]);

  // the selection is always in sight (02d §6 #1)
  useEffect(() => {
    if (route.sel) wallRef.current?.querySelector(`[data-card="${CSS.escape(route.sel)}"]`)?.scrollIntoView({ block: "nearest" });
  }, [route.sel, ids]);

  useEffect(() => {
    const move = (d: number) => {
      if (!ids.length) return;
      const cur = ids.indexOf(route.sel || "");
      const cols = Math.max(1, Math.round((wallRef.current?.clientWidth || 600) / 240));
      const step = Math.abs(d) === 1 ? d : d > 0 ? cols : -cols;
      const nx = Math.min(ids.length - 1, Math.max(0, cur < 0 ? 0 : cur + step));
      select(ids[nx] === MACHINE ? null : ids[nx]);
    };
    const inWall = () => !!wallRef.current?.contains(document.activeElement);
    const one = (action: "step" | "fold" | "cycle") => {
      const id = route.sel;
      if (!id || !ids.includes(id)) return;
      const level = levelOf(detail, id);
      setWallOne(id, action === "fold" ? "fold" : action === "step" ? step(level) : cycle(level));
    };
    // on the map tab the map has its own arrows (MapView); the wall's are not registered then
    const wall = route.view !== "wall" || route.ask ? [] : [
      { key: "ArrowRight", zone: "stage" as const, run: () => move(1) }, { key: "l", zone: "stage" as const, run: () => move(1) },
      { key: "ArrowLeft", zone: "stage" as const, run: () => move(-1) }, { key: "h", zone: "stage" as const, run: () => move(-1) },
      { key: "ArrowDown", zone: "stage" as const, run: () => move(2) }, { key: "j", zone: "stage" as const, run: () => move(1) },
      { key: "ArrowUp", zone: "stage" as const, run: () => move(-2) }, { key: "k", zone: "stage" as const, run: () => move(-1) },
      { key: "Enter", zone: "stage" as const, run: () => { if (route.sel) enter(route.sel); } },
      { key: "Tab", zone: "stage" as const, when: inWall, run: () => one("cycle") },
      { key: "o", zone: "stage" as const, when: inWall, run: () => one("step") },
      { key: "c", zone: "stage" as const, when: inWall, run: () => one("fold") },
      { key: "shift+o", zone: "stage" as const, when: inWall, run: () => setWallAll(step(detail.all)) },
      { key: "shift+c", zone: "stage" as const, when: inWall, run: () => setWallAll("fold") },
    ];
    return bind([
      ...wall,
      ...(route.ask || route.view === "todo" ? [] : [{ key: "q", run: up }]),
      { key: "Backspace", run: () => up() },
      { key: "w", run: () => setView("wall") }, { key: "m", run: () => setView("map") }, { key: "t", run: () => setView("todo") },
      { key: "n", run: () => { if (!hot) return; const list = ids.filter(hot); if (!list.length) return;
        const i = list.indexOf(route.sel || ""); const nx = list[(i + 1) % list.length]; select(nx === MACHINE ? null : nx); } },
    ]);
  }, [ids, route.sel, route.view, route.ask, hot, detail]);

  const tabBtn = (v: "wall" | "map" | "todo", label: string, key: string, extra?: React.ReactNode) => (
    <button className={`shrink-0 whitespace-nowrap rounded px-2 py-0.5 ${route.view === v && !route.ask ? "bg-slate-700" : "text-slate-400 hover:bg-slate-800"}`}
      onClick={() => { if (route.ask) openAsk(null); setView(v); }}>
      {label}{extra} <kbd className="text-xs text-slate-500">{key}</kbd>
    </button>
  );
  const selName = route.sel && tree?.nodes[route.sel] ? route.sel : null;
  return (
    <main data-zone="stage" tabIndex={-1} className="relative flex min-h-0 flex-col bg-slate-950 focus-within:ring-1 focus-within:ring-sky-700">
      <div className="flex h-9 shrink-0 items-center gap-2 border-b border-slate-800 px-3 text-sm">
        {tabBtn("wall", "部門牆", "w")}
        {tabBtn("map", "地圖", "m")}
        {tabBtn("todo", "待辦", "t", <b className="ml-1">{todo.length}</b>)}
        {multi.length >= 2 && <button className="shrink-0 rounded bg-sky-900 px-2 text-xs" onClick={clearMulti}>已選 {multi.length} ×</button>}
        {route.ask && <span className="shrink-0 whitespace-nowrap rounded bg-sky-800 px-2 py-0.5 text-white">作答</span>}
        {route.view !== "todo" && !route.ask && <button disabled={!route.focus} className="shrink-0 whitespace-nowrap rounded px-2 py-0.5 text-slate-300 hover:bg-slate-800 disabled:opacity-40" onClick={up} title="回上一層（q 或 Backspace）">⬑ 上一層 <kbd className="text-xs text-slate-500">q</kbd></button>}
        <span className="ml-auto min-w-0 truncate text-xs text-slate-500">
          {route.ask ? "一次一題，選了跳下一題，最後總覽再送" : route.view === "todo" ? "點藍色那張就作答；點別張選中那個人" : route.focus ? `${displayName(route.focus)}：${ids.length} 格` : lead ? `公司（${lead} 底下）：${ids.length} 格` : `公司：${ids.length} 個部門`}
        </span>
        {route.view === "wall" && !route.ask && <span className="flex shrink-0 gap-1 text-xs text-slate-400">
          <button className="rounded px-1.5 py-0.5 hover:bg-slate-800" title="Shift+c" onClick={() => setWallAll("fold")}>全部折起</button>
          <button className="rounded px-1.5 py-0.5 hover:bg-slate-800" title="Shift+o" onClick={() => setWallAll(step(detail.all))}>全部詳細一點</button>
        </span>}
        <button data-help className="shrink-0 whitespace-nowrap rounded px-2 py-0.5 text-xs text-slate-400 hover:bg-slate-800" onClick={() => ui.set({ helpOpen: true })}>⌨ 操作說明 <kbd>?</kbd></button>
        {selName && !rightOpen(prefs) && (
          <button className="shrink-0 rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-200 hover:bg-slate-700" onClick={() => setRight(true)} title="打開右欄（]）">‹ {displayName(selName)}</button>
        )}
      </div>
      {route.ask ? <Decision letter={route.ask} /> : route.view === "todo" ? <Inbox /> : route.view === "map" ? <MapView /> : (
        <div ref={wallRef} onClick={(e) => { if (e.target === e.currentTarget) clearMulti(); }} className="min-h-0 flex-1 overflow-y-auto p-3" tabIndex={0}>
          {!loaded && <p className="text-slate-400">讀取中…</p>}
          {loaded && !tree && <p className="text-red-300">讀不到部門樹：{treeErr || "後端還沒有第一次採樣"}</p>}
          {tree && route.focus && route.focus !== MACHINE && !tree.nodes[route.focus] && (
            <p className="mb-3 text-amber-300">這個部門已經不在樹上了（可能收隊了）。<button className="underline" onClick={() => up()}>回上一層</button></p>
          )}
          {tree && (
            <div onClick={(e) => { if (e.target === e.currentTarget) clearMulti(); }} className="grid items-start gap-2.5" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))" }}>
              {ids.map((id, i) => (
                <Card key={id} tree={tree} id={id} lead={!!lead && i === 0 && id === lead}
                  selected={(route.sel || null) === (id === MACHINE ? "_none_" : id)} dim={!!hot && !hot(id)} now={now} order={ids.filter((id) => id !== MACHINE)} />
              ))}
            </div>
          )}
        </div>
      )}
    </main>
  );
}
