// The command panel offers page actions, mode buttons, and fill-only CLI commands.
import { useEffect, useRef, useState } from "react";
import { useData, useUi } from "../state/hooks.ts";
import { ui } from "../state/app.ts";
import { caretToComposer } from "../state/nav.ts";
import { pushOverlay } from "../input/keys.ts";
import { cliProblem, GROUP_WORD, listCommands } from "../model/commands.ts";
import { readHistory, readPins, togglePin } from "../model/cmdHistory.ts";
import { pageCommand, fillCommand } from "../composer/commandActions.ts";
import { setRight, toggleLeft, toggleRight } from "../state/layout.ts";
import { fontBigger, fontSmaller } from "../state/sizes.ts";
const close = () => ui.set({ panelOpen: false });
export function CommandPanel() {
  const slash = useData((s) => s.slash), orders = useData((s) => s.orders), tree = useData((s) => s.tree);
  const route = useUi((s) => s.route), multi = useUi((s) => s.multi), rev = useUi((s) => s.cmdRev);
  const n = route.sel ? tree?.nodes[route.sel] : undefined;
  const [query, setQuery] = useState(""); const input = useRef<HTMLInputElement>(null);
  useEffect(() => { input.current?.focus(); return pushOverlay(close); }, []);
  const commands = listCommands({ orders, slash, cli: n?.live?.cli ?? slash[0]?.cli[0] ?? "claude", multi: multi.length, target: n?.id });
  const pins = readPins(localStorage); void rev;
  const setMode = (mode: "say" | "mail" | "order", orderKind?: string) => {
    if (!n || n.kind !== "agent") return;
    setRight(true);
    ui.set({ prefill: { target: n.id, mode, orderKind, n: Date.now() }, panelOpen: false }); caretToComposer();
  };
  const rows: { label: string; group: string; line?: string; disabled?: string | null; run: () => void; screen?: boolean }[] = commands.map((c) => ({
    label: `${c.confirm ? "⚠ " : ""}${c.label}`, group: GROUP_WORD[c.group], line: "/" + c.name, screen: c.how === "screen",
    disabled: c.group === "page" ? null : c.group === "cli" ? cliProblem(n, slash.find((s) => s.name === c.name)) || (multi.length >= 2 && c.confirm ? "這個指令一次只能對一個人下" : null) : (!n || n.kind !== "agent") ? "先選一個 agent" : null,
    run: () => { if (c.group === "page") { close(); pageCommand(c.name); } else if (c.group === "talk") setMode(c.name === "mail" ? "mail" : "say"); else fillCommand("/" + c.name); },
  }));
  for (const order of orders) rows.splice(2, 0, { label: order.label, group: "董事長令", disabled: (!n || n.kind !== "agent") ? "先選一個 agent" : multi.length >= 2 ? "董事長令一次只能對一個對象" : null, run: () => setMode("order", order.kind) });
  for (const [label, run] of [["左欄 [", toggleLeft], ["右欄 ]", toggleRight], ["字大", fontBigger], ["字小", fontSmaller]] as const) rows.push({ label, group: "這一頁", run: () => { run(); close(); } });
  for (const h of readHistory(localStorage).slice(0, 8)) rows.push({ label: h.line, line: h.line, group: "最近用過", run: () => fillCommand(h.line) });
  const shown = rows.filter((r) => `${r.label} ${r.line || ""}`.includes(query) || commands.find((c) => "/" + c.name === r.line)?.aliases.some((a) => a.includes(query)));
  return <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 pt-20" onMouseDown={(e) => { if (e.target === e.currentTarget) close(); }}>
    <div data-panel role="dialog" aria-label="指令面板" className="max-h-[80vh] w-[640px] max-w-[95vw] overflow-y-auto rounded-lg border border-slate-600 bg-slate-900 p-3 shadow-xl">
      <div className="mb-2 flex justify-between text-sm"><b>指令面板｜{multi.length >= 2 ? `已選 ${multi.length} 個` : n ? `對：${n.id}` : "沒選人"}</b><button onClick={close}>關 Esc</button></div>
      <input ref={input} value={query} placeholder="篩選…" className="mb-2 w-full rounded bg-slate-800 p-2 text-sm" onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => {
        if (e.nativeEvent.isComposing) return;
        if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); }
        if (e.key === "Enter") { e.preventDefault(); shown.find((r) => !r.disabled)?.run(); }
      }} />
      {[...new Set(shown.map((r) => r.group))].map((group) => <section key={group} className="mb-3"><h3 className="mb-1 text-xs text-slate-500">{group}</h3><div className="flex flex-wrap gap-1">{shown.filter((r) => r.group === group).map((r, i) => <span key={i} className="inline-flex rounded bg-slate-800">
        <button disabled={!!r.disabled} title={r.disabled || (r.screen ? "打進它開著的畫面，把印出來的內容抄回『做過・說過』；要先開畫面" : r.line)} className="px-2 py-1 text-sm disabled:opacity-40" onClick={r.run}>{r.label} <small className="text-slate-500">{r.line}{r.screen ? " 看畫面" : ""}</small></button>
        {r.line && <button className="px-1 text-xs text-sky-300" title="加進／拿出常用" onClick={() => { togglePin(localStorage, r.line!); ui.set({ cmdRev: ui.get().cmdRev + 1 }); }}>{pins.includes(r.line) ? "★" : "☆"}</button>}
      </span>)}</div></section>)}
    </div>
  </div>;
}
