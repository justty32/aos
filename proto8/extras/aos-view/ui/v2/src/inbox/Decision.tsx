// The answer page (P3; q1 a, q2 a, q3 a): the center 作答 tab while route.ask is set (it was docked on the right).
// One question at a time (route.q in the address bar), picking jumps to the next, the last step is an overview
// that sends; the plain-words line is open, "why recommended" is folded; the asker stays visible on the right.
// - It holds its own copy of the letter: a background update never swaps the card or clears what you typed;
//   if the letter left the to-do meanwhile, the card says so.
// - a / b / c … pick an option for the current question (outside inputs); 全照推薦 fills the recommended ones,
//   not offered when the letter is irreversible; Ctrl+Enter sends only from its own note box and never when irreversible.
// - Half-answered cards are kept per letter (aosview.ask:<letter>).
import { useEffect, useMemo, useRef, useState } from "react";
import type { Ask } from "../api/types.ts";
import { post } from "../api/client.ts";
import { pulseSoon } from "../api/poll.ts";
import { useData, useNow, answeredHere } from "../state/hooks.ts";
import { ui } from "../state/app.ts";
import { openAsk, setQuestion } from "../state/nav.ts";
import { useUi } from "../state/hooks.ts";
import { bind, isSubmit, pushOverlay } from "../input/keys.ts";
import { askOrder } from "../model/inbox.ts";
import { loadAsk, saveAsk, dropAsk, type AskDraft } from "../model/drafts.ts";
import { ago } from "../model/time.ts";

export function Decision({ letter }: { letter: string }) {
  const asks = useData((s) => s.asks);
  const now = useNow();
  const live = asks.find((a) => a.letter === letter) || null;
  const [snap, setSnap] = useState<Ask | null>(live);
  const [d, setD] = useState<AskDraft>(() => loadAsk(localStorage, letter));
  const cur = useUi((s) => s.route.q);
  const setCur = (i: number) => setQuestion(i);
  const [full, setFull] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [mode, setMode] = useState<"answer" | "reply">("answer");
  const saveT = useRef<ReturnType<typeof setTimeout> | null>(null);

  // a new letter = a new card; the same letter keeps its snapshot
  useEffect(() => { setSnap(asks.find((a) => a.letter === letter) || null); setD(loadAsk(localStorage, letter)); setMsg(null); setMode("answer"); setFull(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [letter]);
  useEffect(() => { if (!snap && live) setSnap(live); }, [live, snap]);
  useEffect(() => pushOverlay(() => openAsk(null)), []);

  const a = snap;
  const qs = a?.questions || [];
  const irreversible = a?.risk === "irreversible";
  const order = useMemo(() => asks.filter((x) => !answeredHere.has(x.letter) && !x.error).sort(askOrder), [asks]);
  const idx = order.findIndex((x) => x.letter === letter);
  const go = (step: number) => {
    if (!order.length) return;
    const nx = order[((idx < 0 ? 0 : idx + step) + order.length) % order.length];
    if (nx && nx.letter !== letter) openAsk(nx.letter);
  };

  const put = (p: Partial<AskDraft>) => {
    setD((old) => {
      const nd = { ...old, ...p };
      if (saveT.current) clearTimeout(saveT.current);
      saveT.current = setTimeout(() => saveAsk(localStorage, letter, nd, Date.now() / 1000), 300);
      return nd;
    });
  };
  const pick = (qid: string, key: string) => {
    put({ answers: { ...d.answers, [qid]: key } });
    const i = qs.findIndex((q) => q.id === qid);
    if (i >= 0) setCur(i + 1);                 // the next question; after the last one = the overview
  };
  const allRecommended = () => {
    const ans = { ...d.answers };
    for (const q of qs) if (q.recommend) ans[q.id] = q.recommend;
    put({ answers: ans });
    setCur(qs.length);
  };

  const send = async (what: "answer" | "reply" | "ok") => {
    if (!a || busy) return;
    setBusy(true); setMsg(null);
    const body = what === "answer" ? { letter, do: "answer", answers: d.answers, note: d.note } :
      what === "reply" ? { letter, do: "reply", text: d.text } : { letter, do: "ok" };
    const r = await post("/api/answer", body);
    setBusy(false);
    if (!r.ok) { setMsg({ ok: false, text: r.message || "送不出去" }); return; }
    answeredHere.add(letter);
    dropAsk(localStorage, letter);
    ui.set({ flash: r.message || "已送出" });
    pulseSoon();
    const rest = order.filter((x) => x.letter !== letter);
    openAsk(rest.length ? rest[Math.max(0, Math.min(idx, rest.length - 1))].letter : null);
  };

  // option keys (outside inputs): a/b/c… for the current question; [ ] = previous / next card
  useEffect(() => {
    if (!a) return;
    const q = qs[cur];
    const list = (q?.options || []).filter((o) => /^[a-z]$/.test(o.key)).map((o) => ({ key: o.key, zone: "global" as const, run: () => pick(q.id, o.key) }));
    return bind(list);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [a, cur, d.answers, order, letter]);

  const unanswered = qs.filter((q) => !d.answers[q.id]).length;
  const gone = !live && !!a;
  const atOverview = cur >= qs.length;
  const q = qs[Math.min(cur, qs.length - 1)];

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 items-center gap-2 border-b border-slate-800 px-4 py-1.5 text-xs text-slate-400">
        <span className="font-semibold text-sky-300">🔵 要你決定</span>
        {order.length > 1 && <span>這是第 {idx + 1} 封，共 {order.length} 封</span>}
        <button className="rounded px-1.5 hover:bg-slate-800 hover:text-slate-100" onClick={() => go(-1)}>‹ 上一封</button>
        <button className="rounded px-1.5 hover:bg-slate-800 hover:text-slate-100" onClick={() => go(1)}>下一封 ›</button>
        <button className="ml-auto rounded px-1.5 hover:bg-slate-800 hover:text-slate-100" onClick={() => openAsk(null)}>✕ 收起 Esc</button>
      </div>
      {!a && <p className="p-4 text-sm text-slate-400">這封信不在待辦裡（可能已經回過了）。</p>}
      {a && <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
        {gone && <p className="mb-2 rounded bg-amber-950 px-2 py-1 text-xs text-amber-200">這封已經不在待辦裡了（可能在別處回過）。送出會被擋下來，不會重複。</p>}
        <div className="flex flex-wrap items-center gap-1">
          {a.urgent && <span className="rounded bg-red-700 px-1 text-xs">急</span>}
          {irreversible && <span className="rounded bg-rose-800 px-1 text-xs">不可逆：請一題一題看</span>}
          <h3 className="text-base font-semibold">{a.title}</h3>
        </div>
        <p className="text-xs text-slate-400">{a.from || "?"}｜{ago(a.sent_at, now)}{a.deadline ? `｜期限 ${a.deadline}` : ""}{a.same > 1 ? `｜同樣的問了 ${a.same} 次` : ""}</p>
        {a.what && <>
          <p className={`mt-1 whitespace-pre-wrap break-words text-sm text-slate-300 ${full ? "" : "line-clamp-2"}`}>{a.what}</p>
          <button className="text-xs text-sky-300 hover:underline" onClick={() => setFull(!full)}>{full ? "收起" : "看全文"}</button>
        </>}
        {a.decide && !qs.length && <p className="mt-1 text-sm text-sky-100">要決定：{a.decide}</p>}

        {qs.length > 0 && mode === "answer" && <>
          <div className="mt-3 flex flex-wrap items-center gap-1">
            {qs.map((x, i) => (
              <button key={x.id} onClick={() => setCur(i)} title={x.question}
                className={`h-7 min-w-8 rounded px-2 text-xs ${i === cur ? "bg-sky-700 text-white" : d.answers[x.id] ? "bg-slate-700 text-slate-100" : "bg-slate-800 text-slate-400"}`}>
                {i + 1}{d.answers[x.id] ? ` ${d.answers[x.id]}` : ""}
              </button>
            ))}
            <button onClick={() => setCur(qs.length)}
              className={`h-7 rounded px-2 text-xs ${atOverview ? "bg-sky-700 text-white" : "bg-slate-800 text-slate-300"}`}>總覽{unanswered ? `（還有 ${unanswered} 題）` : " ✓"}</button>
          </div>
          {!atOverview && q && (
            <div className="mt-3 rounded-lg border border-sky-800 p-3">
              <div className="text-xs text-slate-500">第 {cur + 1} 題，共 {qs.length} 題</div>
              <div className="text-base font-medium">{q.question}</div>
              {q.eli5 && <div className="mt-1 text-sm text-slate-300">白話：{q.eli5}</div>}
              <div className="mt-2 space-y-1">
                {q.options.map((o) => {
                  const on = d.answers[q.id] === o.key;
                  return (
                    <button key={o.key} onClick={() => pick(q.id, o.key)}
                      className={`block w-full rounded px-3 py-1.5 text-left text-sm ${on ? "bg-sky-800 text-white" : "bg-slate-800 hover:bg-slate-700"}`}>
                      <kbd className="mr-1 text-xs text-slate-400">{o.key}</kbd>{o.label}
                      {q.recommend === o.key && <span className="ml-1 rounded bg-emerald-900 px-1 text-xs text-emerald-200">推薦</span>}
                      {o.consequence && <span className="block text-xs text-slate-400">→ {o.consequence}</span>}
                    </button>
                  );
                })}
              </div>
              {q.why && <details className="mt-2 text-xs text-slate-400"><summary className="cursor-pointer">為什麼推薦</summary><p className="mt-1">{q.why}</p></details>}
            </div>
          )}
          {atOverview && (
            <div className="mt-3 space-y-1">
              {qs.map((x, i) => {
                const k = d.answers[x.id];
                const o = x.options.find((y) => y.key === k);
                return (
                  <button key={x.id} onClick={() => setCur(i)} className="block w-full rounded bg-slate-900 px-3 py-1.5 text-left text-sm hover:bg-slate-800">
                    <span className="text-slate-400">{i + 1}. {x.question}</span>
                    <span className={`block ${k ? "text-slate-100" : "text-amber-300"}`}>{k ? `${k}　${o?.label || ""}` : "還沒選（點這裡回去選）"}</span>
                  </button>
                );
              })}
              <textarea value={d.note} onChange={(e) => put({ note: e.target.value })} rows={2} placeholder="備註（選填）"
                onKeyDown={(e) => { if (!irreversible && isSubmit(e.nativeEvent)) { e.preventDefault(); if (!unanswered) send("answer"); } }}
                className="w-full rounded bg-slate-800 p-1.5 text-sm" />
            </div>
          )}
        </>}

        {(!qs.length || mode === "reply") && (
          <div className="mt-3 space-y-1">
            <textarea value={d.text} onChange={(e) => put({ text: e.target.value })} rows={4} placeholder="回一段話給它"
              onKeyDown={(e) => { if (!irreversible && isSubmit(e.nativeEvent)) { e.preventDefault(); if (d.text.trim()) send("reply"); } }}
              className="w-full rounded bg-slate-800 p-1.5 text-sm" />
          </div>
        )}
      </div>}
      {a && (
        <div className="flex shrink-0 flex-wrap items-center gap-2 border-t border-slate-800 bg-slate-900 px-4 py-2">
          {qs.length > 0 && mode === "answer" ? <>
            {!irreversible && qs.some((x) => x.recommend) && (
              <button className="rounded bg-emerald-800 px-2 py-1 text-sm hover:bg-emerald-700" onClick={allRecommended}>全照推薦</button>
            )}
            <button disabled={busy || unanswered > 0} onClick={() => send("answer")}
              className="rounded bg-sky-700 px-3 py-1 text-sm font-medium hover:bg-sky-600 disabled:opacity-40">
              {busy ? "送出中…" : unanswered ? `還有 ${unanswered} 題` : irreversible ? "確定送出（不可逆）" : "送出"}
            </button>
            <button className="text-xs text-slate-400 hover:text-slate-100" onClick={() => setMode("reply")}>改用一段話回</button>
          </> : <>
            <button disabled={busy || !d.text.trim()} onClick={() => send("reply")} className="rounded bg-sky-700 px-3 py-1 text-sm hover:bg-sky-600 disabled:opacity-40">回覆</button>
            {!qs.length && <button disabled={busy} onClick={() => send("ok")} className="rounded bg-slate-700 px-3 py-1 text-sm hover:bg-slate-600">知道了</button>}
            {qs.length > 0 && <button className="text-xs text-slate-400 hover:text-slate-100" onClick={() => setMode("answer")}>回去選答案</button>}
          </>}
          {msg && <span className={`text-sm ${msg.ok ? "text-emerald-300" : "text-red-300"}`}>{msg.text}</span>}
        </div>
      )}
    </div>
  );
}
