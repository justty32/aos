// The center 待辦 tab (02f §1.2; was the left column in 02c §2): 待辦 (four kinds, one queue), 追蹤 (everything sent, where it is), 已處理 (answered here).
import { useEffect, useMemo, useState } from "react";
import { data, ui } from "../state/app.ts";
import { useData, useInbox, useNow, useUi } from "../state/hooks.ts";
import { jump, openAsk, select } from "../state/nav.ts";
import { dismiss, markSeen } from "../api/poll.ts";
import { bind } from "../input/keys.ts";
import { trackOrder, waitReason, type Todo, type TodoKind } from "../model/inbox.ts";
import { ago, dayTime } from "../model/time.ts";
import { Dot, Steps } from "../shell/bits.tsx";
import type { OutItem } from "../api/types.ts";

const KIND_HEAD: Record<TodoKind, string> = { ask: "🔵 要你決定", red: "🔴 出事", reply: "✉ 回了話", wait: "⏳ 等很久" };

export function openTodo(t: Todo) {
  if (t.kind === "ask") {
    if (t.node) jump(t.node, false);      // the card takes the keys, not the composer
    openAsk(t.letter || null);
    return;
  }
  if (t.kind === "reply") markSeen([t.key]);              // an explicit open (12.8 #6)
  if (t.node) {
    jump(t.node);
    if (t.kind !== "red") select(t.node, "thread");
  }
}

function TodoRow({ t, active, now }: { t: Todo; active: boolean; now: number }) {
  return (
    <li className={`group rounded px-2 py-1.5 ${active ? "bg-slate-700" : "hover:bg-slate-800"}`}>
      <button className="block w-full text-left" onClick={() => openTodo(t)}>
        <div className="flex items-center gap-1 text-sm">
          {t.urgent && <span className="rounded bg-red-700 px-1 text-[10px]">急</span>}
          <span className="line-clamp-2">{t.title}</span>
        </div>
        <div className="text-xs text-slate-400">{t.sub}{t.sub ? "｜" : ""}{ago(t.at, now)}</div>
      </button>
      {t.canDismiss && (
        <button className="hidden text-xs text-slate-400 hover:text-slate-100 group-hover:inline"
          onClick={() => dismiss(t.key)}>{t.kind === "wait" ? "不等了" : "知道了"}</button>
      )}
    </li>
  );
}

function TodoList() {
  const { todo } = useInbox();
  const filter = useUi((s) => s.filter);
  const tree = useData((s) => s.tree);
  const now = useNow();
  const [cur, setCur] = useState(0);
  const shown = useMemo(() => todo.filter((t) =>
    !filter || (filter === "ask" && t.kind === "ask") || (filter === "red" && t.kind === "red") ||
    (filter === "reply" && (t.kind === "reply" || t.kind === "wait"))), [todo, filter]);
  useEffect(() => bind([
    { key: "ArrowDown", zone: "inbox", run: () => setCur((c) => Math.min(c + 1, shown.length - 1)) },
    { key: "j", zone: "inbox", run: () => setCur((c) => Math.min(c + 1, shown.length - 1)) },
    { key: "ArrowUp", zone: "inbox", run: () => setCur((c) => Math.max(c - 1, 0)) },
    { key: "k", zone: "inbox", run: () => setCur((c) => Math.max(c - 1, 0)) },
    { key: "Enter", zone: "inbox", run: () => shown[cur] && openTodo(shown[cur]) },
  ]), [shown, cur]);

  if (filter === "yellow") {
    const ys = tree ? Object.values(tree.nodes).filter((n) => n.light === "yellow" || n.team_light?.light === "yellow") : [];
    return (
      <ul className="space-y-0.5">
        <li className="px-2 text-xs text-slate-400">黃燈不進待辦，這裡只是列出來（02c §2）</li>
        {ys.map((n) => (
          <li key={n.id}><button className="w-full rounded px-2 py-1 text-left hover:bg-slate-800" onClick={() => jump(n.id)}>
            <div className="flex items-center gap-1 text-sm"><Dot light="yellow" />{n.id}</div>
            <div className="text-xs text-slate-400">{n.light === "yellow" ? n.why : n.team_light?.why}</div>
          </button></li>
        ))}
        {!ys.length && <li className="px-2 text-sm text-slate-500">沒有黃燈</li>}
      </ul>
    );
  }
  if (!shown.length) return <p className="px-2 py-6 text-center text-sm text-slate-500">{filter ? "這一種沒有待辦" : "沒有要你處理的事"}</p>;
  let lastKind: TodoKind | null = null;
  return (
    <ul className="space-y-0.5">
      {shown.map((t, i) => {
        const head = t.kind !== lastKind ? KIND_HEAD[t.kind] : null;
        lastKind = t.kind;
        return [
          head && <li key={"h" + t.kind} className="flex items-center px-2 pt-2 text-xs font-semibold text-slate-400">{head}
            {t.kind === "reply" && shown.filter((x) => x.kind === "reply").length > 1 && (
              <button className="ml-auto font-normal text-slate-500 hover:text-slate-200"
                onClick={() => markSeen(shown.filter((x) => x.kind === "reply").map((x) => x.key))}>全部看過</button>
            )}</li>,
          <TodoRow key={t.key} t={t} active={i === cur} now={now} />,
        ];
      })}
    </ul>
  );
}

function TrackRow({ o, now }: { o: OutItem; now: number }) {
  const tree = useData((s) => s.tree);
  const why = waitReason(o, tree, now);
  return (
    <li className="group rounded px-2 py-1.5 hover:bg-slate-800">
      <button className="block w-full text-left" onClick={() => tree?.nodes[o.to] && (jump(o.to), select(o.to, "thread"))}>
        <div className="text-sm">
          <span className="text-slate-400">給 {o.to}{o.kind === "order" ? "（指令）" : o.kind === "say" ? "（說話）" : ""}：</span>
          <span className="line-clamp-1">{o.title}</span>
        </div>
        <Steps it={o} compact />
        {why && <div className="text-xs text-amber-300">⏳ {why}</div>}
        {o.correction_of && <div className="text-xs text-slate-400">更正 {o.correction_of}</div>}
        <div className="text-xs text-slate-500">{dayTime(o.sent_at, now)}{o.batch ? `｜一批 ${o.batch}` : ""}{o.gone ? "｜對方已收隊" : ""}</div>
      </button>
      {!o.reply && <button className="hidden text-xs text-slate-400 hover:text-slate-100 group-hover:inline" onClick={() => dismiss("wait:" + o.letter)}>不等了</button>}
    </li>
  );
}

function Track() {
  const outbox = useData((s) => s.outbox);
  const tree = useData((s) => s.tree);
  const seen = useData((s) => s.seen);
  const dismissed = useData((s) => s.dismissed);
  const checked = useData((s) => s.outboxChecked);
  const now = useNow();
  // closed = replied and the reply seen, or "不等了"
  const open = trackOrder(outbox.filter((o) => !(o.reply && seen["in:" + o.reply.letter]) && !dismissed["wait:" + o.letter] && o.followed), tree, now);
  return (
    <div>
      <p className="px-2 pb-1 text-xs text-slate-500">送出後 7 天內、還沒結案的。狀態上次查：{checked ? ago(checked, now) : "還沒查"}</p>
      <ul className="space-y-0.5">{open.map((o) => <TrackRow key={o.letter} o={o} now={now} />)}</ul>
      {!open.length && <p className="px-2 py-6 text-center text-sm text-slate-500">沒有還在等的</p>}
    </div>
  );
}

function Done() {
  const answered = useData((s) => s.answered);
  const now = useNow();
  return (
    <ul className="space-y-1">
      {answered.map((a) => (
        <li key={a.letter + a.at} className="rounded px-2 py-1.5 hover:bg-slate-800">
          <div className="text-sm">{a.from || "?"}：{a.title || a.letter}</div>
          <div className="text-xs text-slate-400">{a.do === "answer" ? `選了 ${a.answers.join(" ")}` : a.do === "reply" ? "回了一段話" : "知道了"}｜{ago(a.at, now)}</div>
          {a.corrections.length > 0 && <div className="text-xs text-amber-300">已更正 {a.corrections.length} 次</div>}
          {a.from && (
            <button className="text-xs text-sky-300 hover:underline" onClick={() => {
              if (data.get().tree?.nodes[a.from!]) jump(a.from!);
              ui.set({ prefill: { target: a.from!, mode: "mail", mailTitle: `更正：${a.title || a.letter}`, correctionOf: a.letter, n: Date.now() } });
            }}>寄更正</button>
          )}
        </li>
      ))}
      {!answered.length && <p className="px-2 py-6 text-center text-sm text-slate-500">24 小時內沒有在這一頁回答過</p>}
    </ul>
  );
}

export function Inbox() {
  const tab = useUi((s) => s.inboxTab);
  const { todo } = useInbox();
  const outbox = useData((s) => s.outbox);
  const answered = useData((s) => s.answered);
  const seen = useData((s) => s.seen);
  const tabBtn = (t: typeof tab, label: string, n: number) => (
    <button onClick={() => ui.set({ inboxTab: t })}
      className={`flex-1 border-b-2 py-1.5 text-sm ${tab === t ? "border-sky-400 text-slate-100" : "border-transparent text-slate-400 hover:text-slate-200"}`}>
      {label} {n}
    </button>
  );
  const tracking = outbox.filter((o) => o.followed && !(o.reply && seen["in:" + o.reply.letter])).length;
  return (
    <div data-zone="inbox" tabIndex={-1} className="flex min-h-0 flex-1 flex-col focus-within:ring-1 focus-within:ring-sky-700">
      <div className="flex shrink-0">{tabBtn("todo", "待辦", todo.length)}{tabBtn("track", "追蹤", tracking)}{tabBtn("done", "已處理", answered.length)}</div>
      <div className="min-h-0 flex-1 overflow-y-auto p-1" tabIndex={0}>
        {tab === "todo" ? <TodoList /> : tab === "track" ? <Track /> : <Done />}
      </div>
    </div>
  );
}
