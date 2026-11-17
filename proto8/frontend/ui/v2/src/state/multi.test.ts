// Multi-selection actions are exercised with a fake route, tree, and browser history.
import { test } from "node:test";
import assert from "node:assert/strict";
import type { Node, Tree } from "../api/types.ts";
import { data, ui } from "./app.ts";
import { clearMulti, dropFromMulti, pickWith, setMulti } from "./multi.ts";

test("agent selection supports ranges, modifiers, primary targets, and non-agent rejection", () => {
  const oldLocation = Object.getOwnPropertyDescriptor(globalThis, "location");
  const oldHistory = Object.getOwnPropertyDescriptor(globalThis, "history");
  const oldData = data.get(), oldUi = ui.get();
  Object.defineProperty(globalThis, "location", { configurable: true, value: { hash: "" } });
  Object.defineProperty(globalThis, "history", { configurable: true, value: { pushState() {}, replaceState() {} } });
  const make = (id: string, kind = "agent") => ({ id, kind, children: [], parent: null }) as Node;
  const tree: Tree = { format: "test", generated_at: 0, roots: ["a", "b", "c", "p"], llm_workers: 0, nodes: { a: make("a"), b: make("b"), c: make("c"), p: make("p", "proc") } };
  const none = { ctrlKey: false, metaKey: false, shiftKey: false };
  try {
    data.set({ tree, prefs: {} });
    ui.set({ multi: [], anchor: null, route: { ...oldUi.route, focus: null, sel: null, tab: "history" } });
    pickWith(none, "a", ["a", "b", "c"]);
    pickWith({ ...none, ctrlKey: true }, "b", ["a", "b", "c"]);
    assert.deepEqual(ui.get().multi, ["a", "b"]);
    assert.equal(ui.get().route.sel, "a");
    pickWith({ ...none, ctrlKey: true }, "b", ["a", "b", "c"]);
    assert.deepEqual(ui.get().multi, []);
    assert.equal(ui.get().route.sel, "a");
    pickWith(none, "a", ["a", "b", "c"]);
    pickWith({ ...none, shiftKey: true }, "c", ["a", "b", "c"]);
    assert.deepEqual(ui.get().multi, ["a", "b", "c"]);
    pickWith({ ...none, ctrlKey: true }, "p", []);
    assert.deepEqual(ui.get().multi, ["a", "b", "c"]);
    assert.ok(ui.get().flash?.includes("不收話"));
    dropFromMulti("b"); dropFromMulti("a");
    assert.deepEqual(ui.get().multi, []);
    assert.equal(ui.get().route.sel, "c");
    setMulti(["a", "b"]); setMulti(["c", "p"], true);
    assert.deepEqual(ui.get().multi, ["a", "b", "c"]);
    clearMulti();
    assert.equal(ui.get().route.sel, "a");
    assert.equal(ui.get().route.tab, "history");
    assert.deepEqual(ui.get().multi, []);
  } finally {
    data.set(oldData); ui.set(oldUi);
    if (oldLocation) Object.defineProperty(globalThis, "location", oldLocation); else Reflect.deleteProperty(globalThis, "location");
    if (oldHistory) Object.defineProperty(globalThis, "history", oldHistory); else Reflect.deleteProperty(globalThis, "history");
  }
});
