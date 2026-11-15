// The page: header on top; three columns: inbox 340 px | stage | inspector 420 px (decision card + selection + composer).
import { useEffect } from "react";
import { Header } from "./shell/Header.tsx";
import { Inbox } from "./inbox/Inbox.tsx";
import { Stage } from "./stage/Stage.tsx";
import { Inspector } from "./inspector/Inspector.tsx";
import { Composer } from "./composer/Composer.tsx";
import { Dialogs } from "./shell/Dialogs.tsx";
import { ui, type Filter } from "./state/app.ts";
import { bind } from "./input/keys.ts";
import { caretToComposer, select } from "./state/nav.ts";

const FILTERS: Filter[] = ["ask", "red", "yellow", "reply"];

export function App() {
  useEffect(() => bind([
    { key: "/", run: caretToComposer },
    { key: "mod+k", inInput: true, run: () => ui.set({ searchOpen: true }) },
    ...FILTERS.map((f, i) => ({ key: `alt+${i + 1}`, run: () => ui.set({ filter: ui.get().filter === f ? null : f, inboxTab: "todo" as const }) })),
    { key: "Escape", run: () => { if (ui.get().filter) ui.set({ filter: null }); else select(null); } },
  ]), []);
  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <Header />
      <div className="grid min-h-0 flex-1" style={{ gridTemplateColumns: "340px minmax(0,1fr) 420px" }}>
        <Inbox />
        <Stage />
        <div className="flex min-h-0 flex-col">
          <Inspector />
          <Composer />
        </div>
      </div>
      <Dialogs />
    </div>
  );
}
