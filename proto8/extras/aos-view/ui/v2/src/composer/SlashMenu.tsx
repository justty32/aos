// Slash completion shows grouped canonical commands and optional screen-result hints.
import { GROUP_WORD, type Command } from "../model/commands.ts";
export function SlashMenu({ commands, current, choose }: { commands: Command[]; current: number; choose: (c: Command) => void }) {
  return <div data-slash-menu className="absolute bottom-full left-0 z-20 mb-1 max-h-64 w-full overflow-y-auto rounded border border-slate-600 bg-slate-900 p-1 shadow-xl">
    {commands.map((c, i) => <div key={c.name}>
      {(i === 0 || commands[i - 1].group !== c.group) && <div className="px-2 py-1 text-xs text-slate-500">{GROUP_WORD[c.group]}</div>}
      <button className={`flex w-full gap-2 rounded px-2 py-1 text-left text-sm ${i === current ? "bg-slate-700" : "hover:bg-slate-800"}`} onMouseDown={(e) => e.preventDefault()} onClick={() => choose(c)}>
        <code>/{c.name}</code><span>{c.confirm ? "⚠ " : ""}{c.label}</span>{c.how === "screen" && <span className="text-xs text-slate-500" title="打進它開著的畫面，把印出來的內容抄回『做過・說過』；要先開畫面">看畫面</span>}
      </button>
    </div>)}
    {!commands.length && <p className="px-2 py-1 text-xs text-slate-500">目前沒有符合的指令</p>}
  </div>;
}
