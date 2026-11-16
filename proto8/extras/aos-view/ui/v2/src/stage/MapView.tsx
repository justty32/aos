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
import { foldAll, mapFolds, setFoldsUnder, toggleFold } from "../state/mapFold.ts";
import { bind } from "../input/keys.ts";
import { layoutMap, itemKey, nearest, STEP_WORD, type Dir, type MapItem } from "../model/layoutMap.ts";
import { displayName, isDept, MACHINE } from "../model/tree.ts";
import { useBand } from "./useBand.ts";
import { clearMulti } from "../state/multi.ts";
import { Item } from "./MapItem.tsx";
import { MapOptions } from "./MapOptions.tsx";
import { mapOpts } from "../state/mapOpts.ts";
import { FONT_PX, plateOf } from "../model/mapOpts.ts";
import { widths, textW } from "./mapText.ts";

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

export function MapView() {
  const tree = useData((s) => s.tree);
  const ask = useUi((s) => s.route.ask);
  const focus = useUi((s) => s.route.focus);
  const sel = useUi((s) => s.route.sel);
  const box = useRef<HTMLDivElement>(null);
  const fonts = useFontsReady();
  const { w, h } = useSize(box);
  const folds = useStore(mapFolds, (s) => s.f);
  const opts = useStore(mapOpts, (s) => s.opts);
  const [optionsOpen, setOptionsOpen] = useState(false);
  const userSet = folds.all !== null || Object.keys(folds.ids).length > 0;
  const lay = useMemo(() => {
    if (w <= 0) return null;
    const base = layoutMap(tree, focus, w, h, folds, plateOf(opts, 116), opts.name === "full");
    const fit = Math.max(116, ...base.items.filter((it) => it.kind === "plate" || it.kind === "fold").map((it) => textW(it.name, FONT_PX[opts.font]) + 26));
    return opts.w === "fit" ? layoutMap(tree, focus, w, h, folds, plateOf(opts, fit), opts.name === "full") : base;
  }, [tree, focus, w, h, fonts, folds, opts]);
  const band = useBand(lay?.items || []);
  const order = lay?.items.filter((it) => (it.kind === "plate" || it.kind === "dot") && tree?.nodes[it.id]?.kind === "agent").map((it) => it.id) || [];
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
  const focusMap = (key?: string) => requestAnimationFrame(() => {
    const el = key ? box.current?.querySelector<HTMLElement>(`[data-key="${CSS.escape(key)}"]`) : null;
    if (el) { el.tabIndex = -1; el.focus({ preventScroll: true }); }
    else box.current?.focus({ preventScroll: true });
  });
  const flip = (it: MapItem) => {
    if (it.kind !== "room" && it.kind !== "fold") return;
    const folded = it.kind === "fold";
    toggleFold(it.id, folded);
    const key = `${folded ? "room" : "fold"}:${it.id}`;
    setCur(key);
    focusMap(key);
  };
  useEffect(() => {
    if (!lay || !tree || ask) return;
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
    const current = () => items.find((x) => itemKey(x) === cur);
    const roomOfItem = (it: MapItem) => it.id === MACHINE ? MACHINE : isDept(tree.nodes[it.id]) ? it.id : tree.nodes[it.id]?.parent;
    const tab = () => {
      const it = current();
      if (!it) return;
      if (it.kind === "room" || it.kind === "fold") { flip(it); return; }
      const room = roomOfItem(it);
      if (!room) return;
      toggleFold(room, false);
      setCur("fold:" + room);
      focusMap("fold:" + room);
    };
    const under = (mode: "fold" | "open") => {
      const it = current();
      const room = it ? roomOfItem(it) : focus;
      if (!room || room === MACHINE) foldAll(mode);
      else {
        const self = mode === "open" || it?.kind === "room" || it?.kind === "fold";
        setFoldsUnder(tree, room, mode, self);
        if (self && mode === "fold") { setCur("fold:" + room); focusMap("fold:" + room); return; }
      }
      focusMap();
    };
    return bind([
      { key: "ArrowRight", zone: "stage", run: go("right") }, { key: "l", zone: "stage", run: go("right") },
      { key: "ArrowLeft", zone: "stage", run: go("left") }, { key: "h", zone: "stage", run: go("left") },
      { key: "ArrowDown", zone: "stage", run: go("down") }, { key: "j", zone: "stage", run: go("down") },
      { key: "ArrowUp", zone: "stage", run: go("up") }, { key: "k", zone: "stage", run: go("up") },
      { key: "Enter", zone: "stage", run: ent },
      { key: "Tab", zone: "stage", when: () => !!box.current?.contains(document.activeElement), run: tab },
      { key: "o", zone: "stage", run: () => under("open") },
      { key: "c", zone: "stage", run: () => under("fold") },
      { key: " ", zone: "stage", run: () => { const it = items.find((x) => itemKey(x) === cur); if (it) flip(it); } },
    ]);
  }, [lay, cur, tree, ask, focus]);
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
        <div className="relative ml-auto shrink-0">
          <button data-map-options-toggle className="rounded px-1.5 py-0.5 hover:bg-slate-800" title="地圖怎麼排：格寬、名字、字級" onClick={() => setOptionsOpen((v) => !v)}>⚙ 佈局</button>
          {optionsOpen && <MapOptions opts={opts} close={() => setOptionsOpen(false)} />}
        </div>
      </div>
      <div ref={box} onClick={(e) => { if (e.target === e.currentTarget) clearMulti(); }} data-cur={cur ?? ""} className="relative min-h-0 flex-1 overflow-y-auto overflow-x-hidden p-3" tabIndex={0}>
        {!tree && <p className="text-sm text-slate-400">讀取中…</p>}
        {tree && lay && (
          <div {...band.handlers} className={`relative ${band.rect ? "select-none" : ""}`} style={{ width: lay.width, height: lay.height }}>
            {band.rect && <div data-band className="pointer-events-none absolute z-10 border border-sky-400 bg-sky-400/10" style={{ left: band.rect.x, top: band.rect.y, width: band.rect.w, height: band.rect.h }} />}
            {lay.items.map((it, i) => <Item key={it.kind + it.id + i} it={it} order={order} opts={opts} sel={sel} cur={cur === itemKey(it)} onFlip={flip} />)}
          </div>
        )}
      </div>
    </div>
  );
}
