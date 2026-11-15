// The decision card (02c §4.3, 12.8 #1): docked on top of the right column while route.ask is set.
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
import { openAsk } from "../state/nav.ts";
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
  const [cur, setCur] = useState(0);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [mode, setMode] = useState<"answer" | "reply">("answer");
  const saveT = useRef<ReturnType<typeof setTimeout> | null>(null);

  // a new letter = a new card; the same letter keeps its snapshot
  useEffect(() => { setSnap(asks.find((a) => a.letter === letter) || null); setD(loadAsk(localStorage, letter)); setCur(0); setMsg(null); setMode("answer");
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
    if (i >= 0 && i < qs.length - 1) setCur(i + 1);
  };
  const allRecommended = () => {
    const ans = { ...d.answers };
    for (const q of qs) if (q.recommend) ans[q.id] = q.recommend;
    put({ answers: ans });
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

  return (
    <div className="max-h-[65vh] shrink-0 overflow-y-auto border-b-2 border-sky-700 bg-slate-900 p-3">
      <div className="mb-1 flex items-center gap-2 text-xs text-slate-400">
        <span className="font-semibold text-sky-300">🔵 要你決定</span>
        {order.length > 1 && <span>{idx + 1}/{order.length}</span>}
        <button className="hover:text-slate-100" onClick={() => go(-1)} title="上一張">‹</button>
        <button className="hover:text-slate-100" onClick={() => go(1)} title="下一張">›</button>
        <button className="ml-auto hover:text-slate-100" onClick={() => openAsk(null)}>收起 Esc</button>
      </div>
      {!a && <p className="text-sm text-slate-400">這封信不在待辦裡（可能已經回過了）。</p>}
      {a && <>
        {gone && <p className="mb-1 rounded bg-amber-950 px-2 py-1 text-xs text-amber-200">這封已經不在待辦裡了（可能在別處回過）。送出會被擋下來，不會重複。</p>}
        <div className="flex flex-wrap items-center gap-1">
          {a.urgent && <span className="rounded bg-red-700 px-1 text-[10px]">急</span>}
          {irreversible && <span className="rounded bg-rose-800 px-1 text-[10px]">不可逆：請一題一題看</span>}
          <h3 className="font-semibold">{a.title}</h3>
        </div>
        <p className="text-xs text-slate-400">{a.from || "?"}｜{ago(a.sent_at, now)}{a.deadline ? `｜期限 ${a.deadline}` : ""}{a.same > 1 ? `｜同樣的問了 ${a.same} 次` : ""}</p>
        {a.what && <p className="mt-1 line-clamp-6 whitespace-pre-wrap break-words text-sm text-slate-300" title={a.what}>{a.what}</p>}
        {a.decide && !qs.length && <p className="mt-1 text-sm text-sky-100">要決定：{a.decide}</p>}

        {qs.length > 0 && mode === "answer" && (
          <div className="mt-2 space-y-2">
            {qs.map((q, i) => (
              <div key={q.id} className={`rounded border p-2 ${i === cur ? "border-sky-600" : "border-slate-700"}`} onClick={() => setCur(i)}>
                <div className="text-sm font-medium">{q.id}. {q.question}</div>
                {q.eli5 && <div className="text-xs text-slate-400">白話：{q.eli5}</div>}
                <div className="mt-1 space-y-0.5">
                  {q.options.map((o) => {
                    const on = d.answers[q.id] === o.key;
                    return (
                      <button key={o.key} onClick={(e) => { e.stopPropagation(); pick(q.id, o.key); }}
                        className={`block w-full rounded px-2 py-1 text-left text-sm ${on ? "bg-sky-800 text-white" : "bg-slate-800 hover:bg-slate-700"}`}>
                        <kbd className="mr-1 text-xs text-slate-400">{o.key}</kbd>{o.label}
                        {q.recommend === o.key && <span className="ml-1 rounded bg-emerald-900 px-1 text-[10px] text-emerald-200">推薦</span>}
                        {o.consequence && <span className="block text-xs text-slate-400">→ {o.consequence}</span>}
                      </button>
                    );
                  })}
                </div>
                {q.why && <div className="mt-1 text-xs text-slate-500">推薦的理由：{q.why}</div>}
              </div>
            ))}
            <textarea value={d.note} onChange={(e) => put({ note: e.target.value })} rows={2} placeholder="備註（選填）"
              onKeyDown={(e) => { if (!irreversible && isSubmit(e.nativeEvent)) { e.preventDefault(); if (!unanswered) send("answer"); } }}
              className="w-full rounded bg-slate-800 p-1.5 text-sm" />
            <div className="flex flex-wrap items-center gap-2">
              {!irreversible && qs.some((q) => q.recommend) && (
                <button className="rounded bg-emerald-800 px-2 py-1 text-sm hover:bg-emerald-700" onClick={allRecommended}>全照推薦</button>
              )}
              <button disabled={busy || unanswered > 0} onClick={() => send("answer")}
                className="rounded bg-sky-700 px-3 py-1 text-sm font-medium hover:bg-sky-600 disabled:opacity-40">
                {busy ? "送出中…" : unanswered ? `還有 ${unanswered} 題` : irreversible ? "確定送出（不可逆）" : "送出"}
              </button>
              <button className="text-xs text-slate-400 hover:text-slate-100" onClick={() => setMode("reply")}>改用一段話回</button>
            </div>
          </div>
        )}

        {(!qs.length || mode === "reply") && (
          <div className="mt-2 space-y-1">
            <textarea value={d.text} onChange={(e) => put({ text: e.target.value })} rows={3} placeholder="回一段話給它"
              onKeyDown={(e) => { if (!irreversible && isSubmit(e.nativeEvent)) { e.preventDefault(); if (d.text.trim()) send("reply"); } }}
              className="w-full rounded bg-slate-800 p-1.5 text-sm" />
            <div className="flex items-center gap-2">
              <button disabled={busy || !d.text.trim()} onClick={() => send("reply")} className="rounded bg-sky-700 px-3 py-1 text-sm hover:bg-sky-600 disabled:opacity-40">回覆</button>
              {!qs.length && <button disabled={busy} onClick={() => send("ok")} className="rounded bg-slate-700 px-3 py-1 text-sm hover:bg-slate-600">知道了</button>}
              {qs.length > 0 && <button className="text-xs text-slate-400 hover:text-slate-100" onClick={() => setMode("answer")}>回去選答案</button>}
            </div>
          </div>
        )}
        {msg && <p className={`mt-1 text-sm ${msg.ok ? "text-emerald-300" : "text-red-300"}`}>{msg.text}</p>}
      </>}
    </div>
  );
}
