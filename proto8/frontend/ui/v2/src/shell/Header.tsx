// The header bar: data freshness, the counters that filter the to-do list, breadcrumb, and font size buttons.
import { useEffect } from "react";
import { ui, type Filter } from "../state/app.ts";
import { useData, useInbox, useNow, useUi } from "../state/hooks.ts";
import { goTo, setView } from "../state/nav.ts";
import { chainOf, displayName, soleRoot } from "../model/tree.ts";
import { hhmm } from "../model/time.ts";
import { listDrafts } from "../model/drafts.ts";
import { useStore } from "../state/store.ts";
import { FONT_DEFAULT, FONT_STEPS, fontBigger, fontSmaller, setSizes, sizes } from "../state/sizes.ts";

const STALE_S = 35;   // a collector round is poll_s (20) + its own time; 35 s without a new one = the data stopped

function toggle(f: Filter) {
  const on = ui.get().filter === f ? null : f;
  ui.set({ filter: on, inboxTab: "todo" });
  if (on) setView("todo");          // a header number opens the center to-do list with only that group (02f §1.2)
}

export function Freshness() {
  const pulse = useData((s) => s.pulse);
  const okAt = useData((s) => s.pulseOkAt);
  const err = useData((s) => s.pulseError);
  const treeErr = useData((s) => s.treeError);
  const now = useNow();
  const clock = useData((s) => s.clock);
  const tickAt = pulse?.tick.at ?? null;
  if (err && (!okAt || clock - okAt > 12)) {
    return <span className="text-red-400" title={err}>● 連不上後端，畫面停在 {okAt ? hhmm(okAt) : "--:--"}</span>;
  }
  if (!tickAt) return <span className="text-slate-400">● 等第一次採樣…</span>;
  const age = Math.max(0, Math.round(now - tickAt));
  if (age > STALE_S || pulse?.tick.ok === false || treeErr) {
    const why = pulse?.tick.error || treeErr || `採樣 ${age} 秒沒更新`;
    return <span className="text-amber-300" title={why}>● 資料停在 {hhmm(tickAt)}（{why}）</span>;
  }
  return <span className="text-emerald-400" title={`後端每一輪採樣花 ${pulse?.tick.took_ms ?? "?"} ms`}>● {age < 5 ? "剛剛" : `${age} 秒前`}</span>;
}

export function Header() {
  const tree = useData((s) => s.tree);
  const board = useData((s) => s.board);
  const focus = useUi((s) => s.route.focus);
  const filter = useUi((s) => s.filter);
  const { counts } = useInbox();
  useUi((s) => s.flash);           // re-read drafts after a send
  const drafts = listDrafts(localStorage).length;
  const one = soleRoot(tree);
  const chain = chainOf(tree, focus).filter((id) => id !== one);   // the company view already is the sole top department

  useEffect(() => {
    const n = counts.ask + counts.red;
    document.title = n ? `(${n}) 全景` : "全景";
  }, [counts.ask, counts.red]);

  const btn = (f: Filter, label: string, n: number, color: string, key: string) => (
    <button onClick={() => toggle(f)} title={`只看這一種（Alt+${key}）`}
      className={`rounded px-2 py-0.5 text-sm ${filter === f ? "bg-slate-200 text-slate-900" : n ? color : "bg-slate-800 text-slate-500"}`}>
      {label} <b>{n}</b>
    </button>
  );
  const v1 = `http://${location.hostname}:8767/`;

  return (
    <header className="flex h-11 shrink-0 items-center gap-3 border-b border-slate-800 bg-slate-900 px-3">
      <nav className="flex min-w-0 items-center gap-1 text-sm" aria-label="所在位置">
        <button className="font-bold text-slate-100 hover:underline" onClick={() => goTo(null)}>全景</button>
        {chain.map((id) => (
          <span key={id} className="flex min-w-0 items-center gap-1">
            <span className="text-slate-500">›</span>
            <button className="truncate hover:underline" onClick={() => goTo(id)}>{displayName(id)}</button>
          </span>
        ))}
      </nav>
      <div className="flex items-center gap-1">
        {btn("ask", "🔵 要決定", counts.ask, "bg-sky-900 text-sky-100", "1")}
        {btn("red", "🔴 出事", counts.red, "bg-red-900 text-red-100", "2")}
        {btn("yellow", "🟡 留意", counts.yellow, "bg-amber-900 text-amber-100", "3")}
        {btn("reply", "✉ 新回覆", counts.reply, "bg-indigo-900 text-indigo-100", "4")}
      </div>
      <div className="ml-auto flex items-center gap-3 text-sm">
        <button className="rounded bg-slate-800 px-2 py-0.5 text-slate-300 hover:bg-slate-700" onClick={() => ui.set({ searchOpen: true, searchText: "" })}>
          🔍 找人 <kbd className="text-xs text-slate-500">Ctrl+K</kbd>
        </button>
        <button className="rounded bg-slate-800 px-2 py-0.5 text-slate-300" onClick={() => ui.set({ panelOpen: true })}>指令 <kbd className="text-xs text-slate-500">Ctrl+/</kbd></button>
        {drafts > 0 && (
          <button className="text-slate-300 hover:underline" onClick={() => ui.set({ draftsOpen: true })}>草稿 {drafts}</button>
        )}
        <button className={`max-w-64 truncate ${board ? "text-amber-200" : "text-slate-500"}`} onClick={() => ui.set({ boardOpen: true })}
          title={board ? board.text : "留一句話給 agent：睡覺、出門、開會"}>
          📌 {board ? `${board.text}${board.back ? `，${board.back} 回` : ""}` : "我的公告"}
        </button>
        <FontSize />
        <Freshness />
        <a className="text-slate-500 hover:text-slate-300" href={v1} title="v1 清單版（8767，已凍結）">舊版</a>
      </div>
    </header>
  );
}

/** A− / A＋: the whole page's text size (11-15 "字體大小希望可以調"); not Ctrl+= / Ctrl+-, those are the browser's zoom */
function FontSize() {
  const step = useStore(sizes, (s) => s.font);
  const b = "h-7 min-w-7 rounded px-1.5 text-slate-300 hover:bg-slate-800 disabled:opacity-30";
  return (
    <span className="flex items-center" role="group" aria-label="字級">
      <button className={b} onClick={fontSmaller} disabled={step <= 0} title="字小一點" aria-label="字小一點">A−</button>
      <button className="min-w-8 text-center text-xs text-slate-400 hover:text-slate-200" onClick={() => setSizes({ font: FONT_DEFAULT })}
        title="字級（點一下回預設）" data-font-px={FONT_STEPS[step]}>{FONT_STEPS[step]}</button>
      <button className={b} onClick={fontBigger} disabled={step >= FONT_STEPS.length - 1} title="字大一點" aria-label="字大一點">A＋</button>
    </span>
  );
}
