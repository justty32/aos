// Entry of the v2 page: apply saved sizes, install keys and the URL hash, render <App />, start polling.
import { createRoot } from "react-dom/client";
import "./app.css";
import { App } from "./App.tsx";
import { install } from "./input/keys.ts";
import { installHash } from "./state/nav.ts";
import { start } from "./api/poll.ts";
import { data } from "./state/app.ts";
import { pruneDrafts } from "./model/drafts.ts";
import { applySizes } from "./state/sizes.ts";

applySizes();                  // the user's font step and widths before the first paint
install();
installHash();
createRoot(document.getElementById("root")!).render(<App />);
start().then(() => {
  const t = data.get().tree;
  if (t) pruneDrafts(localStorage, Date.now() / 1000, (id) => !!t.nodes[id]);
});
