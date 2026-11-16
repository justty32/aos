// A single responsive command strip fills the composer without sending anything immediately.
import { useEffect, useRef, useState } from "react";
import { useUi } from "../state/hooks.ts";
import { ui } from "../state/app.ts";
import { readHistory, readPins, togglePin } from "../model/cmdHistory.ts";
import { fillCommand } from "./commandActions.ts";
export function CmdSide() {
  const rev = useUi((s) => s.cmdRev);
  const box = useRef<HTMLDivElement>(null);
  const [wide, setWide] = useState(false);
  useEffect(() => { const el = box.current?.parentElement?.parentElement; if (!el) return; const ro = new ResizeObserver(() => setWide(el.clientWidth >= 520)); ro.observe(el); return () => ro.disconnect(); }, []);
  const pins = readPins(localStorage), history = readHistory(localStorage);
  void rev;
  return <div ref={box} data-cmd-side={wide ? "col" : "row"} className="flex max-h-16 shrink-0 gap-2 overflow-y-auto text-xs @[520px]:max-h-none @[520px]:w-44 @[520px]:flex-col">
    <div><div className="text-slate-500">常用</div><div className="flex flex-wrap gap-1">{pins.map((p) => <button key={p} className="rounded bg-slate-800 px-1 text-sky-200" onClick={() => fillCommand(p)}>{p}</button>)}</div></div>
    <div><div className="text-slate-500">最近</div>{history.map((h) => <span key={h.line} className="mr-1 inline-flex max-w-full items-center gap-1">
      <button className="truncate text-slate-300 hover:underline" title={h.target || "這一頁"} onClick={() => fillCommand(h.line)}>{h.line}<small className="ml-1 text-slate-500">{h.target}</small></button>
      <button title="加進／拿出常用" onClick={() => { togglePin(localStorage, h.line); ui.set({ cmdRev: ui.get().cmdRev + 1 }); }}>{pins.includes(h.line) ? "★" : "☆"}</button>
    </span>)}</div>
  </div>;
}
