// Inspector shell, node heading, tabs, and right-column controls.
import { useEffect, useRef } from "react";
import { bind } from "../input/keys.ts";
import type { Node, Tree } from "../api/types.ts";
import { setRight } from "../state/layout.ts";
import { useData, useNow, useUi } from "../state/hooks.ts";
import { enter, jump, setTab } from "../state/nav.ts";
import type { Tab } from "../state/route.ts";
import { ReadButtons } from "./ReadButtons.tsx";
import { SlashResults } from "./SlashResults.tsx";
import { MultiPanel } from "./MultiPanel.tsx";
import { Thread } from "./Thread.tsx";
import { AgentNow } from "./AgentNow.tsx";
import { History } from "./History.tsx";
import { Overview, Plain } from "./Overview.tsx";
import { BelowMark, Dot, LIGHT_WORD } from "../shell/bits.tsx";
import { displayName, isDept } from "../model/tree.ts";
import { belowOf } from "../model/lights.ts";
import { Clamp } from "../shell/Clamp.tsx";
import { whyWord } from "../model/words.ts";

function Tabs({ tab, has }: { tab: Tab; has: Tab[] }) {
  const word: Record<Tab, string> = { now: "現在", thread: "往來", history: "做過・說過" };
  return (
    <div className="flex shrink-0 border-b border-slate-800">
      {has.map((t) => (
        <button key={t} onClick={() => setTab(t)}
          className={`flex-1 border-b-2 py-2 text-sm ${tab === t ? "border-sky-400 text-slate-100" : "border-transparent text-slate-400 hover:text-slate-200"}`}>{word[t]}</button>
      ))}
    </div>
  );
}

function Head({ n, tree, slim = false }: { n: Node; tree: Tree; slim?: boolean }) {
  const dept = isDept(n);
  return (
    <div className="shrink-0 border-b border-slate-800 py-2 pl-3 pr-8">
      <div className="flex items-center gap-2">
        <Dot light={n.light} title={`${LIGHT_WORD[n.light]}：${whyWord(n.why)}`} />
        <h2 className="truncate text-base font-semibold">{displayName(n.id)}</h2>
        <span className="text-xs text-slate-500">{n.kind === "agent" ? (dept ? "部門主管" : "員工") : n.kind === "proc" ? "程序" : "外部服務"}</span>
        <span className="ml-auto flex items-center gap-1">
          <ReadButtons n={n} />
          {dept && <button className="rounded bg-slate-800 px-2 py-0.5 text-xs hover:bg-slate-700" onClick={() => enter(n.id)}>進部門 ▸</button>}
        </span>
      </div>
      {/* on the 往來 tab the head is one line: the thread gets the room (Fable 11-15 #4) */}
      {!slim && <div className="mt-0.5 text-sm text-slate-300" title={n.why_full ?? n.why}><Clamp node={n.id} id="why" lines={2} text={`${LIGHT_WORD[n.light]}：${whyWord(n.why_full ?? n.why)}`} /></div>}
      {!slim && dept && <div className="flex flex-wrap items-center gap-1 text-xs">
        <BelowMark below={belowOf(n)} size="full" names={n.rollup.worst_ids?.filter((id) => id !== n.id)} />
        {(n.rollup.worst_ids || []).filter((id) => id !== n.id).slice(0, 3).map((id) => <button key={id} className="text-sky-300 hover:underline" onClick={() => jump(id, false)}>{id}</button>)}
      </div>}
      {!slim && n.parent && tree.nodes[n.parent] && (
        <p className="text-xs text-slate-500">隸屬 <button className="hover:underline" onClick={() => jump(n.parent!, false)}>{n.parent}</button></p>
      )}
    </div>
  );
}

export function Inspector() {
  const section = useRef<HTMLElement>(null);
  useEffect(() => bind(["Home", "End", "PageUp", "PageDown"].map((key) => ({
    key, zone: "inspector" as const, run: () => {
      const el = section.current?.querySelector<HTMLElement>("[data-scroll]");
      if (!el) return;
      if (key === "Home") el.scrollTop = 0;
      else if (key === "End") el.scrollTop = el.scrollHeight;
      else el.scrollTop += el.clientHeight * 0.9 * (key === "PageUp" ? -1 : 1);
    },
  }))), []);
  const tree = useData((s) => s.tree);
  const multi = useUi((s) => s.multi);
  const route = useUi((s) => s.route);
  const now = useNow();
  const n = tree && route.sel ? tree.nodes[route.sel] : undefined;
  let body: React.ReactNode;
  if (!tree) body = <p className="p-3 text-sm text-slate-400">讀取中…</p>;
  else if (multi.length >= 2) body = <MultiPanel tree={tree} ids={multi} />;
  else if (!route.sel) body = <Overview tree={tree} focus={route.focus} now={now} />;
  else if (!n) body = (
    <div className="flex min-h-0 flex-1 flex-col p-3">
      <p className="mb-2 text-sm text-amber-300">{route.sel} 已經不在樹上了（可能收隊了）。</p>
      <Thread name={route.sel} />
    </div>
  );
  else if (n.kind !== "agent") body = <><Head n={n} tree={tree} /><Plain n={n} now={now} /></>;
  else body = (
    <>
      <Head n={n} tree={tree} slim={route.tab === "thread"} />
      <SlashResults key={n.id} n={n} />
      <Tabs tab={route.tab} has={["now", "thread", "history"]} />
      <div data-scroll={route.tab === "now" ? "now" : undefined} className={`flex min-h-0 flex-1 flex-col p-3 ${route.tab === "now" ? "overflow-y-auto" : ""}`}>
        {route.tab === "now" && <AgentNow key={n.id} n={n} tree={tree} now={now} />}
        {route.tab === "thread" && <Thread key={n.id} name={n.id} />}
        {route.tab === "history" && <History key={n.id} n={n} />}
      </div>
    </>
  );
  return (
    <section ref={section} data-zone="inspector" tabIndex={-1} onPointerDown={(e) => {
      if (!(e.target as Element).closest("button, input, textarea, select, a, [contenteditable=true]")) {
        section.current?.focus({ preventScroll: true });
      }
    }} className="relative flex min-h-0 flex-1 flex-col border-l border-slate-800 bg-slate-900/60 focus-within:ring-1 focus-within:ring-sky-700">
      <button className="absolute right-1 top-1 z-10 rounded px-1.5 text-slate-400 hover:bg-slate-800 hover:text-slate-100" title="收起右欄（]）；打的字留著"
        onClick={() => setRight(false)}>»</button>
      <div className="flex min-h-0 flex-1 flex-col">{body}</div>
    </section>
  );
}
