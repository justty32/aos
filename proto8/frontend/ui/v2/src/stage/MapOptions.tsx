// A small anchored panel changes map width, names, wrapping, and font size.
import { useEffect, useRef } from "react";
import { pushOverlay } from "../input/keys.ts";
import { DEFAULT_OPTS, type MapOpts } from "../model/mapOpts.ts";
import { setMapOpts } from "../state/mapOpts.ts";

export function MapOptions({ opts, close }: { opts: MapOpts; close: () => void }) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const off = pushOverlay(close);
    const outside = (e: PointerEvent) => { if (!box.current?.contains(e.target as Node) && !(e.target as Element).closest("[data-map-options-toggle]")) close(); };
    document.addEventListener("pointerdown", outside);
    return () => { off(); document.removeEventListener("pointerdown", outside); };
  }, [close]);
  const row = <K extends keyof MapOpts>(key: K, label: string, choices: [MapOpts[K], string][]) => <div className="flex items-center gap-1" key={key}>
    <span className="w-12 shrink-0 text-slate-500">{label}</span>
    {choices.map(([value, text]) => <button key={value} className={`rounded px-1.5 py-1 ${opts[key] === value ? "bg-sky-800 text-white" : "hover:bg-slate-700"}`} onClick={() => setMapOpts({ [key]: value })}>{text}</button>)}
  </div>;
  return <div ref={box} data-map-options className="absolute right-0 top-full z-20 mt-1 space-y-1 rounded-lg border border-slate-600 bg-slate-900 p-2 text-xs text-slate-300 shadow-xl">
    {row("w", "格寬", [["std", "標準"], ["wide", "寬"], ["xwide", "特寬"], ["fit", "配合名字"]])}
    {row("name", "名字", [["short", "短名"], ["full", "全名"]])}
    {row("over", "太長時", [["cut", "中間省略"], ["wrap", "換兩行"]])}
    {row("font", "字級", [["s", "小"], ["m", "中"], ["l", "大"]])}
    <button className="block w-full text-right text-sky-300 hover:underline" onClick={() => setMapOpts(DEFAULT_OPTS)}>回預設</button>
  </div>;
}
