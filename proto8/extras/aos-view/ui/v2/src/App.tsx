// The page: header on top; three columns: left tree (48 closed) | center tabs | right (0 closed) with the selection
// and the composer (02f §4–§5). Only the user opens or closes a side ([ ] or the « » buttons, q6b a); the right side
// shows only when something is selected (02f §3). Widths are CSS variables the user drags (state/sizes.ts, 11-15
// "各版面大小希望也可以拉調整"); closing and opening a side comes back at the dragged width.
import { useEffect, useRef } from "react";
import { Splitter } from "./shell/Splitter.tsx";
import { clampComposer, clampLeft, clampRight, LEFT, RIGHT, setSizes, sizes, STRIP } from "./state/sizes.ts";
import { Header } from "./shell/Header.tsx";
import { Left } from "./left/Left.tsx";
import { Stage } from "./stage/Stage.tsx";
import { Inspector } from "./inspector/Inspector.tsx";
import { Composer } from "./composer/Composer.tsx";
import { Dialogs } from "./shell/Dialogs.tsx";
import { ui, type Filter } from "./state/app.ts";
import { useData, useUi } from "./state/hooks.ts";
import { bind } from "./input/keys.ts";
import { caretToComposer, select, setView } from "./state/nav.ts";
import { leftOpen, rightOpen, toggleLeft, toggleRight } from "./state/layout.ts";

const FILTERS: Filter[] = ["ask", "red", "yellow", "reply"];

export function App() {
  const prefs = useData((s) => s.prefs);
  const sel = useUi((s) => s.route.sel);
  const L = leftOpen(prefs);
  const R = rightOpen(prefs) && !!sel;
  useEffect(() => bind([
    { key: "/", run: caretToComposer },
    { key: "mod+k", inInput: true, run: () => ui.set({ searchOpen: true }) },
    ...FILTERS.map((f, i) => ({ key: `alt+${i + 1}`, run: () => {
      const on = ui.get().filter === f ? null : f;
      ui.set({ filter: on, inboxTab: "todo" as const });
      if (on) setView("todo");
    } })),
    { key: "[", run: toggleLeft },
    { key: "]", run: toggleRight },
    { key: "Escape", run: () => { if (ui.get().filter) ui.set({ filter: null }); else select(null); } },
  ]), []);
  const col = useRef<HTMLDivElement>(null);
  const comp = useRef<HTMLDivElement>(null);
  const page = () => document.documentElement.clientWidth;
  const cols = [L ? "var(--left-w)" : `${STRIP}px`, ...(L ? ["auto"] : []), "minmax(0,1fr)", ...(R ? ["auto", "var(--right-w)"] : [])];
  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <Header />
      <div className="grid min-h-0 flex-1" style={{ gridTemplateColumns: cols.join(" ") }}>
        <Left />
        {L && (
          <Splitter dir="col" label="左欄寬度" value={() => sizes.get().left}
            calc={(st, x) => clampLeft(st.size + (x - st.x), page(), R ? sizes.get().right : 0)}
            set={(v, persist) => setSizes({ left: v }, persist)} reset={() => setSizes({ left: LEFT.def })} />
        )}
        <Stage />
        {R && (
          <Splitter dir="col" label="右欄寬度" value={() => sizes.get().right}
            calc={(st, x) => clampRight(st.size - (x - st.x), page(), L ? sizes.get().left : STRIP)}
            set={(v, persist) => setSizes({ right: v }, persist)} reset={() => setSizes({ right: RIGHT.def })} />
        )}
        {R && (
          <div ref={col} className="flex min-h-0 min-w-0 flex-col">
            <Inspector />
            <Splitter dir="row" label="打字區高度" value={() => comp.current?.offsetHeight || 200}
              calc={(st, _x, y) => clampComposer(st.size - (y - st.y), col.current?.clientHeight || 600)}
              set={(v, persist) => setSizes({ composer: v }, persist)} reset={() => setSizes({ composer: null })} />
            <div ref={comp} className="flex min-h-0 shrink-0 flex-col" style={{ height: "var(--composer-h)" }}><Composer /></div>
          </div>
        )}
      </div>
      <Dialogs />
    </div>
  );
}
