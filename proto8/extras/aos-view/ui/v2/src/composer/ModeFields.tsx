// Mail and order fields are shared by the composer without changing their original behavior.
import type { OrderKind } from "../api/types.ts";
import type { Draft } from "../model/drafts.ts";
import { statusWord } from "../model/words.ts";
import { isSubmit } from "../input/keys.ts";
const MAIL_STATUS = ["REQUEST", "PROGRESS", "DONE", "BLOCKED", "NEEDS-USER", "FAILED"];
const MODELS = ["chatgpt-gpt-6.1-sol", "opus", "fable", "sonnet", "haiku"];
const FIELD_WORD: Record<string, string> = { budget: "預算", role: "角色", model: "模型", count: "人數", priority: "優先", quota: "額度" };

export function ModeFields({ d, put, send, orders, kind, target, orderTo }: { d: Draft; put: (p: Partial<Draft>) => void; send: () => void; orders: OrderKind[]; kind: OrderKind | undefined; target: string | null; orderTo: string | null }) {
  return <>
      {d.mode === "mail" && (
        <div className="mb-2 flex shrink-0 gap-1">
          <select value={d.mailStatus} onChange={(e) => put({ mailStatus: e.target.value })} className="rounded bg-slate-800 px-1 text-xs">
            {MAIL_STATUS.map((s) => <option key={s} value={s}>{statusWord(s)}</option>)}
          </select>
          <input value={d.mailTitle} onChange={(e) => put({ mailTitle: e.target.value })} placeholder="標題（一行看得懂）" maxLength={300}
            onKeyDown={(e) => { if (isSubmit(e.nativeEvent)) { e.preventDefault(); send(); } }}
            className="min-w-0 flex-1 rounded bg-slate-800 px-1.5 py-0.5 text-sm" />
        </div>
      )}
      {d.mode === "order" && (
        <div className="mb-2 shrink-0 space-y-1">
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
          {target && orderTo && <p className="text-xs text-slate-400">這張單會寄給 {orderTo}{orderTo !== target ? `（關於 ${target}）` : ""}；頁面不直接動樹，對方照自己的規矩辦。</p>}
        </div>
      )}
  </>;
}
