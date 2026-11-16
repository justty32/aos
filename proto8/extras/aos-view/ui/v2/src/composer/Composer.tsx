// The composer (02c §5, 12.8 #5): always at the bottom of the right column, talking to whatever is selected.
// Modes: 說話 (say, lands in its conversation), 寄信 (mail, in its mailbox), 指令 (an order letter to whoever handles it).
// One draft per target with every field, saved 0.3 s after typing; switching mode or target never loses text.
// Ctrl+Enter sends say and mail from inside this form only; an order is sent with its button.
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useStore } from "../state/store.ts";
import { sizes } from "../state/sizes.ts";
import { ui } from "../state/app.ts";
import { useData, useUi } from "../state/hooks.ts";
import { jump, setTab } from "../state/nav.ts";
import { isSubmit } from "../input/keys.ts";
import { dropDraft, emptyDraft, loadDraft, saveDraft, type Draft } from "../model/drafts.ts";
import { displayName } from "../model/tree.ts";
import { ModeFields } from "./ModeFields.tsx";
import { SlashMenu } from "./SlashMenu.tsx";
import { CmdSide } from "./CmdSide.tsx";
import { listCommands, complete, parseLine, type Command } from "../model/commands.ts";
import { resetHistory } from "../inspector/History.tsx";
import { readHistory, recordCommand } from "../model/cmdHistory.ts";
import { pageCommand } from "./commandActions.ts";
import { useSend } from "./useSend.ts";

export function Composer() {
  const tree = useData((s) => s.tree);
  const slash = useData((s) => s.slash);
  const fill = useUi((s) => s.fill);
  const sendRequest = useUi((s) => s.sendRequest);
  const flashGo = useUi((s) => s.flashGo);
  const [menuOff, setMenuOff] = useState(false);
  const [menuCur, setMenuCur] = useState(0);
  const [historyAt, setHistoryAt] = useState(-1);
  const [called, setCalled] = useState("");
  const [copyText, setCopyText] = useState<string | null>(null);
  const orders = useData((s) => s.orders);
  const multi = useUi((s) => s.multi);
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
  // dragged to a height (state/sizes.ts): the box fills it; otherwise the box grows with the text up to 40 % of the window
  const fixed = useStore(sizes, (s) => s.composer != null);
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
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    el.style.height = "";
    if (!fixed) el.style.height = `${el.scrollHeight + 2}px`;     // max-h-[40vh] caps it, then it scrolls
  }, [d.text, fixed, d.mode]);

  // 更正 / 回這封: taken once
  useEffect(() => {
    if (!prefill) return;
    if (prefill.target !== tgtRef.current) {
      if (tree?.nodes[prefill.target]) { jump(prefill.target, false); return; }   // comes back here with the new target
      ui.set({ prefill: null }); ui.set({ flash: `${prefill.target} 不在樹上了，寄不了` }); return;
    }
    put({ mode: prefill.mode, ...(prefill.orderKind ? { orderKind: prefill.orderKind } : {}), ...(prefill.mailTitle ? { mailTitle: prefill.mailTitle } : {}), ...(prefill.mailStatus ? { mailStatus: prefill.mailStatus } : {}) });
    setCorr(prefill.correctionOf || null);
    ui.set({ prefill: null });
    setTimeout(() => box.current?.focus(), 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefill, target]);

  useEffect(() => { if (fill) { put({ text: fill.text }); ui.set({ fill: null }); setMenuOff(true); box.current?.focus(); } }, [fill]);
  const kind = orders.find((o) => o.kind === d.orderKind) || orders[0];
  const orderTo = kind ? kind.to || target : null;

  const sending = useSend({ target, busy, multi, d, corr, kind, setErr, setBusy, put, success: () => {
    if (saveT.current) { clearTimeout(saveT.current); saveT.current = null; }
    dropDraft(localStorage, target);
    setD({ ...emptyDraft(), mode: d.mode, mailStatus: d.mailStatus, orderKind: d.orderKind });
    setCorr(null);
  } });

  const throwAway = () => {
    if (!confirm("丟掉這份草稿？")) return;
    if (saveT.current) { clearTimeout(saveT.current); saveT.current = null; }
    dropDraft(localStorage, target);
    setD({ ...emptyDraft(), mode: d.mode });
    setCorr(null);
  };

  const send = sending.send;
  useEffect(() => { if (sendRequest) { ui.set({ sendRequest: 0 }); send(); } }, [sendRequest]);
  const parsed = parseLine(d.text);
  const cmds = listCommands({ orders, slash, cli: n?.live?.cli ?? null, multi: multi.length, target });
  const matches = complete(d.text, cmds);
  const menu = !menuOff && /^\/\S*$/.test(d.text);
  const choose = (c: Command) => {
    setMenuOff(true);
    if (c.group === "page" && c.args === "none") { pageCommand(c.name); recordCommand(localStorage, "/" + c.name, target, Date.now() / 1000); ui.set({ cmdRev: ui.get().cmdRev + 1 }); put({ text: "" }); }
    else if (c.group === "talk") { if (!target) { setErr("先選一個 agent"); return; } put({ mode: c.name === "mail" ? "mail" : "say", text: "" }); recordCommand(localStorage, "/" + c.name, target, Date.now() / 1000); ui.set({ cmdRev: ui.get().cmdRev + 1 }); }
    else put({ text: "/" + c.name + " " });
    box.current?.focus();
  };
  const copyOpen = async () => {
    const line = `aos-agent open --target ${target}`;
    try { await navigator.clipboard.writeText(line); ui.set({ flash: `已複製：${line}，貼到你的終端機`, flashGo: null }); }
    catch { setCopyText(line); }
  };

  return (
    <div className="@container flex min-h-0 flex-1 flex-col border-t border-slate-800 bg-slate-900 p-3" data-composer onKeyDownCapture={(e) => {
      if (!sending.confirm || e.nativeEvent.isComposing || !["Enter", "Escape"].includes(e.key)) return;
      e.preventDefault(); e.stopPropagation(); if (e.key === "Escape") sending.cancel(); else send();
    }}>
      <div className="mb-2 flex shrink-0 flex-wrap items-center gap-2">
        {target
          ? <span className="max-w-48 truncate rounded bg-sky-900 px-2 py-0.5 text-xs text-sky-100" title={multi.length >= 2 ? multi.join("、") : target}>對：{multi.length >= 2 ? `${multi.length} 個` : displayName(target)}</span>
          : <button className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-300" onClick={() => ui.set({ searchOpen: true, searchText: "" })}>
              {n ? `${n.id} 不收話；` : ""}對：＋點這裡或按 Ctrl+K 選對象</button>}
        <button data-mode className="rounded bg-slate-800 px-2 py-1 text-xs" title="/say 切說話，/mail 切寄信；董事長令從指令面板切換" onClick={() => ui.set({ panelOpen: true })}>{d.mode === "say" ? "說話" : d.mode === "mail" ? "寄信" : `董事長令：${kind?.label || ""}`} ▾</button>
        {d.mode !== "say" && <button title="回說話" onClick={() => put({ mode: "say" })}>×</button>}
        {n?.live?.cli && <button className="text-xs text-sky-300" onClick={copyOpen}>⧉ 開畫面</button>}
        {corr && <span className="truncate rounded bg-amber-900 px-1.5 text-xs text-amber-100" title={corr}>更正 {corr}
          <button className="ml-1" onClick={() => setCorr(null)}>×</button></span>}
      </div>

      {copyText && <input readOnly autoFocus onFocus={(e) => e.currentTarget.select()} value={copyText} className="mb-1 w-full rounded bg-slate-800 p-1 text-xs" />}
      <ModeFields d={d} put={put} send={send} orders={orders} kind={kind} target={target} orderTo={orderTo} />
      {sending.confirm && <div data-confirm className="mb-1 rounded bg-red-950 p-2 text-xs text-red-200">{sending.confirm}</div>}
      <div className={`flex min-h-0 flex-col gap-2 @[520px]:flex-row ${fixed ? "flex-1" : ""}`}>
        <div className="relative min-w-0 flex-1">
          {menu && <SlashMenu commands={matches} current={menuCur} choose={choose} />}
          <textarea ref={box} value={d.text} onChange={(e) => { put({ text: e.target.value }); setMenuOff(false); setMenuCur(0); setHistoryAt(-1); sending.cancel(); }} rows={2}
            placeholder={!target ? "可用 /map、/find；說話先選 agent" : d.mode === "say" ? `對 ${target} 說…` : d.mode === "mail" ? "信的內容…" : "要什麼、為什麼…"}
            onKeyDown={(e) => {
              if (e.nativeEvent.isComposing || e.keyCode === 229) return;
              if (sending.confirm && (e.key === "Enter" || e.key === "Escape")) { e.preventDefault(); e.stopPropagation(); if (e.key === "Escape") sending.cancel(); else send(); return; }
              if (menu && !e.ctrlKey && !e.metaKey && !e.shiftKey && ["ArrowUp", "ArrowDown", "Tab", "Enter", "Escape"].includes(e.key)) {
                e.preventDefault(); e.stopPropagation();
                if (e.key === "Escape") setMenuOff(true);
                else if (e.key === "ArrowUp" || e.key === "ArrowDown") setMenuCur((v) => Math.max(0, Math.min(matches.length - 1, v + (e.key === "ArrowUp" ? -1 : 1))));
                else if (matches[menuCur]) { if (e.key === "Enter" && d.text === "/" + matches[menuCur].name && matches[menuCur].group === "cli") send(); else choose(matches[menuCur]); }
                else if (e.key === "Enter") send();
                return;
              }
              if ((e.key === "ArrowUp" || e.key === "ArrowDown") && (!d.text || d.text === called)) {
                const rows = readHistory(localStorage); const i = Math.min(rows.length - 1, Math.max(-1, historyAt + (e.key === "ArrowUp" ? 1 : -1))); const text = rows[i]?.line || "";
                e.preventDefault(); setHistoryAt(i); setCalled(text); put({ text }); setMenuOff(true); return;
              }
              if (isSubmit(e.nativeEvent) || (parsed && !d.text.includes("\n") && e.key === "Enter" && !e.shiftKey)) { e.preventDefault(); send(); }
            }}
            className={`w-full overflow-y-auto rounded bg-slate-800 p-2.5 text-[0.9375rem] leading-6 ${fixed ? "h-full min-h-0 resize-none" : "max-h-[40vh] min-h-11 resize-none"}`} />
        </div>
        <CmdSide />
      </div>
      {parsed && <p className="mt-1 truncate text-xs text-slate-500">{cmds.find((c) => c.name === parsed.name)?.group === "cli" ? `/${parsed.name}：原樣送進 ${target} 的畫面，不加「使用者經全景頁」的開頭` : `/${parsed.name}：執行這一頁的指令`}</p>}
      <div className="mt-2 flex shrink-0 items-center gap-2">
        <button onClick={send} disabled={busy}
          className={`rounded px-4 py-1.5 text-sm font-medium disabled:opacity-40 ${d.mode === "order" ? "bg-amber-700 hover:bg-amber-600" : "bg-sky-700 hover:bg-sky-600"}`}>
          {busy ? (flash?.startsWith("送出中") ? flash : "送出中…") : parsed ? (cmds.find((c) => c.name === parsed.name)?.group === "cli" ? "送進畫面" : "執行") : multi.length >= 2 ? "群發" : d.mode === "say" ? "說" : d.mode === "mail" ? "寄出" : "下指令"}
        </button>
        <span className="text-xs text-slate-500">{parsed ? "Enter 執行，Shift+Enter 換行" : d.mode === "order" ? "按按鈕送出" : "Ctrl+Enter 送出"}</span>
        {(d.text || d.mailTitle) && <button className="text-xs text-slate-500 hover:text-slate-200" onClick={throwAway}>丟掉草稿</button>}
        {flashGo && <button data-flash-go className="text-xs text-sky-300" onClick={() => { const id = ui.get().flashTarget || target; if (id) { resetHistory(id); jump(id, false); } ui.set({ historyJump: Date.now() }); setTab("history"); }}>去看 ▸</button>}
        <span className={`ml-auto truncate text-xs ${err ? "text-red-300" : "text-emerald-300"}`} title={err || flash || ""}>{err || flash || ""}</span>
      </div>
    </div>
  );
}
