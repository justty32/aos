// Company overview and details for non-agent nodes.
import type { Node, Tree } from "../api/types.ts";
import { useData } from "../state/hooks.ts";
import { belowOf } from "../model/lights.ts";
import { Clamp } from "../shell/Clamp.tsx";
import { Row } from "./BoardFull.tsx";
import { BelowMark, Dot, SectionTitle } from "../shell/bits.tsx";
import { boardCounts } from "../model/board.ts";
import { ago } from "../model/time.ts";
import { isDept, machineIds, MACHINE, soleRoot } from "../model/tree.ts";
import { jump } from "../state/nav.ts";
import { stateWord, whyWord } from "../model/words.ts";

export function Plain({ n, now }: { n: Node; now: number }) {
  return (
    <div className="space-y-1 p-3">
      <Row k="狀態"><span title={n.state || "?"}>{stateWord(n.state)}</span></Row>
      <Row k="動靜">{ago(n.active_at, now)}</Row>
      {n.ext && <><Row k="網址"><span className="font-mono text-xs">{n.ext.url}</span></Row>
        {n.ext.listen && <Row k="聽">{n.ext.listen.join("、")}</Row>}</>}
      {n.tags.length > 0 && <Row k="標籤">{n.tags.join("、")}</Row>}
      <p className="pt-2 text-xs text-slate-500">{n.kind === "external" ? "外部服務只看得到檢查結果，不能說話。" : "程序不收話；要動它請找它的主管。"}</p>
    </div>
  );
}

export function Overview({ tree, focus, now }: { tree: Tree; focus: string | null; now: number }) {
  const board = useData((s) => s.board);
  const relay = useData((s) => s.relay);
  const one = soleRoot(tree);
  const ids = focus === MACHINE ? machineIds(tree) : one ? [one, ...tree.nodes[one].children] : tree.roots.filter((r) => tree.nodes[r]?.kind === "agent");
  const all = Object.values(tree.nodes);
  const bc = boardCounts(all, now);
  return (
    <div className="space-y-1 overflow-y-auto p-3">
      <h2 className="text-base font-semibold">{focus === MACHINE ? "機房" : "公司全景"}</h2>
      {focus !== MACHINE && <>
        <Row k="規模">{all.filter((n) => n.kind === "agent").length} 個 agent，{tree.llm_workers} 個在用模型</Row>
        <Row k="我的公告"><Clamp node="company" id="myboard" lines={2} text={board ? `${board.text}${board.back ? `（${board.back} 回）` : ""}` : "沒有"} /></Row>
        {bc.waitingUser.length > 0 && <Row k="在等你">{bc.waitingUser.length} 件（它們的公告寫的）</Row>}
      </>}
      <SectionTitle>{focus === MACHINE ? "程序和外部服務" : "部門"}</SectionTitle>
      <ul className="space-y-0.5">
        {ids.map((id) => { const n = tree.nodes[id]; return n && (
          <li key={id}><button className="flex w-full items-center gap-1.5 rounded px-1 py-0.5 text-left text-sm hover:bg-slate-800" onClick={() => jump(id, false)}>
            <Dot light={n.light} size="sm" /><span className="truncate">{id}</span>{isDept(n) && <BelowMark below={belowOf(n)} names={n.rollup.worst_ids?.filter((k) => k !== id)} />}
            <span className="ml-auto truncate text-xs text-slate-500">{isDept(n) ? `${n.rollup.nodes} 人` : whyWord(n.why)}</span>
          </button></li>); })}
      </ul>
      {focus !== MACHINE && relay.length > 0 && <>
        <SectionTitle>最近寄給你的</SectionTitle>
        <ul className="space-y-0.5 text-sm">{relay.slice(0, 8).map((l) => (
          <li key={l.letter}><button className="line-clamp-1 w-full text-left hover:underline" title={l.title} onClick={() => tree.nodes[l.from] && jump(l.from)}>
            <span className="text-slate-400">{l.from}：</span>{l.title}<span className="text-xs text-slate-500"> {ago(l.sent_at, now)}</span></button></li>
        ))}</ul>
      </>}
      <p className="pt-3 text-xs text-slate-500">點中間的格子看細節；在下面打字就是對選到的那個說話。</p>
    </div>
  );
}

