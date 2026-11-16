// Read-only CLI buttons use the same slash submission path as the composer.
import { useState } from "react";
import type { Node } from "../api/types.ts";
import { useData } from "../state/hooks.ts";
import { ui } from "../state/app.ts";
import { cliProblem, listCommands } from "../model/commands.ts";
import { sendSlash } from "../composer/useSend.ts";
export function ReadButtons({ n }: { n: Node }) {
  const slash = useData((s) => s.slash);
  const [busy, setBusy] = useState(false);
  if (!n.live?.cli || n.kind !== "agent") return null;
  return <>{[["usage", "📊 用量"], ["context", "🧠 上下文"]].map(([name, label]) => {
    const spec = slash.find((c) => c.name === name);
    const problem = cliProblem(n, spec) || (name === "context" && n.live?.screen === false ? "要先開畫面" : null);
    return <button key={name} className="rounded bg-slate-800 px-2 py-0.5 text-xs hover:bg-slate-700 disabled:opacity-40" title={problem || `送進 ${n.id} 的畫面`} disabled={busy || !!problem} onClick={async () => {
      const cmd = listCommands({ orders: [], slash, cli: n.live!.cli, multi: 0, target: n.id }).find((c) => c.name === name);
      if (!cmd) return;
      setBusy(true); const r = await sendSlash(n, cmd, "/" + name); setBusy(false);
      if (!r.ok) ui.set({ flash: r.message, flashGo: null });
    }}>{label}</button>;
  })}</>;
}
