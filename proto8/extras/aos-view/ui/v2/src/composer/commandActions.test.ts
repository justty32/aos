// Command action tests fake browser navigation and HTTP to verify page routing and bare slash sends.
import { test } from "node:test";
import assert from "node:assert/strict";
import { MemoryKv } from "../model/drafts.ts";
import { data, ui } from "../state/app.ts";
import { pageCommand, fillCommand } from "./commandActions.ts";
import { sendSlash } from "./useSend.ts";
import { listCommands } from "../model/commands.ts";
import type { Node, Ask } from "../api/types.ts";

test("page commands use visible asks, fill only once, and preserve selection for help", () => {
  const keys = ["location", "history", "localStorage"];
  const old = keys.map((k) => Object.getOwnPropertyDescriptor(globalThis, k));
  const previousData = data.get(), previousUi = ui.get();
  for (const [i, value] of [{ hash: "" }, { replaceState() {}, pushState() {} }, new MemoryKv()].entries()) Object.defineProperty(globalThis, keys[i], { configurable: true, value });
  try {
    const ask = (letter: string) => ({ letter, kind: "decide", title: letter, from: null, questions: [], urgent: false, risk: "normal", sent_at: 1 }) as Ask;
    data.set({ tree: null, asks: [ask("hidden"), ask("visible")], dismissed: { "ask:hidden": 1 }, relay: [], outbox: [], answered: [], prefs: { view: "map" } });
    pageCommand("decide"); assert.equal(ui.get().route.ask, "visible");
    pageCommand("map"); assert.equal(ui.get().route.view, "map"); assert.equal(ui.get().route.ask, null);
    pageCommand("help"); assert.equal(ui.get().helpOpen, true);
    pageCommand("cmds"); assert.equal(ui.get().panelOpen, true);
    pageCommand("find", "board"); assert.equal(ui.get().searchText, "board");
    fillCommand("/compact"); assert.equal(ui.get().fill?.text, "/compact"); assert.equal(ui.get().panelOpen, false);
  } finally {
    data.set(previousData); ui.set(previousUi);
    keys.forEach((k, i) => old[i] ? Object.defineProperty(globalThis, k, old[i]!) : Reflect.deleteProperty(globalThis, k));
  }
});

test("slash sends bare canonical text, marks only result commands, and honors preflight", async () => {
  const original = globalThis.fetch, previousData = data.get(), previousUi = ui.get();
  const posted: { path: string; body: unknown }[] = [];
  globalThis.fetch = async (input, init) => {
    if (String(input) === "/api/session") return new Response(JSON.stringify({ token: "test" }));
    posted.push({ path: String(input), body: JSON.parse(String(init?.body)) });
    return new Response(JSON.stringify({ ok: true, message: "sent", letter: "L" }));
  };
  try {
    const slash = [{ name: "usage", args: "none" as const, confirm: false, how: "turn" as const, cli: ["claude"] }, { name: "compact", args: "optional" as const, confirm: false, how: "turn" as const, cli: ["claude"] }, { name: "custom-screen", args: "none" as const, confirm: false, how: "screen" as const, cli: ["claude"] }];
    const n = { id: "board", kind: "agent", state: "running", queued: 0, live: { cli: "claude", in_turn: false } } as Node;
    data.set({ slash });
    const commands = listCommands({ orders: [], slash, cli: "claude", multi: 0, target: n.id });
    await sendSlash(n, commands.find((c) => c.name === "usage")!, "/usage");
    assert.deepEqual(posted[0], { path: "/api/slash", body: { name: "board", text: "/usage" } });
    assert.equal(ui.get().flashGo, "history"); assert.equal(ui.get().flashTarget, "board");
    const at = ui.get().slashAt;
    await sendSlash(n, commands.find((c) => c.name === "compact")!, "/compact keep plan");
    assert.equal(ui.get().flashGo, null); assert.equal(ui.get().slashAt, at);
    await sendSlash(n, commands.find((c) => c.name === "custom-screen")!, "/custom-screen");
    assert.equal(ui.get().flashGo, "history");
    const count = posted.length;
    assert.equal((await sendSlash({ ...n, queued: 1 }, commands[2], "/usage")).ok, false); assert.equal(posted.length, count);
  } finally { globalThis.fetch = original; data.set(previousData); ui.set(previousUi); }
});

test("CLI batch calls carry one shared batch id without adding text wrappers", async () => {
  const original = globalThis.fetch, before = data.get();
  const rows: Record<string, unknown>[] = [];
  globalThis.fetch = async (input, init) => {
    if (String(input) === "/api/session") return new Response(JSON.stringify({ token: "test" }));
    rows.push(JSON.parse(String(init?.body)));
    return new Response(JSON.stringify({ ok: true, message: "sent" }));
  };
  try {
    const slash = [{ name: "status", args: "none" as const, confirm: false, how: "turn" as const, cli: ["claude"] }];
    data.set({ slash });
    const cmd = listCommands({ orders: [], slash, cli: "claude", multi: 2, target: "a" }).find((c) => c.name === "status")!;
    for (const id of ["a", "b"]) await sendSlash({ id, kind: "agent", state: "running", queued: 0, live: { cli: "claude" } } as Node, cmd, "/status", "b-shared");
    assert.deepEqual(rows.map((r) => r.batch), ["b-shared", "b-shared"]);
    assert.deepEqual(rows.map((r) => r.text), ["/status", "/status"]);
  } finally { globalThis.fetch = original; data.set(before); }
});
