// Agent history restores recent reading positions and follows new records only at the bottom.
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { AgentCard, Node } from "../api/types.ts";
import { Clamp } from "../shell/Clamp.tsx";
import { useUi } from "../state/hooks.ts";
import { createMemo } from "../state/memo.ts";
import { followsLayout, type ScrollMetrics } from "./historyScroll.ts";
import { useLive } from "./useLive.ts";

const KEEP = 8;
const TTL_S = 600;
interface Position { line: number; offset: number; atBottom: boolean }
const positions = createMemo<Position>(KEEP, TTL_S);
export function resetHistory(name: string): void { positions.set(name, { line: -1, offset: 0, atBottom: true }, Date.now() / 1000); }

export function History({ n }: { n: Node }) {
  const slashAt = useUi((s) => s.slashAt);
  const jumpAt = useUi((s) => s.historyJump);
  const live = useLive<AgentCard>("/api/agent?name=" + encodeURIComponent(n.id), ["tree"], 30000);
  const box = useRef<HTMLDivElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const initialized = useRef(false);
  const bottom = useRef(true);
  const frame = useRef<number | null>(null);
  const measured = useRef<ScrollMetrics | null>(null);
  const [edges, setEdges] = useState({ top: true, bottom: true });
  const h = live.data ? [...live.data.history].reverse() : [];

  const remember = (el: HTMLDivElement) => {
    const current = { top: el.scrollTop, height: el.scrollHeight, client: el.clientHeight };
    // Scroll events from the previous jump can arrive after Clamp adds its expand buttons.
    if (followsLayout(measured.current, current, bottom.current)) el.scrollTop = el.scrollHeight;
    measured.current = { top: el.scrollTop, height: el.scrollHeight, client: el.clientHeight };
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight <= 40;
    bottom.current = atBottom;
    setEdges({ top: el.scrollTop <= 2, bottom: atBottom });
    if (!initialized.current) return;
    const top = el.getBoundingClientRect().top + el.clientTop;
    const first = [...el.querySelectorAll<HTMLElement>("[data-line]")].find((row) => row.getBoundingClientRect().bottom > top);
    if (first) positions.set(n.id, { line: Number(first.dataset.line), offset: top - first.getBoundingClientRect().top, atBottom }, Date.now() / 1000);
  };

  useLayoutEffect(() => {
    const el = box.current;
    if (!el || !live.data) return;
    if (!initialized.current) {
      const saved = positions.get(n.id, Date.now() / 1000);
      const row = saved && el.querySelector<HTMLElement>(`[data-line="${saved.line}"]`);
      if (saved && row && !saved.atBottom) {
        el.scrollTop += row.getBoundingClientRect().top - el.getBoundingClientRect().top - el.clientTop + saved.offset;
      } else el.scrollTop = el.scrollHeight;
      initialized.current = true;
    } else if (bottom.current) el.scrollTop = el.scrollHeight;
    remember(el);
    // The previous scroll event records whether a data refresh should follow the latest entry.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [live.data, n.id]);

  useLayoutEffect(() => {
    const el = box.current;
    const observer = new ResizeObserver(() => {
      if (!el || !initialized.current) return;
      if (bottom.current) el.scrollTop = el.scrollHeight;
      remember(el);
    });
    if (list.current) observer.observe(list.current);
    if (el) observer.observe(el);
    return () => {
      observer.disconnect();
      if (frame.current !== null) cancelAnimationFrame(frame.current);
      if (el) remember(el);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [n.id]);

  useEffect(() => {
    if (!slashAt) return;
    const timers = [3000, 10000, 20000].filter((ms) => slashAt + ms > Date.now()).map((ms) => setTimeout(live.reload, slashAt + ms - Date.now()));
    return () => timers.forEach(clearTimeout);
  }, [slashAt, live.reload]);
  useLayoutEffect(() => {
    if (!jumpAt || !box.current) return;
    bottom.current = true;
    box.current.scrollTop = box.current.scrollHeight;
    remember(box.current);
  }, [jumpAt]);

  const jump = (end: boolean) => {
    const el = box.current;
    if (!el) return;
    el.scrollTop = end ? el.scrollHeight : 0;
    remember(el);
  };
  return (
    <div className="relative flex min-h-0 flex-1 flex-col">
      <div ref={box} data-scroll="history" className="min-h-0 flex-1 overflow-y-auto" onWheel={(e) => { if (e.deltaY < 0) bottom.current = false; }} onScroll={() => {
        if (box.current && measured.current && box.current.scrollTop < measured.current.top) bottom.current = false;
        if (frame.current !== null) return;
        frame.current = requestAnimationFrame(() => {
          frame.current = null;
          if (box.current) remember(box.current);
        });
      }}>
        {live.error && <p className="text-xs text-red-300">讀不到紀錄：{live.error}</p>}
        {!live.data && !live.error && <p className="text-xs text-slate-400">讀取中…</p>}
        <ul ref={list} className="space-y-1.5">
          {h.map((x) => (
            <li key={x.line} data-line={x.line} className={`rounded px-2 py-1 text-sm ${x.slash ? "bg-slate-800" : "bg-slate-900"}`}>
              <div className="text-xs text-slate-500">#{x.line} {x.slash ? `指令結果　${x.slash}` : x.role === "assistant" ? "它" : x.role === "user" ? "收到" : x.role}{x.tools.length ? `｜用了 ${x.tools.join("、")}` : ""}</div>
              <div className={`text-slate-200 ${x.slash ? "font-mono" : ""}`}><Clamp node={n.id} id={`h:${x.line}`} lines={x.slash ? 12 : 6} text={x.text} /></div>
            </li>
          ))}
        </ul>
        {live.data && !h.length && <p className="text-xs text-slate-500">沒有紀錄</p>}
      </div>
      <div className="absolute bottom-2 right-3 flex gap-1">
        {!edges.top && <button data-jump="top" className="rounded bg-slate-700 px-2 py-1 text-xs text-slate-100 hover:bg-slate-600" title="捲到最舊的一則（Home）" onClick={() => jump(false)}>⤒ 最舊</button>}
        {!edges.bottom && <button data-jump="bottom" className="rounded bg-slate-700 px-2 py-1 text-xs text-slate-100 hover:bg-slate-600" title="捲到最新的一則（End）" onClick={() => jump(true)}>⤓ 最新</button>}
      </div>
    </div>
  );
}
