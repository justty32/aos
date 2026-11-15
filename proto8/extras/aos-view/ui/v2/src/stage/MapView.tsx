// The center 地圖 tab (P4, 02e §3, q5 a): the whole company (or the room you stand in) as boxes — rooms framed,
// people as 116×28 name plates, people before rooms. When it does not fit: fold quiet sub-rooms, then quiet people
// become dots, then scroll down; the toolbar says which step it is on. Click a person = select; click a room = enter.
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useData, useUi } from "../state/hooks.ts";
import { enter, select } from "../state/nav.ts";
import { layoutMap, itemLight, PLATE, STEP_WORD, type MapItem } from "../model/layoutMap.ts";
import { displayName, MACHINE } from "../model/tree.ts";
import { LIGHT_BG, LIGHT_WORD } from "../shell/bits.tsx";

const FONT = "13px ui-sans-serif, system-ui, sans-serif";
const TEXT_W = PLATE.w - 26;           // plate minus the dot and padding

// measured once per name after the fonts are in (02e §3.1: measure, do not guess); cut in the middle with "…"
const widths = new Map<string, number>();
let ctx: CanvasRenderingContext2D | null = null;
function textW(s: string): number {
  let w = widths.get(s);
  if (w == null) {
    if (!ctx) { ctx = document.createElement("canvas").getContext("2d"); if (ctx) ctx.font = FONT; }
    w = ctx ? ctx.measureText(s).width : s.length * 7;
    widths.set(s, w);
  }
  return w;
}
export function fitName(s: string, max = TEXT_W): string {
  if (textW(s) <= max) return s;
  let a = Math.ceil(s.length / 2), b = Math.floor(s.length / 2);
  while (a > 1) {
    const t = s.slice(0, a) + "…" + s.slice(s.length - b);
    if (textW(t) <= max) return t;
    if (a >= b) a--; else b--;
  }
  return s.slice(0, 1) + "…";
}

function useFontsReady(): boolean {
  const [ok, setOk] = useState(false);
  useEffect(() => {
    let live = true;
    (document.fonts?.ready || Promise.resolve()).then(() => { widths.clear(); if (live) setOk(true); });
    return () => { live = false; };
  }, []);
  return ok;
}

function useSize(ref: React.RefObject<HTMLDivElement | null>) {
  const [sz, setSz] = useState({ w: 0, h: 0 });
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setSz({ w: el.clientWidth - 24, h: el.clientHeight - 24 }));
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return sz;
}

function Item({ it, sel }: { it: MapItem; sel: string | null }) {
  const tree = useData((s) => s.tree)!;
  const light = itemLight(tree, it);
  const pos = { left: it.x, top: it.y, width: it.w, height: it.h };
  const n = tree.nodes[it.id];
  if (it.kind === "room") {
    return (
      <div className="absolute rounded-md border border-slate-700 bg-slate-900/50" style={pos}>
        <button className="flex h-[26px] w-full items-center gap-1.5 rounded-t-md px-2 text-left text-xs font-semibold text-slate-300 hover:bg-slate-800"
          title={`進 ${displayName(it.id)}`} onClick={() => enter(it.id)}>
          <span className={`inline-block h-2 w-2 shrink-0 rounded-full ${LIGHT_BG[light]}`} />
          <span className="truncate">{fitName(it.title, it.w - 60)}</span>
          <span className="ml-auto shrink-0 font-normal text-slate-500">{it.count}</span>
        </button>
      </div>
    );
  }
  const on = sel === it.id;
  const why = n ? `${it.id} · ${LIGHT_WORD[n.light]}${n.why ? " · " + n.why : ""}` : it.id;
  if (it.kind === "dot") {
    return <button data-map={it.id} className={`absolute rounded-full ${LIGHT_BG[light]} opacity-70 hover:opacity-100 ${on ? "ring-2 ring-sky-300" : ""}`}
      style={pos} title={why} aria-label={it.id} onClick={() => select(it.id)} />;
  }
  if (it.kind === "fold") {
    return (
      <button className="absolute flex items-center gap-1.5 rounded border border-dashed border-slate-600 bg-slate-900 px-2 text-left text-[13px] text-slate-300 hover:border-slate-400"
        style={pos} title={`${displayName(it.id)}：${it.count} 人，點了進去`} onClick={() => enter(it.id)}>
        <span className={`inline-block h-2.5 w-2.5 shrink-0 rounded-sm ${LIGHT_BG[light]}`} />
        <span className="min-w-0 flex-1 overflow-hidden whitespace-nowrap">{fitName(it.name, TEXT_W - 18)}</span>
        <span className="shrink-0 text-[11px] text-slate-500">{it.count}</span>
      </button>
    );
  }
  return (
    <button data-map={it.id} className={`absolute flex items-center gap-1.5 rounded px-2 text-left text-[13px]
        ${on ? "bg-slate-600 ring-2 ring-sky-400" : it.busy ? "bg-slate-700 hover:bg-slate-600" : "bg-slate-800 hover:bg-slate-700"}
        ${it.lead ? "font-semibold" : ""}`}
      style={pos} title={why} onClick={() => (it.id === MACHINE ? enter(MACHINE) : select(it.id))}>
      <span className={`inline-block h-2.5 w-2.5 shrink-0 rounded-full ${LIGHT_BG[light]}`} />
      <span className="min-w-0 overflow-hidden whitespace-nowrap">{fitName(it.name)}</span>
      {!!n?.asks && <span className="ml-auto shrink-0 text-[11px] text-sky-300">🔵{n.asks}</span>}
    </button>
  );
}

export function MapView() {
  const tree = useData((s) => s.tree);
  const focus = useUi((s) => s.route.focus);
  const sel = useUi((s) => s.route.sel);
  const box = useRef<HTMLDivElement>(null);
  const fonts = useFontsReady();
  const { w, h } = useSize(box);
  const lay = useMemo(() => (w > 0 ? layoutMap(tree, focus, w, h) : null), [tree, focus, w, h, fonts]);
  useEffect(() => {
    if (sel) box.current?.querySelector(`[data-map="${CSS.escape(sel)}"]`)?.scrollIntoView({ block: "nearest" });
  }, [sel, lay]);
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-7 shrink-0 items-center gap-3 border-b border-slate-900 px-3 text-xs text-slate-500">
        <span>{focus ? displayName(focus) : "全公司"}</span>
        {lay && <span data-map-step={lay.step}>第 {lay.step} 步：{STEP_WORD[lay.step]}</span>}
        <span className="ml-auto">點人＝選取，點房間＝進去</span>
      </div>
      <div ref={box} className="relative min-h-0 flex-1 overflow-y-auto overflow-x-hidden p-3" tabIndex={0}>
        {!tree && <p className="text-sm text-slate-400">讀取中…</p>}
        {tree && lay && (
          <div className="relative" style={{ width: lay.width, height: lay.height }}>
            {lay.items.map((it, i) => <Item key={it.kind + it.id + i} it={it} sel={sel} />)}
          </div>
        )}
      </div>
    </div>
  );
}
