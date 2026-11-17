// The left column (02f §1, §4): the tree on top (it scrolls), "等你處理" pinned below (3–4 signposts, the full list is
// the center 待辦 tab). Closed = a 48 px strip with » and the numbers; only the user opens or closes it (q6b a).
import { useEffect, useState } from "react";
import { ui, type Filter } from "../state/app.ts";
import { useData, useInbox } from "../state/hooks.ts";
import { setView } from "../state/nav.ts";
import { leftOpen, toggleLeft } from "../state/layout.ts";
import { pickWaiting, type WaitRow } from "../model/inbox.ts";
import { openTodo } from "../inbox/Inbox.tsx";
import { Tree, TreeHead } from "./Tree.tsx";

const ICON: Record<WaitRow["group"], string> = { ask: "🔵", red: "🔴", you: "⏳", reply: "✉", wait: "⌛" };

function useTall(): boolean {
  const [tall, setTall] = useState(() => window.innerHeight - 44 >= 700);
  useEffect(() => {
    const h = () => setTall(window.innerHeight - 44 >= 700);
    window.addEventListener("resize", h);
    return () => window.removeEventListener("resize", h);
  }, []);
  return tall;
}

/** open the center to-do list, keeping only one group (null = all) */
export function openList(f: Filter) {
  ui.set({ filter: f, inboxTab: "todo" });
  setView("todo");
}

function Waiting() {
  const { todo } = useInbox();
  const tall = useTall();
  const rows = pickWaiting(todo, tall ? 4 : 3);
  const total = todo.length;
  return (
    <div className="shrink-0 border-t border-slate-800">
      <div className="flex h-7 items-center px-2 text-xs font-semibold text-slate-400">
        等你處理 {total}
        <button className="ml-auto font-normal text-sky-300 hover:underline" onClick={() => openList(null)}>全部 ▸</button>
      </div>
      {!rows.length && <p className="px-2 pb-2 text-xs text-slate-500">沒有等你的事</p>}
      {rows.map((r) => (
        <button key={r.key} title={r.title} className="flex h-8 w-full items-center gap-1 px-2 text-left text-sm hover:bg-slate-800"
          onClick={() => openTodo(r.todo)}>
          <span className="shrink-0">{ICON[r.group]}</span><span className="truncate">{r.title}</span>
        </button>
      ))}
    </div>
  );
}

function Strip() {
  const { counts } = useInbox();
  const n = (f: Filter, icon: string, v: number, title: string) => (
    <button title={title} onClick={() => openList(f)}
      className={`w-10 rounded py-1 text-center text-xs ${v ? "bg-slate-800 text-slate-100" : "text-slate-600"}`}>{icon}<br />{v}</button>
  );
  return (
    <aside data-zone="tree" tabIndex={-1} className="flex min-h-0 flex-col items-center gap-1.5 border-r border-slate-800 bg-slate-900/60 py-1.5">
      <button className="h-7 w-10 rounded text-slate-300 hover:bg-slate-800" title="打開左欄（[）" onClick={toggleLeft}>»</button>
      {n("ask", "🔵", counts.ask, "要你決定")}
      {n("red", "🔴", counts.red, "出事")}
      {n("reply", "✉", counts.reply, "新回覆")}
      {n("yellow", "🟡", counts.yellow, "留意")}
    </aside>
  );
}

export function Left() {
  const prefs = useData((s) => s.prefs);
  if (!leftOpen(prefs)) return <Strip />;
  return (
    <aside data-zone="tree" tabIndex={-1} className="flex min-h-0 flex-col border-r border-slate-800 bg-slate-900/60 focus-within:ring-1 focus-within:ring-sky-700">
      <TreeHead onHide={toggleLeft} />
      <Tree />
      <Waiting />
    </aside>
  );
}
