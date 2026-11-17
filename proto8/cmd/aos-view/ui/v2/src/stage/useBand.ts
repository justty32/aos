// Pointer capture draws a selection band on map background and suppresses the click after a drag.
import { useRef, useState } from "react";
import type { PointerEvent, MouseEvent } from "react";
import type { MapItem } from "../model/layoutMap.ts";
import { bandRect, hits, type Rect } from "../model/multi.ts";
import { clearMulti, setMulti } from "../state/multi.ts";

export function useBand(items: MapItem[]) {
  const [rect, setRect] = useState<Rect | null>(null);
  const start = useRef<{ x: number; y: number; dragging: boolean; add: boolean } | null>(null);
  const swallow = useRef(false);
  const bounds = (el: HTMLElement, x: number, y: number, from: { x: number; y: number }): Rect => {
    const b = el.getBoundingClientRect();
    return bandRect(from.x, from.y, x, y, b.left, b.top);
  };
  const down = (e: PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0 || (e.target as Element).closest("button")) return;
    swallow.current = false;
    start.current = { x: e.clientX, y: e.clientY, dragging: false, add: e.ctrlKey || e.metaKey || e.shiftKey };
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const move = (e: PointerEvent<HTMLDivElement>) => {
    const s = start.current;
    if (!s) return;
    if (!s.dragging && Math.hypot(e.clientX - s.x, e.clientY - s.y) <= 4) return;
    s.dragging = true;
    setRect(bounds(e.currentTarget, e.clientX, e.clientY, s));
  };
  const up = (e: PointerEvent<HTMLDivElement>) => {
    const s = start.current;
    if (!s) return;
    if (s.dragging) { setMulti(hits(items, bounds(e.currentTarget, e.clientX, e.clientY, s)), s.add); swallow.current = true; }
    else clearMulti();
    start.current = null;
    setRect(null);
    if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId);
  };
  return { rect, handlers: { onPointerDown: down, onPointerMove: move, onPointerUp: up,
    onPointerCancel: () => { start.current = null; setRect(null); },
    onClickCapture: (e: MouseEvent) => { if (swallow.current) { swallow.current = false; e.preventDefault(); e.stopPropagation(); } },
  } };
}
