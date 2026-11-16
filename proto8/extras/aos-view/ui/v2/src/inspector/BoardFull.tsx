// Full board details and the shared inspector field row.
import { Clamp, MoreList } from "../shell/Clamp.tsx";
import { MODE_WORD, type BoardView } from "../model/board.ts";
import { ago, dayTime, parseIso } from "../model/time.ts";

export function Row({ k, children }: { k: string; children: React.ReactNode }) {
  return <div className="flex gap-2 text-sm"><span className="w-16 shrink-0 text-slate-500">{k}</span><div className="min-w-0 flex-1 break-words text-slate-200">{children}</div></div>;
}

export function BoardFull({ v, now, node }: { v: BoardView; now: number; node: string }) {
  const b = v.raw;
  return (
    <div className={`rounded-lg border p-2 text-sm ${v.stale ? "border-slate-700 text-slate-500" : v.mode === "dnd" ? "border-rose-800 bg-rose-950/40" : "border-slate-700 bg-slate-900"}`}>
      <div className="flex items-center gap-2">
        <span className="font-semibold">📋 公告欄：{MODE_WORD[v.mode]}</span>
        <span className="ml-auto text-xs text-slate-500">{v.stale ? "過期了（只當參考）" : `${ago(v.updated, now)}寫的`}{b.by === "auto" ? "・自動" : ""}{v.clockOdd ? "・對方時鐘快了" : ""}</span>
      </div>
      {b.text && <div className="mt-1"><Clamp node={node} id="board" lines={4} text={b.text} /></div>}
      {b.doing && <Row k="在做">{b.doing}</Row>}
      {v.waiting.length > 0 && (
        <div className="mt-1">
          <div className="text-xs text-slate-400">在等：</div>
          <div className="ml-3">
            <MoreList node={node} id="board:waiting" items={v.waiting} first={3} more="項" render={(w, i) => (
              <div key={i} className={w.who === "user" ? "text-sky-200" : ""}>
                {w.who === "user" ? "等你" : w.who}：{w.what}
                <span className="text-xs text-slate-500">（{ago(parseIso(w.since_at), now)}起{w.level === "urgent" ? "・急" : ""}）</span>
              </div>
            )} />
          </div>
        </div>
      )}
      {(b.back_at || b.back_text) && <Row k="回來">{b.back_text || dayTime(parseIso(b.back_at), now)}{v.overdue && <span className="text-amber-300">（已經過了說好的時間）</span>}</Row>}
      {b.deputy && <Row k="找代理">{b.deputy}</Row>}
    </div>
  );
}

