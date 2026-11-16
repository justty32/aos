// Page-only command actions change navigation or overlays without sending agent messages.
import { setRight } from "../state/layout.ts";
import { data, ui } from "../state/app.ts";
import { caretToComposer, openAsk, setView, up } from "../state/nav.ts";
import { buildInbox } from "../model/inbox.ts";
import { answeredHere } from "../state/hooks.ts";
import { serverNow } from "../state/app.ts";
export function pageCommand(name: string, rest = ""): void {
  if (name === "wall" || name === "map" || name === "todo") { openAsk(null); setView(name); }
  else if (name === "up") up();
  else if (name === "find") ui.set({ searchOpen: true, searchText: rest });
  else if (name === "help") ui.set({ helpOpen: true });
  else if (name === "cmds") ui.set({ panelOpen: true });
  else if (name === "decide") {
    const d = data.get();
    const { todo } = buildInbox({ ...d, answeredHere: new Set([...answeredHere, ...d.answered.map((x) => x.letter)]), now: serverNow(d) });
    const ask = todo.find((t) => t.kind === "ask");
    if (ask?.letter) openAsk(ask.letter); else ui.set({ flash: "沒有要你決定的信" });
  }
}
export function fillCommand(text: string): void { setRight(true); ui.set({ fill: { text, n: Date.now() }, panelOpen: false }); caretToComposer(); }
