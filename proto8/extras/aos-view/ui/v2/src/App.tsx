// The page: header on top; three columns: left tree 280 (48 closed) | center tabs | right 400 (0 closed) with the
// selection and the composer (02f §4–§5). Only the user opens or closes a side ([ ] or the « » buttons, q6b a);
// the right side shows only when something is selected (02f §3).
import { useEffect } from "react";
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
  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <Header />
      <div className="grid min-h-0 flex-1" style={{ gridTemplateColumns: `${L ? 280 : 48}px minmax(0,1fr) ${R ? 400 : 0}px` }}>
        <Left />
        <Stage />
        {R ? (
          <div className="flex min-h-0 flex-col">
            <Inspector />
            <Composer />
          </div>
        ) : <div />}
      </div>
      <Dialogs />
    </div>
  );
}
