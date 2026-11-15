// The right column (02c §4): the selected thing (the answer page moved to the center, P3; the asker shows here):
// nothing = the company (or the machine room) at a glance; a department = its lead and what is below;
// an agent = tabs 現在 / 往來 / 做過・說過; a proc or outside service = what the tree knows.
import { useState } from "react";
import type { AgentCard, Node, Tree } from "../api/types.ts";
import { post } from "../api/client.ts";
import { pulseSoon } from "../api/poll.ts";
import { ui } from "../state/app.ts";
import { setRight } from "../state/layout.ts";
import { useData, useNow, useUi } from "../state/hooks.ts";
import { enter, jump, setTab } from "../state/nav.ts";
import type { Tab } from "../state/route.ts";
import { useLive } from "./useLive.ts";
import { Thread } from "./Thread.tsx";
import { Dot, LIGHT_WORD, SectionTitle } from "../shell/bits.tsx";
import { readBoard, boardCounts, MODE_WORD, type BoardView } from "../model/board.ts";
import { ago, dayTime, parseIso } from "../model/time.ts";
import { descendants, displayName, isDept, machineIds, MACHINE, soleRoot } from "../model/tree.ts";
import { stateWord, statusWord, whyWord } from "../model/words.ts";

function Row({ k, children }: { k: string; children: React.ReactNode }) {
  return <div className="flex gap-2 text-sm"><span className="w-16 shrink-0 text-slate-500">{k}</span><span className="min-w-0 break-words text-slate-200">{children}</span></div>;
}

export function BoardFull({ v, now }: { v: BoardView; now: number }) {
  const b = v.raw;
  return (
    <div className={`rounded-lg border p-2 text-sm ${v.stale ? "border-slate-700 text-slate-500" : v.mode === "dnd" ? "border-rose-800 bg-rose-950/40" : "border-slate-700 bg-slate-900"}`}>
      <div className="flex items-center gap-2">
        <span className="font-semibold">📋 公告欄：{MODE_WORD[v.mode]}</span>
        <span className="ml-auto text-xs text-slate-500">{v.stale ? "過期了（只當參考）" : `${ago(v.updated, now)}寫的`}{b.by === "auto" ? "・自動" : ""}{v.clockOdd ? "・對方時鐘快了" : ""}</span>
      </div>
      {b.text && <p className="mt-1 whitespace-pre-wrap break-words">{b.text}</p>}
      {b.doing && <Row k="在做">{b.doing}</Row>}
      {v.waiting.length > 0 && (
        <div className="mt-1">
          <div className="text-xs text-slate-400">在等：</div>
          <ul className="ml-3 list-disc">
            {v.waiting.map((w, i) => (
              <li key={i} className={w.who === "user" ? "text-sky-200" : ""}>
                {w.who === "user" ? "等你" : w.who}：{w.what}
                <span className="text-xs text-slate-500">（{ago(parseIso(w.since_at), now)}起{w.level === "urgent" ? "・急" : ""}）</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {(b.back_at || b.back_text) && <Row k="回來">{b.back_text || dayTime(parseIso(b.back_at), now)}{v.overdue && <span className="text-amber-300">（已經過了說好的時間）</span>}</Row>}
      {b.deputy && <Row k="找代理">{b.deputy}</Row>}
    </div>
  );
}

function Tabs({ tab, has }: { tab: Tab; has: Tab[] }) {
  const word: Record<Tab, string> = { now: "現在", thread: "往來", history: "做過・說過" };
  return (
    <div className="flex shrink-0 border-b border-slate-800">
      {has.map((t) => (
        <button key={t} onClick={() => setTab(t)}
          className={`flex-1 border-b-2 py-1.5 text-sm ${tab === t ? "border-sky-400 text-slate-100" : "border-transparent text-slate-400 hover:text-slate-200"}`}>{word[t]}</button>
      ))}
    </div>
  );
}

/** 11-15: a bare /compact (no prefix, no tail) for a claude / codex agent; refused while letters wait (they would batch). */
function CompactButton({ n }: { n: Node }) {
  const [busy, setBusy] = useState(false);
  if (n.kind !== "agent" || !n.live?.cli) return null;
  const waiting = n.queued || 0;
  const click = async () => {
    if (!confirm(`叫 ${n.id} 壓縮對話（/compact）？`)) return;
    setBusy(true);
    const r = await post("/api/compact", { name: n.id });
    setBusy(false);
    ui.set({ flash: r.ok ? r.message || "已送出" : `壓縮送不出去：${r.message}` });
    pulseSoon();
  };
  return (
    <button className="rounded bg-slate-800 px-2 py-0.5 text-xs hover:bg-slate-700 disabled:opacity-40" onClick={click}
      disabled={busy || waiting > 0}
      title={waiting > 0 ? `信箱還排著 ${waiting} 封，/compact 會跟它們併成一批而失效；等它讀完再按` : "送一句裸的 /compact，叫它壓縮對話"}>
      {busy ? "送出中…" : "🗜 壓縮"}
    </button>
  );
}

function Head({ n, tree }: { n: Node; tree: Tree }) {
  const dept = isDept(n);
  return (
    <div className="shrink-0 border-b border-slate-800 py-2 pl-3 pr-8">
      <div className="flex items-center gap-2">
        <Dot light={n.light} />
        <h2 className="truncate text-base font-semibold">{displayName(n.id)}</h2>
        <span className="text-xs text-slate-500">{n.kind === "agent" ? (dept ? "部門主管" : "員工") : n.kind === "proc" ? "程序" : "外部服務"}</span>
        <span className="ml-auto flex items-center gap-1">
          <CompactButton n={n} />
          {dept && <button className="rounded bg-slate-800 px-2 py-0.5 text-xs hover:bg-slate-700" onClick={() => enter(n.id)}>進部門 ▸</button>}
        </span>
      </div>
      <p className="mt-0.5 text-sm text-slate-300" title={n.why}>{LIGHT_WORD[n.light]}：{whyWord(n.why)}</p>
      {n.parent && tree.nodes[n.parent] && (
        <p className="text-xs text-slate-500">隸屬 <button className="hover:underline" onClick={() => jump(n.parent!, false)}>{n.parent}</button></p>
      )}
    </div>
  );
}

function DeptSummary({ n, tree, now }: { n: Node; tree: Tree; now: number }) {
  const below = descendants(tree, n.id).map((k) => tree.nodes[k]).filter(Boolean);
  const bc = boardCounts([n, ...below], now);
  const c = n.rollup.counts;
  return (
    <>
      <SectionTitle>部門</SectionTitle>
      <Row k="底下">{n.rollup.nodes} 個（{n.children.length} 個直屬）</Row>
      <Row k="最差">{LIGHT_WORD[n.rollup.worst]}{n.rollup.why ? `：${whyWord(n.rollup.why)}` : ""}</Row>
      {c && (c.red || c.blue || c.yellow) ? <Row k="燈">{c.red ? `出事 ${c.red} ` : ""}{c.blue ? `要決定 ${c.blue} ` : ""}{c.yellow ? `留意 ${c.yellow}` : ""}</Row> : null}
      {n.note && <Row k="主管說"><span title={n.note.on || ""}>「{n.note.text}」</span><span className="text-xs text-slate-500">（{n.note.status}，{ago(n.note.at, now)}）</span></Row>}
      {n.aide && <Row k="小助手">{n.aide.name}：{n.aide.state || "?"}，心跳 {ago(n.aide.last_beat, now)}</Row>}
      {n.team_light && <Row k="隊燈">{LIGHT_WORD[n.team_light.light]}：{whyWord(n.team_light.why)}</Row>}
      {(bc.dnd > 0 || bc.waiting > 0) && <Row k="公告欄">{bc.dnd ? `${bc.dnd} 個請勿打擾 ` : ""}{bc.waiting ? `${bc.waiting} 個在等你` : ""}</Row>}
      {bc.waitingUser.length > 0 && (
        <div className="mt-1 rounded bg-sky-950/60 p-2 text-sm">
          <div className="text-xs text-sky-300">在等你的：</div>
          {bc.waitingUser.map((w, i) => (
            <button key={i} className="block text-left hover:underline" onClick={() => jump(w.id)}>{w.id}：{w.what}<span className="text-xs text-slate-400">（{ago(w.since, now)}）</span></button>
          ))}
        </div>
      )}
      <SectionTitle>直屬</SectionTitle>
      <ul className="space-y-0.5">
        {n.children.map((id) => tree.nodes[id] && (
          <li key={id}><button className="flex w-full items-center gap-1.5 rounded px-1 py-0.5 text-left text-sm hover:bg-slate-800" onClick={() => jump(id, false)}>
            <Dot light={isDept(tree.nodes[id]) ? tree.nodes[id].rollup.worst : tree.nodes[id].light} size="sm" />
            <span className="truncate">{id}</span><span className="ml-auto truncate text-xs text-slate-500" title={tree.nodes[id].why}>{whyWord(tree.nodes[id].why)}</span>
          </button></li>
        ))}
      </ul>
    </>
  );
}

function AgentNow({ n, tree, now }: { n: Node; tree: Tree; now: number }) {
  const live = useLive<AgentCard>("/api/agent?name=" + encodeURIComponent(n.id), ["tree"]);
  const a = live.data;
  const bv = readBoard(n.board, n.state, now);
  return (
    <div className="space-y-1">
      {bv && <BoardFull v={bv} now={now} />}
      {isDept(n) && <DeptSummary n={n} tree={tree} now={now} />}
      <SectionTitle right={live.at ? <span className="normal-case">{ago(live.at, now)}讀的</span> : null}>它現在</SectionTitle>
      <Row k="狀態"><span title={`${n.state || "?"}${n.phase ? " / " + n.phase : ""}`}>{stateWord(n.state)}{n.phase && n.phase !== n.state ? `（${stateWord(n.phase)}）` : ""}</span>{n.busy ? `，正在 ${n.busy}` : ""}</Row>
      <Row k="信箱">{n.queued ? `排著 ${n.queued} 則` : "空"}</Row>
      <Row k="動靜">{ago(n.active_at, now)}</Row>
      {n.cooldown && <Row k="冷卻"><span className="text-amber-300">{n.cooldown.reason || n.cooldown.code || "冷卻中"}{n.cooldown.until ? `，到 ${dayTime(n.cooldown.until, now)}` : ""}</span></Row>}
      {a && <>
        {a.now.memory_mb != null && <Row k="資源">{a.now.memory_mb} MB{a.now.up_min != null ? `，開了 ${a.now.up_min} 分` : ""}</Row>}
        {a.now.workspace && <Row k="工作區"><span className="font-mono text-xs">{a.now.workspace}</span></Row>}
      </>}
      {live.error && <p className="text-xs text-red-300">讀不到它的細節：{live.error}</p>}
      {(a?.now.last_answer || n.last_answer) && (
        <>
          <SectionTitle>最後一句話</SectionTitle>
          <p className="whitespace-pre-wrap break-words rounded bg-slate-900 p-2 text-sm text-slate-200">{a?.now.last_answer || n.last_answer}</p>
        </>
      )}
      {a && a.mailbox.letters.length > 0 && (
        <>
          <SectionTitle>信箱裡等著的</SectionTitle>
          <ul className="space-y-0.5 text-sm">{a.mailbox.letters.map((l, i) => (
            <li key={i}><span className="text-slate-400">{l.from}（{statusWord(l.status)}）：</span>{l.title}<span className="text-xs text-slate-500"> {ago(l.sent_at, now)}</span></li>
          ))}</ul>
        </>
      )}
      {n.reports.length > 0 && (
        <>
          <SectionTitle>寄給上面的報告</SectionTitle>
          <ul className="space-y-0.5 text-sm">{n.reports.slice(0, 5).map((r) => (
            <li key={r.letter}><span className="text-slate-400">{statusWord(r.status)}：</span>{r.title}<span className="text-xs text-slate-500"> {ago(r.sent_at, now)}</span></li>
          ))}</ul>
        </>
      )}
    </div>
  );
}

function History({ n }: { n: Node }) {
  const live = useLive<AgentCard>("/api/agent?name=" + encodeURIComponent(n.id), ["tree"], 30000);
  if (live.error) return <p className="text-xs text-red-300">讀不到紀錄：{live.error}</p>;
  if (!live.data) return <p className="text-xs text-slate-400">讀取中…</p>;
  const h = [...live.data.history].reverse();
  return (
    <ul className="space-y-1.5">
      {h.map((x) => (
        <li key={x.line} className="rounded bg-slate-900 px-2 py-1 text-sm">
          <div className="text-xs text-slate-500">#{x.line} {x.role === "assistant" ? "它" : x.role === "user" ? "收到" : x.role}{x.tools.length ? `｜用了 ${x.tools.join("、")}` : ""}</div>
          <div className="line-clamp-6 whitespace-pre-wrap break-words text-slate-200">{x.text}</div>
        </li>
      ))}
      {!h.length && <p className="text-xs text-slate-500">沒有紀錄</p>}
    </ul>
  );
}

function Plain({ n, now }: { n: Node; now: number }) {
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

function Overview({ tree, focus, now }: { tree: Tree; focus: string | null; now: number }) {
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
        <Row k="我的公告">{board ? `${board.text}${board.back ? `（${board.back} 回）` : ""}` : "沒有"}</Row>
        {bc.waitingUser.length > 0 && <Row k="在等你">{bc.waitingUser.length} 件（它們的公告寫的）</Row>}
      </>}
      <SectionTitle>{focus === MACHINE ? "程序和外部服務" : "部門"}</SectionTitle>
      <ul className="space-y-0.5">
        {ids.map((id) => { const n = tree.nodes[id]; return n && (
          <li key={id}><button className="flex w-full items-center gap-1.5 rounded px-1 py-0.5 text-left text-sm hover:bg-slate-800" onClick={() => jump(id, false)}>
            <Dot light={isDept(n) ? n.rollup.worst : n.light} size="sm" /><span className="truncate">{id}</span>
            <span className="ml-auto truncate text-xs text-slate-500">{isDept(n) ? `${n.rollup.nodes} 人` : whyWord(n.why)}</span>
          </button></li>); })}
      </ul>
      {focus !== MACHINE && relay.length > 0 && <>
        <SectionTitle>最近寄給你的</SectionTitle>
        <ul className="space-y-0.5 text-sm">{relay.slice(0, 8).map((l) => (
          <li key={l.letter}><button className="w-full text-left hover:underline" onClick={() => tree.nodes[l.from] && jump(l.from)}>
            <span className="text-slate-400">{l.from}：</span>{l.title}<span className="text-xs text-slate-500"> {ago(l.sent_at, now)}</span></button></li>
        ))}</ul>
      </>}
      <p className="pt-3 text-xs text-slate-500">點中間的格子看細節；在下面打字就是對選到的那個說話。</p>
    </div>
  );
}

export function Inspector() {
  const tree = useData((s) => s.tree);
  const route = useUi((s) => s.route);
  const now = useNow();
  const n = tree && route.sel ? tree.nodes[route.sel] : undefined;
  let body: React.ReactNode;
  if (!tree) body = <p className="p-3 text-sm text-slate-400">讀取中…</p>;
  else if (!route.sel) body = <Overview tree={tree} focus={route.focus} now={now} />;
  else if (!n) body = (
    <div className="flex min-h-0 flex-1 flex-col p-3">
      <p className="mb-2 text-sm text-amber-300">{route.sel} 已經不在樹上了（可能收隊了）。</p>
      <Thread name={route.sel} />
    </div>
  );
  else if (n.kind !== "agent") body = <><Head n={n} tree={tree} /><Plain n={n} now={now} /></>;
  else body = (
    <>
      <Head n={n} tree={tree} />
      <Tabs tab={route.tab} has={["now", "thread", "history"]} />
      <div className={`flex min-h-0 flex-1 flex-col p-3 ${route.tab === "thread" ? "" : "overflow-y-auto"}`}>
        {route.tab === "now" && <AgentNow key={n.id} n={n} tree={tree} now={now} />}
        {route.tab === "thread" && <Thread key={n.id} name={n.id} />}
        {route.tab === "history" && <History key={n.id} n={n} />}
      </div>
    </>
  );
  return (
    <section data-zone="inspector" tabIndex={-1} className="relative flex min-h-0 flex-1 flex-col border-l border-slate-800 bg-slate-900/60 focus-within:ring-1 focus-within:ring-sky-700">
      <button className="absolute right-1 top-1 z-10 rounded px-1.5 text-slate-400 hover:bg-slate-800 hover:text-slate-100" title="收起右欄（]）；打的字留著"
        onClick={() => setRight(false)}>»</button>
      <div className="flex min-h-0 flex-1 flex-col">{body}</div>
    </section>
  );
}
