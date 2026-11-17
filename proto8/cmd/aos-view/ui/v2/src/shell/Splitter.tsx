// A drag bar between two panes (11-15 "各版面大小希望也可以拉調整"). Drag = resize (live, saved on release);
// double-click = back to the default; focused, the arrow keys move it 16 px. The value rules live in state/sizes.ts.
import { useRef } from "react";

interface Props {
  dir: "col" | "row";                                  // col = a vertical bar (drag sideways), row = horizontal
  label: string;
  value: () => number;                                 // the current size in px
  /** the new size for a pointer at (x, y) given where the drag started; return the clamped size */
  calc: (start: { size: number; x: number; y: number }, x: number, y: number) => number;
  set: (v: number, persist: boolean) => void;
  reset: () => void;
  step?: number;                                       // arrow key step: moves the bar like a drag of that many px
  className?: string;
}

export function Splitter({ dir, label, value, calc, set, reset, step = 16, className = "" }: Props) {
  const start = useRef<{ size: number; x: number; y: number } | null>(null);
  const col = dir === "col";
  return (
    <div role="separator" aria-orientation={col ? "vertical" : "horizontal"} aria-label={label} tabIndex={0}
      title={`${label}：拖動調整，雙擊回預設`} data-splitter={label}
      className={`group relative z-20 shrink-0 select-none touch-none ${col ? "w-1.5 cursor-col-resize" : "h-1.5 cursor-row-resize"} bg-slate-800/60 hover:bg-sky-700 focus-visible:bg-sky-600 ${className}`}
      onPointerDown={(e) => {
        if (e.button !== 0) return;
        e.preventDefault();
        (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
        start.current = { size: value(), x: e.clientX, y: e.clientY };
        document.body.style.cursor = col ? "col-resize" : "row-resize";
      }}
      onPointerMove={(e) => { if (start.current) set(calc(start.current, e.clientX, e.clientY), false); }}
      onPointerUp={(e) => {
        if (!start.current) return;
        set(calc(start.current, e.clientX, e.clientY), true);
        start.current = null;
        document.body.style.cursor = "";
      }}
      onPointerCancel={() => { start.current = null; document.body.style.cursor = ""; }}
      onDoubleClick={reset}
      onKeyDown={(e) => {
        const d = col ? (e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0) : (e.key === "ArrowDown" ? 1 : e.key === "ArrowUp" ? -1 : 0);
        if (!d) return;
        e.preventDefault(); e.stopPropagation();                // not the wall / map / tree arrows
        set(calc({ size: value(), x: 0, y: 0 }, col ? d * step : 0, col ? 0 : d * step), true);
      }}>
      {/* a wider invisible grip than the 6 px bar */}
      <span className={`absolute ${col ? "inset-y-0 -left-1 -right-1" : "inset-x-0 -top-1 -bottom-1"}`} />
    </div>
  );
}
