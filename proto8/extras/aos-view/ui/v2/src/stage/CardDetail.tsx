// Expanded wall cards show full notes, status, last answers, and posted work without overflowing.
import type { AgentCard, Node, Tree } from "../api/types.ts";
import { useLive } from "../inspector/useLive.ts";
import { BoardFull } from "../inspector/BoardFull.tsx";
import { BelowMark } from "../shell/bits.tsx";
import { Clamp } from "../shell/Clamp.tsx";
import { belowOf } from "../model/lights.ts";
import { readBoard } from "../model/board.ts";
import { ago } from "../model/time.ts";
import { whyWord } from "../model/words.ts";
import { jump } from "../state/nav.ts";

function LastAnswer({ n }: { n: Node }) {
  const live = useLive<AgentCard>(n.kind === "agent" ? "/api/agent?name=" + encodeURIComponent(n.id) : null, ["tree"]);
  const text = live.data?.now.last_answer_full ?? live.data?.now.last_answer ?? n.last_answer;
  return text ? <div><div className="text-xs text-slate-500">最後一句話</div><Clamp node={n.id} id="wall:last" text={text} lines={8} cut={live.data?.now.last_answer_cut} /></div> : null;
}

export function DeptDetail({ n, tree, now }: { n: Node; tree: Tree; now: number }) {
  const board = readBoard(n.board, n.state, now);
  return <div data-chip className="space-y-2 border-t border-slate-700 pt-2 text-sm text-slate-300">
    {n.note && <div><div className="text-xs text-slate-500">主管說</div><Clamp node={n.id} id="wall:note" text={n.note.text} lines={6} /></div>}
    <BelowMark below={belowOf(n)} size="full" names={n.rollup.worst_ids?.filter((id) => id !== n.id)} />
    {(n.rollup.worst_ids || []).filter((id) => id !== n.id).slice(0, 3).map((id) => tree.nodes[id] && <button key={id} className="block w-full truncate text-left text-xs hover:underline" title={`${id}：${whyWord(tree.nodes[id].why)}`} onClick={() => jump(id, false)}>{id}：{whyWord(tree.nodes[id].why)}</button>)}
    <LastAnswer n={n} />
    {board?.raw.doing && <div>在做：<Clamp node={n.id} id="wall:doing" text={board.raw.doing} lines={4} /></div>}
    {board && board.waiting.length > 0 && <div><div className="text-xs text-slate-500">在等</div>{board.waiting.map((w, i) => <Clamp key={i} node={n.id} id={`wall:waiting:${i}`} text={`${w.who === "user" ? "等你" : w.who}：${w.what}`} lines={3} />)}</div>}
    {n.aide && <div className="text-xs text-slate-500">小助手 {n.aide.name}：心跳 {ago(n.aide.last_beat, now)}</div>}
  </div>;
}

export function PersonDetail({ n, now }: { n: Node; now: number }) {
  const board = readBoard(n.board, n.state, now);
  return <div data-chip className="space-y-2 border-t border-slate-700 pt-2 text-sm text-slate-300">
    <Clamp node={n.id} id="wall:why" text={whyWord(n.why_full ?? n.why)} lines={4} />
    <LastAnswer n={n} />
    {board && <BoardFull node={n.id} v={board} now={now} />}
    <div className="text-xs text-slate-500">信箱排著 {n.queued || 0} 則｜動靜 {ago(n.active_at, now)}</div>
  </div>;
}
