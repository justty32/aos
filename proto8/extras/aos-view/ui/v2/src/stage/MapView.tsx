// The center 地圖 tab (P4, 02e §3, q5 a): the whole company (or the room you stand in) as boxes — rooms framed,
// people as 116×28 name plates, people before rooms. When it does not fit: fold quiet sub-rooms, then quiet people
// become dots, then scroll down; the toolbar says which step it is on. Click a person = select; click a room = enter.
// The user can fold rooms too (11-15 "地圖那邊我希望可以折疊"): the ▾ / ▸ in front of a room's name or Space on it, and
// 全部折疊 / 全部展開 / 自動 in the toolbar; kept per browser (state/mapFold.ts).
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useData, useUi } from "../state/hooks.ts";
import { caretToComposer, enter, select } from "../state/nav.ts";
import { setRight } from "../state/layout.ts";
import { useStore } from "../state/store.ts";
import { foldAll, mapFolds, toggleFold } from "../state/mapFold.ts";
import { bind } from "../input/keys.ts";
import { layoutMap, itemLight, itemKey, nearest, PLATE, STEP_WORD, type Dir, type MapItem } from "../model/layoutMap.ts";
import { displayName, MACHINE } from "../model/tree.ts";
import { LIGHT_BG, LIGHT_WORD } from "../shell/bits.tsx";
import { whyWord } from "../model/words.ts";

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

/** the small fold / open switch in front of a room's name (its own button: the name still enters the room) */
function Twist({ it, onFlip }: { it: MapItem; onFlip: (it: MapItem) => void }) {
  const folded = it.kind === "fold";
  return (
    <button data-fold={it.id} className="flex h-full w-4 shrink-0 items-center justify-center text-slate-500 hover:text-slate-200"
      title={folded ? "展開（Space）" : "折疊（Space）"} aria-label={folded ? "展開" : "折疊"} aria-expanded={!folded}
      onClick={(e) => { e.stopPropagation(); onFlip(it); }}>
      {folded ? "▸" : "▾"}
    </button>
  );
}

function Item({ it, sel, cur, onFlip }: { it: MapItem; sel: string | null; cur: boolean; onFlip: (it: MapItem) => void }) {
  const tree = useData((s) => s.tree)!;
  const light = itemLight(tree, it);
  const pos = { left: it.x, top: it.y, width: it.w, height: it.h };
  const n = tree.nodes[it.id];
  if (it.kind === "room") {
    return (
      <div className="absolute rounded-md border border-slate-700 bg-slate-900/50" style={pos}>
        <div data-key={itemKey(it)} className={`flex h-[26px] w-full items-center rounded-t-md pl-1 ${cur ? "ring-2 ring-sky-400" : ""}`}>
          <Twist it={it} onFlip={onFlip} />
          <button className="flex h-full min-w-0 flex-1 items-center gap-1.5 rounded-tr-md px-1 text-left text-xs font-semibold text-slate-300 hover:bg-slate-800"
            title={`進 ${displayName(it.id)}`} onClick={() => enter(it.id)}>
            <span className={`inline-block h-2 w-2 shrink-0 rounded-full ${LIGHT_BG[light]}`} />
            <span className="truncate">{fitName(it.title, it.w - 76)}</span>
            <span className="ml-auto shrink-0 font-normal text-slate-500">{it.count} 人</span>
          </button>
        </div>
      </div>
    );
  }
  const on = sel === it.id || cur;
  const why = n ? `${it.id} · ${LIGHT_WORD[n.light]}${n.why ? " · " + whyWord(n.why) : ""}` : it.id;
  if (it.kind === "dot") {
    return <button data-map={it.id} data-key={itemKey(it)} className={`absolute rounded-full ${LIGHT_BG[light]} opacity-70 hover:opacity-100 ${on ? "ring-2 ring-sky-300" : ""}`}
      style={pos} title={why} aria-label={it.id} onClick={() => select(it.id)} />;
  }
  if (it.kind === "fold") {
    return (
      <div data-key={itemKey(it)} className={`absolute flex items-center rounded border border-dashed bg-slate-900 pl-0.5 text-[13px] text-slate-300 ${it.busy ? "border-slate-400" : "border-slate-600"} hover:border-slate-300 ${cur ? "ring-2 ring-sky-400" : ""}`}
        style={pos}>
        <Twist it={it} onFlip={onFlip} />
        <button className="flex h-full min-w-0 flex-1 items-center gap-1.5 pl-0.5 pr-2 text-left"
          title={`${displayName(it.id)}：${it.count} 人，點了進去`} onClick={() => enter(it.id)}>
          <span className={`inline-block h-2.5 w-2.5 shrink-0 rounded-sm ${LIGHT_BG[light]}`} />
          <span className="min-w-0 flex-1 overflow-hidden whitespace-nowrap">{fitName(it.name, TEXT_W - 30)}</span>
          <span className="shrink-0 text-xs text-slate-500">{it.count}</span>
        </button>
      </div>
    );
  }
  return (
    <button data-map={it.id} data-key={itemKey(it)} className={`absolute flex items-center gap-1.5 rounded px-2 text-left text-[13px]
        ${on ? "bg-slate-600 ring-2 ring-sky-400" : it.busy ? "bg-slate-700 hover:bg-slate-600" : "bg-slate-800 hover:bg-slate-700"}
        ${it.lead ? "font-semibold" : ""}`}
      style={pos} title={why} onClick={() => (it.id === MACHINE ? enter(MACHINE) : select(it.id))}>
      <span className={`inline-block h-2.5 w-2.5 shrink-0 rounded-full ${LIGHT_BG[light]}`} />
      <span className="min-w-0 overflow-hidden whitespace-nowrap">{fitName(it.name)}</span>
      {!!n?.asks && <span className="ml-auto shrink-0 text-xs text-sky-300">🔵{n.asks}</span>}
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
  const folds = useStore(mapFolds, (s) => s.f);
  const userSet = folds.all !== null || Object.keys(folds.ids).length > 0;
  const lay = useMemo(() => (w > 0 ? layoutMap(tree, focus, w, h, folds) : null), [tree, focus, w, h, fonts, folds]);
  // the keyboard cursor (02d §6 #2): a key per piece; follows the selection when that is a person on the map
  const [cur, setCur] = useState<string | null>(null);
  const lastSel = useRef<string | null>(null);
  useEffect(() => {
    if (!lay || !sel) return;
    // only when the selection moved (or no cursor yet): a re-layout (fold / open) keeps the cursor where it is
    if (sel === lastSel.current && cur) return;
    lastSel.current = sel;
    const it = lay.items.find((x) => x.id === sel && (x.kind === "plate" || x.kind === "dot"));
    if (it && cur !== itemKey(it)) setCur(itemKey(it));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sel, lay]);
  useEffect(() => {
    if (cur) box.current?.querySelector(`[data-key="${CSS.escape(cur)}"]`)?.scrollIntoView({ block: "nearest" });
  }, [cur, lay]);
  // fold / open one room; the cursor stays on it (its key changes kind: room:x <-> fold:x)
  const flip = (it: MapItem) => {
    if (it.kind !== "room" && it.kind !== "fold") return;
    const folded = it.kind === "fold";
    toggleFold(it.id, folded);
    setCur(`${folded ? "room" : "fold"}:${it.id}`);
  };
  useEffect(() => {
    if (!lay) return;
    const items = lay.items;
    const pick = (k: string | null) => {
      if (!k) return;
      setCur(k);
      const it = items.find((x) => itemKey(x) === k);
      if (it && (it.kind === "plate" || it.kind === "dot") && it.id !== MACHINE) select(it.id);
    };
    const go = (d: Dir) => () => pick(nearest(items, items.some((x) => itemKey(x) === cur) ? cur : null, d));
    const ent = () => {
      const it = items.find((x) => itemKey(x) === cur);
      if (!it) return pick(nearest(items, null, "right"));
      if (it.kind === "room" || it.kind === "fold" || it.id === MACHINE) { setCur(null); enter(it.id); return; }
      setRight(true); caretToComposer();
    };
    return bind([
      { key: "ArrowRight", zone: "stage", run: go("right") }, { key: "l", zone: "stage", run: go("right") },
      { key: "ArrowLeft", zone: "stage", run: go("left") }, { key: "h", zone: "stage", run: go("left") },
      { key: "ArrowDown", zone: "stage", run: go("down") }, { key: "j", zone: "stage", run: go("down") },
      { key: "ArrowUp", zone: "stage", run: go("up") }, { key: "k", zone: "stage", run: go("up") },
      { key: "Enter", zone: "stage", run: ent },
      { key: " ", zone: "stage", run: () => { const it = items.find((x) => itemKey(x) === cur); if (it) flip(it); } },
    ]);
  }, [lay, cur]);
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-7 shrink-0 items-center gap-3 whitespace-nowrap border-b border-slate-900 px-3 text-xs text-slate-500">
        <span className="shrink-0">{focus ? displayName(focus) : "全公司"}</span>
        {lay && (userSet
          ? <span className="shrink-0" data-map-step={lay.step}>照你折的{lay.step === 3 ? "，可往下捲" : ""}</span>
          : <span className="shrink-0" data-map-step={lay.step}>自動第 {lay.step} 步：{STEP_WORD[lay.step]}</span>)}
        <span className="flex shrink-0 items-center gap-1">
          {([["fold", "全部折疊"], ["open", "全部展開"], [null, "自動"]] as const).map(([m, label]) => (
            <button key={label} data-fold-all={m ?? "auto"}
              className={`rounded px-1.5 py-0.5 ${folds.all === m && !Object.keys(folds.ids).length && (m !== null || !userSet) ? "bg-slate-700 text-slate-100" : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"}`}
              title={m === null ? "照畫面大小自動折（預設）" : label} onClick={() => foldAll(m)}>{label}</button>
          ))}
        </span>
        <span className="ml-auto min-w-0 truncate" title="點人＝選取，點房間名＝進去，點 ▾／▸＝折疊／展開；方向鍵走、Enter 進房間或開打字區、Space 折疊／展開房間、Backspace 回上一層">點人＝選取，點房間＝進去，▾／▸ 或 Space＝折疊／展開；方向鍵走、Enter 進去、Backspace 回上一層</span>
      </div>
      <div ref={box} data-cur={cur ?? ""} className="relative min-h-0 flex-1 overflow-y-auto overflow-x-hidden p-3" tabIndex={0}>
        {!tree && <p className="text-sm text-slate-400">讀取中…</p>}
        {tree && lay && (
          <div className="relative" style={{ width: lay.width, height: lay.height }}>
            {lay.items.map((it, i) => <Item key={it.kind + it.id + i} it={it} sel={sel} cur={cur === itemKey(it)} onFlip={flip} />)}
          </div>
        )}
      </div>
    </div>
  );
}
