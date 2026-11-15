// Small shared pieces: the light dot, the delivery steps, a section title. Agent text always as React text.
import type { Delivery, Light, OutItem, ThreadItem } from "../api/types.ts";
import { hhmm } from "../model/time.ts";

export const LIGHT_BG: Record<Light, string> = {
  red: "bg-red-500", blue: "bg-sky-400", yellow: "bg-amber-400", green: "bg-emerald-500", gray: "bg-slate-500",
};
export const LIGHT_WORD: Record<Light, string> = { red: "出事", blue: "要你決定", yellow: "留意", green: "正常", gray: "停著" };

export function Dot({ light, title, size = "md" }: { light: Light; title?: string; size?: "sm" | "md" }) {
  const s = size === "sm" ? "h-2 w-2" : "h-2.5 w-2.5";
  return <span title={title || LIGHT_WORD[light]} className={`inline-block shrink-0 rounded-full ${s} ${LIGHT_BG[light]}`} />;
}

const STEP_WORD: Record<Delivery, string> = { queued: "排隊中", read: "已讀（推定）", replied: "已回", unknown: "狀態不明" };

/** ● 送出 10:02 ─ ● 排隊（前面 2 則）─ ○ 已讀 ─ ○ 已回  (02c §4.4; "read" is inferred, a say's reply is "之後有來信") */
export function Steps({ it, compact = false }: { it: Pick<OutItem, "delivery" | "queue_ahead" | "sent_at" | "kind"> & { reply?: OutItem["reply"]; turn?: OutItem["turn"] }; compact?: boolean }) {
  const d = it.delivery;
  if (d === "unknown") return <span className="text-xs text-slate-400" title="讀不到對方的信箱和紀錄，不猜">狀態不明</span>;
  const rank = d === "queued" ? 1 : d === "read" ? 2 : 3;
  const step = (n: number, label: string, tip?: string) => (
    <span title={tip} className={`whitespace-nowrap ${rank >= n ? "text-slate-100" : "text-slate-500"}`}>{rank >= n ? "●" : "○"} {label}</span>
  );
  const queued = d === "queued" ? `排隊${it.queue_ahead != null ? `（前面 ${it.queue_ahead} 則）` : ""}` : "排隊";
  const replied = it.kind === "say" ? "之後有來信" : "已回";
  return (
    <span className="inline-flex flex-wrap items-center gap-1 text-xs">
      {!compact && step(0, `送出 ${hhmm(it.sent_at)}`)}
      {!compact && <span className="text-slate-600">─</span>}
      {step(1, queued)}<span className="text-slate-600">─</span>
      {step(2, "已讀", "信離開了對方的信箱，或話進了對方的紀錄（推定）")}<span className="text-slate-600">─</span>
      {step(3, replied, it.kind === "say" ? "你說完之後它寄過信來，不保證是回這一句" : undefined)}
      {it.reply?.status && <span className="ml-1 rounded bg-slate-700 px-1 text-[10px]">{it.reply.status}</span>}
      {d === "queued" && it.turn && <span className="ml-1 text-amber-300">它這一輪結束才會讀</span>}
    </span>
  );
}

export function deliveryWord(d: Delivery | null | undefined): string {
  return d ? STEP_WORD[d] : "";
}

export function SectionTitle({ children, right }: { children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div className="mb-1 mt-3 flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-slate-400">
      <span>{children}</span>{right}
    </div>
  );
}

export function PriorityMark({ p }: { p?: string | null }) {
  // reserved for ok-board's letter classes (03 §12.4): shown only when the backend sends one
  if (!p) return null;
  return <span className="mr-1 rounded bg-rose-900 px-1 text-[10px] text-rose-100">{p}</span>;
}

export function isOut(x: ThreadItem): boolean { return x.dir === "out"; }
