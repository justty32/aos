// Map pieces render room frames, fold controls, agent plates, and dots.
import { pickWith } from "../state/multi.ts";
import { useData, useUi } from "../state/hooks.ts";
import { enter } from "../state/nav.ts";
import { itemLight, itemKey, type MapItem } from "../model/layoutMap.ts";
import { displayName, machineRollup, MACHINE } from "../model/tree.ts";
import { BelowMark, Dot, LIGHT_BG, LIGHT_WORD } from "../shell/bits.tsx";
import { belowOf, roomOf } from "../model/lights.ts";
import { whyWord } from "../model/words.ts";
import { FONT_PX, type MapOpts } from "../model/mapOpts.ts";
import { fitName } from "./mapText.ts";

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

export function Item({ it, sel, cur, onFlip, opts, order }: { order: string[]; opts: MapOpts; it: MapItem; sel: string | null; cur: boolean; onFlip: (it: MapItem) => void }) {
  const multi = useUi((s) => s.multi);
  const tree = useData((s) => s.tree)!;
  const light = itemLight(tree, it);
  const font = FONT_PX[opts.font];
  const pos = { left: it.x, top: it.y, width: it.w, height: it.h, fontSize: font };
  const n = tree.nodes[it.id];
  const names = n?.rollup.worst_ids?.filter((id) => id !== n.id);
  const room = it.id === MACHINE ? roomOf({ rollup: machineRollup(tree) }) : roomOf(n);
  if (it.kind === "room") {
    return (
      <div className="absolute rounded-md border border-slate-700 bg-slate-900/50" style={pos}>
        <div data-key={itemKey(it)} className={`flex h-[26px] w-full items-center rounded-t-md pl-1 ${cur ? "ring-2 ring-sky-400" : ""}`}>
          <Twist it={it} onFlip={onFlip} />
          <button className="flex h-full min-w-0 flex-1 items-center gap-1.5 rounded-tr-md px-1 text-left text-xs font-semibold text-slate-300 hover:bg-slate-800"
            title={`進 ${displayName(it.id)}`} onClick={() => enter(it.id)}>
            <BelowMark below={room} names={n?.rollup.worst_ids} />
            <span className="truncate">{fitName(it.title, it.w - 76, font)}</span>
            <span className="ml-auto shrink-0 font-normal text-slate-500">{it.count} 人</span>
          </button>
        </div>
      </div>
    );
  }
  const selected = multi.includes(it.id);
  const on = sel === it.id || cur || selected;
  const why = n ? `${it.id} · ${LIGHT_WORD[n.light]}${n.why ? " · " + whyWord(n.why) : ""}` : it.id;
  if (it.kind === "dot") {
    return <button data-multi={selected ? "1" : undefined} data-own-light={light} data-map={it.id} data-key={itemKey(it)} className={`absolute rounded-full ${LIGHT_BG[light]} opacity-70 hover:opacity-100 ${on ? "ring-2 ring-sky-300" : ""}`}
      style={pos} title={why} aria-label={it.id} onClick={(e) => pickWith(e, it.id, order)} />;
  }
  if (it.kind === "fold") {
    return (
      <div data-key={itemKey(it)} className={`absolute flex items-center rounded border border-dashed bg-slate-900 pl-0.5 text-[13px] text-slate-300 ${it.busy ? "border-slate-400" : "border-slate-600"} hover:border-slate-300 ${cur ? "ring-2 ring-sky-400" : ""}`}
        style={pos}>
        <Twist it={it} onFlip={onFlip} />
        <button className="flex h-full min-w-0 flex-1 items-center gap-1.5 pl-0.5 pr-2 text-left"
          title={`${displayName(it.id)}：${it.count} 人，點了進去`} onClick={() => enter(it.id)}>
          {it.id !== MACHINE && <Dot light={light} />}
          <BelowMark below={it.id === MACHINE ? room : belowOf(n)} names={names} />
          <span className={`min-w-0 flex-1 ${opts.over === "wrap" ? "line-clamp-2 break-all leading-4" : "overflow-hidden whitespace-nowrap"}`}>{opts.over === "wrap" ? it.name : fitName(it.name, it.w - 56, font)}</span>
          <span className="shrink-0 text-xs text-slate-500">{it.count}</span>
        </button>
      </div>
    );
  }
  return (
    <button data-multi={selected ? "1" : undefined} data-map={it.id} data-key={itemKey(it)} className={`absolute flex items-center gap-1.5 rounded px-2 text-left text-[13px]
        ${on ? "bg-slate-600 ring-2 ring-sky-400" : it.busy ? "bg-slate-700 hover:bg-slate-600" : "bg-slate-800 hover:bg-slate-700"}
        ${it.lead ? "font-semibold" : ""}`}
      style={pos} title={why} onClick={(e) => it.id === MACHINE && !e.ctrlKey && !e.metaKey && !e.shiftKey ? enter(MACHINE) : pickWith(e, it.id, order)}>
      {it.id === MACHINE ? <BelowMark below={room} /> : <Dot light={light} />}
      <span className={`min-w-0 ${opts.over === "wrap" ? "line-clamp-2 break-all leading-4" : "overflow-hidden whitespace-nowrap"}`}>{opts.over === "wrap" ? it.name : fitName(it.name, it.w - 26, font)}</span>
      {!!n?.asks && <span className="ml-auto shrink-0 text-xs text-sky-300">🔵{n.asks}</span>}
    </button>
  );
}

