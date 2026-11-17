// The multi-selection inspector lists each agent and lets the user remove or select one target.
import type { Tree } from "../api/types.ts";
import { ui } from "../state/app.ts";
import { Dot } from "../shell/bits.tsx";
import { clearMulti, dropFromMulti, pickWith } from "../state/multi.ts";
import { whyWord } from "../model/words.ts";

export function MultiPanel({ tree, ids }: { tree: Tree; ids: string[] }) {
  return <div className="min-h-0 flex-1 overflow-y-auto p-3" data-multi-panel>
    <div className="mb-2 flex items-center gap-2 text-sm font-semibold">已選 {ids.length} 個<button className="ml-auto text-xs text-sky-300 hover:underline" onClick={clearMulti}>清除（Esc）</button></div>
    <ul className="space-y-1">{ids.map((id) => {
      const n = tree.nodes[id];
      return <li key={id} className="flex items-center gap-1.5 rounded bg-slate-800 p-2 text-sm">
        {n && <Dot light={n.light} />}<div className="min-w-0 flex-1"><button className="block w-full truncate text-left hover:underline" onClick={() => pickWith({ shiftKey: false, ctrlKey: false, metaKey: false }, id, ids)}>{id}</button>
          <div className="truncate text-xs text-slate-400" title={n?.why}>{n ? whyWord(n.why) : "已經不在樹上了"}</div></div>
        <button className="w-6 shrink-0 text-slate-400 hover:text-slate-100" title="拿出多選" onClick={() => dropFromMulti(id)}>×</button>
      </li>;
    })}</ul>
    <button className="mt-3 rounded bg-sky-700 px-3 py-1 text-sm hover:bg-sky-600" onClick={() => ui.set({ sendRequest: Date.now(), focusComposer: ui.get().focusComposer + 1 })}>群發</button>
  </div>;
}
