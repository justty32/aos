// 往來: what you sent to one node and what came back, like a chat (oldest at the top, newest at the bottom).
// Seen (12.8 #6): opening this tab yourself marks what is here as seen. A letter that arrives while it is open is
// seen only if the tab is in front, the list is scrolled to the bottom and you moved or typed in the last minute;
// otherwise "↓ 有 N 則新回覆" stays and the to-do keeps it.
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { Thread as T } from "../api/types.ts";
import { useLive } from "./useLive.ts";
import { markSeen } from "../api/poll.ts";
import { useNow } from "../state/hooks.ts";
import { dayTime } from "../model/time.ts";
import { PriorityMark, Steps } from "../shell/bits.tsx";
import { ui } from "../state/app.ts";
import { statusWord } from "../model/words.ts";

let lastActivity = Date.now();
if (typeof window !== "undefined") {
  for (const ev of ["mousemove", "keydown", "pointerdown", "wheel"]) window.addEventListener(ev, () => { lastActivity = Date.now(); }, { passive: true });
}

export function Thread({ name }: { name: string }) {
  const live = useLive<T>("/api/thread?name=" + encodeURIComponent(name), ["relay", "outbox"]);
  const now = useNow();
  const box = useRef<HTMLDivElement>(null);
  const known = useRef<Set<string> | null>(null);
  const [fresh, setFresh] = useState<string[]>([]);
  const atBottom = () => { const b = box.current; return !!b && b.scrollHeight - b.scrollTop - b.clientHeight < 24; };

  useEffect(() => { known.current = null; setFresh([]); }, [name]);
  const items = live.data ? [...live.data.letters].reverse() : [];
  const ins = items.filter((x) => x.dir === "in" && x.letter).map((x) => x.letter!) as string[];

  useLayoutEffect(() => {
    if (!live.data) return;
    if (known.current === null) {            // first load after an explicit open: all seen, jump to the bottom
      known.current = new Set(ins);
      markSeen(ins.map((l) => "in:" + l));
      box.current && (box.current.scrollTop = box.current.scrollHeight);
      return;
    }
    const added = ins.filter((l) => !known.current!.has(l));
    if (!added.length) return;
    added.forEach((l) => known.current!.add(l));
    const ok = document.visibilityState === "visible" && atBottom() && Date.now() - lastActivity < 60000;
    if (ok) { markSeen(added.map((l) => "in:" + l)); box.current && (box.current.scrollTop = box.current.scrollHeight); }
    else setFresh((f) => [...f, ...added]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [live.data]);

  const showFresh = () => {
    markSeen(fresh.map((l) => "in:" + l));
    setFresh([]);
    box.current && (box.current.scrollTop = box.current.scrollHeight);
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {live.data?.gone && <p className="mb-1 rounded bg-amber-950 px-2 py-1 text-xs text-amber-200">這個部門已經收隊（不在樹上），下面是以前的往來；回信照樣會寄到它的信箱。</p>}
      {live.data?.turn && (
        <p className="mb-1 rounded bg-slate-800 px-2 py-1 text-xs text-amber-200">它正在一輪裡，信箱排著 {live.data.turn.queued} 則；這一輪結束才會讀。</p>
      )}
      <div ref={box} data-scroll="thread" className="flex min-h-0 flex-1 flex-col space-y-3 overflow-y-auto pr-1"
        onScroll={() => { if (fresh.length && atBottom()) showFresh(); }}>
        {live.error && <p className="text-xs text-red-300">讀不到往來：{live.error}</p>}
        {!live.data && !live.error && <p className="text-xs text-slate-400">讀取中…</p>}
        {live.data && !items.length && <p className="text-xs text-slate-500">還沒有往來。在下面打字就是對它說話。</p>}
        {items.map((x, i) => (
          <div key={(x.letter || "") + i} className={`w-fit max-w-[85%] rounded-lg px-3 py-2 text-[0.9375rem] leading-6 ${x.dir === "out" ? "ml-auto bg-sky-950" : "bg-slate-800"}`}>
            <div className="mb-1 flex items-center gap-2 text-xs text-slate-400">
              <PriorityMark p={x.priority} />
              <span>{x.dir === "out" ? `你${x.kind === "say" ? "說" : x.kind === "order" ? "下指令" : "寄信"}` : `${x.from}${x.status ? `（${statusWord(x.status)}）` : ""}`}</span>
              <span className="ml-auto">{dayTime(x.sent_at, now)}</span>
            </div>
            {x.kind !== "say" && x.title && <div className="font-medium">{x.title}</div>}
            <div className="whitespace-pre-wrap break-words text-slate-200">{x.what}</div>
            {x.dir === "out" && x.delivery && <div className="mt-1"><Steps it={{ delivery: x.delivery, queue_ahead: x.queue_ahead ?? null, sent_at: x.sent_at, kind: x.kind }} compact /></div>}
            {x.dir === "in" && (
              <button className="mt-1 text-xs text-sky-300 hover:underline" onClick={() =>
                ui.set({ prefill: { target: name, mode: "mail", mailTitle: `回：${x.title}`.slice(0, 120), n: Date.now() } })}>回這封</button>
            )}
          </div>
        ))}
      </div>
      {fresh.length > 0 && (
        <button onClick={showFresh} className="mt-1 rounded bg-sky-800 px-2 py-1 text-xs text-sky-50">↓ 有 {fresh.length} 則新回覆</button>
      )}
    </div>
  );
}
