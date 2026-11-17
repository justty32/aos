// The shortcut dialog renders the shared reference and closes through the overlay stack.
import { useEffect, useRef } from "react";
import { KEY_HELP } from "../model/keyHelp.ts";
import { pushOverlay } from "../input/keys.ts";
import { ui } from "../state/app.ts";

const close = () => ui.set({ helpOpen: false });

export function HelpDialog() {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    box.current?.focus();
    const off = pushOverlay(close);
    return () => { off(); previous?.focus({ preventScroll: true }); };
  }, []);
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 pt-12" onMouseDown={(e) => { if (e.target === e.currentTarget) close(); }}>
      <div ref={box} tabIndex={-1} data-help-dialog role="dialog" aria-modal="true" aria-label="操作說明" className="max-h-[85vh] w-[720px] max-w-[95vw] overflow-y-auto rounded-lg border border-slate-600 bg-slate-900 p-3 shadow-2xl">
        <div className="mb-2 flex items-center justify-between text-sm"><b>操作說明</b><button className="text-slate-400 hover:text-slate-100" onClick={close}>關 Esc</button></div>
        {KEY_HELP.map(({ area, rows }) => <section key={area} className="mb-3">
          <h3 className="mb-1 text-sm font-semibold text-sky-300">{area}</h3>
          <table className="w-full text-left text-sm"><tbody>{rows.map(([keys, what]) => <tr key={keys} className="border-t border-slate-800">
            <td className="w-2/5 py-1 pr-3 align-top"><kbd className="text-xs text-slate-300">{keys}</kbd></td><td className="py-1 text-slate-400">{what}</td>
          </tr>)}</tbody></table>
        </section>)}
      </div>
    </div>
  );
}
