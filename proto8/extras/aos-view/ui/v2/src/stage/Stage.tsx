// The middle column: the department wall (v2.0). One level at a time; the lead desk first (02c §3.3).
// The map comes in v2.1 (from v1 map.js); the tab is there so the place in the URL is already shared.
import { useEffect, useMemo, useRef, useState } from "react";
import { useData, useInbox, useNow, useUi } from "../state/hooks.ts";
import { enter, jump, select, setView, up } from "../state/nav.ts";
import { bind, pushOverlay } from "../input/keys.ts";
import { Card } from "./Card.tsx";
import { Dot } from "../shell/bits.tsx";
import { MACHINE, membersOf, displayName, machineIds, isDept, descendants, leadOf } from "../model/tree.ts";
import type { Tree } from "../api/types.ts";

function TreePopover({ tree, onClose }: { tree: Tree; onClose: () => void }) {
  useEffect(() => pushOverlay(onClose), [onClose]);
  const row = (id: string, depth: number): React.ReactNode => {
    const n = tree.nodes[id];
    if (!n) return null;
    return (
      <div key={id}>
        <button className="flex w-full items-center gap-1.5 rounded px-1 py-0.5 text-left text-sm hover:bg-slate-700"
          style={{ paddingLeft: 4 + depth * 14 }} onClick={() => { jump(id, false); onClose(); }}>
          <Dot light={isDept(n) ? n.rollup.worst : n.light} size="sm" />{id}
          {isDept(n) && <span className="text-xs text-slate-500">{n.rollup.nodes}</span>}
        </button>
        {n.children.map((c) => row(c, depth + 1))}
      </div>
    );
  };
  return (
    <div className="absolute left-2 top-10 z-20 max-h-[70vh] w-80 overflow-y-auto rounded-lg border border-slate-600 bg-slate-900 p-2 shadow-xl">
      <div className="mb-1 flex items-center justify-between text-xs text-slate-400"><span>部門樹（點了直接跳過去）</span>
        <button onClick={onClose} className="hover:text-slate-100">關 Esc</button></div>
      {tree.roots.filter((r) => tree.nodes[r]?.kind === "agent").map((r) => row(r, 0))}
      {machineIds(tree).length > 0 && <div className="mt-1 border-t border-slate-700 pt-1 text-xs text-slate-500">機房</div>}
      {machineIds(tree).map((r) => row(r, 0))}
    </div>
  );
}

export function Stage() {
  const tree = useData((s) => s.tree);
  const treeErr = useData((s) => s.treeError);
  const loaded = useData((s) => s.loaded);
  const route = useUi((s) => s.route);
  const filter = useUi((s) => s.filter);
  const { todo } = useInbox();
  const now = useNow();
  const [treeOpen, setTreeOpen] = useState(false);
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

  useEffect(() => {
    const move = (d: number) => {
      if (!ids.length) return;
      const cur = ids.indexOf(route.sel || "");
      const cols = Math.max(1, Math.round((wallRef.current?.clientWidth || 600) / 240));
      const step = Math.abs(d) === 1 ? d : d > 0 ? cols : -cols;
      const nx = Math.min(ids.length - 1, Math.max(0, cur < 0 ? 0 : cur + step));
      select(ids[nx] === MACHINE ? null : ids[nx]);
    };
    return bind([
      { key: "ArrowRight", zone: "stage", run: () => move(1) }, { key: "l", zone: "stage", run: () => move(1) },
      { key: "ArrowLeft", zone: "stage", run: () => move(-1) }, { key: "h", zone: "stage", run: () => move(-1) },
      { key: "ArrowDown", zone: "stage", run: () => move(2) }, { key: "j", zone: "stage", run: () => move(1) },
      { key: "ArrowUp", zone: "stage", run: () => move(-2) }, { key: "k", zone: "stage", run: () => move(-1) },
      { key: "Enter", zone: "stage", run: () => route.sel && enter(route.sel) },
      { key: "Backspace", run: () => up() },
      { key: "w", run: () => setView("wall") }, { key: "m", run: () => setView("map") },
      { key: "n", run: () => { if (!hot) return; const list = ids.filter(hot); if (!list.length) return;
        const i = list.indexOf(route.sel || ""); const nx = list[(i + 1) % list.length]; select(nx === MACHINE ? null : nx); } },
    ]);
  }, [ids, route.sel, hot]);

  return (
    <main data-zone="stage" tabIndex={-1} className="relative flex min-h-0 flex-col bg-slate-950 focus-within:ring-1 focus-within:ring-sky-700">
      <div className="flex shrink-0 items-center gap-2 border-b border-slate-800 px-3 py-1.5 text-sm">
        <button className={`rounded px-2 py-0.5 ${route.view === "wall" ? "bg-slate-700" : "text-slate-400"}`} onClick={() => setView("wall")}>部門牆 <kbd className="text-xs text-slate-500">w</kbd></button>
        <button className={`rounded px-2 py-0.5 ${route.view === "map" ? "bg-slate-700" : "text-slate-400"}`} onClick={() => setView("map")}>地圖 <kbd className="text-xs text-slate-500">m</kbd></button>
        <button className="rounded px-2 py-0.5 text-slate-300 hover:bg-slate-800" onClick={() => setTreeOpen((o) => !o)}>🌳 部門樹</button>
        {route.focus && <button className="rounded px-2 py-0.5 text-slate-300 hover:bg-slate-800" onClick={up} title="Backspace">⬑ 上一層</button>}
        <span className="ml-auto text-xs text-slate-500">
          {route.focus ? `${displayName(route.focus)}：${ids.length} 格` : lead ? `公司（${lead} 底下）：${ids.length} 格` : `公司：${ids.length} 個部門`}｜點一下選，點標題、雙擊或 Enter 進去
        </span>
      </div>
      {treeOpen && tree && <TreePopover tree={tree} onClose={() => setTreeOpen(false)} />}
      <div ref={wallRef} className="min-h-0 flex-1 overflow-y-auto p-3" tabIndex={0}>
        {!loaded && <p className="text-slate-400">讀取中…</p>}
        {loaded && !tree && <p className="text-red-300">讀不到部門樹：{treeErr || "後端還沒有第一次採樣"}</p>}
        {route.view === "map" && <p className="mb-3 rounded border border-slate-700 p-3 text-sm text-slate-300">地圖排在 v2.1（從 v1 的地圖搬過來並補齊）。這一版先用部門牆；舊版 8767 的地圖還能用。</p>}
        {tree && route.focus && route.focus !== MACHINE && !tree.nodes[route.focus] && (
          <p className="mb-3 text-amber-300">這個部門已經不在樹上了（可能收隊了）。<button className="underline" onClick={() => up()}>回上一層</button></p>
        )}
        {tree && (
          <div className="grid gap-2.5" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))" }}>
            {ids.map((id, i) => (
              <Card key={id} tree={tree} id={id} lead={!!lead && i === 0 && id === lead}
                selected={(route.sel || null) === (id === MACHINE ? "_none_" : id)} dim={!!hot && !hot(id)} now={now} />
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
