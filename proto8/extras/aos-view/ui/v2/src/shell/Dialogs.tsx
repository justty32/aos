// Overlays: Ctrl+K search (jump to anyone), the user's board (留話), the drafts list. Esc closes the top one.
import { useEffect, useMemo, useRef, useState } from "react";
import { ui, data } from "../state/app.ts";
import { useData, useUi } from "../state/hooks.ts";
import { jump } from "../state/nav.ts";
import { pushOverlay } from "../input/keys.ts";
import { post } from "../api/client.ts";
import { pulseSoon } from "../api/poll.ts";
import { listDrafts, dropDraft } from "../model/drafts.ts";
import { isDept } from "../model/tree.ts";
import { ago } from "../model/time.ts";
import { Dot } from "./bits.tsx";

function Modal({ onClose, children, title }: { onClose: () => void; children: React.ReactNode; title: string }) {
  useEffect(() => pushOverlay(onClose), [onClose]);
  return (
    <div className="fixed inset-0 z-40 flex items-start justify-center bg-black/50 pt-24" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div role="dialog" aria-label={title} className="w-[32rem] max-w-[95vw] rounded-lg border border-slate-600 bg-slate-900 p-3 shadow-2xl">
        <div className="mb-2 flex items-center justify-between text-sm"><b>{title}</b><button className="text-slate-400 hover:text-slate-100" onClick={onClose}>關 Esc</button></div>
        {children}
      </div>
    </div>
  );
}

const closeSearch = () => ui.set({ searchOpen: false });
const closeBoard = () => ui.set({ boardOpen: false });
const closeDrafts = () => ui.set({ draftsOpen: false });

function Search() {
  const tree = useData((s) => s.tree);
  const [q, setQ] = useState("");
  const [cur, setCur] = useState(0);
  const inp = useRef<HTMLInputElement>(null);
  useEffect(() => { inp.current?.focus(); }, []);
  const hits = useMemo(() => {
    if (!tree) return [];
    const s = q.trim().toLowerCase();
    const all = Object.values(tree.nodes);
    const score = (id: string) => (id.toLowerCase().startsWith(s) ? 0 : 1);
    return all.filter((n) => !s || n.id.toLowerCase().includes(s) || (n.tags || []).some((t) => t.toLowerCase().includes(s)))
      .sort((a, b) => score(a.id) - score(b.id) || (a.kind === "agent" ? 0 : 1) - (b.kind === "agent" ? 0 : 1) || a.id.localeCompare(b.id)).slice(0, 30);
  }, [tree, q]);
  const go = (id: string) => { closeSearch(); jump(id, data.get().tree?.nodes[id]?.kind === "agent"); };
  return (
    <Modal onClose={closeSearch} title="找人（Enter 跳過去，游標進打字區）">
      <input ref={inp} value={q} onChange={(e) => { setQ(e.target.value); setCur(0); }} placeholder="名字或標籤…"
        onKeyDown={(e) => {
          if (e.nativeEvent.isComposing) return;
          if (e.key === "ArrowDown") { e.preventDefault(); setCur((c) => Math.min(c + 1, hits.length - 1)); }
          if (e.key === "ArrowUp") { e.preventDefault(); setCur((c) => Math.max(c - 1, 0)); }
          if (e.key === "Enter" && hits[cur]) { e.preventDefault(); go(hits[cur].id); }
          if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); closeSearch(); }
        }}
        className="mb-2 w-full rounded bg-slate-800 px-2 py-1.5 text-sm" />
      <ul className="max-h-80 overflow-y-auto">
        {hits.map((n, i) => (
          <li key={n.id}><button onMouseEnter={() => setCur(i)} onClick={() => go(n.id)}
            className={`flex w-full items-center gap-2 rounded px-2 py-1 text-left text-sm ${i === cur ? "bg-slate-700" : ""}`}>
            <Dot light={isDept(n) ? n.rollup.worst : n.light} size="sm" /><span>{n.id}</span>
            <span className="text-xs text-slate-500">{n.kind === "agent" ? (isDept(n) ? "部門" : "") : n.kind === "proc" ? "程序" : "外部"}</span>
            <span className="ml-auto truncate text-xs text-slate-500">{n.why}</span>
          </button></li>
        ))}
        {!hits.length && <li className="px-2 text-sm text-slate-500">找不到</li>}
      </ul>
    </Modal>
  );
}

const PRESET = ["睡覺了，明早回", "出門，晚點回", "開會中", "在，但很忙，急事才找"];

function Board() {
  const board = useData((s) => s.board);
  const [text, setText] = useState(board?.text || "");
  const [back, setBack] = useState(board?.back || "");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const save = async (t: string, b: string) => {
    setBusy(true);
    const r = await post("/api/board", { text: t, back: b });
    setBusy(false);
    if (!r.ok) { setMsg(r.message || "存不了"); return; }
    data.set({ board: (r as { user?: typeof board }).user ?? null });
    pulseSoon();
    closeBoard();
  };
  return (
    <Modal onClose={closeBoard} title="📌 給 agent 的留話（它們久等你時會來看）">
      <div className="mb-2 flex flex-wrap gap-1">
        {PRESET.map((p) => <button key={p} className="rounded bg-slate-800 px-2 py-0.5 text-xs hover:bg-slate-700" onClick={() => setText(p)}>{p}</button>)}
      </div>
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={2} placeholder="一句話" className="w-full rounded bg-slate-800 p-1.5 text-sm" />
      <input value={back} onChange={(e) => setBack(e.target.value)} placeholder="幾點回來（選填，如 09:00）" className="mt-1 w-full rounded bg-slate-800 px-1.5 py-1 text-sm" />
      {board?.at && <p className="mt-1 text-xs text-slate-500">現在掛著的是 {board.at} 寫的</p>}
      <div className="mt-2 flex items-center gap-2">
        <button disabled={busy || !text.trim()} className="rounded bg-sky-700 px-3 py-1 text-sm disabled:opacity-40" onClick={() => save(text.trim(), back.trim())}>掛上</button>
        {board && <button disabled={busy} className="rounded bg-slate-700 px-3 py-1 text-sm" onClick={() => save("", "")}>拿掉留話</button>}
        {msg && <span className="text-sm text-red-300">{msg}</span>}
      </div>
    </Modal>
  );
}

function Drafts() {
  const [list, setList] = useState(() => listDrafts(localStorage));
  const now = Date.now() / 1000;
  return (
    <Modal onClose={closeDrafts} title="還沒送出的草稿">
      <ul className="max-h-96 space-y-1 overflow-y-auto">
        {list.map(({ target, draft }) => (
          <li key={target} className="rounded bg-slate-800 p-2 text-sm">
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <span>給 {target === "_none" ? "（還沒選對象）" : target}｜{draft.mode === "say" ? "說話" : draft.mode === "mail" ? "寄信" : "指令"}｜{ago(draft.updatedAt, now)}</span>
              {target !== "_none" && <button className="ml-auto text-sky-300 hover:underline" onClick={() => { closeDrafts(); jump(target); }}>接著寫</button>}
              <button className="text-slate-400 hover:text-red-300" onClick={() => { if (confirm("丟掉這份草稿？")) { dropDraft(localStorage, target === "_none" ? null : target); setList(listDrafts(localStorage)); } }}>丟掉</button>
            </div>
            {draft.mailTitle && <div className="font-medium">{draft.mailTitle}</div>}
            <div className="line-clamp-3 whitespace-pre-wrap break-words">{draft.text}</div>
          </li>
        ))}
        {!list.length && <li className="text-sm text-slate-500">沒有草稿</li>}
      </ul>
    </Modal>
  );
}

export function Dialogs() {
  const s = useUi((x) => x.searchOpen);
  const b = useUi((x) => x.boardOpen);
  const d = useUi((x) => x.draftsOpen);
  return <>{s && <Search />}{b && <Board />}{d && <Drafts />}</>;
}
