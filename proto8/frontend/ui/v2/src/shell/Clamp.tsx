// Expandable text and short lists share a bounded in-memory expansion cache.
import { useLayoutEffect, useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { createMemo } from "../state/memo.ts";

const expanded = createMemo<boolean>(200);

function useOpen(key: string) {
  const [state, setState] = useState(() => ({ key, open: expanded.get(key, Date.now() / 1000) ?? false }));
  const open = state.key === key ? state.open : expanded.get(key, Date.now() / 1000) ?? false;
  const toggle = () => {
    expanded.set(key, !open, Date.now() / 1000);
    setState({ key, open: !open });
  };
  return { open, toggle };
}

export function Clamp({ text, lines, id, node = "", cut = false }: {
  text: string; lines: number; id?: string; node?: string; cut?: boolean;
}) {
  const { open, toggle } = useOpen(`${node}:${id ?? "text"}:${text.length}`);
  const box = useRef<HTMLDivElement>(null);
  const [clipped, setClipped] = useState(false);
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    const measure = () => {
      // Measure the collapsed height even while the user is reading the full text.
      const previous = el.style.cssText;
      Object.assign(el.style, { display: "-webkit-box", WebkitBoxOrient: "vertical", WebkitLineClamp: String(lines), overflow: "hidden" });
      setClipped(el.scrollHeight > el.clientHeight + 1);
      el.style.cssText = previous;
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, [text, lines, open]);
  const style: CSSProperties | undefined = open ? undefined : {
    display: "-webkit-box", WebkitBoxOrient: "vertical", WebkitLineClamp: lines, overflow: "hidden",
  };
  return (
    <div data-clamp={id} data-open={open ? "1" : "0"}>
      <div ref={box} className="whitespace-pre-wrap break-words" style={style}>{text}</div>
      {(clipped || open) && <button className="block text-left text-xs text-sky-300 hover:underline" onClick={toggle}>
        {open ? "收起 ▴" : `展開 ▾（共 ${text.length} 字）`}
      </button>}
      {open && cut && <p className="text-xs text-slate-500">（只留到前 {text.length} 字）</p>}
    </div>
  );
}

export function MoreList<T>({ items, first, render, more, id, node = "" }: {
  items: T[]; first: number; render: (item: T, index: number) => ReactNode; more: string; id?: string; node?: string;
}) {
  const { open, toggle } = useOpen(`${node}:${id ?? "list"}:${items.length}`);
  return (
    <div data-more={id}>
      {items.slice(0, open ? items.length : first).map(render)}
      {items.length > first && <button className="block text-left text-xs text-sky-300 hover:underline" onClick={toggle}>
        {open ? "收起 ▴" : `還有 ${items.length - first} ${more} ▾`}
      </button>}
    </div>
  );
}
