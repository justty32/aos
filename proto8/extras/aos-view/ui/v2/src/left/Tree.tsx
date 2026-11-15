// The left department tree (02f §2, q9 a, q10 a): NERDTree-like layout without the TUI look. Rows of 28 px, 14 px per
// level, arrow / light / short name / head count / up to three badges. Closed departments show the summed badges and
// the worst light. Clicks and keys as in 02f §2.3–2.4; the selection's departments open and its row scrolls into view.
import { useEffect, useMemo, useRef } from "react";
import { useData, useInbox, useUi } from "../state/hooks.ts";
import { caretToComposer, enter, goTo, jump, select } from "../state/nav.ts";
import { setRight, setTreeOpen, toggleDept, treeOpenSet } from "../state/layout.ts";
import { bind } from "../input/keys.ts";
import { Dot } from "../shell/bits.tsx";
import { MACHINE, openFor, treeRows, type TreeRow } from "../model/tree.ts";
import { ui } from "../state/app.ts";

const badge = (n: number) => (n > 99 ? "99+" : String(n));

function Badges({ r }: { r: TreeRow }) {
  const b = r.badges;
  return (
    <span className="ml-auto flex shrink-0 items-center gap-1 text-[11px]">
      {b.ask > 0 && <span className="min-w-8 rounded bg-sky-900 px-1 text-center text-sky-100" title="要你決定">🔵{badge(b.ask)}</span>}
      {b.red > 0 && <span className="min-w-8 rounded bg-red-900 px-1 text-center text-red-100" title="出事">🔴{badge(b.red)}</span>}
      {b.reply > 0 && <span className="min-w-8 rounded bg-indigo-900 px-1 text-center text-indigo-100" title="新回覆">✉{badge(b.reply)}</span>}
    </span>
  );
}

/** what a click on a row does (02f §2.3): the center follows, unless it is busy with the to-do list or an answer. */
export function pickRow(r: TreeRow) {
  const route = ui.get().route;
  const busyCenter = route.view === "todo" || !!route.ask;
  if (r.id === MACHINE) { if (!busyCenter) enter(MACHINE); return; }
  if (busyCenter) { select(r.id); return; }
  if (r.dept) enter(r.id); else jump(r.id, false);
}

export function Tree() {
  const tree = useData((s) => s.tree);
  const prefs = useData((s) => s.prefs);
  const sel = useUi((s) => s.route.sel);
  const focus = useUi((s) => s.route.focus);
  const { todo } = useInbox();
  const open = useMemo(() => treeOpenSet(prefs), [prefs, tree]);
  const replies = useMemo(() => {
    const m: Record<string, number> = {};
    for (const t of todo) if (t.kind === "reply" && t.node) m[t.node] = (m[t.node] || 0) + 1;
    return m;
  }, [todo]);
  const rows = useMemo(() => treeRows(tree, open, replies), [tree, open, replies]);
  const box = useRef<HTMLDivElement>(null);
  const cur = sel || (focus === MACHINE ? MACHINE : null);

  // the selection is always visible: open the departments above it (kept as the user's own), then scroll to it
  useEffect(() => {
    if (!tree || !sel) return;
    const need = openFor(tree, sel).filter((d) => !open.has(d));
    if (need.length) { setTreeOpen([...open, ...need]); return; }
    box.current?.querySelector(`[data-row="${CSS.escape(sel)}"]`)?.scrollIntoView({ block: "nearest" });
  }, [sel, tree, open]);

  useEffect(() => {
    const at = () => rows.findIndex((r) => r.id === cur);
    const move = (d: number) => {
      if (!rows.length) return;
      const i = at();
      pickRow(rows[Math.min(rows.length - 1, Math.max(0, i < 0 ? 0 : i + d))]);
    };
    const right = () => {
      const i = at(); const r = rows[i];
      if (!r) return move(1);
      if (r.dept && !r.open) toggleDept(r.id);
      else if (r.dept) { const nx = rows[i + 1]; if (nx && nx.depth > r.depth) pickRow(nx); }
      else { setRight(true); caretToComposer(); }
    };
    const left = () => {
      const i = at(); const r = rows[i];
      if (!r) return;
      if (r.dept && r.open) { toggleDept(r.id); return; }
      for (let k = i - 1; k >= 0; k--) if (rows[k].depth < r.depth) { pickRow(rows[k]); return; }
    };
    const ent = () => {
      const r = rows[at()];
      if (!r) return;
      if (r.dept) toggleDept(r.id); else { setRight(true); caretToComposer(); }
    };
    return bind([
      { key: "j", zone: "tree", run: () => move(1) }, { key: "ArrowDown", zone: "tree", run: () => move(1) },
      { key: "k", zone: "tree", run: () => move(-1) }, { key: "ArrowUp", zone: "tree", run: () => move(-1) },
      { key: "l", zone: "tree", run: right }, { key: "ArrowRight", zone: "tree", run: right },
      { key: "h", zone: "tree", run: left }, { key: "ArrowLeft", zone: "tree", run: left },
      { key: "Enter", zone: "tree", run: ent },
    ]);
  }, [rows, cur]);

  if (!tree) return <div className="min-h-0 flex-1 p-2 text-sm text-slate-500">讀取中…</div>;
  return (
    <div ref={box} className="min-h-0 flex-1 overflow-y-auto px-1.5 py-1" tabIndex={0} role="tree" aria-label="部門樹">
      {rows.map((r) => {
        const on = r.id === cur;
        return (
          <div key={r.id} data-row={r.id} role="treeitem" aria-expanded={r.dept ? r.open : undefined} aria-selected={on}
            onClick={() => pickRow(r)} onDoubleClick={() => r.dept && toggleDept(r.id)}
            title={r.id}
            className={`flex h-7 cursor-default select-none items-center gap-1.5 rounded pr-1 text-sm
              ${on ? "border-l-[3px] border-sky-400 bg-slate-700/80" : "border-l-[3px] border-transparent hover:bg-slate-800"}`}
            style={{ paddingLeft: 2 + r.depth * 14 }}>
            {r.dept
              ? <button className="flex h-7 w-4 shrink-0 items-center justify-center text-slate-400 hover:text-slate-100" aria-label={r.open ? "收起" : "打開"}
                  onClick={(e) => { e.stopPropagation(); toggleDept(r.id); }}>{r.open ? "▾" : "▸"}</button>
              : <span className="w-4 shrink-0" />}
            <Dot light={r.light} />
            <span className={`min-w-0 truncate ${r.dept ? "font-semibold" : ""}`}>{r.name}</span>
            {r.dept && <span className="shrink-0 text-xs text-slate-500">{r.members}</span>}
            <Badges r={r} />
          </div>
        );
      })}
    </div>
  );
}

/** the fixed row on top of the left column: 全公司 N (= company view, nothing selected), ⊟ (close all), « (hide). */
export function TreeHead({ onHide }: { onHide: () => void }) {
  const tree = useData((s) => s.tree);
  const n = tree ? Object.values(tree.nodes).filter((x) => x.kind === "agent").length : 0;
  return (
    <div className="flex h-9 shrink-0 items-center gap-1 border-b border-slate-800 px-2 text-sm">
      <button className="truncate font-semibold hover:underline" onClick={() => goTo(null)} title="回全公司、不選人">全公司 <span className="text-slate-400">{n}</span></button>
      <button className="ml-auto rounded px-1.5 text-slate-400 hover:bg-slate-800 hover:text-slate-100" title="全部收起" onClick={() => setTreeOpen([])}>⊟</button>
      <button className="rounded px-1.5 text-slate-400 hover:bg-slate-800 hover:text-slate-100" title="收起左欄（[）" onClick={onHide}>«</button>
    </div>
  );
}
