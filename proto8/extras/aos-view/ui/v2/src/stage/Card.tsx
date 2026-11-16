// One card component for the wall (and later the map): lead desk, member, sub-department, machine room, proc, outside service.
import type { Node, Tree } from "../api/types.ts";
import { BelowMark, Dot } from "../shell/bits.tsx";
import { readBoard, boardCounts, MODE_WORD } from "../model/board.ts";
import { ago } from "../model/time.ts";
import { descendants, displayName, isDept, machineIds, machineRollup, MACHINE } from "../model/tree.ts";
import { pickWith } from "../state/multi.ts";
import { useUi } from "../state/hooks.ts";
import { enter, jump } from "../state/nav.ts";
import { belowOf, roomOf } from "../model/lights.ts";
import { DeptDetail, PersonDetail } from "./CardDetail.tsx";
import { cycle, levelOf, type Level } from "../model/wallDetail.ts";
import { wallDetail, setWallOne } from "../state/wallDetail.ts";
import { useStore } from "../state/store.ts";
import { whyWord } from "../model/words.ts";

export interface CardProps { tree: Tree; id: string; lead: boolean; selected: boolean; dim: boolean; now: number; order: string[] }

function Shell({ id, selected, dim, children, dept, level, order }: { order: string[]; id: string; selected: boolean; dim: boolean; dept: boolean; level: Level; children: React.ReactNode }) {
  const multi = useUi((s) => s.multi);
  const word = { fold: "折疊", simple: "簡單", detail: "詳細" };
  const symbol = { fold: "▁", simple: "▃", detail: "▇" };
  return (
    <div role="button" tabIndex={-1} data-card={id} data-level={level} data-multi={multi.includes(id) ? "1" : undefined}
      onClick={(e) => { if (!(e.target as HTMLElement).closest("[data-enter],[data-chip],[data-detail]")) pickWith(e, id, order); }}
      onDoubleClick={(e) => { if (!(e.target as HTMLElement).closest("[data-detail],[data-chip]")) dept && enter(id); }}
      className={`relative flex cursor-default select-none flex-col rounded-lg border text-left transition-opacity ${level === "fold" ? "h-9 justify-center px-2 pr-8" : "min-h-28 gap-1 p-2.5 pr-8"}
        ${selected || multi.includes(id) ? "border-sky-400 bg-slate-800 ring-1 ring-sky-400" : "border-slate-700 bg-slate-900 hover:border-slate-500"}
        ${dim ? "opacity-35" : ""}`}>
      <button data-detail className="absolute right-1 top-1 rounded px-1 text-xs text-slate-400 hover:bg-slate-700 hover:text-slate-100"
        title={`詳細度：${word[level]}（Tab 循環，o 詳細一點，c 折起）`} onClick={() => setWallOne(id, cycle(level, id === MACHINE ? "simple" : "detail"))}>{symbol[level]}</button>
      {children}
    </div>
  );
}

function BoardChip({ n, now }: { n: Node; now: number }) {
  const v = readBoard(n.board, n.state, now);
  if (!v) return null;   // 03 §12.4: the place is there; nothing posted = nothing shown
  return (
    <div data-chip className={`truncate rounded px-1.5 py-0.5 text-xs ${v.stale ? "bg-slate-800 text-slate-500" : v.mode === "dnd" ? "bg-rose-950 text-rose-200" : "bg-slate-800 text-slate-300"}`}
      title={v.raw.text || ""}>
      📋 {MODE_WORD[v.mode]}{v.raw.doing ? `：${v.raw.doing}` : v.raw.text ? `：${v.raw.text}` : ""}{v.waiting.length ? `｜等 ${v.waiting.length}` : ""}
    </div>
  );
}

function AlertChips({ tree, ids }: { tree: Tree; ids: string[] }) {
  // 12.8 #3: the worst 3 below, each one click away
  if (!ids.length) return null;
  return (
    <div className="flex flex-wrap gap-1">
      {ids.map((i) => tree.nodes[i] && (
        <button key={i} data-chip onClick={() => jump(i, false)} title={whyWord(tree.nodes[i].why)}
          className="flex max-w-full items-center gap-1 rounded bg-slate-800 px-1.5 py-0.5 text-xs hover:bg-slate-700">
          <Dot light={tree.nodes[i].light} size="sm" /><span className="truncate">{i}</span>
        </button>
      ))}
    </div>
  );
}

export function Card({ tree, id, lead, selected, dim, now, order }: CardProps) {
  const d = useStore(wallDetail, (s) => s.d);
  const level = levelOf(d, id, id === MACHINE ? "simple" : "detail");
  if (level === "fold") {
    const n = tree.nodes[id];
    if (id !== MACHINE && !n) return null;
    const dept = id === MACHINE || (isDept(n) && !lead);
    return <Shell id={id} selected={selected} dim={dim} dept={dept} level={level} order={order}>
      <div className="flex min-w-0 items-center gap-1.5 text-sm">
        {id === MACHINE ? <BelowMark below={roomOf({ rollup: machineRollup(tree) })} /> : <Dot light={n.light} title={whyWord(n.why)} />}
        {dept ? <button data-enter className="min-w-0 truncate font-semibold hover:underline" onClick={() => enter(id)}>{displayName(id)} ▸</button> : <span className="min-w-0 truncate font-semibold">{displayName(id)}</span>}
        {id !== MACHINE && dept && <BelowMark below={belowOf(n)} names={n.rollup.worst_ids?.filter((x) => x !== id)} />}
        {dept ? <span className="ml-auto shrink-0 text-xs text-slate-400">{id === MACHINE ? machineIds(tree).length : n.rollup.nodes} {id === MACHINE ? "個" : "人"}</span> : !!n.queued && <span className="ml-auto shrink-0 text-xs text-amber-300">✉{n.queued}</span>}
      </div>
    </Shell>;
  }
  if (id === MACHINE) {
    const r = machineRollup(tree);
    const ids = machineIds(tree);
    return (
      <Shell id={id} selected={selected} dim={dim} dept level={level} order={order}>
        <div className="flex items-center gap-2">
          <BelowMark below={roomOf({ rollup: r })} />
          <button data-enter className="font-semibold hover:underline" onClick={() => enter(MACHINE)}>機房 ▸</button>
          <span className="ml-auto text-xs text-slate-400">{r.nodes} 個</span>
        </div>
        <div className="flex flex-wrap gap-1">{ids.map((i) => <Dot key={i} light={tree.nodes[i].light} size="sm" title={i} />)}</div>
        <p className="text-xs text-slate-400">程序和外部服務</p>
        <AlertChips tree={tree} ids={ids.filter((i) => ["red", "yellow"].includes(tree.nodes[i].light)).slice(0, 3)} />
      </Shell>
    );
  }
  const n = tree.nodes[id];
  if (!n) return null;
  const dept = isDept(n) && !lead;
  if (dept) {
    const below = descendants(tree, id).map((k) => tree.nodes[k]).filter(Boolean);
    const bc = boardCounts([n, ...below], now);
    return (
      <Shell id={id} selected={selected} dim={dim} dept level={level} order={order}>
        <div className="flex items-center gap-2">
          <Dot light={n.light} title={whyWord(n.why)} />
          <button data-enter className="truncate font-semibold hover:underline" onClick={() => enter(id)}>{id} ▸</button>
          {n.aide && <span className="rounded bg-slate-800 px-1 text-xs text-slate-400" title={`小助手 ${n.aide.name}`}>助 {ago(n.aide.last_beat, now)}</span>}
          <span className="ml-auto text-xs text-slate-400">{n.rollup.nodes} 人</span>
        </div>
        <div className="flex flex-wrap gap-1">
          {n.children.slice(0, 24).map((c) => {
            const child = tree.nodes[c];
            if (!child) return null;
            const worst = belowOf(child).worst;
            const ring = worst === "red" ? "ring-red-500" : worst === "blue" ? "ring-sky-400" : "ring-amber-400";
            return <span key={c} className={`inline-flex rounded-full ${worst ? `ring-1 ring-offset-1 ring-offset-slate-900 ${ring}` : ""}`}><Dot light={child.light} size="sm" title={c} /></span>;
          })}
        </div>
        {n.note && <p className="line-clamp-2 text-xs text-slate-300" title="主管自己寫的">主管說：{n.note.text}</p>}
        <div className="flex items-center gap-2"><BelowMark below={belowOf(n)} size="full" names={n.rollup.worst_ids?.filter((id) => id !== n.id)} />
          {(bc.dnd > 0 || bc.waiting > 0) && <span className="text-xs text-slate-400">{bc.dnd ? `${bc.dnd} 隻請勿打擾 ` : ""}{bc.waiting ? `${bc.waiting} 隻在等你` : ""}</span>}
        </div>
        <AlertChips tree={tree} ids={(n.rollup.worst_ids || []).filter((x) => x !== id)} />
        {level === "detail" && <DeptDetail n={n} tree={tree} now={now} />}
      </Shell>
    );
  }
  const kindWord = n.kind === "external" ? "外部服務" : n.kind === "proc" ? "程序" : lead ? "主管" : null;
  return (
    <Shell id={id} selected={selected} dim={dim} dept={false} level={level} order={order}>
      <div className="flex items-center gap-2">
        <Dot light={n.light} title={whyWord(n.why)} />
        <span className="truncate font-semibold">{displayName(id)}</span>
        {kindWord && <span className="rounded bg-slate-800 px-1 text-xs text-slate-400">{kindWord}</span>}
        {n.queued ? <span className="ml-auto text-xs text-amber-300" title="信箱裡等著的">✉{n.queued}</span> : null}
      </div>
      <p className="line-clamp-2 text-xs text-slate-400" title={n.why}>{whyWord(n.why)}</p>
      {lead && n.note && <p className="line-clamp-2 text-xs text-slate-300" title="主管自己寫的">主管說：{n.note.text}</p>}
      {!lead && n.last_answer && <p className="line-clamp-2 text-xs text-slate-300" title="最後一句話">「{n.last_answer}」</p>}
      <BoardChip n={n} now={now} />
      {level === "detail" && <PersonDetail n={n} now={now} />}
      <div className="mt-auto text-xs text-slate-500">{n.kind === "external" ? `上次檢查 ${ago(n.active_at, now)}` : `動靜 ${ago(n.active_at, now)}`}</div>
    </Shell>
  );
}
