// Slash result tests cover status wording, exact-command pending detection, refreshes, and inspector polling.
import { test } from "node:test";
import assert from "node:assert/strict";
import type { SlashResult } from "../api/types.ts";
import { pendingOf, refreshSlash, slashLabel, slashResults, watchSlash } from "./slashResults.ts";

const item = (state: SlashResult["state"], command = "/usage"): SlashResult => ({ letter: "L", command, at: 100, state });

test("slash labels describe every state and add the long-turn hint only after thirty minutes", () => {
  assert.equal(slashLabel(item("waiting"), true, "board", 101), "排隊中：等 board 這一輪講完");
  assert.equal(slashLabel(item("waiting"), false, "board", 101), "排隊中");
  assert.equal(slashLabel(item("doing"), true, "board", 101), "做中…");
  assert.equal(slashLabel(item("answered"), false, "board", 9999), "完成");
  assert.equal(slashLabel(item("unknown"), false, "board", 101), "讀不到狀態");
  for (const state of ["waiting", "doing", "unknown"] as const) {
    assert.ok(!slashLabel(item(state), false, "board", 1900).includes("還沒回"));
    assert.ok(slashLabel(item(state), false, "board", 1901).endsWith("（還沒回，可能還在長回合）"));
  }
  assert.equal(slashLabel({ ...item("unknown"), at: null }, false, "board", 9999), "讀不到狀態");
});

test("pending commands match the agent and full command text, only for waiting or doing", () => {
  slashResults.set({ a: { items: [item("waiting"), item("doing", "/compact keep plan"), item("answered", "/context"), item("unknown", "/status")], in_turn: true, loadedAt: 1 } });
  try {
    assert.equal(pendingOf("a", "/usage"), true);
    assert.equal(pendingOf("a", "/compact keep plan"), true);
    assert.equal(pendingOf("a", "/compact"), false);
    assert.equal(pendingOf("a", "/context"), false);
    assert.equal(pendingOf("a", "/status"), false);
    assert.equal(pendingOf("b", "/usage"), false);
  } finally { slashResults.set({ a: { items: [], in_turn: false, loadedAt: 0 } }); }
});

test("refresh encodes agent names, coalesces requests, and stores the response with a load time", async () => {
  const original = globalThis.fetch;
  const paths: string[] = [];
  globalThis.fetch = async (input) => {
    paths.push(String(input));
    return new Response(JSON.stringify({ items: [item("answered")], in_turn: false }));
  };
  try {
    const first = refreshSlash("a/b");
    assert.equal(refreshSlash("a/b"), first);
    await first;
    assert.deepEqual(paths, ["/api/slash_results?name=a%2Fb"]);
    assert.deepEqual(slashResults.get()["a/b"].items, [item("answered")]);
    assert.equal(slashResults.get()["a/b"].in_turn, false);
    assert.ok(slashResults.get()["a/b"].loadedAt > 0);
  } finally { globalThis.fetch = original; }
});

test("one timer per open agent polls at three seconds, stops on answer, and stops on inspector close", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const original = globalThis.fetch;
  let calls = 0;
  let state: SlashResult["state"] = "waiting";
  globalThis.fetch = async () => {
    calls++;
    return new Response(JSON.stringify({ items: [item(state)], in_turn: true }));
  };
  let closeOne = () => {}, closeTwo = () => {};
  try {
    await refreshSlash("poll");
    t.mock.timers.tick(3000);
    assert.equal(calls, 1);
    closeOne = watchSlash("poll"); closeTwo = watchSlash("poll");
    t.mock.timers.tick(2999);
    assert.equal(calls, 1);
    t.mock.timers.tick(1);
    await refreshSlash("poll");
    assert.equal(calls, 2);
    closeOne(); closeOne = () => {};
    state = "answered";
    t.mock.timers.tick(3000);
    await refreshSlash("poll");
    assert.equal(calls, 3);
    t.mock.timers.tick(6000);
    assert.equal(calls, 3);
    state = "doing";
    await refreshSlash("poll");
    closeTwo(); closeTwo = () => {};
    t.mock.timers.tick(6000);
    assert.equal(calls, 4);
  } finally { closeOne(); closeTwo(); globalThis.fetch = original; }
});

test("failed refresh retains known pending results", async () => {
  const original = globalThis.fetch;
  const entry = { items: [item("waiting")], in_turn: true, loadedAt: 1 };
  slashResults.set({ retry: entry });
  globalThis.fetch = async () => { throw new Error("offline"); };
  try {
    await refreshSlash("retry");
    assert.equal(slashResults.get().retry, entry);
  } finally { globalThis.fetch = original; }
});
