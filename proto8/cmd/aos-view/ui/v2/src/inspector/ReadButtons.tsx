// Read-only CLI buttons use the same slash submission path as the composer.
import { useEffect, useState } from "react";
import type { Node } from "../api/types.ts";
import { useData } from "../state/hooks.ts";
import { ui } from "../state/app.ts";
import { cliProblem, listCommands } from "../model/commands.ts";
import { sendSlash } from "../composer/useSend.ts";
import { useStore } from "../state/store.ts";
import { pendingOf, refreshSlash, slashResults } from "../state/slashResults.ts";
export function ReadButtons({ n }: { n: Node }) {
  const slash = useData((s) => s.slash);
  const [busy, setBusy] = useState<string | null>(null);
  useStore(slashResults, (s) => s[n.id]);
  useEffect(() => {
    if (n.kind === "agent" && n.live?.cli) void refreshSlash(n.id);
  }, [n.id, n.kind, n.live?.cli]);
  if (!n.live?.cli || n.kind !== "agent") return null;
  return <>{[["usage", "📊 用量"], ["context", "🧠 上下文"]].map(([name, label]) => {
    const spec = slash.find((c) => c.name === name);
    const problem = cliProblem(n, spec) || (name === "context" && n.live?.screen === false ? "要先開畫面" : null);
    const pending = pendingOf(n.id, "/" + name);
    return <button key={name} className="rounded bg-slate-800 px-2 py-0.5 text-xs hover:bg-slate-700 disabled:opacity-40" title={pending ? "已送出，等結果；結果在『指令結果』" : problem || `送進 ${n.id} 的畫面`} disabled={busy !== null || pending || !!problem} onClick={async () => {
      const cmd = listCommands({ orders: [], slash, cli: n.live!.cli, multi: 0, target: n.id }).find((c) => c.name === name);
      if (!cmd) return;
      setBusy(name); const r = await sendSlash(n, cmd, "/" + name); setBusy(null);
      if (!r.ok) ui.set({ flash: r.message, flashGo: null });
    }}>{busy === name ? "送出中…" : pending ? `${label}（排隊中）` : label}</button>;
  })}</>;
}
