// The inspector shows collapsible slash command status and plain-text results above its tabs.
import { useEffect } from "react";
import type { Node } from "../api/types.ts";
import { useNow } from "../state/hooks.ts";
import { useStore } from "../state/store.ts";
import { slashLabel, slashResults, watchSlash } from "../state/slashResults.ts";

export function SlashResults({ n }: { n: Node }) {
  const entry = useStore(slashResults, (s) => s[n.id]);
  const now = useNow();
  useEffect(() => {
    if (n.kind === "agent" && n.live?.cli) return watchSlash(n.id);
  }, [n.id, n.kind, n.live?.cli]);
  if (n.kind !== "agent" || !n.live?.cli || !entry?.items.length) return null;
  return <details open className="max-h-[45%] shrink-0 overflow-y-auto border-b border-slate-800 px-3 py-2 text-xs">
    <summary className="cursor-pointer text-sm text-slate-300">指令結果</summary>
    {entry.items.map((item, i) => <details key={item.letter} open={i === 0} className="mt-2">
      <summary className="cursor-pointer break-words text-slate-400">
        <code className="text-slate-200">{item.command}</code>{" "}
        <time>{item.at === null ? "--:--" : new Date(item.at * 1000).toLocaleTimeString("zh-TW", { hour: "2-digit", minute: "2-digit", hour12: false })}</time>{" "}
        <span>{slashLabel(item, entry.in_turn, n.id, now)}</span>
      </summary>
      {item.state === "answered" && <pre className="mt-1 max-h-64 overflow-auto whitespace-pre-wrap break-words rounded bg-slate-950/60 p-2 font-mono leading-4 text-slate-200">{item.text}</pre>}
    </details>)}
  </details>;
}
