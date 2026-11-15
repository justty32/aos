// One card component for the wall (and later the map): lead desk, member, sub-department, machine room, proc, outside service.
import type { Node, Tree } from "../api/types.ts";
import { Dot, LIGHT_BG } from "../shell/bits.tsx";
import { readBoard, boardCounts, MODE_WORD } from "../model/board.ts";
import { ago } from "../model/time.ts";
import { descendants, displayName, isDept, machineIds, machineRollup, MACHINE } from "../model/tree.ts";
import { enter, jump, select } from "../state/nav.ts";

export interface CardProps { tree: Tree; id: string; lead: boolean; selected: boolean; dim: boolean; now: number }

function Shell({ id, selected, dim, children, dept }: { id: string; selected: boolean; dim: boolean; dept: boolean; children: React.ReactNode }) {
  return (
    <div role="button" tabIndex={-1} data-card={id}
      onClick={(e) => { if (!(e.target as HTMLElement).closest("[data-enter],[data-chip]")) select(id === MACHINE ? null : id); }}
      onDoubleClick={() => dept && enter(id)}
      className={`relative flex min-h-28 cursor-default flex-col gap-1 rounded-lg border p-2.5 text-left transition-opacity
        ${selected ? "border-sky-400 bg-slate-800 ring-1 ring-sky-400" : "border-slate-700 bg-slate-900 hover:border-slate-500"}
        ${dim ? "opacity-35" : ""}`}>
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
        <button key={i} data-chip onClick={() => jump(i, false)} title={tree.nodes[i].why}
          className="flex max-w-full items-center gap-1 rounded bg-slate-800 px-1.5 py-0.5 text-xs hover:bg-slate-700">
          <Dot light={tree.nodes[i].light} size="sm" /><span className="truncate">{i}</span>
        </button>
      ))}
    </div>
  );
}

function Counts({ c }: { c?: { red: number; yellow: number; blue: number } }) {
  if (!c || !(c.red || c.yellow || c.blue)) return null;
  return (
    <span className="text-xs text-slate-300">
      {c.red ? <span className="text-red-400">🔴{c.red} </span> : null}
      {c.blue ? <span className="text-sky-300">🔵{c.blue} </span> : null}
      {c.yellow ? <span className="text-amber-300">🟡{c.yellow}</span> : null}
    </span>
  );
}

export function Card({ tree, id, lead, selected, dim, now }: CardProps) {
  if (id === MACHINE) {
    const r = machineRollup(tree);
    const ids = machineIds(tree);
    return (
      <Shell id={id} selected={selected} dim={dim} dept>
        <div className="flex items-center gap-2">
          <Dot light={r.worst} />
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
      <Shell id={id} selected={selected} dim={dim} dept>
        <div className="flex items-center gap-2">
          <Dot light={n.rollup.worst} title={n.rollup.why} />
          <button data-enter className="truncate font-semibold hover:underline" onClick={() => enter(id)}>{id} ▸</button>
          {n.aide && <span className="rounded bg-slate-800 px-1 text-[10px] text-slate-400" title={`小助手 ${n.aide.name}`}>助 {ago(n.aide.last_beat, now)}</span>}
          <span className="ml-auto text-xs text-slate-400">{n.rollup.nodes} 人</span>
        </div>
        <div className="flex flex-wrap gap-1">
          {n.children.slice(0, 24).map((c) => tree.nodes[c] && <span key={c} className={`h-2 w-2 rounded-full ${LIGHT_BG[tree.nodes[c].rollup.worst]}`} title={c} />)}
        </div>
        {n.note && <p className="line-clamp-2 text-xs text-slate-300" title="隊長原話">留話：{n.note.text}</p>}
        <div className="flex items-center gap-2"><Counts c={n.rollup.counts} />
          {(bc.dnd > 0 || bc.waiting > 0) && <span className="text-xs text-slate-400">{bc.dnd ? `${bc.dnd} 隻請勿打擾 ` : ""}{bc.waiting ? `${bc.waiting} 隻在等人` : ""}</span>}
        </div>
        <AlertChips tree={tree} ids={(n.rollup.worst_ids || []).filter((x) => x !== id)} />
      </Shell>
    );
  }
  const kindWord = n.kind === "external" ? "外部服務" : n.kind === "proc" ? "程序" : lead ? "主管桌" : null;
  return (
    <Shell id={id} selected={selected} dim={dim} dept={false}>
      <div className="flex items-center gap-2">
        <Dot light={n.light} title={n.why} />
        <span className="truncate font-semibold">{displayName(id)}</span>
        {kindWord && <span className="rounded bg-slate-800 px-1 text-[10px] text-slate-400">{kindWord}</span>}
        {n.queued ? <span className="ml-auto text-xs text-amber-300" title="信箱裡等著的">✉{n.queued}</span> : null}
      </div>
      <p className="line-clamp-2 text-xs text-slate-400">{n.why}</p>
      {lead && n.note && <p className="line-clamp-2 text-xs text-slate-300" title="隊長原話">留話：{n.note.text}</p>}
      {!lead && n.last_answer && <p className="line-clamp-2 text-xs text-slate-300" title="最後一句話">「{n.last_answer}」</p>}
      <BoardChip n={n} now={now} />
      <div className="mt-auto text-[11px] text-slate-500">{n.kind === "external" ? `上次檢查 ${ago(n.active_at, now)}` : `動靜 ${ago(n.active_at, now)}`}</div>
    </Shell>
  );
}
