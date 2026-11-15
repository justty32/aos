// The composer (02c §5, 12.8 #5): always at the bottom of the right column, talking to whatever is selected.
// Modes: 說話 (say, lands in its conversation), 寄信 (mail, in its mailbox), 指令 (an order letter to whoever handles it).
// One draft per target with every field, saved 0.3 s after typing; switching mode or target never loses text.
// Ctrl+Enter sends say and mail from inside this form only; an order is sent with its button.
import { useEffect, useRef, useState } from "react";
import { post } from "../api/client.ts";
import { pulseSoon } from "../api/poll.ts";
import { ui } from "../state/app.ts";
import { useData, useUi } from "../state/hooks.ts";
import { jump } from "../state/nav.ts";
import { isSubmit } from "../input/keys.ts";
import { dropDraft, emptyDraft, loadDraft, saveDraft, type Draft, type Mode } from "../model/drafts.ts";
import { displayName } from "../model/tree.ts";

const MAIL_STATUS = ["REQUEST", "PROGRESS", "DONE", "BLOCKED", "NEEDS-USER", "FAILED"];
const MODELS = ["chatgpt-gpt-6.1-sol", "opus", "fable", "sonnet", "haiku"];
const FIELD_WORD: Record<string, string> = { budget: "預算", role: "角色", model: "模型", count: "人數", priority: "優先", quota: "額度" };

export function Composer() {
  const tree = useData((s) => s.tree);
  const orders = useData((s) => s.orders);
  const sel = useUi((s) => s.route.sel);
  const focusN = useUi((s) => s.focusComposer);
  const prefill = useUi((s) => s.prefill);
  const flash = useUi((s) => s.flash);
  const n = tree && sel ? tree.nodes[sel] : undefined;
  const target = n && n.kind === "agent" ? n.id : null;
  const [d, setD] = useState<Draft>(() => loadDraft(localStorage, target));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [corr, setCorr] = useState<string | null>(null);
  const box = useRef<HTMLTextAreaElement>(null);
  const saveT = useRef<ReturnType<typeof setTimeout> | null>(null);
  const tgtRef = useRef(target);
  const dRef = useRef(d);
  dRef.current = d;

  // a new target = its own draft (a pending save of the old one is done first)
  useEffect(() => {
    if (tgtRef.current === target) return;
    if (saveT.current) { clearTimeout(saveT.current); saveT.current = null; saveDraft(localStorage, tgtRef.current, dRef.current, Date.now() / 1000); }
    tgtRef.current = target;
    setD(loadDraft(localStorage, target)); setErr(null); setCorr(null);
  }, [target]);

  const put = (p: Partial<Draft>) => {
    setD((old) => {
      const nd = { ...old, ...p };
      if (saveT.current) clearTimeout(saveT.current);
      const t = tgtRef.current;
      saveT.current = setTimeout(() => { saveT.current = null; saveDraft(localStorage, t, nd, Date.now() / 1000); }, 300);
      return nd;
    });
  };

  useEffect(() => { if (focusN) box.current?.focus(); }, [focusN]);

  // 更正 / 回這封: taken once
  useEffect(() => {
    if (!prefill) return;
    if (prefill.target !== tgtRef.current) {
      if (tree?.nodes[prefill.target]) { jump(prefill.target, false); return; }   // comes back here with the new target
      ui.set({ prefill: null }); ui.set({ flash: `${prefill.target} 不在樹上了，寄不了` }); return;
    }
    put({ mode: prefill.mode, ...(prefill.mailTitle ? { mailTitle: prefill.mailTitle } : {}), ...(prefill.mailStatus ? { mailStatus: prefill.mailStatus } : {}) });
    setCorr(prefill.correctionOf || null);
    ui.set({ prefill: null });
    setTimeout(() => box.current?.focus(), 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefill, target]);

  const kind = orders.find((o) => o.kind === d.orderKind) || orders[0];
  const orderTo = kind ? kind.to || target : null;

  const send = async () => {
    if (!target || busy) return;
    setErr(null);
    const link = corr ? { correction_of: corr } : {};
    let r;
    if (d.mode === "say") {
      if (!d.text.trim()) return;
      setBusy(true);
      r = await post("/api/say", { name: target, text: d.text, ...link });
    } else if (d.mode === "mail") {
      if (!d.mailTitle.trim() || !d.text.trim()) { setErr("標題和內容都要填"); return; }
      setBusy(true);
      r = await post("/api/mail", { name: target, status: d.mailStatus, title: d.mailTitle, what: d.text, ...link });
    } else {
      if (!kind) { setErr("後端沒有給指令種類"); return; }
      if (!d.text.trim()) { setErr("要寫清楚要什麼"); return; }
      setBusy(true);
      const f: Record<string, string> = {};
      for (const k of kind.fields) if (d.fields[k]?.trim()) f[k] = d.fields[k].trim();
      r = await post("/api/order", { kind: kind.kind, target, what: d.text, ...f, ...link });
    }
    setBusy(false);
    if (!r.ok) { setErr(r.message || "送不出去"); return; }
    if (saveT.current) { clearTimeout(saveT.current); saveT.current = null; }
    dropDraft(localStorage, target);
    setD({ ...emptyDraft(), mode: d.mode, mailStatus: d.mailStatus, orderKind: d.orderKind });
    setCorr(null);
    ui.set({ flash: r.message || "已送出" });
    pulseSoon();
  };

  const throwAway = () => {
    if (!confirm("丟掉這份草稿？")) return;
    if (saveT.current) { clearTimeout(saveT.current); saveT.current = null; }
    dropDraft(localStorage, target);
    setD({ ...emptyDraft(), mode: d.mode });
    setCorr(null);
  };

  const modeBtn = (m: Mode, label: string) => (
    <button onClick={() => put({ mode: m })} disabled={!target}
      className={`rounded px-2 py-0.5 text-xs ${d.mode === m ? "bg-slate-200 text-slate-900" : "bg-slate-800 text-slate-300 hover:bg-slate-700"} disabled:opacity-40`}>{label}</button>
  );

  return (
    <div className="shrink-0 border-t border-slate-800 bg-slate-900 p-2" data-composer>
      <div className="mb-1 flex items-center gap-1.5">
        {target
          ? <span className="max-w-48 truncate rounded bg-sky-900 px-2 py-0.5 text-xs text-sky-100" title={target}>對：{displayName(target)}</span>
          : <button className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-300" onClick={() => ui.set({ searchOpen: true })}>
              {n ? `${n.id} 不收話；` : ""}對：＋點這裡或按 Ctrl+K 選對象</button>}
        {modeBtn("say", "說話")}{modeBtn("mail", "寄信")}{modeBtn("order", "指令")}
        {corr && <span className="truncate rounded bg-amber-900 px-1.5 text-[10px] text-amber-100" title={corr}>更正 {corr}
          <button className="ml-1" onClick={() => setCorr(null)}>×</button></span>}
        <span className="ml-auto text-[10px] text-slate-500">{d.mode === "order" ? "按按鈕送出" : "Ctrl+Enter 送出"}</span>
      </div>

      {d.mode === "mail" && (
        <div className="mb-1 flex gap-1">
          <select value={d.mailStatus} onChange={(e) => put({ mailStatus: e.target.value })} className="rounded bg-slate-800 px-1 text-xs">
            {MAIL_STATUS.map((s) => <option key={s}>{s}</option>)}
          </select>
          <input value={d.mailTitle} onChange={(e) => put({ mailTitle: e.target.value })} placeholder="標題（一行看得懂）" maxLength={300}
            onKeyDown={(e) => { if (isSubmit(e.nativeEvent)) { e.preventDefault(); send(); } }}
            className="min-w-0 flex-1 rounded bg-slate-800 px-1.5 py-0.5 text-sm" />
        </div>
      )}
      {d.mode === "order" && (
        <div className="mb-1 space-y-1">
          <div className="flex flex-wrap gap-1">
            {orders.map((o) => (
              <button key={o.kind} onClick={() => put({ orderKind: o.kind })}
                className={`rounded px-2 py-0.5 text-xs ${kind?.kind === o.kind ? "bg-amber-700 text-white" : "bg-slate-800 text-slate-300"}`}>{o.label}</button>
            ))}
          </div>
          {kind && (
            <div className="flex flex-wrap gap-1">
              {kind.fields.map((k) => k === "model" ? (
                <select key={k} value={d.fields[k] || ""} onChange={(e) => put({ fields: { ...d.fields, [k]: e.target.value } })} className="rounded bg-slate-800 px-1 text-xs">
                  <option value="">模型（不指定）</option>{MODELS.map((m) => <option key={m}>{m}</option>)}
                </select>
              ) : (
                <input key={k} type={k === "count" ? "number" : "text"} min={k === "count" ? 1 : undefined} max={k === "count" ? 20 : undefined}
                  value={d.fields[k] || ""} onChange={(e) => put({ fields: { ...d.fields, [k]: e.target.value } })}
                  placeholder={FIELD_WORD[k] || k} className="w-24 rounded bg-slate-800 px-1.5 py-0.5 text-xs" />
              ))}
            </div>
          )}
          {target && orderTo && <p className="text-[11px] text-slate-400">這張單會寄給 {orderTo}{orderTo !== target ? `（關於 ${target}）` : ""}；頁面不直接動樹，對方照自己的規矩辦。</p>}
        </div>
      )}
      <textarea ref={box} value={d.text} onChange={(e) => put({ text: e.target.value })} rows={3} disabled={!target}
        placeholder={!target ? "先選一個 agent" : d.mode === "say" ? `對 ${target} 說…（進它的對話）` : d.mode === "mail" ? "信的內容…（進它的信箱）" : "要什麼、為什麼…"}
        onKeyDown={(e) => { if (d.mode !== "order" && isSubmit(e.nativeEvent)) { e.preventDefault(); send(); } }}
        className="max-h-60 min-h-11 w-full resize-y overflow-y-auto rounded bg-slate-800 p-1.5 text-sm disabled:opacity-40" />
      <div className="flex items-center gap-2">
        <button onClick={send} disabled={!target || busy}
          className={`rounded px-3 py-1 text-sm font-medium disabled:opacity-40 ${d.mode === "order" ? "bg-amber-700 hover:bg-amber-600" : "bg-sky-700 hover:bg-sky-600"}`}>
          {busy ? "送出中…" : d.mode === "say" ? "說" : d.mode === "mail" ? "寄出" : "下指令"}
        </button>
        {(d.text || d.mailTitle) && <button className="text-xs text-slate-500 hover:text-slate-200" onClick={throwAway}>丟掉草稿</button>}
        <span className={`ml-auto truncate text-xs ${err ? "text-red-300" : "text-emerald-300"}`} title={err || flash || ""}>{err || flash || ""}</span>
      </div>
    </div>
  );
}
