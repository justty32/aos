// Current agent details and department summary.
import type { AgentCard, Node, Tree } from "../api/types.ts";
import { belowOf } from "../model/lights.ts";
import { Clamp, MoreList } from "../shell/Clamp.tsx";
import { useLive } from "./useLive.ts";
import { BoardFull, Row } from "./BoardFull.tsx";
import { BelowMark, Dot, LIGHT_WORD, SectionTitle } from "../shell/bits.tsx";
import { readBoard, boardCounts } from "../model/board.ts";
import { ago, dayTime } from "../model/time.ts";
import { descendants, isDept } from "../model/tree.ts";
import { jump } from "../state/nav.ts";
import { stateWord, statusWord, whyWord } from "../model/words.ts";

function DeptSummary({ n, tree, now }: { n: Node; tree: Tree; now: number }) {
  const below = descendants(tree, n.id).map((k) => tree.nodes[k]).filter(Boolean);
  const bc = boardCounts([n, ...below], now);
  return (
    <>
      <SectionTitle>部門</SectionTitle>
      <Row k="底下">{n.rollup.nodes} 個（{n.children.length} 個直屬）</Row>
      <Row k="最差"><Clamp node={n.id} id="worst" lines={2} text={`${LIGHT_WORD[n.rollup.worst]}${n.rollup.why ? `：${whyWord(n.rollup.why)}` : ""}`} /></Row>
      <Row k="底下"><BelowMark below={belowOf(n)} size="full" names={n.rollup.worst_ids?.filter((id) => id !== n.id)} /></Row>
      {n.note && <Row k="主管說"><div title={n.note.on || ""}><Clamp node={n.id} id="note" lines={3} text={`「${n.note.text}」`} /></div><span className="text-xs text-slate-500">（{n.note.status}，{ago(n.note.at, now)}）</span></Row>}
      {n.aide && <Row k="小助手">{n.aide.name}：{n.aide.state || "?"}，心跳 {ago(n.aide.last_beat, now)}</Row>}
      {n.team_light && <Row k="隊燈"><Clamp node={n.id} id="team" lines={2} text={`${LIGHT_WORD[n.team_light.light]}：${whyWord(n.team_light.why)}`} /></Row>}
      {(bc.dnd > 0 || bc.waiting > 0) && <Row k="公告欄">{bc.dnd ? `${bc.dnd} 個請勿打擾 ` : ""}{bc.waiting ? `${bc.waiting} 個在等你` : ""}</Row>}
      {bc.waitingUser.length > 0 && (
        <div className="mt-1 rounded bg-sky-950/60 p-2 text-sm">
          <div className="text-xs text-sky-300">在等你的：</div>
          <MoreList node={n.id} id="waiting" items={bc.waitingUser} first={3} more="項" render={(w, i) => (
            <button key={i} className="block text-left hover:underline" onClick={() => jump(w.id)}>{w.id}：{w.what}<span className="text-xs text-slate-400">（{ago(w.since, now)}）</span></button>
          )} />
        </div>
      )}
      <SectionTitle>直屬</SectionTitle>
      <div className="space-y-0.5">
        <MoreList node={n.id} id="children" items={n.children.filter((id) => tree.nodes[id])} first={8} more="個" render={(id) => (
          <div key={id}><button className="flex w-full items-center gap-1.5 rounded px-1 py-0.5 text-left text-sm hover:bg-slate-800" onClick={() => jump(id, false)}>
            <Dot light={tree.nodes[id].light} size="sm" />
            <span className="truncate">{id}</span>{isDept(tree.nodes[id]) && <BelowMark below={belowOf(tree.nodes[id])} names={tree.nodes[id].rollup.worst_ids?.filter((k) => k !== id)} />}<span className="ml-auto truncate text-xs text-slate-500" title={tree.nodes[id].why}>{whyWord(tree.nodes[id].why)}</span>
          </button></div>
        )} />
      </div>
    </>
  );
}

export function AgentNow({ n, tree, now }: { n: Node; tree: Tree; now: number }) {
  const live = useLive<AgentCard>("/api/agent?name=" + encodeURIComponent(n.id), ["tree"]);
  const a = live.data;
  const last = a?.now.last_answer_full ?? a?.now.last_answer ?? n.last_answer;
  const bv = readBoard(n.board, n.state, now);
  return (
    <div className="space-y-1">
      {bv && <BoardFull v={bv} now={now} node={n.id} />}
      {isDept(n) && <DeptSummary n={n} tree={tree} now={now} />}
      <SectionTitle right={live.at ? <span className="normal-case">{ago(live.at, now)}讀的</span> : null}>它現在</SectionTitle>
      <Row k="狀態"><span title={`${n.state || "?"}${n.phase ? " / " + n.phase : ""}`}>{stateWord(n.state)}{n.phase && n.phase !== n.state ? `（${stateWord(n.phase)}）` : ""}</span>{n.busy ? `，正在 ${n.busy}` : ""}</Row>
      <Row k="信箱">{n.queued ? `排著 ${n.queued} 則` : "空"}</Row>
      <Row k="動靜">{ago(n.active_at, now)}</Row>
      {n.cooldown && <Row k="冷卻"><div className="text-amber-300"><Clamp node={n.id} id="cooldown" lines={2} text={`${n.cooldown.reason || n.cooldown.code || "冷卻中"}${n.cooldown.until ? `，到 ${dayTime(n.cooldown.until, now)}` : ""}`} /></div></Row>}
      {a && <>
        {a.now.memory_mb != null && <Row k="資源">{a.now.memory_mb} MB{a.now.up_min != null ? `，開了 ${a.now.up_min} 分` : ""}</Row>}
        {a.now.workspace && <Row k="工作區"><div className="truncate font-mono text-xs" title={a.now.workspace}>{a.now.workspace}</div></Row>}
      </>}
      {live.error && <div className="text-xs text-red-300"><Clamp node={n.id} id="liveerr" lines={2} text={`讀不到它的細節：${live.error}`} /></div>}
      {last && (
        <>
          <SectionTitle>最後一句話</SectionTitle>
          <div className="rounded bg-slate-900 p-2 text-sm text-slate-200"><Clamp node={n.id} id="last" lines={6} text={last} cut={a?.now.last_answer_cut} /></div>
        </>
      )}
      {a && a.mailbox.letters.length > 0 && (
        <>
          <SectionTitle>信箱裡等著的</SectionTitle>
          <div className="space-y-0.5 text-sm"><MoreList node={n.id} id="mailbox" items={a.mailbox.letters} first={3} more="封" render={(l, i) => (
            <div key={i}><div className="line-clamp-1" title={l.title}><span className="text-slate-400">{l.from}（{statusWord(l.status)}）：</span>{l.title}</div><span className="text-xs text-slate-500"> {ago(l.sent_at, now)}</span></div>
          )} /></div>
        </>
      )}
      {n.reports.length > 0 && (
        <>
          <SectionTitle>寄給上面的報告</SectionTitle>
          <div className="space-y-0.5 text-sm"><MoreList node={n.id} id="reports" items={n.reports} first={1} more="份" render={(r) => (
            <div key={r.letter}><div className="truncate" title={r.title}><span className="text-slate-400">{statusWord(r.status)}：</span>{r.title}<span className="text-xs text-slate-500"> {ago(r.sent_at, now)}</span></div>
              <Clamp node={n.id} id={`report:${r.letter}`} lines={3} text={r.what} /></div>
          )} /></div>
        </>
      )}
    </div>
  );
}

