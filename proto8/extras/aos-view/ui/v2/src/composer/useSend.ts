// One send path handles speech, mail, orders, slash commands, confirmations, and sequential batches.
import { useEffect, useState } from "react";
import { post } from "../api/client.ts";
import { pulseSoon } from "../api/poll.ts";
import { data, ui } from "../state/app.ts";
import { setMulti } from "../state/multi.ts";
import { saveDraft } from "../model/drafts.ts";
import type { Draft } from "../model/drafts.ts";
import type { Node, OrderKind } from "../api/types.ts";
import { cliProblem, parseLine, resolve, type Command } from "../model/commands.ts";
import { recordCommand } from "../model/cmdHistory.ts";
import { pageCommand } from "./commandActions.ts";

export async function sendSlash(n: Node, cmd: Command, text: string, batch?: string) {
  const problem = cliProblem(n, data.get().slash.find((s) => s.name === cmd.name));
  if (problem) return { ok: false, message: problem };
  const r = await post("/api/slash", { name: n.id, text, ...(batch ? { batch } : {}) });
  if (r.ok) {
    const result = cmd.name === "status" || cmd.name === "usage" || cmd.how === "screen";
    ui.set({ flash: result ? `${n.live?.in_turn ? "它正在一輪裡，這一輪結束才會做；" : ""}已送進 ${n.id} 的畫面。結果會是『做過・說過』最新的一則` : r.message,
      flashTarget: n.id, flashGo: result ? "history" : null, ...(result ? { slashAt: Date.now() } : {}) });
  }
  return r;
}

export function useSend({ target, busy, multi, d, corr, kind, setErr, setBusy, success, put }: {
  target: string | null; busy: boolean; multi: string[]; d: Draft; corr: string | null; kind: OrderKind | undefined;
  setErr: (s: string | null) => void; setBusy: (b: boolean) => void; success: () => void; put: (p: Partial<Draft>) => void;
}) {
  const [confirmation, setConfirmation] = useState<{ signature: string; text: string } | null>(null);
  const signature = JSON.stringify([target, multi, d, corr]);
  useEffect(() => { setConfirmation(null); }, [signature]);
  const confirm = confirmation?.signature === signature ? confirmation.text : null;
  const send = async () => {
    if (busy) return;
    setErr(null);
    ui.set({ flashGo: null });
    const tree = data.get().tree;
    const targets = multi.length >= 2 ? multi : target ? [target] : [];
    const parsed = parseLine(d.text);
    let cmd: Command | null = null, rest = "", text = d.text;
    if (parsed) {
      const found = resolve(d.text, { orders: data.get().orders, slash: data.get().slash, cli: target ? tree?.nodes[target]?.live?.cli ?? null : null, target, multi: multi.length });
      if ("error" in found) { setErr(found.error); return; }
      cmd = found.cmd; rest = found.rest;
      if (cmd.group === "page") { pageCommand(cmd.name, rest); recordCommand(localStorage, d.text.trim(), target, Date.now() / 1000); ui.set({ cmdRev: ui.get().cmdRev + 1 }); put({ text: "" }); return; }
      if (cmd.name === "mail") { put({ mode: "mail", text: "" }); recordCommand(localStorage, "/mail", target, Date.now() / 1000); ui.set({ cmdRev: ui.get().cmdRev + 1 }); return; }
      if (cmd.name === "say") { if (!rest) { put({ mode: "say", text: "" }); recordCommand(localStorage, "/say", target, Date.now() / 1000); ui.set({ cmdRev: ui.get().cmdRev + 1 }); return; } text = rest; }
    }
    if (!targets.length) { setErr("先選一個 agent"); return; }
    if (targets.length > 30) { setErr(`一次最多對 30 個送，現在選了 ${targets.length} 個`); return; }
    const cli = cmd?.group === "cli";
    if (!cli && cmd?.name !== "say" && d.mode === "order" && targets.length >= 2) { setErr("董事長令一次只能對一個對象"); return; }
    if (!text.trim()) return;
    if (!cli && d.mode === "mail" && cmd?.name !== "say" && !d.mailTitle.trim()) { setErr("標題和內容都要填"); return; }
    if (cli) for (const id of targets) { const problem = cliProblem(tree?.nodes[id], data.get().slash.find((s) => s.name === cmd!.name)); if (problem) { setErr(problem); return; } }
    const needs = targets.length >= 2 || cmd?.confirm;
    if (needs && !confirm) {
      const text = targets.length >= 2 ? `要對 ${targets.length} 個各送一則：${targets.join("、")}（再按一次 Enter 送出，Esc 取消）` : cmd?.name === "clear" ? `/clear 會清掉 ${target} 的對話，回不來。再按一次 Enter 確認，Esc 取消` : cmd?.name === "exit" ? `/exit 會關掉 ${target} 開著的畫面。再按一次 Enter 確認，Esc 取消` : "這個指令回不來。再按一次 Enter 確認，Esc 取消";
      setConfirmation({ signature, text }); return;
    }
    setConfirmation(null); setBusy(true);
    const batch = targets.length >= 2 ? "b" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6).padEnd(4, "0") : null;
    const failures: { id: string; why: string }[] = [];
    for (let i = 0; i < targets.length; i++) {
      const id = targets[i];
      if (batch) ui.set({ flash: `送出中 ${i + 1}/${targets.length}…`, flashGo: null });
      const link = { ...(corr ? { correction_of: corr } : {}), ...(batch ? { batch } : {}) };
      let r;
      if (cli) r = await sendSlash(tree!.nodes[id], cmd!, "/" + cmd!.name + (rest ? " " + rest : ""), batch || undefined);
      else if (d.mode === "say" || cmd?.name === "say") r = await post("/api/say", { name: id, text, ...link });
      else if (d.mode === "mail") r = await post("/api/mail", { name: id, status: d.mailStatus, title: d.mailTitle, what: text, ...link });
      else { if (!kind) { r = { ok: false, message: "後端沒有給指令種類" }; } else r = await post("/api/order", { kind: kind.kind, target: id, what: text, ...Object.fromEntries(kind.fields.filter((k) => d.fields[k]?.trim()).map((k) => [k, d.fields[k].trim()])), ...link }); }
      if (!r.ok) failures.push({ id, why: r.message || "送不出去" });
      else if (!cli && !batch) ui.set({ flash: r.message || "已送出", flashGo: null });
    }
    setBusy(false);
    if (failures.length) { if (batch) { for (const f of failures) saveDraft(localStorage, f.id, d, Date.now() / 1000); setMulti(failures.map((f) => f.id)); } const message = `送給 ${targets.length - failures.length} 個，${failures.length} 個沒送成：${failures.map((f) => `${f.id}（${f.why}）`).join("、")}`; setErr(message); ui.set({ flash: message, flashGo: null }); return; }
    if (parsed) { recordCommand(localStorage, d.text.trim(), target, Date.now() / 1000); ui.set({ cmdRev: ui.get().cmdRev + 1 }); }
    success(); if (batch) ui.set({ flash: `已送給 ${targets.length} 個` }); pulseSoon();
  };
  return { send, confirm, cancel: () => setConfirmation(null) };
}
